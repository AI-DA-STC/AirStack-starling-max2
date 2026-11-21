"""VID-1 / L0.4 / L0.5: scripts/make_ste_3d.py with a stand-in for the Isaac module (CPU only; no Isaac).

The stand-in records every call and returns a plain image per render, so the script's own logic is checked: what is
spawned with which look, that the replay moves the drones as the trajectory says (and hides drones that are out), one
raw frame per tick per camera, the stills and their labels, and the encode outputs (MP4, GIF under its cap, README
captions <= 400 characters)."""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
from pathlib import Path

import numpy as np
import pytest

from svg_training.core.rewards import GUARD_WIN
from svg_training.viz import replay3d as r3
from svg_training.viz.starling_look import SETTINGS_FILE

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("make_ste_3d", ROOT / "scripts" / "make_ste_3d.py")
m3 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m3)


class FakeIsaac:
    ISAAC_WORLD_LABEL = "stand-in"

    def __init__(self):
        self.calls, self.drones, self.poses, self.visible, self.renders = [], {}, {}, {}, 0

    def make_display_sim(self, device):
        return "sim"

    def spawn_world_lights(self, sun=True):
        self.calls.append("lights")

    def spawn_floor(self):
        self.calls.append("floor")

    def spawn_display_arena(self, root, half, zone_xy, zone_r, margin, top, floor=True, zone_segments=None):
        self.calls.append(("arena", half, zone_r, zone_segments))

    def spawn_display_drone(self, path, usd, plan, segments=(48, 8)):
        assert usd.endswith("starling2max.usd")
        self.drones[path] = plan

    def set_display_pose(self, path, xyz, yaw, visible=True):
        self.poses.setdefault(path, []).append((tuple(np.round(xyz, 6)), round(yaw, 6), visible))
        self.visible[path] = visible

    def set_visible(self, path, visible):
        self.visible[path] = visible

    def display_play(self, sim):
        self.calls.append("play")

    def make_recorder(self, sim, eye, look, res):
        w, h = res
        fake = self

        def frame():
            fake.renders += 1
            img = np.zeros((h, w, 3), np.uint8)
            img[:, :, 1] = fake.renders % 200
            return img
        frame.set_view = lambda e, lk: fake.calls.append(("view", tuple(e), tuple(lk)))
        return frame


def _traj(tmp_path, name="base_hold", end=6) -> Path:
    t = end + 1
    pos = np.zeros((t, 6, 3), np.float32)
    pos[:, :, 2] = 1.2
    pos[:, :, 0] = np.linspace(-2, 2, 6)[None]
    pos[:, 3:, 1] = np.linspace(2.5, 1.0, t)[:, None]
    alive = np.ones((t, 6), bool)
    alive[4:, 3] = False                               # Strike drone 3 tagged at tick 4
    tr = r3.Trajectory(pos, np.zeros((t, 6), np.float32), alive, 3, 3, 3.25, 0.25, (0.5, 1.8),
                       np.zeros(2), 1.6, 1.6, GUARD_WIN, end,
                       {"variant": "base", "guard": "guard_mark_edge", "strike": "strike_straight",
                        "outcome_name": "hold", "game_index": 0, "record": "T44", "tags": 3})
    return r3.save_trajectory(tmp_path / "trajectories" / name, tr)


def _args(tmp_path, **kw):
    a = dict(work=str(tmp_path / "work"), settings=str(SETTINGS_FILE), stills=False, replay=[], arena_frame=None,
             encode=False, smoke=False, media=str(tmp_path / "media"))
    a.update(kw)
    return argparse.Namespace(**a)


