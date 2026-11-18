"""Checks of the safety filter's CUDA-graph path (``core/safety_filter_graph.py``) on the hangar game of Phase 4 row 5. INFO, no gates of
its own (the equivalence gate is in ``tests/test_safety_filter_graph.py``). Tier 1 (PyTorch; no Isaac Sim); results are observed in the
training simulator. Writes under ``runs/nus_port/filter_graph/`` only (git-ignored, on the 5090 only).

    cd <svg_training>; unset PYTHONPATH; export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
    PYTHONPATH=source ~/miniconda3/envs/env_isaaclab/bin/python scripts/filter_graph_check.py record     # 200 filter states, flag OFF
    ... filter_graph_check.py equiv       # max differences: gate (graph vs existing, same check_every), fixed loop, the reference's spread
    ... filter_graph_check.py calls --games 16384,32768     # one filter call per state, tiled to N games: existing / graph / graph+compact
    ... filter_graph_check.py endtoend    # 64 Phase 4 paired starts, ParkedGuard v S20: OFF, OFF without early stop, ON; game by game

``record``: the P0 probe's set-up (``nus_phase5_probe._context``, its seed, its starts rule) at 1,000 games, arms ``random`` then
``parked_s20``; one game from fresh starts per arm with the flag OFF; the command chain's filter call is recorded (inputs, keywords) at
ticks 0, 2, ..., 198 (100 per arm). ``endtoend``: ``nus/ladder.play_game_pair`` on the first 64 games of the Phase 4 starts file, the same
seed for both runs; compares every per-game field of the two ``MatchResult``s.
"""
from __future__ import annotations

import argparse
import datetime
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
sys.path.insert(0, str(ROOT / "scripts"))

OUT = ROOT / "runs" / "nus_port" / "filter_graph"
STATES = OUT / "states.pt"
RECORD_TICKS = range(0, 200, 2)          # PROPOSED (fixed in the test's docstring before recording)
ARMS = ("random", "parked_s20")
GAMES = 1000
E2E_GAMES = 64


def _now() -> str:
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


