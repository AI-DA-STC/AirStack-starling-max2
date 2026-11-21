"""How a Starling is drawn in Isaac Lab videos (STE tasks L0.4 and L0.5; owner decision D9: videos show the Starling as it
looks in the AirStack simulator). Pure Python and NumPy: a *look plan* says which meshes of the Starling USD get a
display colour and which visual-only markers are added; ``compat/isaaclab_232`` applies it to the stage.

Looks (``LOOKS``):

* ``"painted"``: today's S2b clip look (S2b Task 6): the body mesh dark grey, the four rotor meshes in the team colour,
  a team ball of radius ``marker_radius_m`` above the drone. Kept bit for bit (tests/test_starling_look.py).
* ``"own_ring"``: the Starling USD untouched (no display colour is written, so it renders exactly as the file carries
  it, as the AirStack simulator spawns it) plus a thin team-coloured ring around the drone at arm height.
* ``"own_dot"``: the Starling untouched plus a small team-coloured disc on its top plate.

Colours are sRGB in 0..1 (as on screen). Positions are metres in the drone's body frame (FLU, x to the nose).
Nothing here reaches a game, a drone model or a measurement. The settings file is ``configs/ste_video.toml``.
"""
from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
SETTINGS_FILE = ROOT / "configs" / "ste_video.toml"
LOOKS = ("painted", "own_ring", "own_dot")
STARLING_MESHES = ("body", "rotor0", "rotor1", "rotor2", "rotor3")        # /vehicle/<name>/<name> in starling2max.usd
STARLING_ROTORS_FLU_M = ((0.095, -0.13), (-0.095, 0.13), (0.095, 0.13), (-0.095, -0.13))   # CAD layout (PX4 order)
DRONE_BODY_RGB = (0.22, 0.22, 0.24)          # the S2b clips' body colour (S2b Task 6)
PAINTED_MARKER_LIFT_M = 0.12                 # the S2b ball sits this far above the body origin, plus its radius

_KEYS = {
    "look": {"replay_look", "own_ring", "own_dot", "tag_circle"},
    "look.own_ring": {"major_radius_m", "minor_radius_m", "z_m", "segments", "tube_segments"},
    "look.own_dot": {"diameter_m", "thickness_m", "z_m"},
    "look.tag_circle": {"minor_radius_m", "segments", "tube_segments", "lighten"},
    "arena": {"zone_segments"},
    "cameras": {"resolution", "top_tilt_deg", "perspective_view"},
    "playback": {"speed_x", "hold_s", "gif_max_mb", "mp4_max_mb", "warm_frames", "settle_frames"},
    "key_games": {"record", "run_folder", "gates_sha256", "variants", "outcomes"},
    "trained_games": {"record", "gates_sha256", "runs"},
}


def load_video_settings(path: str | Path = SETTINGS_FILE) -> dict:
    """The settings file as a dict; KeyError names any unknown or missing key or section."""
    data = tomllib.loads(Path(path).read_text())
    for name, keys in _KEYS.items():
        table = data
        for part in name.split("."):
            if part not in table:
                raise KeyError(f"{path}: missing section [{name}]")
            table = table[part]
        have = set(table)
        if have - keys:
            raise KeyError(f"{path}: [{name}] has unknown keys {sorted(have - keys)}")
        if keys - have:
            raise KeyError(f"{path}: [{name}] is missing {sorted(keys - have)}")
    top = set(data) - {n.split(".")[0] for n in _KEYS}
    if top:
        raise KeyError(f"{path}: unknown sections {sorted(top)}")
    if data["look"]["replay_look"] not in LOOKS:
        raise ValueError(f"replay_look must be one of {LOOKS}")
    return data


@dataclass(frozen=True)
class Marker:
    """A visual-only shape under the drone: kind "sphere" (size (diameter,) * 3), "cyl" (diameter, diameter, height)
    or "torus" (major radius, tube radius, 0); xyz_m its centre in the body frame; rgb its colour; casts_shadow False:
    the renderer draws no shadow of it (a ring's shadow on the floor would read as another drone)."""
    kind: str
    size_m: tuple
    xyz_m: tuple
    rgb: tuple
    casts_shadow: bool = True
    segments: tuple | None = None     # torus: (around the ring, around the tube); None = the caller's default


@dataclass(frozen=True)
class LookPlan:
    """paint: mesh name -> display colour (empty = the USD's own surfaces); markers: the shapes added."""
    look: str
    paint: dict
    markers: tuple