def test_replay_moves_drones_as_the_trajectory_and_hides_tagged(tmp_path):
    p = _traj(tmp_path)
    fake = FakeIsaac()
    assert m3.render(_args(tmp_path, replay=[str(p)]), fake) == 0
    look = "own_ring"
    paths = [f"/World/Drones_{look}_tag160cm/Drone_{i}" for i in range(6)]   # the game's 1.6 m tag circles
    assert set(paths) <= set(fake.drones) and all(fake.drones[q].paint == {} for q in paths)
    # per camera: one place before warm-up + one per tick; positions as the file, drone 3 hidden from tick 4
    poses = fake.poses[paths[3]]
    assert len(poses) == 2 * (1 + 7)
    assert [v for _, _, v in poses[1:8]] == [True] * 4 + [False] * 3
    assert poses[1][0][1] == pytest.approx(2.5) and poses[1][0][2] == pytest.approx(1.2)   # tick 0 as the file
    import imageio.v2 as imageio
    for cam in ("top", "3d"):
        rd = imageio.get_reader(str(tmp_path / "work" / "render" / "base_hold" / f"raw_{cam}.mp4"))
        assert rd.count_frames() == 7
        rd.close()
    meta = json.loads((tmp_path / "work" / "render_meta.json").read_text())
    assert meta["replays"][0]["frames"] == 7 and set(meta["replays"][0]["cameras"]) == {"top", "3d"}


def test_stills_spawn_every_look_and_label_inside_the_image(tmp_path):
    p = _traj(tmp_path)
    fake = FakeIsaac()
    assert m3.render(_args(tmp_path, stills=True, arena_frame=str(p)), fake) == 0
    meta = json.loads((tmp_path / "work" / "render_meta.json").read_text())
    names = {s["file"] for s in meta["stills"]}
    assert {"row_l04_close.png", "row_l04_top.png", "row_l05_close.png", "row_l05_top.png"} <= names
    assert {f"arena_{lk}_{c}.png" for lk in ("painted", "own_ring", "own_dot") for c in ("top", "3d")} <= names
    for s in meta["stills"]:
        for _, (x, y) in s.get("labels", []):
            assert 0 <= x <= 1280 and 0 <= y <= 720
    # row L0.4: the file untouched first, then today's paint (body dark grey) without and with the ball
    plans = [fake.drones[f"/World/Row_l04/Drone_{i}"] for i in range(4)]
    assert plans[0].paint == {} and plans[0].markers == ()
    assert plans[1].paint["body"] == (0.22, 0.22, 0.24) and plans[1].markers == ()
    assert plans[2].markers[0].kind == "sphere" and plans[3].paint["rotor0"] != plans[2].paint["rotor0"]


def test_encode_writes_clips_stills_and_short_captions(tmp_path):
    p = _traj(tmp_path)
    fake = FakeIsaac()
    m3.render(_args(tmp_path, stills=True, replay=[str(p)], arena_frame=str(p)), fake)
    assert m3.encode(_args(tmp_path, encode=True)) == 0
    d3 = tmp_path / "media" / "ste_l011" / "3d"
    for cam in ("top", "3d"):
        assert (d3 / f"base_hold_{cam}.mp4").stat().st_size > 0
        assert 0 < (d3 / f"base_hold_{cam}.gif").stat().st_size <= 5e6
    readme = (d3 / "README.md").read_text()
    assert "Training simulator" in readme and "not a flight" in readme.lower()
    rows = [ln for ln in readme.splitlines() if ln.startswith("| base")]
    assert len(rows) == 1
    cap = rows[0].split("|")[-2].strip()
    assert len(cap) <= 400 and 2 <= len(re.findall(r"[.:]\s", cap + " ")) and "Training simulator" in cap
    for d in ("ste_l04", "ste_l05"):
        md = (tmp_path / "media" / d / "README.md").read_text()
        assert "starling2max.usd" in md and "Not compared" in md and "not verified in its window" in md
        for cap in re.findall(r"^\*\*[^*]+\*\* (.+)$", md, flags=re.M):
            assert len(cap) <= 400
    assert (tmp_path / "media" / "ste_l05" / "arena_own_ring_top.png").is_file()


