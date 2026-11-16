#!/usr/bin/env python3
"""S2b throughput: the game on the physics drone in Isaac Lab, one sweep point (size x games) per process.

    scripts/isaac_preflight.sh --approved-headless        # exit 0 needed: the GPU must be free for a timing run
    python scripts/physics_throughput.py --headless --size 5v3 --num-games 2048 --gates configs/s2b.toml \\
        --out runs/<date>_s2b_throughput/results.jsonl
    python scripts/physics_throughput.py --record-from runs/<date>_s2b_throughput    # no Isaac: record, row, figure

``SvgGame`` with ``[starling_layer] enabled = true, backend = "physics"`` (committed neutral values, no local file;
the filter setting of ``configs/s2_game.toml`` at launch is written into every row): commander copy, safety filter
on every pair, PX4 1.14 cascade, rotor model and Isaac Lab, 10 physics steps per 0.05 s tick. Random actions drawn on
the GPU inside the timed section (the policy's stand-in), as S0.

Timing (S0's, ``configs/s0_benchmark.toml [timing]``): the world is built once; each of ``[throughput] repeats``
repeats builds a fresh game on it (new commander, filter and cascade state; ``reset`` writes the starts) and runs
``bench.timing.measure``: warm-up of at least 50 steps and 2 s, then a timed window of at least 200 steps and 2 s,
no extra host sync inside it. After each timed window a short PROFILING pass (``profile_ticks`` ticks, not timed for
throughput) puts a synchronised timer around the safety filter (``CommandChain._filter``), the cascade
(``Px4Cascade.step``) and the physics step (``world.step``, PhysX on Isaac), and counts world state writes per tick
(``world.write_state``; D9 allows two). The synchronisation inflates every part a little, so the shares are a guide.

One row per repeat, appended to ``--out``: game-steps/s and drone-steps/s, the shares, writes per tick, GPU memory
(the allocator's peak and device-wide in use), NaN count (timed steps with a non-finite position, speed or
reward), upsets (D10) and non-finite wrenches, the filter setting, the yaw-rate gains, nvidia-smi's compute
processes before and after. An out-of-memory error is ONE row with status "oom", any other error one "crash" row.
Resume as S0: a point (case, games) that already has a row in ``--out`` is skipped before Isaac starts; delete its
row to measure it again. Exit codes: 0 measured or skipped, 1 oom or crash (row written), 2 bad arguments.
"""
from __future__ import annotations

import argparse
import datetime
import json
import math
import os
import pathlib
import subprocess
import sys
import time
import tomllib
import traceback

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
sys.path.insert(0, str(ROOT / "scripts"))

SIZES = {"2v1": (2, 1), "5v3": (5, 3)}
S0_CONFIG = ROOT / "configs" / "s0_benchmark.toml"
S0_RESULTS = ROOT / "runs" / "2026-11-15_s0_laptop" / "results.jsonl"
S0_CASES = {"2v1": "t2_k3", "5v3": "t2_k8"}               # S0's tier 2 cases at the same drones per game and 200 Hz
FIG = ROOT / "docs" / "figures" / "s2b_throughput.png"
FIRST_LINE = ("Simulator: observed in the training simulator (tier 2, Isaac Lab), random actions, safety filter on "
              "every pair")
ROW_FIELDS = ("tier", "case", "size", "guards", "strikes", "num_games", "drones_per_game", "repeat", "status",
              "game_steps_per_s", "env_steps_per_s", "drone_steps_per_s", "timed_steps", "timed_s", "nan_count",
              "upsets", "nonfinite_count", "share_filter", "share_cascade", "share_physics", "share_other",
              "profile_ticks", "state_writes_per_tick_max", "state_writes_per_tick_mean", "peak_mem_mb",
              "gpu_mem_used_mb", "filter_iterations", "filter_check_every", "filter_pairs", "preset", "world",
              "physics_dt_s", "yaw_rate_gains", "game_config_sha256", "local_file", "device", "gpu_name", "commit",
              "code_sha", "date")


def physics_cfg(base):
    """The game config of this benchmark: ``base`` (committed neutral values) on the physics backend."""
    return base.replace(**{"starling.enabled": True, "starling.backend": "physics"})


