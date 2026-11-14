"""Turn benchmark rows and the config gates into a written record (S0).

Fails closed: a missing measurement is a FAIL, never a silent pass. Standard
library only; nothing here edits the config or changes a gate.
"""

from __future__ import annotations

import math
from statistics import mean

FIRST_LINE = "Simulator: training simulator, tiers 1 and 2 (stand-in drone models, no safety filter)"
BULK_CASE = "t1_5v3_full"


def _expected_points(cfg: dict) -> list[tuple[str, int]]:
    return [(c["name"], n) for key in ("tier1", "tier2") for c in cfg.get(key, []) for n in c["num_games"]]


def _by_point(rows: list[dict]) -> dict[tuple[str, int], list[dict]]:
    out: dict[tuple[str, int], list[dict]] = {}
    for r in rows:
        out.setdefault((r["case"], r["num_games"]), []).append(r)
    return out


MEASURED = ("env_steps_per_s", "drone_steps_per_s", "peak_mem_mb", "nan_count", "mean_reset_fraction")


def _finite(v) -> bool:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return False
    try:
        return math.isfinite(v)
    except OverflowError:  # huge int
        return False


def _field_ok(f: str, v) -> bool:
    if not _finite(v):
        return False
    if f in ("env_steps_per_s", "drone_steps_per_s"):
        return v > 0
    if f == "peak_mem_mb":
        return v >= 0
    if f == "nan_count":
        return v >= 0 and float(v) == int(v)
    return 0 <= v <= 1  # mean_reset_fraction


def _bad_field(r: dict):
    """First measured field of an ok row that is out of range, missing or not finite, else None."""
    for f in MEASURED:
        if not _field_ok(f, r.get(f)):
            return f
    return None


def _ok(rows: list[dict]) -> list[dict]:
    """Valid ok rows only; an ok row with a missing or non-finite measurement does not count."""
    return [r for r in rows if r.get("status") == "ok" and _bad_field(r) is None]


def _distinct(rows: list[dict], key: str) -> list:
    return sorted({r[key] for r in rows if r.get(key) not in (None, "")}, key=str)


def _best(points: dict, names: set[str]):
    """Best mean drone_steps_per_s over points of the named cases with ok rows: (value, case, n) or None."""
    best = None
    for (case, n), rs in points.items():
        ok = _ok(rs)
        if case in names and ok:
            v = mean(r["drone_steps_per_s"] for r in ok)
            if best is None or v > best[0]:
                best = (v, case, n)
    return best


