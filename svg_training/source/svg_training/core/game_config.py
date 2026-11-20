"""S2 game configuration: typed, frozen, TOML only. Unknown keys raise; the local partner file may only
override the partner rules and the zone radius (the partner's numbers never enter a committed file)."""
from __future__ import annotations

import dataclasses
import hashlib
import math
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

CONFIGS = Path(__file__).resolve().parents[3] / "configs"
TICK_S: float = 0.05


@dataclass(frozen=True)
class ArenaCfg:
    bands_m: dict[str, tuple[float, float]] = field(default_factory=lambda: {
        "lab": (4.0, 6.0), "middle": (6.0, 10.0), "large": (10.0, 16.0)})
    band_weights: tuple[float, float, float] = (1.0, 1.0, 1.0)
    zone_radius_frac: tuple[float, float] = (0.10, 0.25)
    zone_wall_margin_m: float = 0.5
    height_band_m: tuple[float, float] = (0.5, 1.8)
    start_height_m: float = 1.2
    walls: str = "keep_in"
    wall_margin_m: float = 0.25


@dataclass(frozen=True)
class PartnerRulesCfg:
    keepout_guard_m: float = 1.10
    keepout_strike_m: float = 1.10
    push_rule: str = "block"
    teammates_pass: bool = True
    win_steps_in_zone: int = 1
    strike_units_per_step: float = 0.025
    guard_units_per_step: float = 0.025 / 1.5
    game_steps: int = 1200
    metres_per_unit: float = 1.0
    seconds_per_step: float = 0.05


@dataclass(frozen=True)
class ContactRulesCfg:
    contact_m: float = 0.50
    guard_survives_tag_prob: float = 0.0


TAG_MODES: tuple[str, ...] = ("off", "nearest_pair_1for1")


@dataclass(frozen=True)
class TagCfg:
    """The STE learning track's study tag (task L0.9), ``[tag]`` in a game file; separate from the contact preset's tag.

    ``mode`` "off" (the default) is today's game, bit for bit. "nearest_pair_1for1": a live Guard drone and a live
    Strike drone whose 3-D centres are closer than ``radius_m`` tag each other, one Guard drone with one Strike drone,
    the closest pair first (``core/pair_rules.proximity_tags``); both leave the game on that step, except that the Guard
    drone stays in the games where "Guard survives" was drawn at the game's start with ``guard_survives_tag_prob``.
    The radius 1.6 m is PROPOSED (P1, ruled at gate G0) and the probability 0.0 is D2 (owner, provisional): study runs
    only. The values equal ``configs/ste_game.toml`` ``[tag]`` (a test keeps them equal). A drone that is tagged leaves
    every filter pair at once; landing as a filter obstacle is task L2.3.
    """
    mode: str = "off"
    radius_m: float = 1.6
    guard_survives_tag_prob: float = 0.0

    def __post_init__(self) -> None:
        if self.mode not in TAG_MODES:
            raise ValueError(f"tag.mode must be one of {TAG_MODES}, got {self.mode!r}")
        for name in ("radius_m", "guard_survives_tag_prob"):    # a TOML true would pass as 1 otherwise
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"tag.{name} must be a number, got {value!r}")
        if not (math.isfinite(self.radius_m) and self.radius_m > 0.0):
            raise ValueError(f"tag.radius_m must be a finite distance above 0 m, got {self.radius_m!r}")
        if not 0.0 <= self.guard_survives_tag_prob <= 1.0:     # NaN fails both comparisons
            raise ValueError(f"tag.guard_survives_tag_prob must be in [0, 1], got {self.guard_survives_tag_prob!r}")


BACKENDS: tuple[str, ...] = ("fitted", "physics")


@dataclass(frozen=True)
class StarlingLayerCfg:
    """The Starling layer: the commander copy and the safety filter, then a drone model ("backend").

    backend "fitted" is S2's fitted PX4 response (``params``); "physics" is S2b's rigid-body drone under the PX4 1.14
    cascade (``physics_params``). An unknown backend raises here, so the game never sees one.
    ``physics_sim_only_gains`` (physics only): the SIM-ONLY override file applied over the drone's gains (owner's
    ruling of 16 November 2026: the AirStack simulator's yaw-rate gains, CHG-0024); "" = the drone's own gains.
    ``filter_cuda_graph`` (opt-in, default off): run the safety filter's sweeps as CUDA graphs on a fixed-shape batch
    (``core/safety_filter_graph.py``; same results within the gate of ``tests/test_safety_filter_graph.py``).
    """
    enabled: bool = False
    params: str = "params/real_exploratory_v0.toml"
    filter_iterations: int = 1000
    filter_check_every: int = 0
    filter_cuda_graph: bool = False
    backend: str = "fitted"
    physics_params: str = "params/starling_physics_v0.toml"
    physics_sim_only_gains: str = "params/sim_only_yaw_v0.toml"

    def __post_init__(self) -> None:
        if self.backend not in BACKENDS:
            raise ValueError(f"starling_layer.backend must be one of {BACKENDS}, got {self.backend!r}")


