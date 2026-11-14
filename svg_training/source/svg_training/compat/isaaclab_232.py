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
