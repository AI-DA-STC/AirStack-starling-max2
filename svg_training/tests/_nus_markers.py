"""Made-up rule values for tests of the partner-game replica (G4). They are derived from a hash of the key, so no
marker number is typed anywhere; each has six significant digits, which makes a leak easy to find in text. The ranges
only keep the game valid (total cap below every push radius, boundary outside the zone)."""
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
sys.path.insert(0, str(ROOT / "scripts"))

_RANGES = {
    "area_radius": (3.1, 4.3),
    "agent_size": (0.61, 0.89),
    "spawn_distance": (14.1, 18.3),
    "spawn_cluster_radius": (2.1, 3.3),
    "start_guard_disc_fraction": (0.31, 0.62),
    "start_static_guard_ring_fraction": (0.31, 0.62),
    "start_static_strike_cluster_fraction": (0.31, 0.62),
    "guard_max_speed": (0.31, 0.49),
    "strike_max_speed": (0.51, 0.79),
    "guard_safety_distance": (0.71, 0.99),
    "strike_safety_distance": (0.31, 0.59),
    "push_gain": (0.61, 0.99),
    "push_smoothing_margin": (0.011, 0.019),
    "total_displacement_cap": (0.81, 0.99),
    "guard_boundary_radius": (15.1, 19.9),
    "boundary_margin": (0.081, 0.199),
    "norm_floor": (1.1e-8, 9.9e-8),
    "obs_direction_floor": (1.1e-6, 9.9e-6),
}
_INTS = {"guard_count": 3, "strike_count": 2, "episode_steps": 7}


def _unit(key: str, salt: int) -> float:
    return int(hashlib.sha256(f"{key}/{salt}".encode()).hexdigest()[:8], 16) / 16**8


def marker_value(key: str) -> float:
    lo, hi = _RANGES[key]
    for salt in range(100):
        v = float(f"{lo + (hi - lo) * _unit(key, salt):.6g}")
        if len(f"{v:.6g}".replace(".", "").replace("e-0", "").strip("0")) >= 6:
            return v
    raise RuntimeError(key)


def marker_rules(random_start: bool = True) -> dict:
    values = {k: marker_value(k) for k in _RANGES}
    values.update(_INTS)
    values["random_start"] = random_start
    return values


def marker_strings(values: dict) -> list[str]:
    """Text forms of the float markers, as a file could show them."""
    out = []
    for v in values.values():
        if isinstance(v, float):
            out += [repr(v), f"{v:.6g}", f"{v:.6g}".replace("e-0", "e-")]
    return sorted(set(out))


def write_toml(path: Path, values: dict) -> None:
    lines = []
    for k, v in values.items():
        lines.append(f"{k} = {str(v).lower() if isinstance(v, bool) else repr(v)}")
    Path(path).write_text("\n".join(lines) + "\n")
