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
TAG_OPTIONAL_KEYS: tuple[str, ...] = ("radius_m_range",)   # opt-in [tag] keys, absent = off: not in every game file


@dataclass(frozen=True)
class TagCfg:
    """The STE learning track's study tag (task L0.9), ``[tag]`` in a game file; separate from the contact preset's tag.

    ``mode`` "off" (the default) is today's game, bit for bit. "nearest_pair_1for1": a live Guard drone and a live
    Strike drone whose 3-D centres are closer than ``radius_m`` tag each other, one Guard drone with one Strike drone,
    the closest pair first (``core/pair_rules.proximity_tags``); both leave the game on that step, except that the Guard
    drone stays in the games where "Guard survives" was drawn at the game's start with ``guard_survives_tag_prob``.
    The radius 1.6 m is PROPOSED (P1, ruled at gate G0) and the probability 0.0 is D2 (owner, provisional): study runs
    only. The values equal ``configs/ste_game.toml`` ``[tag]`` (a test keeps them equal). A drone that is tagged leaves
    every filter pair at once, unless ``[landing]`` is on (``LandingCfg``, task L2.3).

    ``radius_m_range`` (STE task L1.10; optional, ``TAG_OPTIONAL_KEYS``): absent (None) = the fixed ``radius_m``,
    today's game bit for bit. ``[lo, hi]``: every game draws its own tag radius uniformly in [lo, hi] when it starts,
    from a generator of its own seeded from the game seed (``core/game.py``), and its tag uses that radius;
    ``radius_m`` must lie inside the range (its nominal value). Needs the tag on. The learner does not observe the
    drawn radius.
    """
    mode: str = "off"
    radius_m: float = 1.6
    guard_survives_tag_prob: float = 0.0
    radius_m_range: tuple[float, float] | None = None

    def __post_init__(self) -> None:
        self._check_fixed()
        r = self.radius_m_range
        if r is None:
            return
        if not isinstance(r, (tuple, list)) or len(r) != 2 or \
                any(isinstance(x, bool) or not isinstance(x, (int, float)) for x in r):
            raise ValueError(f"tag.radius_m_range must be two numbers [lo, hi] in metres, got {r!r}")
        lo, hi = float(r[0]), float(r[1])
        if not (math.isfinite(lo) and math.isfinite(hi)):
            raise ValueError(f"tag.radius_m_range must be finite, got {r!r}")
        if not lo > 0.0:
            raise ValueError(f"tag.radius_m_range must be above 0 m, got {r!r}")
        if not lo <= hi:
            raise ValueError(f"tag.radius_m_range must have lo <= hi, got {r!r}")
        if self.mode == "off":
            raise ValueError("tag.radius_m_range needs the tag on (tag.mode); with the tag off it would do nothing")
        if not lo <= self.radius_m <= hi:
            raise ValueError(f"tag.radius_m {self.radius_m!r} must lie inside tag.radius_m_range {r!r} (its nominal "
                             "value)")
        object.__setattr__(self, "radius_m_range", (lo, hi))

    def _check_fixed(self) -> None:
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


COMMANDER_READS: tuple[str, ...] = ("true", "estimate")


