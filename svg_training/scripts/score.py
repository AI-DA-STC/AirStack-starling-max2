#!/usr/bin/env python
"""Score Guard and Strike strategies against each other in the S2 game (S2 Task 6).

  score.py --guard <spec>[,<spec>...] --strike <spec>[,<spec>...] [--sizes 2v1,5v3] [--presets pure,starling]
           [--games-per-band 1000] [--bands lab,middle,large] [--scenario <name>] [--seed 0] [--no-local]
           [--local-dir configs/local] [--device cuda] [--batch-per-pair] --out runs/<name>/
  # S2b: the physics drone in Isaac Lab (host conda env_isaaclab python, after scripts/isaac_preflight.sh)
  score.py ... --presets physics --sizes <one size> --batch-per-pair --headless --out runs/<name>/

A spec is a scripted opponent's name (``opponents/scripted.py`` REGISTRY: guard_mark_edge, guard_mark_inside,
guard_field, guard_mirror, strike_straight, strike_flank, random, zero) or ``package.module:ClassName`` (outside
code with the same constructor). A comma list plays every Guard spec against every Strike spec. Size "GvS" =
G Guard drones v S Strike drones. Presets: "pure" = pure partner rules; "starling" = with the Starling layer
(``[starling_layer]`` of the game file as it is at launch, switched on); "physics" (S2b) = the same Starling layer's
command chain flying the physics drone (rigid-body Starling under PX4 1.14's cascade, the drone's gains with the
owner's SIM-ONLY yaw-rate gains) in Isaac Lab. Each band is its own batch (``SvgGame(band=...)``): every Guard x
Strike pair plays ``--games-per-band`` games on its own slice of that batch (``SplitStrategy``), so the pairs meet
different (independently drawn) arenas and starts. With ``--batch-per-pair`` (S2b D15, default off; S2 behaviour and
S2 results unchanged without it) every pair plays its own batch of ``--games-per-band`` games with the band's game
seed, so slot k meets the same arena and starts in every pair and on every backend (no backend draws from the game's
generator; same games-per-band and device only); per_game.npz then also holds each slot's start positions and arena.
Every game slot counts its first finished game only. Game seed = --seed + band index; strategy seeds = --seed + 101 (Guard) and
--seed + 202 (Strike). With ``--scenario`` the one named fixed scenario replaces the
bands (sizes default to 1v1 for a two-drone scenario).

Writes into --out (refuses if ``scores.json`` is already there): ``gates.toml`` (``gates = []``: scoring is
INFO, written before anything runs), ``scores.json`` ({"meta": ..., "rows": [...]}, one row per preset x size x
Guard x Strike x band), ``scores.md`` (one table per preset x size, a row per band, rates with Wilson 95 %
intervals) and ``per_game.npz`` (per-game arrays for figures). The game config file is named with its sha256;
the local partner file, if used, by its file name and sha256 only: no rule value is ever printed.

The physics preset needs ``--batch-per-pair``, exactly one size, a CUDA device and ``--headless``: it starts Isaac
Sim (headless) before torch is imported, builds ONE ``IsaacWorld`` of games-per-band games x the size's drones and
reuses it for every band and pair (a new ``SvgGame`` each). Its rows add ``upset_games`` and per_game.npz an
``upset`` array; meta names the physics parameter file, the yaw-rate gains in use and the physics drone's count of
non-finite wrench values. Meta also carries ``motion`` (preset -> the game's motion path) and ``code_sha``.

Exit 0 when the outputs were written, 1 on refusal (including any non-finite action from either strategy: the game
commands such a drone zero and counts it; scoring refuses rather than report a hold rate a NaN strategy "earned"),
2 when the physics preset is asked with more than one size, without --batch-per-pair, without --headless or on a
device other than cuda (refused before Isaac Sim or torch is imported).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

import os
import traceback

# Only the standard library here: with the physics preset Isaac Sim must start before torch is imported (S2b plan).
# numpy, torch and svg_training are imported inside main().
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
sys.path.insert(0, str(ROOT / "scripts"))
CONFIGS = ROOT / "configs"
BAND_NAMES = ("lab", "middle", "large")      # = core.arena.BANDS (checked in main), for the parser's default

PRESET_NAMES = {"pure": "pure partner rules", "starling": "with Starling layer (exploratory drone model)",
                "physics": "physics drone (tier 2: rigid-body Starling, PX4 1.14 cascade)"}


def parse_size(s: str) -> tuple[int, int]:
    """'2v1' -> (2 Guard drones, 1 Strike drone)."""
    try:
        g, st = s.lower().split("v")
        return int(g), int(st)
    except ValueError:
        raise ValueError(f"size must look like '2v1' (Guard v Strike), got {s!r}") from None


def _csv(s: str | None) -> list[str] | None:
    return None if s is None else [x.strip() for x in s.split(",") if x.strip()]


def _sha_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _git_head() -> str:
    try:
        return subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True,
                              check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _fmt(v, nd: int = 2) -> str:
    return "n/a" if v is None else f"{v:.{nd}f}"


def _pct(v) -> str:
    return "n/a" if v is None else f"{100 * v:.1f} %"


def render_md(meta: dict, rows: list[dict]) -> str:
    """scores.md: provenance lines, then one table per preset x size, a row per Guard x Strike x band."""
    world = meta.get("physics", {}).get("world", "")
    tiers = (f"training simulator, tier 2 (S2 game on the physics drone, world `{world}`)"
             if meta["presets"] == ["physics"] else
             f"training simulator, tier 1 (S2 game) and tier 2 (physics drone, world `{world}`)"
             if "physics" in meta["presets"] else "training simulator, tier 1 (S2 game)")
    lines = ["# Scores", "", f"Simulator: {tiers}. Seed {meta['seed']}, "
             f"device {meta['device']}, commit `{meta['commit'][:12]}`.", "",
             f"- Game config: `{meta['game_file']}`, sha256 `{meta['game_sha256']}`.",
             "- Local partner file: " + (f"used: `{meta['local_file']}`, sha256 `{meta['local_sha256']}`."
                                          if meta["local_file"] else "not used (committed neutral values)."),
             f"- Starling layer setting at launch: parameter file `{meta['starling']['params']}` (sha256 "
             f"`{meta['starling']['params_sha256'][:12]}`, exploratory), filter {meta['starling']['filter_iterations']}"
             f" sweeps, check_every {meta['starling']['filter_check_every']}; safety filter on every pair.",
             *([f"- Physics drone: `{meta['physics']['physics_params']}` (sha256 "
                f"`{meta['physics']['physics_params_sha256'][:12]}`), {meta['physics']['yaw_rate_gains']}; physics "
                f"step {meta['physics']['physics_dt_s']} s, motor lag {meta['physics']['motor_lag']}, rotor geometry "
                f"{meta['physics']['rotor_geometry']}, world `{meta['physics']['world']}`; non-finite wrench values "
                f"{meta['physics']['nonfinite_count']}. Upset = a live drone tipped past 60 deg or turned non-finite."]
               if "physics" in meta else []),
             *(["- Paired games (--batch-per-pair): each Guard x Strike pair is its own batch with the band's game "
                "seed, so slot k meets the same arena and starts in every pair and on every backend."]
               if meta.get("batch_per_pair") else []),
             "- Hold rate = share of games the Guard team held (no Strike drone reached the zone), with its "
             "Wilson 95 % interval. Each game slot counts its first finished game only.",
             "- Closest = closest horizontal approach of a Guard and a Strike drone in a game (m): minimum over the "
             "games, then the 5th and 50th percentiles of the per-game values; 3-D = the same measured in 3-D (the "
             "safety filter works in 3-D, so a pair passing one above the other is close only horizontally). "
             "Breach = share of games with an opposite pair closer than the keep-out in 3-D. Filter = share of live drone-steps the safety filter "
             "changed. Start miss = share of games whose starts could not meet the spacing / keep-out.", ""]
    keys = []
    for r in rows:
        k = (r["preset"], r["size"])
        if k not in keys:
            keys.append(k)
    for preset, size in keys:
        up_h, up_s = (" upsets |", "---|") if preset == "physics" else ("", "")
        lines += [f"## {PRESET_NAMES.get(preset, preset)}, {size}", "",
                  "| Guard | Strike | band | games | hold rate (95 % interval) | mean end step | closest min / p5 / "
                  "p50 (m) | 3-D min / p5 / p50 (m) | breach | filter | start miss |" + up_h,
                  "|---|---|---|---|---|---|---|---|---|---|---|" + up_s]
        for r in rows:
            if (r["preset"], r["size"]) != (preset, size):
                continue
            hold = ("n/a" if r["hold_rate"] is None else
                    f"{100 * r['hold_rate']:.1f} % ({100 * r['ci_low']:.1f}–{100 * r['ci_high']:.1f})")
            closest = (f"{_fmt(r['closest_cross_m'])} / {_fmt(r['closest_cross_p05_m'])} / "
                       f"{_fmt(r['closest_cross_p50_m'])}")
            closest3 = (f"{_fmt(r['closest_cross_3d_m'])} / {_fmt(r['closest_cross_3d_p05_m'])} / "
                        f"{_fmt(r['closest_cross_3d_p50_m'])}")
            upset = f" {r['upset_games']} |" if "upset_games" in r else ""
            lines.append(f"| {r['guard']} | {r['strike']} | {r['band']} | {r['games']} | {hold} | "
                         f"{_fmt(r['mean_end_step'], 1)} | {closest} | {closest3} | {_pct(r['rule_breach_rate'])} | "
                         f"{_pct(r['filter_rate'])} | {_pct(r['start_miss_rate'])} |{upset}")
        lines.append("")
    return "\n".join(lines)


def make_parser(isaac: bool = False) -> argparse.ArgumentParser:
    """isaac=True leaves --device (and --headless) to Isaac Lab's launcher arguments (it adds its own)."""
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--guard", required=True)
    ap.add_argument("--strike", required=True)
    ap.add_argument("--sizes")
    ap.add_argument("--presets")
    ap.add_argument("--games-per-band", type=int)
    ap.add_argument("--bands", default=",".join(BAND_NAMES))
    ap.add_argument("--scenario")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--no-local", action="store_true", help="use the committed neutral values only")
    ap.add_argument("--local-dir", default=str(CONFIGS / "local"))
    ap.add_argument("--game-config", default=str(CONFIGS / "s2_game.toml"))
    ap.add_argument("--batch-per-pair", action="store_true",
                    help="one batch per Guard x Strike pair, same game seed: paired games (S2b D15)")
    if not isaac:
        ap.add_argument("--device", default="cuda")
    ap.add_argument("--out", required=True)
    return ap


