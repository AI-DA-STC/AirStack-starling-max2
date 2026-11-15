"""S2b de-risking SPIKE (not a run of record): N games x 8 rigid-body Starlings in Isaac Lab 2.3.2, headless.

docker/run.sh 'svg-isaaclab -p scripts/spike_isaac_starling.py --headless --num-games 64 --out runs/sdd/s2b/isaac_spike/results.jsonl'

One process = one N. Each drone is a plain rigid body (no collider, no USD) with the Starling's mass and inertia
from params/starling_physics_v0.toml. Per-rotor thrusts at the CAD rotor positions are summed into one body-frame
wrench per drone each physics step (Isaac Lab's wrench composer takes one application point per body). Three phases:
  1. hover: 2 s of hover thrust from rest -> drift (Isaac world, ENU/FLU, z up); then 0.5 s at 1.1 x weight -> climb;
  2. tilt: 0.2 s of a 1 % roll differential (total thrust unchanged) -> roll rate and angle vs tau / I_xx * t;
  3. throughput: hover thrust +-1 % noise, `--steps` timed physics steps at 200 Hz.
Prints one JSON line (and appends it to --out). Exits with os._exit (Kit's close spins in the container, as S0 found).
Spike only: Isaac imports live here, inside functions; Task 5 moves them into compat/isaaclab_232.py.
"""
import argparse
import json
import os
import pathlib
import subprocess
import sys
import time
import tomllib
import traceback

ROOT = pathlib.Path(__file__).resolve().parents[1]
PARAMS = ROOT / "params" / "starling_physics_v0.toml"
DRONES_PER_GAME = 8           # 5 Guard + 3 Strike slots (labels only)
PHYSICS_DT_S = 0.005          # 200 Hz (D6)
SPAWN_HEIGHT_M = 2.0
SLOT_SPACING_M = 1.5
HOVER_S = 2.0
TILT_S = 0.2
TILT_FRAC = 0.01


def gpu_used_mib() -> "int | None":
    """Device-wide used memory from nvidia-smi (sees every process on the GPU), or None."""
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=20).stdout
        return int(out.split()[0])
    except Exception:
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--num-games", type=int, required=True)
    ap.add_argument("--steps", type=int, default=2000, help="timed physics steps in phase 3")
    ap.add_argument("--warmup", type=int, default=50)
    ap.add_argument("--spacing-m", type=float, default=40.0)
    ap.add_argument("--out", default="runs/sdd/s2b/isaac_spike/results.jsonl")
    ap.add_argument("--layout", choices=("slots", "collection"), default="slots",
                    help="slots: one RigidObject per drone slot; collection: one RigidObjectCollection")
    ap.add_argument("--profile", action="store_true", help="also time each part of a step (200 extra steps)")
    from isaaclab.app import AppLauncher
    AppLauncher.add_app_launcher_args(ap)
    args = ap.parse_args()
    if not args.headless:
        print("run with --headless", file=sys.stderr)
        return 2
    row = {"spike": "isaac_starling", "num_games": args.num_games, "drones_per_game": DRONES_PER_GAME,
           "drones": args.num_games * DRONES_PER_GAME, "physics_hz": round(1 / PHYSICS_DT_S),
           "nvsmi_before_launch_mib": gpu_used_mib()}
    t0 = time.time()
    app = AppLauncher(args).app
    row["launch_s"] = round(time.time() - t0, 1)
    code = 1
    try:
        code = run(args, row)
    except BaseException as e:
        traceback.print_exc()
        oom = "out of memory" in repr(e).lower()
        row.update(status="oom" if oom else "crash", error=repr(e)[:400], nvsmi_at_fail_mib=gpu_used_mib())
        emit(args.out, row)
    finally:
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(code)


def emit(out: str, row: dict) -> None:
    line = json.dumps(row)
    print("SPIKE_JSON " + line, flush=True)
    p = pathlib.Path(out)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a") as fh:
        fh.write(line + "\n")


