# Every Isaac Lab 2.3.2 call of tier 2 lives in this file; a move to Isaac Lab 3.0 changes this file only.
"""Tier 2 scene for the S0 throughput benchmark: N games x K ARL Robot 1 drones in one Isaac Lab scene.

Importing this module without a running Isaac app raises ImportError; import it only after the AppLauncher.
Shapes: N = games (Isaac Lab environments), K = drones per game, thrust is [N, 4] newtons per drone.
"""
import builtins

import torch

import isaaclab.sim as sim_utils
from isaaclab.assets import AssetBaseCfg
from isaaclab.scene import InteractiveScene, InteractiveSceneCfg
from isaaclab_assets.robots.arl_robot_1 import ARL_ROBOT_1_CFG
from isaaclab_contrib.assets import Multirotor

USD_PATH = ARL_ROBOT_1_CFG.spawn.usd_path
SPAWN_HEIGHT_M = 2.0
DRONE_SPACING_M = 1.5
MIN_HEIGHT_M = 0.3
MAX_DRIFT_M = 5.0
GRAVITY_MPS2 = 9.81


def make_sim(physics_dt_s: float, substeps: int, device: str):
    """SimulationContext with the benchmark's physics step (settings as the shipped ARL drone task)."""
    cfg = sim_utils.SimulationCfg(dt=physics_dt_s, device=device, render_interval=substeps,
                                  physx=sim_utils.PhysxCfg(gpu_max_rigid_patch_count=10 * 2**15))
    return sim_utils.SimulationContext(cfg)


def build_scene(sim, num_games: int, drones_per_game: int, spacing_m: float = 12.0, physics_dt_s: float = 0.005):
    """Ground plane + K drones per game, spawned 1.5 m apart (along x, centred) at 2 m height.

    Returns (scene, drones); drones[k] is the Multirotor of drone k, with num_games instances.
    Call play(sim) afterwards.
    """
    scene_cfg = InteractiveSceneCfg(num_envs=num_games, env_spacing=spacing_m, replicate_physics=True)
    # InteractiveScene reads cfg.__dict__ (interactive_scene.py:729), so assets added to the instance are spawned.
    scene_cfg.ground = AssetBaseCfg(prim_path="/World/defaultGroundPlane", spawn=sim_utils.GroundPlaneCfg())
    thruster = ARL_ROBOT_1_CFG.actuators["thrusters"].replace(dt=physics_dt_s)  # dt is MISSING in the shipped cfg
    for k in range(drones_per_game):
        x_m = (k - (drones_per_game - 1) / 2.0) * DRONE_SPACING_M
        setattr(scene_cfg, f"drone_{k}", ARL_ROBOT_1_CFG.replace(
            prim_path=f"{{ENV_REGEX_NS}}/Drone_{k}",
            init_state=ARL_ROBOT_1_CFG.init_state.replace(pos=(x_m, 0.0, SPAWN_HEIGHT_M)),
            actuators={"thrusters": thruster}))
    scene = InteractiveScene(scene_cfg)
    return scene, [scene[f"drone_{k}"] for k in range(drones_per_game)]


def play(sim) -> None:
    sim.reset()
    # exceptions inside asset initialisation are stored, not raised (asset_base.py:316-321); re-raise the first one
    exc = getattr(builtins, "ISAACLAB_CALLBACK_EXCEPTION", None)
    if exc is not None:
        builtins.ISAACLAB_CALLBACK_EXCEPTION = None
        raise exc


def hover_thrust_n(drones: "list[Multirotor]", device: str) -> "list[torch.Tensor]":
    """Per drone: [N, 1] thrust per rotor that balances its weight (total mass x 9.81 / 4 rotors)."""
    return [(d.root_physx_view.get_masses().sum(-1) * GRAVITY_MPS2 / 4.0).to(device).unsqueeze(-1) for d in drones]


def step_scene(sim, scene, drones, thrust_n, substeps: int, physics_dt_s: float = 0.005) -> None:
    """Set thrust_n[k] ([N, 4] N) on drone k, then run `substeps` physics steps (loop as manager_based_rl_env.py)."""
    for drone, thrust in zip(drones, thrust_n):
        drone.set_thrust_target(thrust)
    for _ in range(substeps):
        scene.write_data_to_sim()
        sim.step(render=False)
        scene.update(dt=physics_dt_s)