def gpu_compute_apps() -> str:
    try:
        return subprocess.run(["nvidia-smi", "--query-compute-apps=pid,used_memory,process_name",
                               "--format=csv,noheader"], capture_output=True, text=True,
                              timeout=20).stdout.strip().replace("\n", "; ")
    except Exception:
        return "nvidia-smi failed"


def _profile(game, step_fn, ticks: int, device) -> dict:
    """Shares of tick time in the filter, the cascade and the physics step, and world writes per tick (see the
    module docstring). Wraps instance attributes and removes them afterwards."""
    import torch

    cuda = str(device).startswith("cuda")

    def sync():
        if cuda:
            torch.cuda.synchronize()

    layer = game._starling
    chain, drone, world = layer.chain, layer.drone, layer.drone.world
    acc = {"filter": 0.0, "cascade": 0.0, "physics": 0.0}
    writes = [0]

    def timed(name, fn):
        def wrapper(*a, **k):
            sync()
            t0 = time.perf_counter()
            r = fn(*a, **k)
            sync()
            acc[name] += time.perf_counter() - t0
            return r
        return wrapper

    orig_ws = world.write_state

    def counted(*a, **k):
        writes[0] += 1
        return orig_ws(*a, **k)

    patches = [(chain, "_filter", timed("filter", chain._filter)),
               (drone.cascade, "step", timed("cascade", drone.cascade.step)),
               (world, "step", timed("physics", world.step)), (world, "write_state", counted)]
    for obj, name, fn in patches:
        setattr(obj, name, fn)
    per_tick, total = [], 0.0
    try:
        for _ in range(ticks):
            writes[0] = 0
            sync()
            t0 = time.perf_counter()
            step_fn()
            sync()
            total += time.perf_counter() - t0
            per_tick.append(writes[0])
    finally:
        for obj, name, _fn in patches:
            vars(obj).pop(name, None)
    share = {k: (v / total if total > 0 else math.nan) for k, v in acc.items()}
    return {"share_filter": share["filter"], "share_cascade": share["cascade"], "share_physics": share["physics"],
            "share_other": 1.0 - sum(share.values()), "profile_ticks": ticks,
            "state_writes_per_tick_max": max(per_tick) if per_tick else None,
            "state_writes_per_tick_mean": sum(per_tick) / len(per_tick) if per_tick else None}