# ------------------------------------------------------------------------------------------------ record
def record(args) -> int:
    import torch

    import nus_phase5_probe as P
    from svg_training.nus.hangar_game import NusHangarGame
    from svg_training.nus.players import parks_guard0
    if STATES.exists():
        print(f"refusing: {STATES} exists", file=sys.stderr)
        return 2
    st = P.load_probe()
    ctx = P._context(st)
    dev, seed = args.device, st["seed"]
    states = []
    for arm in ARMS:
        guard, strike = P._players(ctx, st, arm, GAMES, dev, seed)
        start, jitter = P._starts(ctx, GAMES, seed)
        game = NusHangarGame(ctx.cfg, ctx.geo, ctx.row, start, jitter, ctx.guards, ctx.strikes, device=dev, seed=seed,
                             parked=parks_guard0(guard), video_slots=0, rules=ctx.rules)
        chain = game._chain()
        assert chain._filter_fn.__name__ == "filter_velocities" and chain._filter_fn.__module__.endswith("core.safety_filter")
        inner, tick = chain._filter_fn, {"t": 0}

        def rec(nominal, pos, mask, radius, cap, inner=inner, tick=tick, arm=arm, **kw):
            if tick["t"] in RECORD_TICKS:
                states.append({"arm": arm, "tick": tick["t"], "nominal": nominal.detach().clone(), "pos": pos.detach().clone(),
                               "mask": mask.detach().clone(), "radius_m": float(radius), "cap": cap.detach().clone(), "kwargs": dict(kw)})
            return inner(nominal, pos, mask, radius, cap, **kw)
        chain._filter_fn = rec
        obs = game.reset()
        every = torch.ones(GAMES, dtype=torch.bool, device=dev)
        guard.reset(every)
        strike.reset(every)
        t0 = time.perf_counter()
        for t in range(max(RECORD_TICKS) + 1):
            tick["t"] = t
            out = game.step({"guard": guard.act(obs["guard"]), "strike": strike.act(obs["strike"])})
            guard.reset(out.done)
            strike.reset(out.done)
            obs = out.obs
        print(f"{arm}: {max(RECORD_TICKS) + 1} ticks in {time.perf_counter() - t0:.1f} s", flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    meta = {"date": _now(), "games": GAMES, "ticks": list(RECORD_TICKS), "arms": list(ARMS), "seed": seed, "row": st["row"],
            "device": dev, "torch": torch.__version__, "flag": "filter_cuda_graph OFF (existing path)"}
    torch.save({"meta": meta, "states": [{k: (v.cpu() if hasattr(v, "cpu") else v) for k, v in s.items()} for s in states]}, STATES)
    print(f"wrote {len(states)} states to {STATES}")
    return 0


# ------------------------------------------------------------------------------------------------ equiv
def _cmp(a, b) -> dict:
    import torch
    dv = (a.velocities - b.velocities).abs().amax(dim=(1, 2))
    conv = a.converged & b.converged
    return {"max_abs_mps": float(dv.max()), "games_differing": int((dv > 0).sum()), "bit_identical": bool((dv == 0).all()),
            "max_abs_converged_mps": float(dv[conv].max()) if conv.any() else 0.0,
            "max_abs_unconverged_mps": float(dv[~conv].max()) if (~conv).any() else 0.0,
            "unconverged_games": int((~conv).sum()), "games": int(dv.numel()),
            "converged_equal": bool(torch.equal(a.converged, b.converged)), "emergency_equal": bool(torch.equal(a.emergency, b.emergency)),
            "corrected_equal": bool(torch.equal(a.corrected, b.corrected))}


def _merge(rows: list[dict]) -> dict:
    out = {k: max(r[k] for r in rows) for k in ("max_abs_mps", "max_abs_converged_mps", "max_abs_unconverged_mps")}
    out.update({k: sum(r[k] for r in rows) for k in ("games_differing", "unconverged_games", "games")})
    out.update({k: all(r[k] for r in rows) for k in ("bit_identical", "converged_equal", "emergency_equal", "corrected_equal")})
    return out


def _cases(nom, pos, mask, radius, cap, kw):
    from svg_training.core.safety_filter import filter_velocities as F
    from svg_training.core.safety_filter_graph import filter_velocities_graph as G
    kw = dict(kw)
    k = kw.pop("check_every", 0)
    ref = F(nom, pos, mask, radius, cap, check_every=k, **kw)
    fixed = F(nom, pos, mask, radius, cap, check_every=0, **kw)
    graph = G(nom, pos, mask, radius, cap, check_every=k, **kw)
    compact = G(nom, pos, mask, radius, cap, check_every=k, compact=True, **kw)
    return {"gate_graph_vs_existing_same_check_every": _cmp(ref, graph), "graph_vs_existing_fixed_loop": _cmp(fixed, graph),
            "reference_spread_existing_fixed_vs_early_stop": _cmp(fixed, ref), "compact_vs_existing_same_check_every": _cmp(ref, compact)}


def equiv(args) -> int:
    import importlib.util

    import torch
    spec = importlib.util.spec_from_file_location("filter_parity", ROOT / "scripts" / "filter_parity.py")
    fp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fp)
    result = {"date": _now(), "torch": torch.__version__, "gate_max_abs_mps": 1e-6}
    nom, pos, mask, cap = fp._batch(fp.make_scenes(2000, 20261115))
    t8 = {"alpha": 2.5, "iterations": 1000, "tolerance": 2e-3, "check_every": 8}
    for dev in ("cpu", "cuda"):
        result[f"t2_scenes_t8_setting_{dev}"] = _cases(nom.to(dev), pos.to(dev), mask.to(dev), 0.55, cap.to(dev), t8)
    if args.states and STATES.exists():
        data = torch.load(STATES, map_location="cuda", weights_only=False)
        per = {}
        for s in data["states"]:
            for name, row in _cases(s["nominal"], s["pos"], s["mask"], s["radius_m"], s["cap"], s["kwargs"]).items():
                per.setdefault((s["arm"], name), []).append(row)
        result["recorded_states_cuda"] = {f"{arm}/{name}": _merge(rows) for (arm, name), rows in per.items()}
        result["recorded_states_meta"] = data["meta"]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "equiv.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return 0