@dataclass(frozen=True)
class EstimateErrorCfg:
    """Tier 1's estimate error (STE task L1.7), ``[estimate_error]`` in a game file; absent or ``enabled = false`` = off
    (nothing else is read, today's game bit for bit).

    The same first-order Gauss-Markov error as tier 2's L1.1b (``models/estimator_effect.EstimatorEffect``): per
    quantity and axis, stationary standard deviation sigma and correlation time tau, drawn from the stationary
    distribution at every restart, stepped on the fitted PX4 model's 0.01 s sub-step grid, seeded with the game seed.
    Position (m) and velocity (m/s) only: the fitted model has no attitude state. PX4's feedback (the position and
    velocity errors of the fitted lag1 law) always reads the estimate; the game, tags, walls and scoring read the true
    state. ``commander_reads`` picks what the commander copy and its safety filter read: "true" (as tier 2's
    ``PhysicsLayer`` does since L1.1b, so tier 1 and tier 2 stay comparable) or "estimate" (as on the real drone, whose
    commander reads EKF2's odometry). Values: PROPOSED by L1.3 (T63, EXPLORATORY); 0 here (a sigma of 0 is off).
    Needs the Starling layer on with backend "fitted" (tier 2 has its own, ``state_error_*``)."""
    enabled: bool = False
    pos_sigma_m: float = 0.0
    pos_tau_s: float = 0.0
    vel_sigma_mps: float = 0.0
    vel_tau_s: float = 0.0
    commander_reads: str = "true"

    def __post_init__(self) -> None:
        if not isinstance(self.enabled, bool):
            raise ValueError(f"estimate_error.enabled must be true or false, got {self.enabled!r}")
        if self.commander_reads not in COMMANDER_READS:
            raise ValueError(f"estimate_error.commander_reads must be one of {COMMANDER_READS}, "
                             f"got {self.commander_reads!r}")
        for q, unit in (("pos", "m"), ("vel", "mps")):
            sigma, tau = getattr(self, f"{q}_sigma_{unit}"), getattr(self, f"{q}_tau_s")
            for name, value in ((f"{q}_sigma_{unit}", sigma), (f"{q}_tau_s", tau)):
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) \
                        or value < 0:
                    raise ValueError(f"estimate_error.{name} must be a finite number >= 0 (sigma / tau), got {value!r}")
            if sigma > 0 and tau == 0:
                raise ValueError(f"estimate_error.{q}_sigma_{unit} above 0 needs {q}_tau_s above 0 (the correlation "
                                 "time tau)")

    def error(self) -> dict[str, tuple[float, float]]:
        """{quantity: (sigma, tau_s)} of the quantities switched on (sigma above 0), as ``EstimatorEffect`` takes it;
        empty when off."""
        if not self.enabled:
            return {}
        pairs = {"pos": (self.pos_sigma_m, self.pos_tau_s), "vel": (self.vel_sigma_mps, self.vel_tau_s)}
        return {q: (float(s), float(t)) for q, (s, t) in pairs.items() if s > 0}


@dataclass(frozen=True)
class LandingCfg:
    """Landing drones stay filter obstacles (STE task L2.3), ``[landing]`` in a game file; absent or ``enabled = false``
    = off (nothing else is read, today's game bit for bit: a drone that is tagged or lost is parked at once).

    On: a drone that leaves the game by a tag (the study tag) or a drop-out does not vanish. It descends from where it is
    at ``land_speed_mps`` as an ordinary row of every safety-filter pair, as the flight commander's LANDING state does
    (``swarm_commander.py`` :2086-2087: the nominal command is (0, 0, -land_speed), filtered 50/50, no stick cap or ramp,
    the hold leash, no fence), until its height is at or below ``touchdown_z_m``; then it is parked as an out drone is
    today. While it lands it no longer acts (its action is ignored), tags, is tagged or scores, and the policy sees it as
    out (observation v0.1/v0.2: present 0; v0.3's landing flags are not approved). A drone that leaves through a wall or
    the height band (``walls = "leave"``) is out at once, as today. Needs the Starling layer (either backend) and the
    partner preset (``GameCfg`` refuses the rest). Values, all PROPOSED until the owner rules:

    * ``enabled`` false: off by default (the owner's rule for every new behaviour).
    * ``land_speed_mps`` 0.6: the real ``_ours`` configs' ``land_speed_mps`` (for example
      ``AirStack/robot/ros_ws/src/svg_ground_control/config/goal_two_ours.yaml``: 0.6, "validated 2026-09-03"; the
      commander's own default is 0.3); MEASURED there, PROPOSED as the training value.
    * ``touchdown_z_m`` 0.15: the same configs' ``land_complete_altitude_m`` (ARCHITECTURE proposed 0.1 m); must be
      below the height band's floor.
    """
    enabled: bool = False
    land_speed_mps: float = 0.6
    touchdown_z_m: float = 0.15

    def __post_init__(self) -> None:
        if not isinstance(self.enabled, bool):
            raise ValueError(f"landing.enabled must be true or false, got {self.enabled!r}")
        for name, low_ok in (("land_speed_mps", False), ("touchdown_z_m", True)):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) \
                    or value < 0 or (value == 0 and not low_ok):
                raise ValueError(f"landing.{name} must be a finite number {'>=' if low_ok else '>'} 0, got {value!r}")


FILTER_SHARES: tuple[str, ...] = ("equal", "guard_yields")   # = core/safety_filter.SHARE_MODES (a test keeps them equal)