def reset_drones(scene, drones, only_out_of_bounds: bool = True) -> dict:
    """Write drones back to their spawn pose with zero velocity, in one batched write per drone, no host sync.

    only_out_of_bounds: reset only drones lower than 0.3 m above their game origin or further than 5 m from their
    spawn point or non-finite; False resets every drone. Returns {"pos_m": [N, K, 3] position relative to the game origin after
    the reset, "reset_fraction": scalar tensor, share of the N x K drones reset}.
    """
    origins = scene.env_origins
    pos, flags = [], []
    for d in drones:
        state = torch.cat([d.data.root_link_pose_w, d.data.root_com_vel_w], dim=-1)  # [N, 13], world frame
        spawn = d.data.default_root_state.clone()  # [N, 13], game frame
        spawn[:, :3] += origins
        rel = state[:, :3] - origins
        nonfinite = ~torch.isfinite(state).all(dim=-1)  # NaN compares False, so test it explicitly
        bad = (rel[:, 2] < MIN_HEIGHT_M) | ((state[:, :3] - spawn[:, :3]).norm(dim=-1) > MAX_DRIFT_M) | nonfinite
        if not only_out_of_bounds:
            bad = torch.ones_like(bad)
        d.write_root_state_to_sim(torch.where(bad[:, None], spawn, state))
        # a non-finite position is reported as it was (so measure counts it) although the drone is put back
        pos.append(torch.where((bad & ~nonfinite)[:, None], spawn[:, :3] - origins, rel))
        flags.append(bad)
    if not only_out_of_bounds:
        scene.reset()  # clears the motor and thrust-target buffers (interactive_scene.py:443)
    return {"pos_m": torch.stack(pos, dim=1), "reset_fraction": torch.stack(flags, dim=1).float().mean()}


# =====================================================================================================================
# S2b (Task 5): the physics drone's rigid-body world in Isaac Lab, behind models/rigid_body.RigidBodyWorld.
#
# One RigidObjectCollection holds every drone slot of every game (the S2b spike: one wrench call and one state write
# per step instead of one per slot, 2.3-2.9x faster than one RigidObject per slot). Each drone is a plain rigid body:
# a 0.19 x 0.26 x 0.05 m box with no collider, the CMU mass, a diagonal inertia written into PhysX by hand after
# play (no collider, so PhysX cannot derive one), the centre of mass at the body origin, no damping, no sleeping,
# gyroscopic forces on (set explicitly and read back), max angular velocity 1e4 deg/s. The four rotor thrusts are
# summed by models/starling_airframe.body_wrench_flu into one body-frame (FLU) force and torque and handed to the
# permanent wrench composer without application points: with points, the composer overwrites the torque with r x F
# (isaaclab utils/warp/kernels.py:463), so four rotors cannot be passed as four points.
#
# Frames: world ENU (z up), body FLU, quaternions WXYZ body -> world, as Isaac Lab 2.3.2. Positions are relative to
# the game's own origin (the environment origin is added inside). Gravity (0, 0, -9.81).
# =====================================================================================================================
import math  # noqa: E402

from isaaclab.assets import RigidObjectCfg, RigidObjectCollectionCfg  # noqa: E402

from svg_training.models.frames import quat_wxyz_to_rotmat  # noqa: E402
from svg_training.models.physics_params import G_MPS2, TICK_S, AirframeParams  # noqa: E402

ISAAC_WORLD_LABEL = "isaaclab-2.3.2"
BODY_SIZE_M = (0.19, 0.26, 0.05)          # the Starling's CAD footprint, x along the nose (visual only: no collider)
MAX_ANGULAR_VELOCITY_DEG_S = 1.0e4        # PhysX clamps the body rate here; the cascade limits rates to 150 deg/s
SLOT_SPAWN_SPACING_M = 1.5                # where the slots stand before the first reset (game frame, 2 m up)
VISUALS = (None,)                         # Task 6 adds "starling" and "primitive"


def make_physics_sim(physics_dt_s: float, device: str):
    """SimulationContext for the physics drone: dt = physics_dt_s, gravity (0, 0, -9.81), one render per game tick
    (render_interval = physics steps per 0.05 s tick). PhysX solver settings are Isaac Lab's defaults (TGS)."""
    substeps = round(TICK_S / physics_dt_s)
    cfg = sim_utils.SimulationCfg(dt=physics_dt_s, device=device, render_interval=substeps,
                                  gravity=(0.0, 0.0, -G_MPS2))
    return sim_utils.SimulationContext(cfg)