# ------------------------------------------------------------------------------------------------ calls
def calls(args) -> int:
    import torch

    from svg_training.core.safety_filter import filter_velocities as F
    from svg_training.core.safety_filter_graph import filter_velocities_graph as G
    data = torch.load(STATES, map_location="cuda", weights_only=False)
    picks = [s for s in data["states"] if s["arm"] == args.arm][:: args.stride]
    variants = {"existing": lambda *a, **k: F(*a, **k), "graph": lambda *a, **k: G(*a, **k),
                "graph_compact": lambda *a, **k: G(*a, compact=True, **k),
                "graph_no_early_stop": lambda *a, **k: G(*a, **{**k, "check_every": 0})}
    if args.variants:
        variants = {k: variants[k] for k in args.variants.split(",")}
    out = {"date": _now(), "arm": args.arm, "states": len(picks), "note": "one filter call per recorded state, tiled to N games; "
           "GPU shared with other jobs", "rows": []}
    for n in [int(x) for x in args.games.split(",")]:
        reps = -(-n // GAMES)
        tiled = [{**s, "nominal": s["nominal"].repeat(reps, 1, 1)[:n], "pos": s["pos"].repeat(reps, 1, 1)[:n],
                  "mask": s["mask"].repeat(reps, 1, 1)[:n]} for s in picks]
        for rnd in range(args.rounds):
            for name, fn in variants.items():
                fn(tiled[0]["nominal"], tiled[0]["pos"], tiled[0]["mask"], tiled[0]["radius_m"], tiled[0]["cap"], **tiled[0]["kwargs"])
                torch.cuda.synchronize()
                t0 = time.perf_counter()
                for s in tiled:
                    fn(s["nominal"], s["pos"], s["mask"], s["radius_m"], s["cap"], **s["kwargs"])
                torch.cuda.synchronize()
                sec = (time.perf_counter() - t0) / len(tiled)
                out["rows"].append({"games": n, "variant": name, "round": rnd, "seconds_per_call": sec})
                print(f"{n} games, {name}, round {rnd}: {sec:.4f} s per call", flush=True)
    (OUT / f"calls_{args.arm}.json").write_text(json.dumps(out, indent=2) + "\n")
    return 0


# ------------------------------------------------------------------------------------------------ endtoend
def endtoend(args) -> int:
    import torch

    import nus_phase5_probe as P
    from svg_training.nus import ladder as L
    st = P.load_probe()
    ctx = P._context(st)
    starts = {k: v[:E2E_GAMES] for k, v in L.load_starts(L.STARTS_FILE).items()}
    results, seconds = {}, {}
    order = ("off", "off_fixed_loop", "on") if not args.max_steps else ("off",)
    for label in order:
        cfg = ctx.cfg.replace(**{"starling.filter_cuda_graph": label == "on"})
        if label == "off_fixed_loop":      # the existing path without its early stop (check_every 0): what ON reproduces bit for bit
            cfg = cfg.replace(**{"starling.filter_check_every": 0})
        if args.max_steps:      # cost estimate only: a few ticks
            from svg_training.core.play import play_match
            from svg_training.nus.hangar_game import NusHangarGame
            from svg_training.nus.players import make_player, parks_guard0
            g = make_player(st["guard"], "guard", cfg, E2E_GAMES, args.device, st["seed"])
            s = make_player(st["strike"], "strike", cfg, E2E_GAMES, args.device, st["seed"])
            game = NusHangarGame(cfg, ctx.geo, ctx.row, starts["starts_units"], starts["jitter_m"], ctx.guards, ctx.strikes, device=args.device,
                                 seed=st["seed"], parked=parks_guard0(g), video_slots=0, rules=ctx.rules)
            t0 = time.perf_counter()
            play_match(game, g, s, max_steps=args.max_steps)
            if torch.device(args.device).type == "cuda":
                torch.cuda.synchronize()
            dt = time.perf_counter() - t0
            print(f"{label}: {args.max_steps} ticks in {dt:.1f} s; the game is {ctx.geo.game_ticks} ticks at most "
                  f"(at most {dt / args.max_steps * ctx.geo.game_ticks:.0f} s)")
            return 0
        res, _, _, sec = L.play_game_pair(cfg, ctx.geo, ctx.row, starts, st["guard"], st["strike"], ctx.guards, ctx.strikes, args.device,
                                          st["seed"], 0, rules=ctx.rules)
        results[label], seconds[label] = res, sec
        print(f"{label}: {sec:.1f} s, {res.steps_played} ticks", flush=True)
    def compare(a, b) -> dict:
        fields = {}
        for k in a.__dataclass_fields__:
            x, y = getattr(a, k), getattr(b, k)
            if isinstance(x, torch.Tensor) and x.dim() >= 1 and x.shape[0] == E2E_GAMES:
                same = (x == y) if x.dtype == torch.bool or not x.is_floating_point() else ((x == y) | (x.isnan() & y.isnan()))
                same = same.reshape(E2E_GAMES, -1).all(dim=1)
                fields[k] = {"games_differing": int((~same).sum()),
                             "max_abs": float((x.double() - y.double()).abs().nan_to_num(0.0).max()) if x.is_floating_point() else None}
        return {"outcome_games_differing": fields.get("outcome", {}).get("games_differing"), "fields": fields}
    out = {"date": _now(), "device": args.device, "games": E2E_GAMES, "guard": st["guard"], "strike": st["strike"], "row": st["row"],
           "seed": st["seed"], "seconds": seconds, "ticks": {k: results[k].steps_played for k in results},
           "on_vs_off": compare(results["off"], results["on"]), "on_vs_off_fixed_loop": compare(results["off_fixed_loop"], results["on"]),
           "off_fixed_loop_vs_off": compare(results["off"], results["off_fixed_loop"]),
           "outcomes": {k: results[k].outcome.tolist() for k in results}}
    (OUT / f"endtoend_{torch.device(args.device).type}.json").write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps({k: v for k, v in out.items() if k != "outcomes"}, indent=2))
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("record", "equiv", "calls", "endtoend"):
        q = sub.add_parser(name)
        q.add_argument("--device", default="cuda")
        if name == "calls":
            q.add_argument("--games", default="1000,16384,32768")
            q.add_argument("--arm", default="parked_s20", choices=ARMS)
            q.add_argument("--stride", type=int, default=10)
            q.add_argument("--rounds", type=int, default=2)
            q.add_argument("--variants", help="comma list of variants (default: all)")
        if name == "equiv":
            q.add_argument("--states", action="store_true", help="also the 200 recorded states (four filter calls each; about 0.2 GPU-h shared)")
        if name == "endtoend":
            q.add_argument("--max-steps", type=int, default=0, help="cost estimate: play only this many ticks with the flag OFF")
    args = p.parse_args(argv)
    return {"record": record, "equiv": equiv, "calls": calls, "endtoend": endtoend}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