@dataclass(frozen=True)
class FilterCfg:
    """How the safety filter splits a pair's correction (STE task L2.1, filter option B), ``[filter]`` in a game file;
    absent = ``share = "equal"``, today's filter bit for bit (nothing else is read).

    * ``share`` "equal" (default; MEASURED: the flight filter, ``cbf_filter.py``, splits every pair 50/50): each pair's
      correction is split evenly between its two drones.
    * ``share`` "guard_yields" (option B, PROPOSED, P2 open, ruled by the owner at the L2 gate; no run of record uses it
      before that): in a pair of a live Guard drone and a live Strike drone the Guard drone takes the whole correction and
      the Strike drone's command is left as it is; Guard-Guard and Strike-Strike pairs, and every pair with a landing drone
      (``[landing]``, L2.3), keep the even split. Emergency rule: a game whose option B answer would need the filter's
      emergency action (the Guard drone cannot escape: residual above 5 x tolerance, the filter's own emergency residual)
      takes today's even-split filter that tick, push-apart included (``core/safety_filter.filter_velocities_shared``).
      Needs the Starling layer (the filter runs there) and the partner preset (the contact preset has no Guard-Strike pair).
    """
    share: str = "equal"

    def __post_init__(self) -> None:
        if self.share not in FILTER_SHARES:
            raise ValueError(f"filter.share must be one of {FILTER_SHARES}, got {self.share!r}")


TEAM_SIZE_MODES: tuple[str, ...] = ("fixed", "drawn")