def measure_point(world, cfg, size: str, num_games: int, device, timing: dict, min_warmup_s: float = 2.0,
                  profile_ticks: int = 20, seed: int = 0) -> list[dict]:
    """Rows for one point (one per repeat; one "oom" or "crash" row on failure) on ``world`` (IsaacWorld or
    TorchRigidBodyWorld, num_games x drones of ``size``). ``cfg`` is the physics game config (``physics_cfg``)."""
    import torch

    from svg_training.bench.rows import code_sha
    from svg_training.bench.timing import git_commit, gpu_name, measure
    from svg_training.core.game import SvgGame
    from svg_training.core.physics_layer import load_game_physics_params
    from svg_training.models.physics_params import yaw_gains_text

    g, s = SIZES[size]
    m = g + s
    cuda = str(device).startswith("cuda")
    p = load_game_physics_params(cfg)
    base = {"tier": 2, "case": f"s2b_{size}", "size": size, "guards": g, "strikes": s, "num_games": num_games,
            "drones_per_game": m, "filter_iterations": cfg.starling.filter_iterations,
            "filter_check_every": cfg.starling.filter_check_every,
            "filter_pairs": "every pair" if cfg.preset == "partner" else "team-mates only", "preset": cfg.preset,
            "world": getattr(world, "label", "?"), "physics_dt_s": p.physics_dt_s, "yaw_rate_gains": yaw_gains_text(p),
            "device": str(device), "gpu_name": gpu_name(str(device)), "commit": git_commit(), "code_sha": code_sha()}
    empty = {k: None for k in ("game_steps_per_s", "env_steps_per_s", "drone_steps_per_s", "timed_steps", "timed_s",
                               "nan_count", "upsets", "nonfinite_count", "share_filter", "share_cascade",
                               "share_physics", "share_other", "profile_ticks", "state_writes_per_tick_max",
                               "state_writes_per_tick_mean", "peak_mem_mb", "gpu_mem_used_mb")}
    rows: list[dict] = []
    repeat = 0
    try:
        for repeat in range(int(timing["repeats"])):
            torch.manual_seed(seed + repeat)
            game = SvgGame(cfg, num_games, g, s, device=str(device), seed=seed, world=world)
            upsets = torch.zeros((), dtype=torch.long, device=device)

            def step(game=game):
                nonlocal upsets
                a = {"guard": torch.rand(num_games, g, 4, device=device) * 2 - 1,
                     "strike": torch.rand(num_games, s, 4, device=device) * 2 - 1}
                out = game.step(a)
                upsets = upsets + (out.info["upset"] & out.done).sum()
                return {"pos": game.pos_m, "vel": game.vel_mps, "reward": out.reward["guard"]}

            r = measure(step, int(timing["warmup_steps"]), int(timing["timed_steps"]), str(device), min_warmup_s,
                        float(timing.get("min_timed_s", 0.0)))
            prof = _profile(game, step, profile_ticks, device)
            n_up = int(upsets) + int(game._upset.sum())
            used = None
            if cuda:
                free_b, total_b = torch.cuda.mem_get_info()
                used = (total_b - free_b) / 2**20
            gsps = r["steps_per_s"] * num_games
            rows.append({**base, "repeat": repeat, "status": "ok", "game_steps_per_s": gsps, "env_steps_per_s": gsps,
                         "drone_steps_per_s": gsps * m, "timed_steps": r["timed_steps"], "timed_s": r["timed_s"],
                         "nan_count": r["nan_count"], "upsets": n_up,
                         "nonfinite_count": int(game._starling.drone.nonfinite_count), **prof,
                         "peak_mem_mb": r["peak_mem_mb"] if cuda else None, "gpu_mem_used_mb": used,
                         "local_file": "none", "game_config_sha256": None,
                         "date": datetime.datetime.now().astimezone().isoformat(timespec="seconds")})
            game = step = None
    except Exception as e:  # noqa: BLE001  torch.OutOfMemoryError is an Exception; one bad point is one row
        oom = isinstance(e, torch.OutOfMemoryError) or "out of memory" in str(e).lower()
        return [{**base, **empty, "repeat": repeat, "status": "oom" if oom else "crash", "local_file": "none",
                 "game_config_sha256": None, "error": f"{type(e).__name__}: {e}"[:300],
                 "date": datetime.datetime.now().astimezone().isoformat(timespec="seconds")}]
    return rows


# ------------------------------------------------------------------------------------------------- one point
def make_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--size", required=True, choices=sorted(SIZES))
    ap.add_argument("--num-games", type=int, required=True)
    ap.add_argument("--gates", default="configs/s2b.toml")
    ap.add_argument("--out", required=True)
    return ap


def _point_ok(args) -> tuple[int, dict | None]:
    gates = tomllib.loads(((ROOT / args.gates) if not os.path.isabs(args.gates) else pathlib.Path(args.gates))
                          .read_text())["throughput"]
    if args.size not in gates["sizes"] or args.num_games not in gates["num_games"]:
        print(f"refused: {args.size} x {args.num_games} is not a [throughput] point "
              f"({gates['sizes']} x {gates['num_games']})", file=sys.stderr)
        return 2, None
    from svg_training.bench.rows import existing_points
    if (f"s2b_{args.size}", args.num_games) in existing_points(args.out):
        print(f"skip s2b_{args.size} {args.num_games}: already in {args.out}")
        return 0, None
    return -1, gates