def drone_rigid_props():
    """Rigid-body settings of every drone (S2b plan Task 5; each is read back by IsaacWorld.body_settings)."""
    return sim_utils.RigidBodyPropertiesCfg(
        linear_damping=0.0, angular_damping=0.0, sleep_threshold=0.0, enable_gyroscopic_forces=True,
        max_angular_velocity=MAX_ANGULAR_VELOCITY_DEG_S, max_linear_velocity=1.0e3, disable_gravity=False)


class IsaacWorld:
    """N games x M rigid-body Starlings in PhysX (Isaac Lab 2.3.2): ``models/rigid_body.RigidBodyWorld``.

    Build it after ``make_physics_sim`` and before ``physics_play(sim, world)`` (which starts the simulation, writes
    the inertia and checks the read-back); the world is usable only after that. ``state()`` returns tensors that stay
    as they were (fresh clones after each step or write), so a caller may keep them. ``write_state`` and ``reset`` are
    one batched write of every body (``torch.where`` on the mask; no index gathering, no host read).

    The held wrench (``apply_wrench_b``) is set on the permanent wrench composer before every physics step; ``reset``
    zeroes it for the reset drones, as the torch world does.
    """

    def __init__(self, sim, num_games: int, drones: int, a: AirframeParams, physics_dt_s: float,
                 spacing_m: float = 40.0, visual: str | None = None) -> None:
        if visual not in VISUALS:
            raise NotImplementedError(f"visual {visual!r}: Task 6 adds the Starling and primitive visuals")
        if abs(sim.cfg.dt - physics_dt_s) > 1e-12:
            raise ValueError(f"the simulation steps {sim.cfg.dt} s, the world was asked for {physics_dt_s} s")
        self.sim = sim
        self.num_games, self.drones, self.dt_s = num_games, drones, physics_dt_s
        self.label = ISAAC_WORLD_LABEL
        self.device = torch.device(sim.device)
        self.a = a
        self.visual = visual
        slots = {}
        for s in range(drones):
            x_m = (s - (drones - 1) / 2.0) * SLOT_SPAWN_SPACING_M
            slots[f"drone_{s}"] = RigidObjectCfg(
                prim_path=f"{{ENV_REGEX_NS}}/Drone_{s}",
                spawn=sim_utils.CuboidCfg(size=BODY_SIZE_M, rigid_props=drone_rigid_props(),
                                          mass_props=sim_utils.MassPropertiesCfg(mass=a.mass_kg),
                                          collision_props=None),
                init_state=RigidObjectCfg.InitialStateCfg(pos=(x_m, 0.0, SPAWN_HEIGHT_M)))
        scene_cfg = InteractiveSceneCfg(num_envs=num_games, env_spacing=spacing_m, replicate_physics=True)
        # InteractiveScene reads cfg.__dict__ (interactive_scene.py:729), so an asset added to the instance is spawned
        scene_cfg.drones = RigidObjectCollectionCfg(rigid_objects=slots)
        self.scene = InteractiveScene(scene_cfg)
        self._ready = False

    # ------------------------------------------------------------------------------------------- after play
    def _after_play(self) -> None:
        """Called by physics_play once the simulation runs: write the inertia, cache origins and state."""
        self.co = self.scene["drones"]
        if (self.co.num_instances, self.co.num_objects) != (self.num_games, self.drones):
            raise RuntimeError(f"PhysX holds {self.co.num_instances} x {self.co.num_objects} bodies, "
                               f"expected {self.num_games} x {self.drones}")
        self.origins = self.scene.env_origins.clone()                                     # [N, 3] world
        n, m = self.num_games, self.drones
        kw = dict(device=self.device, dtype=torch.float32)
        self._force_b = torch.zeros(n, m, 3, **kw)
        self._torque_b = torch.zeros(n, m, 3, **kw)
        self.co.permanent_wrench_composer.reset()
        self.write_inertia()                                    # the bodies are at their spawn poses, at rest
        self._ready = True

    def write_inertia(self, inertia_kgm2: tuple[float, float, float] | None = None) -> None:
        """Write a diagonal inertia (default: the airframe's) into PhysX for every drone, then take one settling
        physics step with no wrench and put every body back exactly as it was (pose and velocities, one write).

        Why the settling step: observed in Task 5 (GPU pipeline), the first physics step after play and the inertia
        write turned the bodies about 1.29x as fast as the written inertia allows (a probe with a roll torque); from
        the next step on the body rates match the torch world to 1e-6. Whether play or the write itself causes it was
        not separated, so any later inertia change comes through here and is settled the same way (a precaution). The held wrench (``apply_wrench_b``) is kept and applied from the next step.
        The smoke run's first_step check (tests/test_isaac_world.py) pins this.
        """
        ixx, iyy, izz = self.a.inertia_kgm2 if inertia_kgm2 is None else inertia_kgm2
        view = self.co.root_physx_view
        count = view.count
        want = torch.tensor([ixx, 0.0, 0.0, 0.0, iyy, 0.0, 0.0, 0.0, izz], dtype=torch.float32)
        current = view.get_inertias()
        view.set_inertias(want.expand(count, 9).reshape(current.shape).clone().to(current.device),
                          torch.arange(count, dtype=torch.int32, device=current.device))
        d = self.co.data
        before = torch.cat((d.object_link_pose_w, d.object_com_vel_w), dim=-1).clone()  # [N, M, 13] world
        zero = torch.zeros(self.num_games, self.drones, 3, device=self.device, dtype=torch.float32)
        self.co.permanent_wrench_composer.set_forces_and_torques(forces=zero, torques=zero, is_global=False)
        self.scene.write_data_to_sim()
        self.sim.step(render=False)
        self.scene.update(dt=self.dt_s)
        self.co.write_object_state_to_sim(before)
        self._refresh()

    def _refresh(self) -> None:
        """Read the state PhysX holds (after a step) into game-relative clones."""
        d = self.co.data
        pose = d.object_link_pose_w                                                       # [N, M, 7] pos, wxyz
        self._pos = pose[..., :3] - self.origins[:, None]
        self._quat = pose[..., 3:7].clone()
        self._lin = d.object_com_lin_vel_w.clone()
        self._ang_b = d.object_com_ang_vel_b.clone()

    # ------------------------------------------------------------------------------------------- read-back
    def mass_inertia_readback(self) -> tuple[torch.Tensor, torch.Tensor]:
        """What PhysX holds: mass [N, M] (kg) and the inertia diagonal [N, M, 3] (kg m^2), on the CPU."""
        view = self.co.root_physx_view
        mass = self.co.reshape_view_to_data(view.get_masses().reshape(view.count, -1).cpu())[..., 0]
        inertia = self.co.reshape_view_to_data(view.get_inertias().reshape(view.count, 9).cpu())
        return mass, inertia[..., [0, 4, 8]]

    def inertia_offdiag_max(self) -> float:
        """Largest off-diagonal inertia entry PhysX holds (kg m^2); 0 for the diagonal body we specified."""
        view = self.co.root_physx_view
        i = view.get_inertias().reshape(view.count, 9).cpu()
        return float(i[:, [1, 2, 3, 5, 6, 7]].abs().max())

    def com_offset_max_m(self) -> float:
        """Largest distance of a body's centre of mass from its origin, as PhysX holds it (m)."""
        view = self.co.root_physx_view
        return float(view.get_coms().reshape(view.count, -1)[:, :3].cpu().norm(dim=-1).max())

    def body_settings(self) -> dict:
        """The rigid-body attributes of game 0, slot 0 as the USD stage holds them for PhysX (read back, not assumed)."""
        import omni.usd
        from pxr import Usd, UsdPhysics

        stage = omni.usd.get_context().get_stage()
        root = stage.GetPrimAtPath(self.scene.env_prim_paths[0] + "/Drone_0")
        body = next((p for p in Usd.PrimRange(root) if p.HasAPI(UsdPhysics.RigidBodyAPI)), None)
        if body is None:
            raise RuntimeError("no rigid body under " + str(root.GetPath()))

        def get(name: str):
            attr = body.GetAttribute("physxRigidBody:" + name)
            return attr.Get() if attr and attr.IsValid() else None

        return {"prim": str(body.GetPath()),
                "enable_gyroscopic_forces": bool(get("enableGyroscopicForces")),
                "linear_damping": float(get("linearDamping")), "angular_damping": float(get("angularDamping")),
                "sleep_threshold": float(get("sleepThreshold")),
                "max_angular_velocity_deg_s": float(get("maxAngularVelocity")),
                "has_collider": any(p.HasAPI(UsdPhysics.CollisionAPI) for p in Usd.PrimRange(root)),
                "solver_type": int(self.sim.cfg.physx.solver_type)}

    # ------------------------------------------------------------------------------------------- RigidBodyWorld
    def reset(self, mask: torch.Tensor, pos_m: torch.Tensor, quat_wxyz: torch.Tensor) -> None:
        """Where mask [N, M]: pose pos_m [N, M, 3], quat_wxyz [N, M, 4], at rest, held wrench zero. One write."""
        self.write_state(mask, pos_m, quat_wxyz, torch.zeros_like(self._lin), torch.zeros_like(self._ang_b))
        k = mask.unsqueeze(-1)
        self._force_b = torch.where(k, torch.zeros_like(self._force_b), self._force_b)
        self._torque_b = torch.where(k, torch.zeros_like(self._torque_b), self._torque_b)

    def write_state(self, mask: torch.Tensor, pos_m: torch.Tensor, quat_wxyz: torch.Tensor, lin_vel_mps: torch.Tensor,
                    ang_vel_b_rad_s: torch.Tensor) -> None:
        """Where mask [N, M]: the given state (game-relative ENU position, WXYZ attitude, ENU velocity, FLU body
        rates); elsewhere what PhysX holds. One batched write of every body."""
        k = mask.unsqueeze(-1)
        pos = torch.where(k, pos_m, self._pos)
        quat = torch.where(k, quat_wxyz, self._quat)
        lin = torch.where(k, lin_vel_mps, self._lin)
        ang_b = torch.where(k, ang_vel_b_rad_s, self._ang_b)
        ang_w = (quat_wxyz_to_rotmat(quat) @ ang_b.unsqueeze(-1)).squeeze(-1)
        state = torch.cat((pos + self.origins[:, None], quat, lin, ang_w), dim=-1)          # [N, M, 13] world
        self.co.write_object_state_to_sim(state)
        self._pos, self._quat, self._lin, self._ang_b = pos, quat, lin, ang_b

    def apply_wrench_b(self, force_b: torch.Tensor, torque_b: torch.Tensor) -> None:
        """Body-frame (FLU) force [N, M, 3] (N) and torque [N, M, 3] (N m) about the centre of mass, held until the
        next call. Copied (float32, contiguous) as the composer reads it on the next step."""
        self._force_b = force_b.to(torch.float32).contiguous().clone()
        self._torque_b = torque_b.to(torch.float32).contiguous().clone()

    def step(self) -> None:
        """One physics step: wrench -> write_data_to_sim -> sim.step(render=False) -> update(dt) (S0's step_scene)."""
        self.co.permanent_wrench_composer.set_forces_and_torques(forces=self._force_b, torques=self._torque_b,
                                                                 is_global=False)
        self.scene.write_data_to_sim()
        self.sim.step(render=False)
        self.scene.update(dt=self.dt_s)
        self._refresh()

    def state(self) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        """pos_m [N, M, 3] (game-relative ENU), quat_wxyz [N, M, 4], lin_vel_w [N, M, 3] (ENU), ang_vel_b [N, M, 3]
        (FLU)."""
        return self._pos, self._quat, self._lin, self._ang_b


def physics_play(sim, world: IsaacWorld, rel_err_max: float | None = 1.0e-4) -> None:
    """Start the simulation (``play``), write the drones' inertia into PhysX and read mass and inertia back.

    rel_err_max: raise RuntimeError when the read-back mass or inertia differs from the airframe by more than this
    (relative); None reports nothing and leaves the check to the caller (the agreement run gates it itself).
    """
    play(sim)
    world._after_play()
    if rel_err_max is None:
        return
    mass, inertia = world.mass_inertia_readback()
    want = torch.tensor(world.a.inertia_kgm2, dtype=torch.float32)
    m_err = float(((mass - world.a.mass_kg).abs() / world.a.mass_kg).max())
    i_err = float(((inertia - want).abs() / want).max())
    if not (m_err <= rel_err_max and i_err <= rel_err_max) or math.isnan(m_err + i_err):
        raise RuntimeError(f"PhysX holds a different body: mass rel err {m_err:.3g}, inertia rel err {i_err:.3g} "
                           f"(limit {rel_err_max:g})")