def physics_problem(argv: list[str]) -> str | None:
    """With --presets physics: the reason to refuse (exit 2) before Isaac Sim or torch is imported, else None.
    None also when physics is not asked."""
    pre = argparse.ArgumentParser(add_help=False)
    for flag in ("--presets", "--sizes", "--scenario"):
        pre.add_argument(flag)
    pre.add_argument("--device", default="cuda")
    pre.add_argument("--headless", action="store_true")
    pre.add_argument("--batch-per-pair", action="store_true")
    k, _ = pre.parse_known_args(argv)
    if "physics" not in (_csv(k.presets) or []):
        return None
    if not k.batch_per_pair:
        return "--presets physics needs --batch-per-pair (one world of games-per-band games, reused per pair)"
    sizes = _csv(k.sizes)
    if not (sizes and len(sizes) == 1) and not (sizes is None and k.scenario):
        return (f"--presets physics plays one size per process (one Isaac world); got --sizes {k.sizes or '(default: '}"
                f"{'' if k.sizes else 'the scoring sizes)'}: run once per size")
    if not k.device.startswith("cuda"):
        return f"--presets physics runs on the GPU (Isaac Lab); got --device {k.device}: use cuda"
    if not k.headless:
        return "--presets physics starts Isaac Sim: add --headless (after scripts/isaac_preflight.sh)"
    return None