START_MODES: tuple[str, ...] = ("rings", "anywhere", "zone_disc_ring")


@dataclass(frozen=True)
class StartsCfg:
    """Where drones start (``core/arena.draw_starts``). ``mode`` "rings" (the default) and "anywhere" are S2's starts.
    "zone_disc_ring" (STE task L0.10, the hangar game's starts): Guard drones uniform in radius inside ``guard_disc_m`` round
    the zone centre, Strike drones on the circle ``strike_ring_m`` round it, every bearing drawn per drone; the two keys are
    read in that mode only, so the other modes play as before bit for bit. Their defaults equal ``configs/ste_game.toml``
    ``starts.*`` (a test keeps them equal): the Guard disc 0.8 m (hangar game, PROPOSED) and the Strike ring 2.75 m for the
    6.5 m lab arena (LEAD CALL 21 Nov 2026, L08-F1, PROPOSED: the hangar ring scaled by the arena half-side).
    ``team_spacing_margin_m`` (QC fix round 1, LEAD CALL 21 Nov 2026, PROPOSED): team-mates start at least the filter
    distance (the larger keep-out) + this apart in that mode. ``GameCfg`` refuses the mode unless the zone centre is
    pinned at the arena centre and the ring fits the keep-in box in every band (QC I2)."""
    mode: str = "rings"
    strike_inset_m: float = 0.3
    guard_ring_gap_m: float = 0.3
    spacing_m: float = 1.2
    guard_disc_m: float = 0.8
    strike_ring_m: float = 2.75
    team_spacing_margin_m: float = 0.05


@dataclass(frozen=True)
class RewardsCfg:
    win: float = 1.0
    shaping_weight: float = 0.0


@dataclass(frozen=True)
class GameCfg:
    preset: str
    arena: ArenaCfg
    rules: PartnerRulesCfg
    contact: ContactRulesCfg
    starling: StarlingLayerCfg
    starts: StartsCfg
    rewards: RewardsCfg
    dropout_fraction: float = 0.0
    obs_view: str = "full"
    pad_guards: int = 5
    pad_strikes: int = 3
    yaw_rate_max_rad_s: float = 1.0
    tag: TagCfg = field(default_factory=TagCfg)

    def __post_init__(self) -> None:
        """Starts mode "zone_disc_ring" draws round the zone centre in metres from it, so (QC I2, LEAD CALL 21 Nov 2026) it
        is refused unless the zone centre cannot move off the arena centre (``zone_wall_margin_m`` at least the largest
        side x (1/2 - smallest zone-radius fraction), every band) and the Strike ring fits the keep-in box of the smallest
        side (half less ``wall_margin_m``). Other modes are not checked here."""
        if self.starts.mode != "zone_disc_ring":
            return
        a = self.arena
        sides = [s for band in a.bands_m.values() for s in band]
        if max(sides) * (0.5 - a.zone_radius_frac[0]) > a.zone_wall_margin_m:
            raise ValueError('starts.mode "zone_disc_ring" needs the zone centre pinned at the arena centre: '
                             "arena.zone_wall_margin_m must be at least the largest side x (1/2 - the smallest "
                             f"zone_radius_frac) = {max(sides) * (0.5 - a.zone_radius_frac[0])!r} m, got {a.zone_wall_margin_m!r}")
        if self.starts.strike_ring_m > min(sides) / 2 - a.wall_margin_m:
            raise ValueError(f"starts.strike_ring_m = {self.starts.strike_ring_m!r} m does not fit the keep-in box of the "
                             f"smallest arena side ({min(sides) / 2 - a.wall_margin_m!r} m from the centre)")

    def team_speed_mps(self, team: str) -> float:
        """Team speed in m/s = units/step x metres/unit / seconds/step."""
        if team not in ("strike", "guard"):
            raise ValueError(f"team must be 'strike' or 'guard', got {team!r}")
        u = self.rules.strike_units_per_step if team == "strike" else self.rules.guard_units_per_step
        return u * self.rules.metres_per_unit / self.rules.seconds_per_step

    def game_ticks(self) -> int:
        """Game length in simulator ticks of TICK_S seconds."""
        return round(self.rules.game_steps * self.rules.seconds_per_step / TICK_S)

    def replace(self, **dotted: Any) -> "GameCfg":
        """Return a copy with dotted fields changed, e.g. replace(**{"starling.enabled": True})."""
        sections = {"arena": "arena", "rules": "rules", "contact": "contact",
                    "starling": "starling", "starts": "starts", "rewards": "rewards", "tag": "tag"}
        top: dict[str, Any] = {}
        sub: dict[str, dict[str, Any]] = {}
        for key, val in dotted.items():
            if "." in key:
                sec, name = key.split(".", 1)
                if sec not in sections:
                    raise KeyError(f"unknown section {sec!r} in {key!r}")
                if name not in {f.name for f in dataclasses.fields(getattr(self, sec))}:
                    raise KeyError(f"unknown field {key!r}")
                sub.setdefault(sec, {})[name] = val
            else:
                if key not in {f.name for f in dataclasses.fields(self)}:
                    raise KeyError(f"unknown field {key!r}")
                top[key] = val
        for sec, changes in sub.items():
            top[sec] = dataclasses.replace(getattr(self, sec), **changes)
        return dataclasses.replace(self, **top)