def look_plan(look: str, team_rgb: tuple, marker_radius_m: float | None = None,
              settings: dict | None = None, tag_radius_m: float | None = None) -> LookPlan:
    """The plan of one drone. "painted" needs marker_radius_m (the S2b ball); the own looks need the settings.
    tag_radius_m (Guard drones only; owner request 21 Nov 2026): add a faint circle of that radius around the drone at
    its own height ([look.tag_circle]); None = no circle, the plan exactly as before."""
    plan = _base_plan(look, team_rgb, marker_radius_m, settings)
    if tag_radius_m is None:
        return plan
    if settings is None:
        raise ValueError("a tag circle needs the video settings")
    tc = settings["look"]["tag_circle"]
    f = float(tc["lighten"])
    faint = tuple(float(c) + (1.0 - float(c)) * f for c in team_rgb)
    circle = Marker("torus", (float(tag_radius_m), float(tc["minor_radius_m"]), 0.0), (0.0, 0.0, 0.0), faint,
                    casts_shadow=False, segments=(int(tc["segments"]), int(tc["tube_segments"])))
    return LookPlan(plan.look, plan.paint, plan.markers + (circle,))


def _base_plan(look: str, team_rgb: tuple, marker_radius_m: float | None, settings: dict | None) -> LookPlan:
    rgb = tuple(team_rgb)
    if look == "painted":
        if marker_radius_m is None:
            raise ValueError('look "painted" needs marker_radius_m')
        r = float(marker_radius_m)
        paint = {name: (DRONE_BODY_RGB if name == "body" else rgb) for name in STARLING_MESHES}
        return LookPlan(look, paint, (Marker("sphere", (2 * r,) * 3, (0.0, 0.0, PAINTED_MARKER_LIFT_M + r), rgb),))
    if look not in LOOKS:
        raise ValueError(f"look must be one of {LOOKS}, got {look!r}")
    if settings is None:
        raise ValueError(f"look {look!r} needs the video settings")
    if look == "own_ring":
        s = settings["look"]["own_ring"]
        m = Marker("torus", (float(s["major_radius_m"]), float(s["minor_radius_m"]), 0.0), (0.0, 0.0, float(s["z_m"])),
                   rgb, casts_shadow=False)
    else:
        s = settings["look"]["own_dot"]
        d = float(s["diameter_m"])
        m = Marker("cyl", (d, d, float(s["thickness_m"])), (0.0, 0.0, float(s["z_m"])), rgb, casts_shadow=False)
    return LookPlan(look, {}, (m,))


def torus_mesh(major_radius_m: float, minor_radius_m: float, segments: int, tube_segments: int
               ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """A closed quad torus around the z axis, centred at the origin. Returns points [P, 3] (P = segments x
    tube_segments), face vertex counts [F] (all 4) and face vertex indices [4F], outward-facing."""
    if not 0 < minor_radius_m < major_radius_m:
        raise ValueError("need 0 < minor_radius_m < major_radius_m")
    if segments < 3 or tube_segments < 3:
        raise ValueError("need at least 3 segments each way")
    u = np.linspace(0.0, 2 * np.pi, segments, endpoint=False)
    v = np.linspace(0.0, 2 * np.pi, tube_segments, endpoint=False)
    uu, vv = np.meshgrid(u, v, indexing="ij")                                   # [S, T]
    ring = major_radius_m + minor_radius_m * np.cos(vv)
    pts = np.stack((ring * np.cos(uu), ring * np.sin(uu), minor_radius_m * np.sin(vv)), axis=-1).reshape(-1, 3)
    i, j = np.meshgrid(np.arange(segments), np.arange(tube_segments), indexing="ij")
    i1, j1 = (i + 1) % segments, (j + 1) % tube_segments
    a, b, c, d = i * tube_segments + j, i1 * tube_segments + j, i1 * tube_segments + j1, i * tube_segments + j1
    idx = np.stack((a, b, c, d), axis=-1).reshape(-1)
    counts = np.full(segments * tube_segments, 4, dtype=np.int64)
    return pts, counts, idx.astype(np.int64)


def disc_mesh(radius_m: float, height_m: float, segments: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """A closed flat cylinder (a disc of height_m) around the z axis, centred at the origin, with ``segments`` sides:
    points [2 S + 2, 3] (bottom rim, top rim, bottom centre, top centre), face vertex counts and indices (triangles
    on the caps, quads on the side), outward-facing."""
    if segments < 3 or radius_m <= 0 or height_m <= 0:
        raise ValueError("need radius > 0, height > 0 and at least 3 segments")
    a = np.linspace(0.0, 2 * np.pi, segments, endpoint=False)
    h = height_m / 2
    ring = np.stack((radius_m * np.cos(a), radius_m * np.sin(a)), axis=-1)
    pts = np.concatenate((np.c_[ring, np.full(segments, -h)], np.c_[ring, np.full(segments, h)],
                          [[0.0, 0.0, -h], [0.0, 0.0, h]]))
    bc, tc = 2 * segments, 2 * segments + 1
    faces = []
    for i in range(segments):
        j = (i + 1) % segments
        faces.append([i, j, segments + j, segments + i])      # side
        faces.append([tc, segments + i, segments + j])       # top cap
        faces.append([bc, j, i])                             # bottom cap
    counts = np.array([len(f) for f in faces], dtype=np.int64)
    return pts, counts, np.array([v for f in faces for v in f], dtype=np.int64)