def run(args, row: dict) -> int:
    import torch

    import isaaclab.sim as sim_utils
    from isaaclab.assets import RigidObjectCfg, RigidObjectCollectionCfg
    from isaaclab.scene import InteractiveScene, InteractiveSceneCfg

    p = tomllib.loads(PARAMS.read_text())
    af, gains = p["airframe"], p["gains"]
    mass_kg, inertia = float(af["mass_kg"]), [float(x) for x in af["inertia_kgm2"]]
    device = args.device
    n, k = args.num_games, DRONES_PER_GAME
    torch.manual_seed(0)

    # rotor geometry: CAD (x fwd, y right) FRD -> FLU (y left); yaw reaction sign from CA_ROTOR*_KM (PX4: FRD yaw
    # moment = +km * T, so FLU yaw = -sign(km) * (k_m / k_f) * T)
    rxy = torch.tensor(af["rotor_xy_cad_m"], dtype=torch.float32, device=device)       # [4, 2] FRD
    rx_flu, ry_flu = rxy[:, 0], -rxy[:, 1]
    km_sign = torch.tensor([1.0 if gains[f"ca_rotor{i}_km"] > 0 else -1.0 for i in range(4)], device=device)
    yaw_arm_m = -km_sign * float(af["k_m"]) / float(af["k_f"])                          # [4]

    def wrench(thrust_n: "torch.Tensor") -> "tuple[torch.Tensor, torch.Tensor]":
        """thrust_n [N, K, 4] -> body-frame (FLU) force [N, K, 3], torque [N, K, 3] about the centre of mass."""
        z = torch.zeros_like(thrust_n[..., 0])
        force = torch.stack([z, z, thrust_n.sum(-1)], dim=-1)
        torque = torch.stack([(ry_flu * thrust_n).sum(-1), -(rx_flu * thrust_n).sum(-1),
                              (yaw_arm_m * thrust_n).sum(-1)], dim=-1)
        return torch.nan_to_num(force), torch.nan_to_num(torque)

    sim = sim_utils.SimulationContext(sim_utils.SimulationCfg(dt=PHYSICS_DT_S, device=device, render_interval=10,
                                                              gravity=(0.0, 0.0, -9.81)))
    scene_cfg = InteractiveSceneCfg(num_envs=n, env_spacing=args.spacing_m, replicate_physics=True)
    rigid = sim_utils.RigidBodyPropertiesCfg(linear_damping=0.0, angular_damping=0.0, sleep_threshold=0.0,
                                             enable_gyroscopic_forces=True, max_angular_velocity=1.0e4,
                                             max_linear_velocity=1.0e3, disable_gravity=False)
    slot_cfgs = {}
    for s in range(k):
        x_m = ((s % 4) - 1.5) * SLOT_SPACING_M
        y_m = (s // 4 - 0.5) * SLOT_SPACING_M
        slot_cfgs[f"drone_{s}"] = RigidObjectCfg(
            prim_path=f"{{ENV_REGEX_NS}}/Drone_{s}",
            spawn=sim_utils.CuboidCfg(size=(0.19, 0.26, 0.05), rigid_props=rigid,
                                      mass_props=sim_utils.MassPropertiesCfg(mass=mass_kg), collision_props=None),
            init_state=RigidObjectCfg.InitialStateCfg(pos=(x_m, y_m, SPAWN_HEIGHT_M)))
    collection = args.layout == "collection"
    if collection:  # one asset, N x K bodies, one wrench write per step
        scene_cfg.drones = RigidObjectCollectionCfg(rigid_objects=slot_cfgs)
    else:           # one RigidObject per drone slot (the S2b plan's Task 5 sketch)
        for name, c in slot_cfgs.items():
            setattr(scene_cfg, name, c)
    t0 = time.time()
    scene = InteractiveScene(scene_cfg)
    drones = [scene["drones"]] if collection else [scene[f"drone_{s}"] for s in range(k)]
    sim.reset()
    import builtins
    exc = getattr(builtins, "ISAACLAB_CALLBACK_EXCEPTION", None)
    if exc is not None:
        raise exc
    # inertia: the body has no collider, so PhysX cannot derive it; write the diagonal explicitly (CPU tensors)
    inert_err, mass_err = 0.0, 0.0
    want_i = torch.tensor([inertia[0], 0, 0, 0, inertia[1], 0, 0, 0, inertia[2]], dtype=torch.float32)
    for d in drones:
        view = d.root_physx_view
        cnt = view.count
        ids = torch.arange(cnt, dtype=torch.int32)
        cur = view.get_inertias()
        view.set_inertias(want_i.expand(cnt, 9).reshape(cur.shape).clone(), ids)
        got_i, got_m = view.get_inertias().reshape(cnt, -1), view.get_masses().reshape(cnt, -1)
        inert_err = max(inert_err, float(((got_i - want_i).abs().max() / max(inertia)).item()))
        mass_err = max(mass_err, float(((got_m - mass_kg).abs().max() / mass_kg).item()))
    row.update(layout=args.layout, scene_build_s=round(time.time() - t0, 1),
               body="plain rigid body (no collider, no USD)",
               mass_rel_err=mass_err, inertia_rel_err=inert_err, nvsmi_after_build_mib=gpu_used_mib())

    origins = scene.env_origins                                                     # [N, 3]
    if collection:
        co = drones[0]
        default = co.data.default_object_state.clone()                              # [N, K, 13] game frame
    else:
        default = torch.stack([d.data.default_root_state for d in drones], dim=1).clone()  # [N, K, 13] game frame
    hover_n = mass_kg * 9.81 / 4.0

    def reset_all() -> None:
        if collection:
            st = default.clone()
            st[..., :3] += origins[:, None]
            co.write_object_state_to_sim(st)
        else:
            for s, d in enumerate(drones):
                st = default[:, s].clone()
                st[:, :3] += origins
                d.write_root_state_to_sim(st)
        scene.reset()
        for d in drones:  # the composer keeps its wrench; zero it after the reset
            d.permanent_wrench_composer.reset()

    def set_wrench(thrust_n: "torch.Tensor") -> None:
        f, t = wrench(thrust_n)
        if collection:
            co.permanent_wrench_composer.set_forces_and_torques(forces=f, torques=t)
        else:
            for s, d in enumerate(drones):
                d.permanent_wrench_composer.set_forces_and_torques(forces=f[:, s:s + 1], torques=t[:, s:s + 1])

    def step(thrust_n: "torch.Tensor") -> None:
        set_wrench(thrust_n)
        scene.write_data_to_sim()
        sim.step(render=False)
        scene.update(dt=PHYSICS_DT_S)

    def stack(name_slot: str, name_coll: str) -> "torch.Tensor":
        if collection:
            return getattr(co.data, name_coll)
        return torch.stack([getattr(d.data, name_slot) for d in drones], dim=1)

    def pos_rel() -> "torch.Tensor":
        return stack("root_link_pose_w", "object_link_pose_w")[..., :3] - origins[:, None]  # [N, K, 3]

    hover = torch.full((n, k, 4), hover_n, device=device)

    # phase 1: hover drift after 2 s
    reset_all()
    for _ in range(round(HOVER_S / PHYSICS_DT_S)):
        step(hover)
    drift = (pos_rel() - default[..., :3]).norm(dim=-1)
    row.update(hover_drift_max_m=float(drift.max().item()), hover_drift_mean_m=float(drift.mean().item()),
               hover_nan=int((~torch.isfinite(drift)).sum().item()))

    # phase 1b: climb, 1.1 x weight for 0.5 s from rest -> dz = 0.5 * 0.981 * t^2 (proves gravity on, thrust +z)
    reset_all()
    climb_steps = 100
    for _ in range(climb_steps):
        step(hover * 1.1)
    dz = (pos_rel() - default[..., :3])[..., 2]
    tc = climb_steps * PHYSICS_DT_S
    row.update(climb_dz_want_m=0.5 * 0.1 * 9.81 * tc ** 2, climb_dz_got_m=float(dz.mean().item()),
               climb_dz_spread_m=float((dz.max() - dz.min()).item()))

    # phase 2: tilt. Right rotors (FRD y > 0) +1 %, left -1 %: total thrust unchanged, roll about +x FLU negative.
    reset_all()
    tilt = hover.clone()
    right = (rxy[:, 1] > 0).float() * 2 - 1                                         # +1 right, -1 left
    tilt += hover_n * TILT_FRAC * right
    steps_tilt = round(TILT_S / PHYSICS_DT_S)
    for _ in range(steps_tilt):
        step(tilt)
    tau_x = float((ry_flu * hover_n * TILT_FRAC * right).sum().item())
    t_s = steps_tilt * PHYSICS_DT_S
    want_rate = tau_x / inertia[0] * t_s
    want_angle_deg = 0.5 * tau_x / inertia[0] * t_s ** 2 * 57.29578
    w_b = stack("root_ang_vel_b", "object_ang_vel_b")                               # [N, K, 3]
    q = stack("root_link_quat_w", "object_link_quat_w")                             # [N, K, 4] wxyz
    roll_deg = torch.rad2deg(torch.atan2(2 * (q[..., 0] * q[..., 1] + q[..., 2] * q[..., 3]),
                                         1 - 2 * (q[..., 1] ** 2 + q[..., 2] ** 2)))
    row.update(tilt_roll_rate_want_rad_s=want_rate, tilt_roll_rate_got_rad_s=float(w_b[..., 0].mean().item()),
               tilt_roll_rate_spread_rad_s=float((w_b[..., 0].max() - w_b[..., 0].min()).item()),
               tilt_roll_want_deg=want_angle_deg, tilt_roll_got_deg=float(roll_deg.mean().item()),
               tilt_pitch_yaw_rate_max_rad_s=float(w_b[..., 1:].abs().max().item()))

    # phase 3: throughput (hover +- 1 % noise each step; the wrench is recomputed on the GPU every step)
    reset_all()
    torch.cuda.reset_peak_memory_stats()
    for _ in range(args.warmup):
        step(hover * (0.99 + 0.02 * torch.rand(n, k, 4, device=device)))
    torch.cuda.synchronize()
    t0 = time.perf_counter()
    for _ in range(args.steps):
        step(hover * (0.99 + 0.02 * torch.rand(n, k, 4, device=device)))
    torch.cuda.synchronize()
    dt = time.perf_counter() - t0
    sps = args.steps / dt
    free_b, total_b = torch.cuda.mem_get_info()
    nan = int((~torch.isfinite(stack("root_state_w", "object_state_w"))).sum().item())
    if args.profile:  # where one physics step goes (synchronised after each part, so slower than the timed loop)
        parts = {"wrench_ms": 0.0, "write_ms": 0.0, "physx_step_ms": 0.0, "update_ms": 0.0}
        for _ in range(200):
            th = hover * (0.99 + 0.02 * torch.rand(n, k, 4, device=device))
            for key, fn in (("wrench_ms", lambda: set_wrench(th)), ("write_ms", scene.write_data_to_sim),
                            ("physx_step_ms", lambda: sim.step(render=False)),
                            ("update_ms", lambda: scene.update(dt=PHYSICS_DT_S))):
                torch.cuda.synchronize()
                a = time.perf_counter()
                fn()
                torch.cuda.synchronize()
                parts[key] += (time.perf_counter() - a) * 1e3 / 200
        row.update(profile=parts)
    row.update(status="ok", timed_steps=args.steps, timed_s=round(dt, 3), physics_steps_per_s=sps,
               game_ticks_per_s=sps / 10.0, drone_steps_per_s=sps * n * k,
               drone_ticks_per_s=sps * n * k / 10.0, sim_time_x_realtime=sps * PHYSICS_DT_S,
               torch_max_alloc_mib=torch.cuda.max_memory_allocated() / 2**20,
               device_used_mib=(total_b - free_b) / 2**20, nvsmi_after_run_mib=gpu_used_mib(), nan_after_run=nan,
               gpu=torch.cuda.get_device_name())
    emit(args.out, row)
    return 0


if __name__ == "__main__":
    sys.exit(main())