def test_encode_marks_tagged_drones_and_counts(tmp_path):
    """The held last frame shows a cross where each tagged drone went out (not an empty arena), the README carries
    the cell's counts from the record, and every GIF keeps one frame per tick (its fps is the playback fps)."""
    p = _traj(tmp_path)
    fake = FakeIsaac()
    m3.render(_args(tmp_path, replay=[str(p)]), fake)
    rec = tmp_path / "rec"
    (rec / "cells").mkdir(parents=True)
    import shutil
    shutil.copy(ROOT / "configs" / "ste_l011" / "gates.toml", rec / "gates.toml")   # the pinned gate file
    out = np.full(4 * 1000, 2, np.int8)
    out[:1000][[3, 5]] = 1                                        # cell 0: 998 holds, 2 reaches
    np.savez(rec / "cells" / "base__b00.npz", outcome=out)
    t = r3.load_trajectory(p)
    t.meta.update({"batch": "base/b00", "cell_index": 0, "games_per_cell": 1000})
    r3.save_trajectory(p.with_suffix(""), t)
    a = _args(tmp_path, encode=True)
    a.record_run_dir = str(rec)
    assert m3.encode(a) == 0
    readme = (tmp_path / "media" / "ste_l011" / "3d" / "README.md").read_text()
    assert "998 holds and 2 reaches of 1000" in readme and "1,000 games" not in readme
    (rec / "gates.toml").write_text((rec / "gates.toml").read_text() + "\n# changed\n")
    with pytest.raises(ValueError, match="sha256"):
        m3.encode(a)                                               # counts only from the pinned record
    assert re.search(r"GIF \d+ px wide, 10 frames/s", readme)
    import imageio.v2 as imageio
    last = imageio.imread(str(tmp_path / "work" / "render" / "base_hold" / "overlay_top_last.png"))
    plain = imageio.imread(str(tmp_path / "work" / "render" / "base_hold" / "overlay_top_first.png"))
    assert (np.abs(last.astype(int) - plain.astype(int)).sum(-1) > 60).sum() > 50     # crosses drawn


def test_encode_adds_the_clip_drone_stills(tmp_path):
    import imageio.v2 as imageio

    p = _traj(tmp_path)
    m3.render(_args(tmp_path, stills=True, arena_frame=str(p)), FakeIsaac())
    cd = tmp_path / "clip"
    cd.mkdir()
    for n in ("before_fix", "after_fix"):
        imageio.imwrite(str(cd / f"{n}.png"), np.zeros((720, 1280, 3), np.uint8))
    a = _args(tmp_path, encode=True)
    a.clip_drone_dir = str(cd)
    assert m3.encode(a) == 0
    md = (tmp_path / "media" / "ste_l04" / "README.md").read_text()
    assert "clip_drone_before_fix.png" in md and "clip_drone_after_fix.png" in md and "physics box" in md
    for cap in re.findall(r"^\*\*[^*]+\*\* (.+)$", md, flags=re.M):
        assert len(cap) <= 400


def test_smoke_encodes_nothing(tmp_path):
    p = _traj(tmp_path)
    m3.render(_args(tmp_path, replay=[str(p)], smoke=True), FakeIsaac())
    assert m3.encode(_args(tmp_path, encode=True)) == 0
    assert not (tmp_path / "media").exists()


def test_arenas_must_match(tmp_path):
    a = _traj(tmp_path, "a")
    t = r3.load_trajectory(a)
    t.half_m = 3.75
    b = r3.save_trajectory(tmp_path / "trajectories" / "b", t)
    with pytest.raises(ValueError, match="different arenas"):
        m3.render(_args(tmp_path, replay=[str(a), str(b)]), FakeIsaac())
    t = r3.load_trajectory(a)
    t.guards, t.strikes = 2, 4                                     # same arena, other team sizes: other drone sets
    c = r3.save_trajectory(tmp_path / "trajectories" / "c", t)
    with pytest.raises(ValueError, match="different arenas"):
        m3.render(_args(tmp_path, replay=[str(a), str(c)]), FakeIsaac())


def test_git_status_takes_no_lock():
    src = (ROOT / "scripts" / "make_ste_3d.py").read_text()
    assert '"--no-optional-locks", "status"' in src


def test_script_refuses_without_work():
    src = (ROOT / "scripts" / "make_ste_3d.py").read_text()
    assert "--approved-headless" in src and "start_headless" in src and "isaaclab_232" in src
    assert not re.search(r"^\s*(import|from) isaaclab(\.|\s)", src, flags=re.M)   # Isaac only through compat