def main(argv: list[str] | None = None, world_factory=None) -> int:
    """argv: the command line (default sys.argv[1:]). world_factory(n, m, params, device) -> a rigid-body world of n
    games x m drones for the physics preset: IsaacWorld from __main__ (Isaac Sim already started); a
    TorchRigidBodyWorld only from tests. args: an already parsed namespace (from Isaac Lab's launcher) instead."""
    a = make_parser().parse_args(argv) if not isinstance(argv, argparse.Namespace) else argv
    import numpy as np
    import torch

    from svg_training.bench.rows import code_sha
    from svg_training.core.arena import BANDS
    from svg_training.core.game import SCENARIOS, SvgGame
    from svg_training.core.game_config import load_game_cfg, load_s2_gates
    from svg_training.core.metrics import summarise
    from svg_training.core.play import play_match
    from svg_training.core.starling_layer import resolve_params
    from svg_training.core.strategy import SplitStrategy
    from svg_training.opponents.scripted import make_strategy

    assert tuple(BANDS) == BAND_NAMES, (BANDS, BAND_NAMES)
    argv_list = sys.argv[1:] if argv is None or isinstance(argv, argparse.Namespace) else list(argv)
    scoring = load_s2_gates()["scoring"]
    out = Path(a.out)
    if (out / "scores.json").exists():
        print(f"refusing: {out / 'scores.json'} exists (a scoring run is never overwritten)", file=sys.stderr)
        return 1
    if a.scenario is not None and a.scenario not in SCENARIOS:
        print(f"refusing: unknown scenario {a.scenario!r}; known: {sorted(SCENARIOS)}", file=sys.stderr)
        return 1
    guards, strikes = _csv(a.guard), _csv(a.strike)
    presets = _csv(a.presets) or list(scoring["presets"])
    for p in presets:
        if p not in PRESET_NAMES:
            print(f"refusing: unknown preset {p!r}; use pure, starling and/or physics", file=sys.stderr)
            return 1
    physics = "physics" in presets
    if physics and world_factory is None:
        print("refusing: --presets physics needs a world (run as __main__ with --headless: IsaacWorld)",
              file=sys.stderr)
        return 2
    if physics and not a.batch_per_pair:
        print("refusing: --presets physics needs --batch-per-pair", file=sys.stderr)
        return 2
    sc = SCENARIOS[a.scenario] if a.scenario else None
    if a.sizes:
        sizes = _csv(a.sizes)
    elif sc is not None:
        if len(sc.start_m) != 2:
            print("refusing: give --sizes for a scenario of more than two drones", file=sys.stderr)
            return 1
        sizes = ["1v1"]
    else:
        sizes = list(scoring["sizes"])
    if physics and len(sizes) != 1:
        print("refusing: --presets physics plays one size per process", file=sys.stderr)
        return 2
    n = a.games_per_band or int(scoring["games_per_band"])
    bands = [None] if sc is not None else [BANDS.index(b) for b in _csv(a.bands)]

    cfg, prov = load_game_cfg(a.game_config, local_dir=Path(a.local_dir), use_local=not a.no_local)
    params_path = resolve_params(cfg.starling.params)
    meta = {"seed": a.seed, "device": a.device, "commit": _git_head(), "torch": torch.__version__,
            "python": platform.python_version(), "host": platform.node(),
            "gpu": torch.cuda.get_device_name(0) if a.device.startswith("cuda") else None,
            "game_file": Path(prov.game_file).name, "game_sha256": prov.game_sha256,
            "local_file": Path(prov.local_file).name if prov.local_file else None,
            "local_sha256": prov.local_sha256,
            "starling": {"params": cfg.starling.params, "params_sha256": _sha_file(params_path),
                         "filter_iterations": cfg.starling.filter_iterations,
                         "filter_check_every": cfg.starling.filter_check_every},
            "games_per_band": n, "guards": guards, "strikes": strikes, "sizes": sizes, "presets": presets,
            "scenario": a.scenario, "argv": argv_list}
    if a.batch_per_pair:                       # S2b keys: only with the new flag, so S2 outputs are unchanged
        meta.update({"batch_per_pair": True, "bands": [BANDS[b] for b in bands if b is not None],
                     "code_sha": code_sha(ROOT), "motion": {}})

    def preset_cfg(preset: str):
        if preset == "pure":
            return cfg.replace(**{"starling.enabled": False})
        return cfg.replace(**{"starling.enabled": True,
                              "starling.backend": "physics" if preset == "physics" else "fitted"})

    world = None
    if physics:
        from svg_training.core.physics_layer import load_game_physics_params
        from svg_training.models.physics_params import yaw_gains_text

        pcfg = preset_cfg("physics")
        params = load_game_physics_params(pcfg)
        g0, s0 = parse_size(sizes[0])
        world = world_factory(n, g0 + s0, params, a.device)     # ONE world, reused for every band and pair
        meta["physics"] = {"physics_params": pcfg.starling.physics_params,
                           "physics_params_sha256": _sha_file(resolve_params(pcfg.starling.physics_params)),
                           "sim_only_gains_file": pcfg.starling.physics_sim_only_gains,
                           "yaw_rate_gains": yaw_gains_text(params), "physics_dt_s": params.physics_dt_s,
                           "motor_lag": params.motor_lag, "rotor_geometry": params.rotor_geometry,
                           "world": world.label, "nonfinite_count": 0}
    out.mkdir(parents=True, exist_ok=True)
    (out / "gates.toml").write_text("# Scoring is INFO: no gates (S2 plan, Task 6). Written before the run.\n"
                                    "gates = []\n")
    print(f"game config {meta['game_file']} sha256 {prov.game_sha256}; local file "
          f"{meta['local_file'] or 'not used'}{' sha256 ' + prov.local_sha256 if prov.local_sha256 else ''}",
          flush=True)

    rows: list[dict] = []
    per_game: dict[str, np.ndarray] = {}
    nonfinite_wrench = 0
    t_all = time.time()
    for preset in presets:
        pcfg = preset_cfg(preset)
        for size in sizes:
            g, s = parse_size(size)
            for b in bands:
                pairs = [(gs, ss) for gs in guards for ss in strikes]
                where = BANDS[b] if b is not None else a.scenario
                # S2: one batch per band, every Guard x Strike pair on its own slice of n games (the filter's fixed
                # sweep loop costs about the same per step for 1,000 or 10,000 games, so packing saves time).
                # --batch-per-pair: one batch of n games per pair, all with the band's seed (paired games, D15).
                batches = ([[j] for j in range(len(pairs))] if a.batch_per_pair else [list(range(len(pairs)))])
                for js in batches:
                    nb = n * len(js)
                    game = SvgGame(pcfg, nb, g, s, device=a.device, seed=a.seed + (b or 0), band=b, scenario=sc,
                                   world=world if preset == "physics" else None)
                    sl = [slice(i * n, (i + 1) * n) for i in range(len(js))]
                    guard = SplitStrategy("guard", [(make_strategy(pairs[j][0], "guard", pcfg, n, a.device,
                                                                   a.seed + 101), sl[i]) for i, j in enumerate(js)])
                    strike = SplitStrategy("strike", [(make_strategy(pairs[j][1], "strike", pcfg, n, a.device,
                                                                     a.seed + 202), sl[i]) for i, j in enumerate(js)])
                    t0 = time.time()
                    res_all = play_match(game, guard, strike)
                    if a.device.startswith("cuda"):
                        torch.cuda.synchronize()
                    dt = time.time() - t0
                    bad = int(res_all.nonfinite_actions.sum())          # one host read after the match
                    if bad:
                        print(f"refusing: {bad} drone-steps got non-finite (NaN or inf) actions in {preset}|{size}|"
                              f"band {b}; a strategy that outputs NaN is not scored (no scores written)",
                              file=sys.stderr)
                        return 1
                    if preset == "physics":
                        nonfinite_wrench += int(game._starling.drone.nonfinite_count)
                    if a.batch_per_pair:
                        meta["motion"][preset] = game.motion
                    game_steps = nb * res_all.steps_played
                    label = f"{pairs[js[0]][0]} v {pairs[js[0]][1]}: " if a.batch_per_pair else ""
                    print(f"{preset}|{size}|{where}: {label}{len(js)} pairs x {n} games, {res_all.steps_played} "
                          f"steps, {dt:.1f} s, {game_steps / max(dt, 1e-9):,.0f} game-steps/s", flush=True)
                    for i, j in enumerate(js):
                        gs, ss = pairs[j]
                        res = res_all.slice(sl[i])
                        for r in summarise(res):
                            row = {"preset": preset, "size": size, "guard": gs, "strike": ss,
                                   "scenario": a.scenario, **r, "batch_games": nb,
                                   "steps_played": res.steps_played, "batch_game_steps": game_steps,
                                   "batch_seconds": dt,
                                   "batch_game_steps_per_s": game_steps / dt if dt > 0 else None}
                            if preset == "physics":              # D10: games with an upset drone (first games)
                                sel = res.outcome != 0
                                if "band" in r:
                                    sel = sel & (res.band == BANDS.index(r["band"]))
                                row["upset_games"] = int((res.upset & sel).sum())
                            rows.append(row)
                        key = f"{preset}|{size}|{gs}|{ss}|{where}"
                        fields = ["outcome", "end_step", "band", "closest_cross_m", "closest_cross_3d_m",
                                  "rule_breach", "filter_corrected_rate", "start_miss"]
                        if a.batch_per_pair:
                            fields += ["start_pos_m", "arena_m"]
                        if preset == "physics":
                            fields += ["upset"]
                        for f in fields:
                            per_game[f"{key}|{f}"] = getattr(res, f).detach().cpu().numpy()
                        print(f"  {gs} v {ss}: hold {rows[-1]['hold_rate']}", flush=True)
    if physics:
        meta["physics"]["nonfinite_count"] = nonfinite_wrench
    meta["seconds_total"] = time.time() - t_all
    (out / "scores.json").write_text(json.dumps({"meta": meta, "rows": rows}, indent=1))
    (out / "scores.md").write_text(render_md(meta, rows))
    np.savez_compressed(out / "per_game.npz", **per_game)
    print(f"wrote {out / 'scores.json'}, {out / 'scores.md'}, {out / 'per_game.npz'} "
          f"({meta['seconds_total']:.0f} s)", flush=True)
    return 0


def _isaac_world_factory(n: int, m: int, params, device: str):
    """IsaacWorld of n games x m drones (Isaac Sim already started by __main__), as scripts/train_standin.py."""
    from svg_training.compat import isaaclab_232 as isaac
    sim = isaac.make_physics_sim(params.physics_dt_s, device)
    world = isaac.IsaacWorld(sim, n, m, params.airframe, params.physics_dt_s)
    isaac.physics_play(sim, world)                 # starts PhysX, writes the inertia, checks the read-back
    return world


def _main_cli() -> int:
    argv = sys.argv[1:]
    problem = physics_problem(argv)
    if problem is not None:
        print(f"refusing: {problem}", file=sys.stderr)
        return 2
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--presets")
    if "physics" not in (_csv(pre.parse_known_args(argv)[0].presets) or []):
        return main()
    # physics: Isaac Lab, headless only (S2b plan), started before torch is imported
    from _isaac_app import start_headless
    args, _app = start_headless(make_parser(isaac=True))
    code = 1
    try:
        code = main(args, _isaac_world_factory)
    except BaseException:
        traceback.print_exc()
    finally:
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(code)          # never simulation_app.close() (it swallows exit codes in the container)
    return code


if __name__ == "__main__":
    sys.exit(_main_cli())
