"""STE task L0.12c Longer 1.15 m runs (owner approval 21 Nov 2026: Guard 3x, Strike 5x the L0.12 step budget). The two gate
files are L0.12b's except the step budget and the seeds; each cap lets every planned update start with T51/T52's own
timings plus margin; the seeds are new; the task cap holds the runs. Everything on the CPU."""
import math
import re

from svg_training.ste import exploit, sweep
from svg_training.ste.config import load_ste_learning

ROOT = sweep.ROOT
L012B = ROOT / "configs" / "ste_l012b" / "gates.toml"
STRIKE = ROOT / "configs" / "ste_l012c" / "strike_gates.toml"
GUARD = ROOT / "configs" / "ste_l012c" / "guard_gates.toml"
L012B_STEPS = 550_000_000

# Sizing values (upper bounds) from T52 / T51's own logs (tag 1.15 m, laptop RTX 5070 Ti, 21 Nov 2026):
# Strike update means per 10 updates 18.4-22.8 s (max single 23.8), curve reads 51.8-78.6 s, controls batch 106 s;
# Guard updates 20.3-22.5 s, curve reads 2.0-2.1 s, but one stalled game of 256 makes a read ~75 s (QC): K = 75 s.
MEASURED = {"strike": {"update": 23.8, "read": 78.6}, "guard": {"update": 23.1, "read": 2.1}}
SIZING = {"strike": {"update": 25.0, "read": 100.0}, "guard": {"update": 25.0, "read": 75.0}}
BATCH_S, MEASURED_BATCH_S, START_S = 120.0, 106.0, 10.0
CAP_H = {"strike": 4.8, "guard": 2.7}            # --cap-h in the launch commands (run 0 has the Strike run's cap)
L012_USED_GPU_H = 4.96                           # task L0.12 in runs/shared/gpu_hours.log before L0.12c (21 Nov 2026)
RUN0_PASS_GPU_H = 0.5                            # run 0 PASS read by update 50 (L0.12b: update 10, 0.10 GPU-h)


def load(side):
    return exploit.load_gates(STRIKE if side == "strike" else GUARD)


def planned(g):
    tr = g.trainer
    return math.ceil(int(tr["game_steps_per_run"]) / (int(tr["rollouts"]) * int(tr["decision_ticks"]) * int(tr["num_games"])))


def test_the_two_files_are_l012bs_except_the_budget_and_the_seeds():
    old = exploit.load_gates(L012B)
    for side, factor in (("strike", 5), ("guard", 3)):
        new = load(side)
        assert int(new.trainer["game_steps_per_run"]) == factor * L012B_STEPS
        assert {k: v for k, v in new.trainer.items() if k != "game_steps_per_run"} == \
               {k: v for k, v in old.trainer.items() if k != "game_steps_per_run"}
        for part in ("run", "reference", "games", "players", "controls", "verdict", "videos", "pilot"):
            assert getattr(new, part) == getattr(old, part), part
        strip = lambda v: {n: {k: x for k, x in d.items() if k != "train_seed"} for n, d in v.items()}
        assert strip(new.variants) == strip(old.variants)
        assert {k: v for k, v in new.run0.items() if k != "train_seed"} == \
               {k: v for k, v in old.run0.items() if k != "train_seed"}


def test_the_seeds_are_new_and_never_a_scoring_curve_or_clip_seed():
    used = set()
    for path in (ROOT / "configs").glob("ste_l01[0-9]*/*gates.toml"):
        if path.parent.name != "ste_l012c":
            used |= {int(s) for s in re.findall(r"(?:train_seed|seed)\D{0,30}?(\d{6})", path.read_text())}
            used |= {int(s) for s in re.findall(r"(?:strike|guard) = (\d{6})", path.read_text())}
    mine = set()
    for side in ("strike", "guard"):
        g = load(side)
        mine |= {int(s) for v in g.variants.values() for s in v["train_seed"].values()} | {int(g.run0["train_seed"])}
        assert int(g.run["curve_seed"]) not in mine and int(g.run["clip_seed"]) not in mine
    assert {120401, 120402, 120403, 110000, 120900, 120950} <= used        # the scan sees L0.12b's and the scoring seeds
    assert not mine & used and len(mine) == 4


def updates_that_start(cap_s, batch_s, update_s, read_s, every, start_s, reserve_s):
    """The highest update N whose start the driver allows (cap left >= reserve before it): run_exploit's loop."""
    n = 0
    while start_s + batch_s + n * update_s + (n // every) * read_s <= cap_s - reserve_s:
        n += 1
    return n


def test_every_planned_update_starts_inside_the_cap_with_t51_t52_timings_and_margin():
    assert BATCH_S >= MEASURED_BATCH_S
    for side, want in (("strike", 438), ("guard", 263)):
        g = load(side)
        tr = g.trainer
        assert planned(g) == want
        assert SIZING[side]["update"] >= 1.05 * MEASURED[side]["update"]
        assert SIZING[side]["read"] >= 1.2 * MEASURED[side]["read"] and SIZING[side]["read"] >= 75.0
        reserve = exploit.final_reserve_s(tr, BATCH_S)
        assert reserve == 720.0
        fits = updates_that_start(CAP_H[side] * 3600, BATCH_S, SIZING[side]["update"], SIZING[side]["read"],
                                  int(tr["curve_every_updates"]), START_S, reserve)
        assert fits >= planned(g), (side, fits)
        assert f"--cap-h {CAP_H[side]}," in (STRIKE if side == "strike" else GUARD).read_text()
        assert updates_that_start((CAP_H[side] - 0.5) * 3600, BATCH_S, SIZING[side]["update"], SIZING[side]["read"],
                                  int(tr["curve_every_updates"]), START_S, reserve) < planned(g)   # a cap 0.5 h lower would not do: the sizing bites


def test_the_task_cap_holds_the_runs_in_launch_order_and_the_phase_cap_holds():
    cfg = load_ste_learning()[0]
    cap = cfg.budget.cap_gpu_h("L0.12")
    # Guard first (its whole cap), then run 0 (passing by update 50), then the Strike run asks its whole cap.
    assert L012_USED_GPU_H + CAP_H["guard"] + RUN0_PASS_GPU_H + CAP_H["strike"] <= cap
    # run 0 FAIL: it may use the Strike cap, and then no Strike run launches.
    assert L012_USED_GPU_H + CAP_H["guard"] + CAP_H["strike"] <= cap
    assert cfg.budget.task_caps_total_gpu_h() <= cfg.budget.phase_cap_gpu_h