def evaluate(rows: list[dict], cfg: dict, tests_passed: bool) -> dict:
    """Return gates, decisions, missing points and overall PASS or FAIL."""
    repeats = cfg["timing"]["repeats"]
    seen, duplicate_rows, unique = set(), [], []
    for r in rows:
        key = (r["case"], r["num_games"], r.get("repeat"))
        if key in seen:
            if key not in duplicate_rows:
                duplicate_rows.append(key)
            continue
        seen.add(key)
        unique.append(r)
    rows = unique
    points = _by_point(rows)
    invalid_rows = [(r["case"], r["num_games"], r.get("repeat"), _bad_field(r)) for r in rows
                    if r.get("status") == "ok" and _bad_field(r) is not None]
    extra_repeats = [pt for pt, rs in points.items() if len(_ok(rs)) > repeats]
    missing = []
    for pt in _expected_points(cfg):
        rs = points.get(pt, [])
        if not (len(_ok(rs)) >= repeats or any(r.get("status") == "oom" for r in rs)):
            missing.append(pt)

    spreads = []
    for pt, rs in points.items():
        ok = _ok(rs)
        if len(ok) >= 2:
            vals = [r["env_steps_per_s"] for r in ok]
            m = mean(vals)
            spreads.append(((max(vals) - min(vals)) / m if m else float("inf"), pt))
    worst = max(spreads, key=lambda x: x[0]) if spreads else None
    spread = worst[0] if worst else None
    oom_order = sorted((case, n) for (case, n), rs in points.items()
                       if any(r.get("status") == "oom" for r in rs)
                       and any(c == case and n2 > n and _ok(rs2) for (c, n2), rs2 in points.items()))
    nan_total = sum(r["nan_count"] for rs in points.values() for r in _ok(rs))
    g = cfg["gates"]
    gates = {
        "tests_pass": {"limit": g["tests_pass"], "observed": bool(tests_passed),
                       "pass": bool(tests_passed)},
        "sweep_complete": {"limit": g["sweep_complete"], "observed": f"{len(missing)} missing, {len(invalid_rows)} invalid, "
                                       f"{len(duplicate_rows)} duplicate",
                           "pass": not missing and not invalid_rows and not duplicate_rows},
        "repeat_spread_max": {"limit": g["repeat_spread_max"], "observed": spread,
                              "point": worst[1] if worst else None,
                              "pass": spread is not None and spread <= g["repeat_spread_max"]},
        "nan_count_max": {"limit": g["nan_count_max"], "observed": nan_total,
                          "pass": nan_total <= g["nan_count_max"]},
    }

    d = cfg["decisions"]
    t1 = _best(points, {BULK_CASE})
    t2 = _best(points, {c["name"] for c in cfg.get("tier2", [])})
    lim1, lim2 = d["tier1_bulk_min_drone_steps_per_s"], d["tier2_train_min_drone_steps_per_s"]
    decisions = {
        "tier1_bulk": {"observed": t1[0] if t1 else None, "limit": lim1,
                       "at_num_games": t1[2] if t1 else None, "meets": bool(t1 and t1[0] >= lim1)},
        "tier2_train": {"observed": t2[0] if t2 else None, "limit": lim2, "case": t2[1] if t2 else None,
                        "at_num_games": t2[2] if t2 else None, "meets": bool(t2 and t2[0] >= lim2)},
        "budget_drone_steps": d["budget_drone_steps"],
        "budget_gpu_hours": (d["budget_drone_steps"] / t1[0] / 3600) if t1 and t1[0] > 0 else None,
    }
    overall = "PASS" if all(x["pass"] for x in gates.values()) else "FAIL"
    return {"gates": gates, "decisions": decisions, "missing": missing, "invalid_rows": invalid_rows, "duplicate_rows": duplicate_rows,
            "oom_order": oom_order, "extra_repeats": extra_repeats, "overall": overall}


def _f0(x) -> str:
    return "-" if x is None else f"{x:,.0f}"


def _fv(x) -> str:
    if x is None:
        return "none"
    if isinstance(x, bool):
        return str(x).lower()
    if isinstance(x, float):
        return f"{x:.3g}"
    return str(x)


def _mem_of(r: dict, key: str):
    """Tier 1: torch peak memory; tier 2: device-wide GPU memory used (None when the row lacks it)."""
    v = r.get("gpu_mem_used_mb") if key == "tier2" else r.get("peak_mem_mb")
    return v if _finite(v) else None


def _table(rows: list[dict], cfg: dict, key: str) -> list[str]:
    points = _by_point(rows)
    mem_head = "GPU memory used (device-wide) (MB)" if key == "tier2" else "Peak memory (MB)"
    lines = ["| Case | Games | Drones per game | Environment steps per second | "
             f"Drone-steps per second | {mem_head} | Resets per step (%) | Status |", "|---|---|---|---|---|---|---|---|"]
    for c in cfg.get(key, []):
        for n in c["num_games"]:
            rs = points.get((c["name"], n), [])
            ok = _ok(rs)
            m = c["drones_per_game"] if key == "tier2" else c["guards"] + c["strikes"]
            if ok:
                status = f"ok ({len(ok)} of {cfg['timing']['repeats']})"
                lines.append(f"| {c['name']} | {n:,} | {m} | {_f0(mean(r['env_steps_per_s'] for r in ok))} | "
                             f"{_f0(mean(r['drone_steps_per_s'] for r in ok))} | "
                             f"{_f0(mean(mems)) if (mems := [x for x in (_mem_of(r, key) for r in ok) if x is not None]) else '-'} | "
                             f"{100 * mean(r['mean_reset_fraction'] for r in ok):.1f} | {status} |")
            else:
                status = ("oom" if any(r.get("status") == "oom" for r in rs) else
                          "invalid" if any(r.get("status") == "ok" for r in rs) else
                          "crash" if rs else "MISSING")
                lines.append(f"| {c['name']} | {n:,} | {m} | - | - | - | - | {status} |")
    return lines


