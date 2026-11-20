"""A tiny gate file for the L0.11 driver's CPU tests and the end-to-end drill: the committed gate file with every
section kept and the cells cut down (a few games, a few ticks, one cell per batch). It pins the committed game files
with their real sha256 (read from the committed gate file), so the driver's checks run exactly as in the sweep."""
from pathlib import Path

from svg_training.ste import sweep

GF, GP = "guard_field", "guard_parked_centre"
SS, SA = "strike_straight", "strike_sacrifice"


def toml_value(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, str):
        return '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'
    if isinstance(v, (list, tuple)):
        return "[" + ", ".join(toml_value(x) for x in v) + "]"
    if isinstance(v, dict):
        return "{ " + ", ".join(f"{k} = {toml_value(x)}" for k, x in v.items()) + " }"
    raise TypeError(type(v))


def smoke_gates(path: Path, run: dict | None = None, games: dict | None = None, clips: dict | None = None) -> Path:
    g = sweep.load_gates()
    run = {**g.run, **dict(games_per_cell=4, cells_per_batch=1, ticks_cap=6, device="cpu", cap_check_every_ticks=2),
           **(run or {})}
    pinned = {k: {"file": str(sweep.ROOT / v.file), "sha256": v.sha256} for k, v in g.games.items()}
    pinned.update(games or {})
    groups = [
        dict(name="base", role="sweep", factor="base case", level="base", game="base", size="3v3", guards=[GP, GF],
             strikes=[SS]),
        dict(name="ctl_same_seed", role="control", control="same_seed_twice", of_group="base", of_batch=0),
        dict(name="ctl_stand_still", role="control", control="stand_still_never_reaches", game="base", size="3v3",
             guards=[GF], strikes=["zero"]),
        dict(name="ctl_still_3v3", role="control", control="stand_still_zero_tags", game="base", size="3v3",
             guards=["zero"], strikes=["zero"], ticks=3),
        dict(name="ctl_tiny_tag", role="control", control="zero_tags", game="tag_0p05", size="3v3", guards=[GF],
             strikes=[SS]),
        dict(name="ctl_tag_off", role="control", control="zero_tags", game="tag_off", size="3v3", guards=[GF],
             strikes=[SS]),
        dict(name="sens_strike_dz_1mm", role="sensitivity", factor="sensitivity: Strike start height", level="1 mm up",
             game="base", size="3v3", guards=[GF], strikes=[SS], strike_start_dz_m=0.001),
        dict(name="size_1v1", role="sweep", factor="team size", level="1v1", game="base", size="1v1", guards=[GF],
             strikes=[SS, SA]),
        dict(name="tag_1p2", role="sweep", factor="tag radius", level="1.2 m", game="tag_1p2", size="3v3", guards=[GF],
             strikes=[SS]),
    ]
    sections = {
        "run": run, "players": g.players, "confounds": g.confounds,
        "cut": dict(g.cut, protected=["base", "ctl_same_seed", "ctl_stand_still", "ctl_still_3v3", "ctl_tiny_tag", "ctl_tag_off"]),
        "controls": g.controls,
        "shortlist": dict(g.shortlist, candidates=["base", "tag_1p2"], report_only=["size_1v1"]),
        "clips": dict(g.clips, cells=[[GF, SS]], games=2, max_ticks=120, **(clips or {})),
        "pilot": dict(g.pilot, sizes=["1v1", "3v3"], cells_per_batch=[1, 2], ticks=3, warmup_ticks=1),
    }
    lines = []
    for name, table in sections.items():
        lines.append(f"[{name}]")
        lines += [f"{k} = {toml_value(v)}" for k, v in table.items()]
    lines.append("[games]")
    lines += [f"{k} = {toml_value(v)}" for k, v in pinned.items()]
    lines.append("[projection.seconds_per_batch_tick]")
    for grp in groups:
        lines.append("[[groups]]")
        lines += [f"{k} = {toml_value(v)}" for k, v in grp.items()]
    path.write_text("\n".join(lines) + "\n")
    return path