# ------------------------------------------------------------------------------------------------ VID-1b
def test_guards_carry_the_games_tag_circle_and_the_zone_is_a_true_circle(tmp_path):
    a = _traj(tmp_path, "a")
    t = r3.load_trajectory(a)
    t.tag_radius_m = 1.4
    b = r3.save_trajectory(tmp_path / "trajectories" / "b", t)
    fake = FakeIsaac()
    assert m3.render(_args(tmp_path, replay=[str(a), str(b)]), fake) == 0
    arena = [c for c in fake.calls if isinstance(c, tuple) and c[0] == "arena"]
    assert arena and arena[0][3] == m3.load_video_settings()["arena"]["zone_segments"]
    radii = {}
    for path, plan in fake.drones.items():
        circles = [mk for mk in plan.markers if mk.kind == "torus" and mk.size_m[0] > 1.0]
        drone = int(path.rsplit("_", 1)[1])
        if drone < 3:
            assert len(circles) == 1
            radii.setdefault(path.split("/")[2], set()).add(circles[0].size_m[0])
        else:
            assert circles == []                                       # Strike drones: no tag circle
    assert sorted(r for s in radii.values() for r in s) == [1.4, 1.6]     # one drone set per tag radius


def _trained_traj(tmp_path) -> Path:
    p = _traj(tmp_path, "l012_base_strike")
    t = r3.load_trajectory(p)
    t.outcome = 1
    t.meta = {"kind": "trained", "variant": "base", "side": "strike", "run": "2026-11-21_ste_l012_base_strike",
              "record": "T46", "guard": "guard_mark_edge", "strike": "trained Strike team", "outcome_name": "reach",
              "game_index": 17, "games_per_cell": 1000, "cell_index": 0, "tags": 1,
              "cell_counts": {"games": 1000, "holds": 556, "reaches": 444}}
    return r3.save_trajectory(p.with_suffix(""), t)


def test_trained_clips_go_to_their_folder_with_their_wording(tmp_path):
    p = _trained_traj(tmp_path)
    m3.render(_args(tmp_path, replay=[str(p)]), FakeIsaac())
    a = _args(tmp_path, encode=True)
    a.clip_dir = "ste_l012/3d"
    assert m3.encode(a) == 0
    d = tmp_path / "media" / "ste_l012" / "3d"
    assert (d / "l012_base_strike_top.gif").is_file() and (d / "l012_base_strike_3d.mp4").is_file()
    readme = (d / "README.md").read_text()
    assert "L0.12" in readme and "T46" in readme and "556 holds and 444 reaches of 1000" in readme
    assert "tag" in readme.lower() and "circle" in readme.lower()
    row = [ln for ln in readme.splitlines() if ln.startswith("| base")][0]
    cap = row.split("|")[-2].strip()
    assert len(cap) <= 400 and "Trained Strike team" in cap and "not a flight" in cap
    assert "L0.12" in r3.caption("base", 0.5, source="the L0.12 evaluation")


def test_gif_full_rate_steps_down_in_width_when_a_width_cannot_fit(monkeypatch, tmp_path):
    """A width where no setting fits the cap raises in encode_gif: the next narrower width is tried, keeping every frame;
    only if none keeps every frame does the encoder's own fallback (fewer frames per second) run."""
    calls = []

    def fake(frames, path, fps=10, max_mb=5.0, src_fps=20, speed=1.0, widths=(800,)):
        calls.append(widths)
        if widths and widths[0] >= 720:
            raise RuntimeError("no GIF setting fits")
        return path, {"width": widths[0], "fps": fps, "colours": 128, "speed": 1.0}
    import svg_training.bench.overlay as ov
    monkeypatch.setattr(ov, "encode_gif", fake)
    _, gi = m3.gif_full_rate([np.zeros((8, 8, 3), np.uint8)], tmp_path / "a.gif", 10, 5.0)
    assert gi["width"] == 640 and gi["fps"] == 10 and calls[:3] == [(800,), (720,), (640,)]