def run_point(args, gates: dict, apps_before: str) -> int:
    import torch

    from svg_training.compat import isaaclab_232 as isaac
    from svg_training.core.game_config import load_game_cfg
    from svg_training.core.physics_layer import load_game_physics_params

    timing = {**tomllib.loads(S0_CONFIG.read_text())["timing"], "repeats": int(gates["repeats"])}
    base, prov = load_game_cfg(use_local=False)
    cfg = physics_cfg(base)
    p = load_game_physics_params(cfg)
    g, s = SIZES[args.size]
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    try:
        sim = isaac.make_physics_sim(p.physics_dt_s, args.device)
        world = isaac.IsaacWorld(sim, args.num_games, g + s, p.airframe, p.physics_dt_s)
        isaac.physics_play(sim, world)
        rows = measure_point(world, cfg, args.size, args.num_games, args.device, timing)
    except Exception as e:  # noqa: BLE001  building the world failed: still one row
        oom = isinstance(e, torch.OutOfMemoryError) or "out of memory" in str(e).lower()
        rows = [{**{k: None for k in ROW_FIELDS}, "tier": 2, "case": f"s2b_{args.size}", "size": args.size,
                 "guards": g, "strikes": s, "num_games": args.num_games, "drones_per_game": g + s, "repeat": 0,
                 "status": "oom" if oom else "crash", "error": f"{type(e).__name__}: {e}"[:300],
                 "date": datetime.datetime.now().astimezone().isoformat(timespec="seconds")}]
    extent = None
    try:
        extent = float(world.origins.norm(dim=-1).max())
    except Exception:
        pass
    apps_after = gpu_compute_apps()
    with open(out, "a") as fh:
        for r in rows:
            r.update(game_config_sha256=prov.game_sha256, local_file=prov.local_file or "none",
                     host="host (conda env_isaaclab), not the container", pid=os.getpid(), gpu_apps_before=apps_before,
                     gpu_apps_after=apps_after, wall_s=round(time.time() - t0, 1), world_extent_m=extent,
                     timing=timing)
            fh.write(json.dumps(r) + "\n")
    for r in rows:
        if r["status"] == "ok":
            print(f"{r['case']} games={r['num_games']} repeat={r['repeat']}: {r['game_steps_per_s']:,.0f} game-steps/s, "
                  f"{r['drone_steps_per_s']:,.0f} drone-steps/s, filter {r['share_filter']:.2f} cascade "
                  f"{r['share_cascade']:.2f} physics {r['share_physics']:.2f}, writes/tick "
                  f"{r['state_writes_per_tick_max']}, nan {r['nan_count']}, upsets {r['upsets']}", flush=True)
        else:
            print(f"{r['case']} games={r['num_games']}: {r['status']} {r.get('error', '')}", flush=True)
    return 0 if all(r["status"] == "ok" for r in rows) else 1


# ------------------------------------------------------------------------------------------------- record
def _mean(rows, key):
    vals = [r[key] for r in rows if r.get(key) is not None]
    return sum(vals) / len(vals) if vals else None