@dataclass(frozen=True)
class Provenance:
    game_file: str
    game_sha256: str
    local_file: str | None
    local_sha256: str | None


_PARTNER_KEYS = tuple(f.name for f in dataclasses.fields(PartnerRulesCfg))
LOCAL_ALLOWED: frozenset[str] = frozenset(
    [f"partner_rules.{k}" for k in _PARTNER_KEYS] + ["arena.zone_radius_frac"])

_GAME_KEYS = ("preset", "dropout_fraction", "obs_view", "pad_guards", "pad_strikes", "yaw_rate_max_rad_s")
_SECTION_CLASSES = {"arena": ArenaCfg, "partner_rules": PartnerRulesCfg, "contact_rules": ContactRulesCfg,
                    "starling_layer": StarlingLayerCfg, "starts": StartsCfg, "rewards": RewardsCfg, "tag": TagCfg}


def _tuplify(v: Any) -> Any:
    return tuple(_tuplify(x) for x in v) if isinstance(v, list) else v


def _build(cls: type, table: dict[str, Any], where: str) -> Any:
    names = {f.name for f in dataclasses.fields(cls)}
    bad = sorted(set(table) - names)
    if bad:
        raise ValueError(f"unknown key(s) in [{where}]: {bad}")
    kw = {k: _tuplify(v) for k, v in table.items()}
    if cls is ArenaCfg and "bands_m" in kw:
        kw["bands_m"] = {k: _tuplify(v) for k, v in table["bands_m"].items()}
    return cls(**kw)


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def load_game_cfg(path: str | Path = CONFIGS / "s2_game.toml", local_dir: Path | None = CONFIGS / "local",
                  use_local: bool = True) -> tuple[GameCfg, Provenance]:
    """Load the committed game file, then overlay the git-ignored local partner file if present.

    The local file may set only keys in LOCAL_ALLOWED; anything else raises ValueError.
    """
    path = Path(path)
    raw = path.read_bytes()
    data = tomllib.loads(raw.decode())
    unknown = sorted(set(data) - set(_SECTION_CLASSES) - {"game"})
    if unknown:
        raise ValueError(f"unknown section(s) in {path.name}: {unknown}")

    local_file = local_sha = None
    if use_local and local_dir is not None:
        lp = Path(local_dir) / "partner_rules.toml"
        if lp.is_file():
            lraw = lp.read_bytes()
            ldata = tomllib.loads(lraw.decode())
            for sec, table in ldata.items():
                if not isinstance(table, dict):
                    raise ValueError(f"local key {sec!r} not allowed")
                for key in table:
                    if f"{sec}.{key}" not in LOCAL_ALLOWED:
                        raise ValueError(f"local key '{sec}.{key}' not allowed (allowed: {sorted(LOCAL_ALLOWED)})")
                data.setdefault(sec, {}).update(table)
            local_file, local_sha = str(lp), _sha(lraw)

    game = data.get("game", {})
    bad = sorted(set(game) - set(_GAME_KEYS))
    if bad:
        raise ValueError(f"unknown key(s) in [game]: {bad}")
    parts = {name: _build(cls, data.get(name, {}), name) for name, cls in _SECTION_CLASSES.items()}
    cfg = GameCfg(arena=parts["arena"], rules=parts["partner_rules"], contact=parts["contact_rules"],
                  starling=parts["starling_layer"], starts=parts["starts"], rewards=parts["rewards"],
                  tag=parts["tag"], **{"preset": "partner", **game})
    return cfg, Provenance(str(path), _sha(raw), local_file, local_sha)


def load_s2_gates(path: str | Path = CONFIGS / "s2.toml") -> dict:
    """Load the S2 gates file as a plain dict."""
    return tomllib.loads(Path(path).read_text())


def load_s2b_gates(path: str | Path = CONFIGS / "s2b.toml") -> dict:
    """Load the S2b settings and gates file (owner-approved 16 November 2026) as a plain dict."""
    return tomllib.loads(Path(path).read_text())