def render_record(rows: list[dict], cfg: dict, verdict: dict, meta: dict) -> str:
    """Markdown record: first line names the simulator (STANDARDS §8)."""
    date = meta.get("date", "")
    name = meta.get("name", "")
    gpus = _distinct(rows, "gpu_name") or [meta.get("gpu") or "unknown"]
    commits = _distinct(rows, "commit") or [meta.get("commit") or "unknown"]
    shas = _distinct(rows, "code_sha") or ["unknown"]
    seed_vals = _distinct(rows, "seed")
    seeds = meta.get("seeds", "NOT GIVEN")
    if seed_vals:
        seeds += f"\n\nSeed values found in the rows: {', '.join(str(x) for x in seed_vals)}"
    warn = ["WARNING: rows from more than one GPU", ""] if len(gpus) > 1 else []
    if len(commits) > 1:
        warn += ["WARNING: rows from more than one commit", ""]
    if len(shas) > 1:
        warn += ["WARNING: rows from more than one code version", ""]
    cfg_path = meta.get("config_path", "configs/s0_benchmark.toml")
    cfg_line = f"`{cfg_path}`" + (f", sha256 `{meta['config_sha256']}`" if meta.get("config_sha256") else "")
    t = cfg["timing"]
    L = [FIRST_LINE, "", f"# {name if name.startswith(date) else f'{date} {name}'.strip()} record", "",
         ] + warn + ["## Purpose", "",
         "Measure how fast the training simulator runs, in tier 1 (batched game model) and tier 2 "
         "(Isaac Lab physics), over the cases and numbers of games in the config. Overall result: "
         f"**{verdict['overall']}**.", "",
         "## Commit", "", 'repository commit (svg_training/ is tracked; "-dirty" = uncommitted changes under '
         'svg_training/ at the start of the run): '
         + ", ".join(f"`{c}`" for c in commits), "",
         "## Code version", "", "code_sha (first 12 hex of a sha256 over the files under source/, scripts/ and "
         "configs/): " + ", ".join(f"`{c}`" for c in shas), "",
         "## Config", "", cfg_line,
         f"Timing: {t['warmup_steps']} warm-up steps and at least 2 s; timed window at least {t['timed_steps']} steps "
         f"and at least {t.get('min_timed_s', 0)} s; {t['repeats']} repeats.", "",
         "## Model parameter set", "", "placeholder", "",
         "## Seeds", "", seeds, "",
         "## Machine", "", f"- Machine: {meta.get('machine', 'unknown')}", f"- GPU: {', '.join(gpus)}", "",
         "## Throughput", "",
         "Mean of the repeats. Environment steps per second = games x policy steps per second.", "",
         "### Tier 1 — MEASURED", ""] + _table(rows, cfg, "tier1") + ["", "### Tier 2 (ARL Robot 1 airframe) — MEASURED", ""] \
        + _table(rows, cfg, "tier2") + ["", "## Gates", "",
                                        f"Limits: FIXED (approved config, sha256 {meta.get('config_sha256') or 'not given'}). "
                                        "Observed values: MEASURED.", "",
                                        "| Gate | Limit | Observed | Result |", "|---|---|---|---|"]
    for k, gt in verdict["gates"].items():
        obs = _fv(gt["observed"])
        if gt.get("point"):
            obs += f" (worst: {gt['point'][0]} at {gt['point'][1]:,} games)"
        L.append(f"| {k} | {_fv(gt['limit'])} | {obs} | {'PASS' if gt['pass'] else 'FAIL'} |")
    if meta.get("note"):
        L.insert(L.index("## Gates") + 2, f"Note: {meta['note']}")
        L.insert(L.index("## Gates") + 3, "")
    if meta.get("retried_points"):
        L += ["", "Retried once after an Isaac Sim start-up crash: "
              + ", ".join(f"{c} {n}" for c, n in meta["retried_points"])]
    short = [r for r in _ok(rows) if isinstance(r.get("timed_s"), (int, float)) and not isinstance(r["timed_s"], bool)
             and r["timed_s"] < 0.8 * t.get("min_timed_s", 0)]
    if short:
        L.append("")
        L += [f"short timed window: {r['case']} {r['num_games']} repeat {r['repeat']} ({r['timed_s']:.2f} s)"
              for r in short]
    if verdict.get("oom_order"):
        L += ["", "Unexpected out-of-memory order (out of memory at this size while a larger size of the same case "
              "is ok): " + ", ".join(f"{c} at {n:,} games" for c, n in verdict["oom_order"])]
    if meta.get("overflow_points"):
        L += ["", "PhysX buffer overflow logged: numbers for these points are not trustworthy: "
              + ", ".join(f"{c} at {n:,} games" for c, n in meta["overflow_points"])]
    if verdict.get("invalid_rows"):
        L += ["", "Invalid rows (status ok but a measurement is missing or not finite): "
              + ", ".join(f"{c} at {n:,} games, repeat {rp}, field {f}" for c, n, rp, f in verdict["invalid_rows"])]
    if verdict.get("duplicate_rows"):
        L += ["", "Duplicate rows (same case, games and repeat; later ones not counted): "
              + ", ".join(f"{c} at {n:,} games, repeat {rp}" for c, n, rp in verdict["duplicate_rows"])]
    if verdict.get("extra_repeats"):
        L += ["", "Extra repeats (more ok rows than `[timing].repeats`; not a failure): "
              + ", ".join(f"{c} at {n:,} games" for c, n in verdict["extra_repeats"])]
    if verdict["missing"]:
        L += ["", "Missing points (no complete measurement): "
              + ", ".join(f"{c} at {n:,} games" for c, n in verdict["missing"])]
    d = verdict["decisions"]
    b, t2 = d["tier1_bulk"], d["tier2_train"]
    L += ["", "## Decision rules", "",
          "PROPOSED rules read off MEASURED numbers; not pass or fail.", "",
          f"- Tier 1 bulk training (case {BULK_CASE}): best {_f0(b['observed'])} drone-steps per second "
          f"at {_fv(b['at_num_games'])} games, rule is at least {_f0(b['limit'])}: "
          f"{'meets' if b['meets'] else 'does not meet' if b['observed'] is not None else 'not measured'}.",
          f"- Tier 2 training (best tier 2 case {_fv(t2['case'])}): best {_f0(t2['observed'])} drone-steps "
          f"per second at {_fv(t2['at_num_games'])} games, rule is at least {_f0(t2['limit'])}: "
          f"{'meets' if t2['meets'] else 'does not meet' if t2['observed'] is not None else 'not measured'}.", "",
          "## Compute budget", ""]
    if d["budget_gpu_hours"] is None:
        L.append(f"No observation of {BULK_CASE}, so no GPU-hours estimate (PROPOSED; a lower bound: simulator stepping only).")
    else:
        L.append(f"{d['budget_drone_steps']:,.0f} drone-steps / {_f0(b['observed'])} drone-steps per second "
                 f"(case {BULK_CASE} at {b['at_num_games']:,} games) = {d['budget_gpu_hours']:,.1f} GPU-hours "
                 "(PROPOSED; a lower bound: simulator stepping only).")
    L += ["", "## Limits of this record", "",
          "- Stand-in drone models: tier 1 uses a placeholder lag and delay, tier 2 uses Isaac Lab's "
          "ARL Robot 1 airframe.",
          "- no safety filter in either tier (its port is S1).",
          "- Ray march fixed at 24 steps.",
          "- Throughput includes a per-step finiteness check of every floating-point output.",
          f"- Warm-up is at least {t['warmup_steps']} steps and at least 2 s per repeat.",
          "- No policy network and no learning update are inside the timed step: the compute budget covers "
          "simulator stepping only and is a lower bound on training time.",
          "- The budget assumes the published 2 billion samples are drone-steps; if they are environment steps, "
          "multiply it by the number of drones per game (8 for 5 against 3).",
          "- Tier 2 rewrites every drone's root state on every policy step and has no flight controller.",
          "- Case t2_k8_250hz runs a 20.8 Hz policy (12 steps of 4 ms), not 20 Hz.",
          "- Tier 1 computes respawn candidates for every drone on every step, whether or not a drone is respawned.",
          "- Numbers were observed in the training simulator; nothing here is a flight result.", ""]
    return "\n".join(L)


def ledger_row(n: int, meta: dict, verdict: dict) -> str:
    """One row for records/LEDGER.md, numbered T<n>."""
    name = meta["name"]
    return (f"| T{n} | {meta['date']} | training simulator, tiers 1 and 2 | {name} | S0 throughput sweep | "
            f"{verdict['overall']} | records/{name}_record.md |")