def summarise(rows: list[dict]) -> list[dict]:
    """One line per point: means over the "ok" repeats; the spread of the two repeats."""
    pts: dict = {}
    for r in rows:
        pts.setdefault((r["size"], r["num_games"]), []).append(r)
    out = []
    for (size, n), rs in sorted(pts.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        ok = [r for r in rs if r["status"] == "ok"]
        d = {"size": size, "num_games": n, "drones_per_game": rs[0]["drones_per_game"], "repeats_ok": len(ok),
             "status": "ok" if ok else rs[0]["status"]}
        for k in ("game_steps_per_s", "drone_steps_per_s", "share_filter", "share_cascade", "share_physics",
                  "share_other", "peak_mem_mb", "gpu_mem_used_mb", "state_writes_per_tick_max"):
            d[k] = _mean(ok, k)
        d["nan_count"] = sum(r["nan_count"] for r in ok) if ok else None
        d["upsets"] = sum(r["upsets"] for r in ok) if ok else None
        d["writes_max"] = max((r["state_writes_per_tick_max"] for r in ok), default=None)
        sp = [r["game_steps_per_s"] for r in ok]
        d["repeat_spread"] = (max(sp) - min(sp)) / (sum(sp) / len(sp)) if len(sp) > 1 else None
        d["foreign_gpu_process"] = any(_foreign(r) for r in rs)
        out.append(d)
    return out


def _foreign(r: dict) -> bool:
    """A compute process other than the remote-desktop daemon was on the GPU before or after the point."""
    for key in ("gpu_apps_before", "gpu_apps_after"):
        for app in (r.get(key) or "").split(";"):
            app = app.strip()
            if app and "remote-desktop" not in app and app.split(",")[0].strip() != str(r.get("pid")):
                return True
    return False


def next_ledger_number(text: str) -> int:
    import re
    return max((int(x) for x in re.findall(r"^\|\s*T(\d+)\s*\|", text, re.M)), default=0) + 1


def _n(x, fmt="{:,.0f}"):
    return "—" if x is None else fmt.format(x)


def record_from(run_dir: pathlib.Path, gates_path: pathlib.Path) -> int:
    from svg_training.bench.rows import code_sha

    rows = [json.loads(line) for line in (run_dir / "results.jsonl").read_text().splitlines() if line.strip()]
    gates = tomllib.loads(gates_path.read_text())["throughput"]
    name = run_dir.name
    rec = ROOT / "records" / f"{name}_record.md"
    if rec.exists():
        print(f"refused: {rec} exists", file=sys.stderr)
        return 2
    import make_s2b_figures as figs

    figs.throughput(str(FIG), str(run_dir / "results.jsonl"), str(S0_RESULTS))
    pts = summarise(rows)
    want = {(s, n) for s in gates["sizes"] for n in gates["num_games"]}
    have = {(p["size"], p["num_games"]) for p in pts}
    best = max((p["drone_steps_per_s"] for p in pts if p["drone_steps_per_s"]), default=None)
    line = gates["trainable_drone_steps_per_s_min"]
    ok_rows = [r for r in rows if r["status"] == "ok"]
    r0 = ok_rows[0] if ok_rows else rows[0]
    verdict = "INFO (no gates)" if want <= have else "ABORTED"
    date = min(r["date"] for r in rows if r.get("date"))
    L = [FIRST_LINE, "", f"# {date} {name} record", "",
         f"Result: **{verdict}**. Read-off (not a gate): the best point runs {_n(best)} drone-steps per second; S0's "
         f"decision line for training on tier 2 is {line:,} (`trainable_drone_steps_per_s_min`): "
         f"{'above' if best and best >= line else 'below'} it. Observed in the training simulator; nothing here is a "
         "flight result.", "",
         "## Purpose", "",
         "How fast does the game run on the physics drone in Isaac Lab, with everything a training run would have on: "
         "the commander copy, the safety filter on every pair, PX4 1.14's cascade at 200 Hz and PhysX? The actions are "
         "random (the stand-in for a policy). The numbers decide whether training can use this tier directly or only "
         "check results from tier 1.", "",
         "## Throughput", "",
         "Means of the repeats. Game-steps per second = games x game ticks per second (environment steps).", "",
         "| Size | Games | Drones per game | Game-steps per second | Drone-steps per second | filter / cascade / physics "
         "share | writes per tick (max) | GPU memory, peak allocated / device in use (MB) | repeat spread | NaN | "
         "upsets | status |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for p in pts:
        shares = ("—" if p["share_filter"] is None else
                  f"{p['share_filter']:.2f} / {p['share_cascade']:.2f} / {p['share_physics']:.2f}")
        L.append(f"| {p['size']} | {p['num_games']:,} | {p['drones_per_game']} | {_n(p['game_steps_per_s'])} | "
                 f"{_n(p['drone_steps_per_s'])} | {shares} | {_n(p['writes_max'], '{}')} | "
                 f"{_n(p['peak_mem_mb'])} / {_n(p['gpu_mem_used_mb'])} | "
                 f"{_n(p['repeat_spread'], '{:.1%}')} | {_n(p['nan_count'], '{}')} | {_n(p['upsets'], '{}')} | "
                 f"{p['status']} ({p['repeats_ok']} of {gates['repeats']}){' *' if p['foreign_gpu_process'] else ''} |")
    L += ["", "![Drone-steps per second against games](../docs/figures/s2b_throughput.png)", "",
          "*Drone-steps per second against the number of games, physics drone in Isaac Lab with the commander, the "
          "safety filter on every pair and PX4's cascade; random actions. Dashed: S0's tier 2 benchmark (ARL Robot 1 "
          "stand-in drones with thrusters, random thrust, no controller, no filter) at the same drones per game. Grey: S0's 20,000 decision line. Made by "
          "`scripts/make_s2b_figures.py throughput`.*", "",
          "## How it was measured", "",
          f"- One process per point, on the HOST (conda `env_isaaclab`), not the container; headless; "
          f"`scripts/isaac_preflight.sh --approved-headless` returned 0 (GPU free) before each point. A `*` in the "
          "status column marks a point where nvidia-smi listed another compute process before or after it.",
          f"- Timing as S0: {r0.get('timing', {}).get('warmup_steps')} warm-up steps and at least 2 s, a timed window of "
          f"at least {r0.get('timing', {}).get('timed_steps')} steps and {r0.get('timing', {}).get('min_timed_s')} s, "
          f"{gates['repeats']} repeats; the world is built once per point, the game afresh per repeat.",
          "- Shares come from a separate 20-tick pass with a synchronised timer around the safety filter, the cascade "
          "and the physics step (each called once or 10 times per tick); the timers' own synchronisation is included, "
          "so the shares are a guide, not a split of the throughput above. Writes per tick: world state writes in one "
          "game tick (D9 allows two).",
          f"- Game: `configs/s2_game.toml` (sha256 `{str(r0.get('game_config_sha256'))[:12]}`), committed neutral "
          f"values, local file: {r0.get('local_file')}; preset {r0.get('preset')}; safety filter on {r0.get('filter_pairs')}, "
          f"{r0.get('filter_iterations')} sweeps, early stop every {r0.get('filter_check_every')} (as the file says at "
          "launch).",
          f"- Physics drone: physics step {r0.get('physics_dt_s')} s (10 per tick), motor lag on; {r0.get('yaw_rate_gains')}.",
          "- NaN = timed steps with a non-finite position, speed or reward; upsets = games in which a drone tipped "
          "past 60 deg or turned non-finite (D10).", "",
          "## Commit", "", f"`{r0.get('commit')}`, code fingerprint `{r0.get('code_sha')}`.", "",
          "## Config", "",
          f"`configs/s2b.toml` `[throughput]` (no gates; sizes {gates['sizes']}, games {gates['num_games']}, "
          f"{gates['repeats']} repeats). Command per point: `python scripts/physics_throughput.py --headless --size "
          f"<size> --num-games <n> --gates configs/s2b.toml --out runs/{name}/results.jsonl`.", "",
          "## Model parameter set", "",
          "Rigid-body Starling `params/starling_physics_v0.toml` (drone's gains) with the SIM-ONLY yaw-rate gains of "
          "`params/sim_only_yaw_v0.toml` (owner's ruling of 16 November 2026; never a drone value).", "",
          "## Seeds", "", "Game seed 0; torch seeded 0 + repeat for the random actions.", "",
          "## Machine", "", f"{r0.get('gpu_name')}; Isaac Sim 5.1.0 / Isaac Lab 2.3.2 on the host, headless.", "",
          "## Games at once", "", f"{', '.join(f'{n:,}' for n in gates['num_games'])} games of 2v1 (3 drones) and 5v3 "
          "(8 drones).", "",
          "## Files", "", f"`runs/{name}/`: `results.jsonl` (every row), one `preflight_<size>_<games>.txt` and "
          "`log_<size>_<games>.txt` per point.", ""]
    rec.write_text("\n".join(L))
    ledger = ROOT / "records" / "LEDGER.md"
    text = ledger.read_text()
    t = next_ledger_number(text)
    row = (f"| T{t} | {date} | training simulator, tier 2 (Isaac Lab: rigid-body Starlings, PX4 1.14 cascade, SIM-ONLY "
           f"yaw-rate gains; commander copy and safety filter on every pair) | {name} | S2b throughput: game on the "
           f"physics drone, random actions, 2v1 and 5v3 x 1024 / 2048 / 4096 games, one process per point; best "
           f"{_n(best)} drone-steps/s (S0 decision line {line:,}) | {verdict} | records/{name}_record.md |")
    ledger.write_text(text + ("" if text.endswith("\n") else "\n") + row + "\n")
    print(f"wrote {rec.relative_to(ROOT)} and ledger row T{t}")
    return 0


def main() -> int:
    if "--record-from" in sys.argv:
        ap = argparse.ArgumentParser()
        ap.add_argument("--record-from", required=True)
        ap.add_argument("--gates", default="configs/s2b.toml")
        a = ap.parse_args()
        return record_from(pathlib.Path(a.record_from).resolve(), (ROOT / a.gates).resolve())
    probe = make_parser()
    probe.add_argument("--headless", action="store_true")
    known, _rest = probe.parse_known_args()
    code, gates = _point_ok(known)
    if code >= 0:
        return code                                     # bad point or already measured: no app launched
    apps_before = gpu_compute_apps()
    from _isaac_app import start_headless
    args, _app = start_headless(make_parser())
    code = 1
    try:
        code = run_point(args, gates, apps_before)
    except BaseException:
        traceback.print_exc()
    finally:
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(code)


if __name__ == "__main__":
    sys.exit(main())