@dataclass(frozen=True)
class TeamSizeCfg:
    """Team size per game (STE task L2.4), ``[team_size]`` in a game file; absent or ``mode = "fixed"`` = today's game bit
    for bit (nothing else is read and nothing is drawn: the team sizes are the game's ``guards`` and ``strikes``).

    ``mode = "drawn"`` (PROPOSED; STANDARDS section 4 lists random team sizes as PROPOSED, P7 decides whether they are part
    of the flown game): the game's ``guards`` and ``strikes`` are slot counts (at least each range's top) and every game,
    when it starts, draws its Guard and Strike counts uniformly from the whole numbers in ``guards_range`` and
    ``strikes_range`` ([lo, hi], both ends included), from a generator of its own seeded from the game seed
    (``core/game.py``). The first g Guard slots and the first s Strike slots are present; the others are absent: out of
    the game from its start (never alive, parked), so they never act, tag, are tagged, score or enter a filter pair, and
    every observation shows them with present 0. Values PROPOSED: 1-5 Guard and 1-3 Strike drones (WORK_BREAKDOWN L2.4;
    the observation's pads 5 + 3), 3v3 the main size (a uniform draw: no weight on it). Drawn sizes need the partner
    preset and starts mode "zone_disc_ring" (the only starts drawn per size so far; ``GameCfg`` refuses the rest)."""
    mode: str = "fixed"
    guards_range: tuple[int, int] = (1, 5)
    strikes_range: tuple[int, int] = (1, 3)

    def __post_init__(self) -> None:
        if self.mode not in TEAM_SIZE_MODES:
            raise ValueError(f"team_size.mode must be one of {TEAM_SIZE_MODES}, got {self.mode!r}")
        for name in ("guards_range", "strikes_range"):
            r = getattr(self, name)
            if not isinstance(r, (tuple, list)) or len(r) != 2 or \
                    any(isinstance(x, bool) or not isinstance(x, int) for x in r):
                raise ValueError(f"team_size.{name} must be two whole numbers [lo, hi], got {r!r}")
            if not 1 <= r[0] <= r[1]:
                raise ValueError(f"team_size.{name} must have 1 <= lo <= hi, got {r!r}")
            object.__setattr__(self, name, (int(r[0]), int(r[1])))


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
    estimate_error: EstimateErrorCfg = field(default_factory=EstimateErrorCfg)
    landing: LandingCfg = field(default_factory=LandingCfg)
    filter: FilterCfg = field(default_factory=FilterCfg)
    team_size: TeamSizeCfg = field(default_factory=TeamSizeCfg)

    def __post_init__(self) -> None:
        """An enabled ``[estimate_error]`` needs the Starling layer with backend "fitted" (else it would do nothing).
        Starts mode "zone_disc_ring" draws round the zone centre in metres from it, so (QC I2, LEAD CALL 21 Nov 2026) it
        is refused unless the zone centre cannot move off the arena centre (``zone_wall_margin_m`` at least the largest
        side x (1/2 - smallest zone-radius fraction), every band) and the Strike ring fits the keep-in box of the smallest
        side (half less ``wall_margin_m``). Other modes are not checked here."""
        if self.estimate_error.enabled and not (self.starling.enabled and self.starling.backend == "fitted"):
            raise ValueError('estimate_error needs the Starling layer on with backend "fitted" (tier 1); the physics '
                             "backend has its own (state_error_* in its parameter file)")
        self._check_landing()
        self._check_filter()
        self._check_team_size()
        if self.starts.mode != "zone_disc_ring":
            return
        a = self.arena
        sides = [s for band in a.bands_m.values() for s in band]
        need_m = max(sides) * (0.5 - min(a.zone_radius_frac))      # either order of the pair (QC re-check N2)
        if need_m > a.zone_wall_margin_m:
            raise ValueError('starts.mode "zone_disc_ring" needs the zone centre pinned at the arena centre: '
                             "arena.zone_wall_margin_m must be at least the largest side x (1/2 - the smallest "
                             f"zone_radius_frac) = {need_m!r} m, got {a.zone_wall_margin_m!r}")
        if self.starts.strike_ring_m > min(sides) / 2 - a.wall_margin_m:
            raise ValueError(f"starts.strike_ring_m = {self.starts.strike_ring_m!r} m does not fit the keep-in box of the "
                             f"smallest arena side ({min(sides) / 2 - a.wall_margin_m!r} m from the centre)")

    def _check_landing(self) -> None:
        """An enabled ``[landing]`` (STE L2.3) needs the Starling layer (the pure rules are planar: nothing descends) and
        the partner preset (the contact preset's filter pairs are team-mates only and it has its own tag), and a
        touchdown height below the height band's floor (a landing drone is exempt from the band)."""
        if not self.landing.enabled:
            return
        if not self.starling.enabled:
            raise ValueError("landing needs the Starling layer on (starling_layer.enabled = true): the pure partner rules "
                             "are planar, so nothing could descend")
        if self.preset != "partner":
            raise ValueError('landing is built for preset "partner" only (the contact preset filters team-mates only)')
        if not self.landing.touchdown_z_m < self.arena.height_band_m[0]:
            raise ValueError(f"landing.touchdown_z_m {self.landing.touchdown_z_m!r} must be below the height band's "
                             f"floor {self.arena.height_band_m[0]!r} m")

    def _check_filter(self) -> None:
        """``[filter] share = "guard_yields"`` (STE L2.1) needs the Starling layer (the only place the filter runs) and the
        partner preset (the contact preset's filter pairs are team-mates only, so the setting would do nothing)."""
        if self.filter.share == "equal":
            return
        if not self.starling.enabled:
            raise ValueError(f"filter.share {self.filter.share!r} needs the Starling layer on (starling_layer.enabled = "
                             "true): the safety filter runs there")
        if self.preset != "partner":
            raise ValueError(f'filter.share {self.filter.share!r} is built for preset "partner" only (the contact preset '
                             "filters team-mates only: no Guard-Strike pair)")

    def _check_team_size(self) -> None:
        """``[team_size] mode = "drawn"`` (STE L2.4) needs each range's top inside the observation's pads (absent slots are
        padding), the partner preset (the contact preset is a side quest: not built) and starts mode "zone_disc_ring"
        (the only starts drawn per team size; ``core/arena.draw_starts_sized``)."""
        ts = self.team_size
        if ts.mode == "fixed":
            return
        if ts.guards_range[1] > self.pad_guards or ts.strikes_range[1] > self.pad_strikes:
            raise ValueError(f"team_size ranges {ts.guards_range!r} / {ts.strikes_range!r} do not fit the pads "
                             f"{self.pad_guards} + {self.pad_strikes}")
        if self.preset != "partner":
            raise ValueError('team_size.mode "drawn" is built for preset "partner" only')
        if self.starts.mode != "zone_disc_ring":
            raise ValueError('team_size.mode "drawn" needs starts.mode "zone_disc_ring" (the only starts drawn per team '
                             f"size), got {self.starts.mode!r}")

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
                    "starling": "starling", "starts": "starts", "rewards": "rewards", "tag": "tag",
                    "estimate_error": "estimate_error", "landing": "landing", "filter": "filter",
                    "team_size": "team_size"}
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
                    "starling_layer": StarlingLayerCfg, "starts": StartsCfg, "rewards": RewardsCfg, "tag": TagCfg,
                    "estimate_error": EstimateErrorCfg, "landing": LandingCfg, "filter": FilterCfg,
                    "team_size": TeamSizeCfg}


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
                  tag=parts["tag"], estimate_error=parts["estimate_error"], landing=parts["landing"],
                  filter=parts["filter"], team_size=parts["team_size"],
                  **{"preset": "partner", **game})
    return cfg, Provenance(str(path), _sha(raw), local_file, local_sha)


def load_s2_gates(path: str | Path = CONFIGS / "s2.toml") -> dict:
    """Load the S2 gates file as a plain dict."""
    return tomllib.loads(Path(path).read_text())


def load_s2b_gates(path: str | Path = CONFIGS / "s2b.toml") -> dict:
    """Load the S2b settings and gates file (owner-approved 16 November 2026) as a plain dict."""
    return tomllib.loads(Path(path).read_text())
