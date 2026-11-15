#!/usr/bin/env python
"""Score Guard and Strike strategies against each other in the S2 game (S2 Task 6).

  score.py --guard <spec>[,<spec>...] --strike <spec>[,<spec>...] [--sizes 2v1,5v3] [--presets pure,starling]
           [--games-per-band 1000] [--bands lab,middle,large] [--scenario <name>] [--seed 0] [--no-local]
           [--local-dir configs/local] [--device cuda] --out runs/<name>/

A spec is a scripted opponent's name (``opponents/scripted.py`` REGISTRY: guard_mark_edge, guard_mark_inside,
guard_field, guard_mirror, strike_straight, strike_flank, random, zero) or ``package.module:ClassName`` (outside
code with the same constructor). A comma list plays every Guard spec against every Strike spec. Size "GvS" =
G Guard drones v S Strike drones. Presets: "pure" = pure partner rules; "starling" = with the Starling layer
(``[starling_layer]`` of the game file as it is at launch, switched on). Each band is its own batch
(``SvgGame(band=...)``): every Guard x Strike pair plays ``--games-per-band`` games on its own slice of that
batch (``SplitStrategy``), so the pairs meet different (independently drawn) arenas and starts. Every game slot
counts its first finished game only. Game seed = --seed + band index; strategy seeds = --seed + 101 (Guard) and
--seed + 202 (Strike). With ``--scenario`` the one named fixed scenario replaces the
bands (sizes default to 1v1 for a two-drone scenario).

Writes into --out (refuses if ``scores.json`` is already there): ``gates.toml`` (``gates = []``: scoring is
INFO, written before anything runs), ``scores.json`` ({"meta": ..., "rows": [...]}, one row per preset x size x
Guard x Strike x band), ``scores.md`` (one table per preset x size, a row per band, rates with Wilson 95 %
intervals) and ``per_game.npz`` (per-game arrays for figures). The game config file is named with its sha256;
the local partner file, if used, by its file name and sha256 only: no rule value is ever printed.

Exit 0 when the outputs were written, 1 on refusal.
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

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
from svg_training.core.arena import BANDS  # noqa: E402
from svg_training.core.game import SCENARIOS, SvgGame  # noqa: E402
from svg_training.core.game_config import CONFIGS, load_game_cfg, load_s2_gates  # noqa: E402
from svg_training.core.metrics import summarise  # noqa: E402
from svg_training.core.play import play_match  # noqa: E402
from svg_training.core.starling_layer import resolve_params  # noqa: E402
from svg_training.core.strategy import SplitStrategy  # noqa: E402
from svg_training.opponents.scripted import make_strategy  # noqa: E402

PRESET_NAMES = {"pure": "pure partner rules", "starling": "with Starling layer (exploratory drone model)"}


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
    lines = ["# Scores", "", f"Simulator: training simulator, tier 1 (S2 game). Seed {meta['seed']}, "
             f"device {meta['device']}, commit `{meta['commit'][:12]}`.", "",
             f"- Game config: `{meta['game_file']}`, sha256 `{meta['game_sha256']}`.",
             "- Local partner file: " + (f"used: `{meta['local_file']}`, sha256 `{meta['local_sha256']}`."
                                          if meta["local_file"] else "not used (committed neutral values)."),
             f"- Starling layer setting at launch: parameter file `{meta['starling']['params']}` (sha256 "
             f"`{meta['starling']['params_sha256'][:12]}`, exploratory), filter {meta['starling']['filter_iterations']}"
             f" sweeps, check_every {meta['starling']['filter_check_every']}; safety filter on every pair.",
             "- Hold rate = share of games the Guard team held (no Strike drone reached the zone), with its "
             "Wilson 95 % interval. Each game slot counts its first finished game only.",
             "- Closest = closest horizontal approach of a Guard and a Strike drone in a game (m): minimum over the "
             "games, then the 5th and 50th percentiles of the per-game values. Breach = share of games with an "
             "opposite pair closer than the keep-out. Filter = share of live drone-steps the safety filter "
             "changed. Start miss = share of games whose starts could not meet the spacing / keep-out.", ""]
    keys = []
    for r in rows:
        k = (r["preset"], r["size"])
        if k not in keys:
            keys.append(k)
    for preset, size in keys:
        lines += [f"## {PRESET_NAMES.get(preset, preset)}, {size}", "",
                  "| Guard | Strike | band | games | hold rate (95 % interval) | mean end step | closest min / p5 / "
                  "p50 (m) | breach | filter | start miss |",
                  "|---|---|---|---|---|---|---|---|---|---|"]
        for r in rows:
            if (r["preset"], r["size"]) != (preset, size):
                continue
            hold = ("n/a" if r["hold_rate"] is None else
                    f"{100 * r['hold_rate']:.1f} % ({100 * r['ci_low']:.1f}–{100 * r['ci_high']:.1f})")
            closest = (f"{_fmt(r['closest_cross_m'])} / {_fmt(r['closest_cross_p05_m'])} / "
                       f"{_fmt(r['closest_cross_p50_m'])}")
            lines.append(f"| {r['guard']} | {r['strike']} | {r['band']} | {r['games']} | {hold} | "
                         f"{_fmt(r['mean_end_step'], 1)} | {closest} | {_pct(r['rule_breach_rate'])} | "
                         f"{_pct(r['filter_rate'])} | {_pct(r['start_miss_rate'])} |")
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--guard", required=True)
    ap.add_argument("--strike", required=True)
    ap.add_argument("--sizes")
    ap.add_argument("--presets")
    ap.add_argument("--games-per-band", type=int)
    ap.add_argument("--bands", default=",".join(BANDS))
    ap.add_argument("--scenario")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--no-local", action="store_true", help="use the committed neutral values only")
    ap.add_argument("--local-dir", default=str(CONFIGS / "local"))
    ap.add_argument("--game-config", default=str(CONFIGS / "s2_game.toml"))
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)

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
            print(f"refusing: unknown preset {p!r}; use pure and/or starling", file=sys.stderr)
            return 1
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
            "scenario": a.scenario, "argv": sys.argv[1:] if argv is None else argv}
    out.mkdir(parents=True, exist_ok=True)
    (out / "gates.toml").write_text("# Scoring is INFO: no gates (S2 plan, Task 6). Written before the run.\n"
                                    "gates = []\n")
    print(f"game config {meta['game_file']} sha256 {prov.game_sha256}; local file "
          f"{meta['local_file'] or 'not used'}{' sha256 ' + prov.local_sha256 if prov.local_sha256 else ''}",
          flush=True)

    rows: list[dict] = []
    per_game: dict[str, np.ndarray] = {}
    t_all = time.time()
    for preset in presets:
        pcfg = cfg.replace(**{"starling.enabled": preset == "starling"})
        for size in sizes:
            g, s = parse_size(size)
            for b in bands:
                # one batch per band: every Guard x Strike pair on its own slice of n games (the filter's fixed
                # sweep loop costs about the same per step for 1,000 or 10,000 games, so packing saves time)
                pairs = [(gs, ss) for gs in guards for ss in strikes]
                game = SvgGame(pcfg, n * len(pairs), g, s, device=a.device, seed=a.seed + (b or 0), band=b,
                               scenario=sc)
                sl = [slice(j * n, (j + 1) * n) for j in range(len(pairs))]
                guard = SplitStrategy("guard", [(make_strategy(gs, "guard", pcfg, n, a.device, a.seed + 101), sl[j])
                                                for j, (gs, _) in enumerate(pairs)])
                strike = SplitStrategy("strike", [(make_strategy(ss, "strike", pcfg, n, a.device, a.seed + 202),
                                                   sl[j]) for j, (_, ss) in enumerate(pairs)])
                t0 = time.time()
                res_all = play_match(game, guard, strike)
                if a.device.startswith("cuda"):
                    torch.cuda.synchronize()
                dt = time.time() - t0
                game_steps = n * len(pairs) * res_all.steps_played
                where = BANDS[b] if b is not None else a.scenario
                print(f"{preset}|{size}|{where}: {len(pairs)} pairs x {n} games, {res_all.steps_played} steps, "
                      f"{dt:.1f} s, {game_steps / max(dt, 1e-9):,.0f} game-steps/s", flush=True)
                for j, (gs, ss) in enumerate(pairs):
                    res = res_all.slice(sl[j])
                    for r in summarise(res):
                        rows.append({"preset": preset, "size": size, "guard": gs, "strike": ss,
                                     "scenario": a.scenario, **r, "batch_games": n * len(pairs),
                                     "steps_played": res.steps_played, "batch_game_steps": game_steps,
                                     "batch_seconds": dt,
                                     "batch_game_steps_per_s": game_steps / dt if dt > 0 else None})
                    key = f"{preset}|{size}|{gs}|{ss}|{where}"
                    for f in ("outcome", "end_step", "band", "closest_cross_m", "rule_breach",
                              "filter_corrected_rate", "start_miss"):
                        per_game[f"{key}|{f}"] = getattr(res, f).detach().cpu().numpy()
                    print(f"  {gs} v {ss}: hold {rows[-1]['hold_rate']}", flush=True)
    meta["seconds_total"] = time.time() - t_all
    (out / "scores.json").write_text(json.dumps({"meta": meta, "rows": rows}, indent=1))
    (out / "scores.md").write_text(render_md(meta, rows))
    np.savez_compressed(out / "per_game.npz", **per_game)
    print(f"wrote {out / 'scores.json'}, {out / 'scores.md'}, {out / 'per_game.npz'} "
          f"({meta['seconds_total']:.0f} s)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
