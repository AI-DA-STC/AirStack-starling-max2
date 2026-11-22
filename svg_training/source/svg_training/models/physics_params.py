"""Tier 2 physics drone parameters: the rigid-body Starling's airframe and the drone's own PX4 1.14 gains.

PyTorch-free, frozen dataclasses, SI units. Read from a parameter file written by
``scripts/make_physics_params.py`` (``params/starling_physics_v0.toml``): the gains are copied from the drone's
parameter file and never tuned; the airframe is CMU's system identification (``../docs/CONFIG.md`` "Inertials").
``load_physics_params`` returns the drone's values only. Sim-only values are applied after it, from a separate file
that says SIM-ONLY (``apply_sim_only_gains``, owner's ruling of 16 November 2026: the yaw-rate gains), or from the
pre-written fallback (``apply_rate_gain_fallback``); each records itself in ``PhysicsParams.source``.

Frames: rotor positions are (x, y) in PX4's body frame FRD (x forward, y right), PX4 rotor order 0..3; inertia is
the diagonal (roll, pitch, yaw) about the centre of mass.

STE track L1.1 and L1.2 add optional [model] keys (``EFFECT_KEYS``), each 0 by default so that a file without them
(``params/starling_physics_v0.toml``) flies exactly as before: ``state_delay_s`` and ``state_noise_*`` (what PX4's
cascade sees: ``models/estimator_effect.py``) and ``drag_*`` (a linear body drag, ``models/starling_airframe.py``).
"""
from __future__ import annotations

import dataclasses
import hashlib
import math
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]          # svg_training/
G_MPS2: float = 9.81
TICK_S: float = 0.05                                # the game tick (core.game_config.TICK_S)
ROTOR_GEOMETRIES: tuple[str, ...] = ("cad", "params")
# STE L1.1 / L1.2: optional effects, all 0 by default (off = the physics drone of S2b, bit for bit). Units in the name.
EFFECT_KEYS: tuple[str, ...] = (
    "state_delay_s",              # the cascade sees position, velocity and attitude this much late (whole physics steps)
    "state_noise_pos_m",          # standard deviation of Gaussian noise per axis on what the cascade sees, per step
    "state_noise_vel_mps",
    "state_noise_att_rad",        # a small random rotation (body frame) per step, per axis
    "state_noise_rate_rad_s",     # body rates (from the gyro in PX4: noisy, never delayed)
    "drag_x_n_per_mps",           # linear drag, body FLU axes: F_b = -diag(d_x, d_y, d_z) v_b (Pegasus's simple drag)
    "drag_y_n_per_mps",
    "drag_z_n_per_mps")
OVERRIDABLE: tuple[str, ...] = ("physics_dt_s", "rotor_geometry", "motor_lag", "setpoint_delay_s") + EFFECT_KEYS
IGNORED_OVERRIDES: tuple[str, ...] = ("params", "fallback_physics_dt_s")   # other keys of configs/s2b.toml [physics]


@dataclass(frozen=True)
class AirframeParams:
    """The rigid-body Starling. f_max_n() = k_f * omega_max^2; hover_u() = rotor command that holds the weight."""
    mass_kg: float
    inertia_kgm2: tuple[float, float, float]                 # roll, pitch, yaw (FRD axes)
    k_f: float                                               # N / (rad/s)^2
    k_m: float                                               # N m / (rad/s)^2
    omega_max_rad_s: float
    tau_up_s: float                                          # first-order rotor-speed lag, speeding up
    tau_down_s: float                                        # slowing down
    rotor_xy_cad_m: tuple[tuple[float, float], ...]          # 4 x (x, y) FRD, PX4 rotor order 0..3 (CMU CAD)
    rotor_xy_params_m: tuple[tuple[float, float], ...]       # the drone's CA_ROTOR*_PX/PY
    rotor_km: tuple[float, float, float, float]              # the drone's CA_ROTOR*_KM (sign = spin)

    def f_max_n(self) -> float:
        """Full thrust of one rotor in newtons."""
        return self.k_f * self.omega_max_rad_s ** 2

    def hover_u(self) -> float:
        """Rotor thrust command (fraction of f_max) at which four rotors hold the weight."""
        return self.mass_kg * G_MPS2 / 4.0 / self.f_max_n()


@dataclass(frozen=True)
class Px4Gains:
    """The drone's PX4 1.14 parameters the cascade uses. Field = PX4 name in lower case; value as in the drone's file.

    Units as PX4 stores them (degrees and deg/s for tilt and rate limits, Hz for filters, metres for rotor arms).
    """
    mpc_xy_p: float
    mpc_z_p: float
    mpc_xy_vel_p_acc: float
    mpc_xy_vel_i_acc: float
    mpc_xy_vel_d_acc: float
    mpc_z_vel_p_acc: float
    mpc_z_vel_i_acc: float
    mpc_z_vel_d_acc: float
    mpc_veld_lp: float
    mpc_xy_vel_max: float
    mpc_z_vel_max_up: float
    mpc_z_vel_max_dn: float
    mpc_tiltmax_air: float
    mpc_thr_hover: float
    mpc_thr_min: float
    mpc_thr_max: float
    mpc_thr_xy_marg: float
    mc_roll_p: float
    mc_pitch_p: float
    mc_yaw_p: float
    mc_yaw_weight: float
    mc_rollrate_p: float
    mc_rollrate_i: float
    mc_rollrate_d: float
    mc_pitchrate_p: float
    mc_pitchrate_i: float
    mc_pitchrate_d: float
    mc_yawrate_p: float
    mc_yawrate_i: float
    mc_yawrate_d: float
    mc_rollrate_k: float
    mc_pitchrate_k: float
    mc_yawrate_k: float
    mc_rollrate_ff: float
    mc_pitchrate_ff: float
    mc_yawrate_ff: float
    mc_rollrate_max: float
    mc_pitchrate_max: float
    mc_yawrate_max: float
    mc_rr_int_lim: float
    mc_pr_int_lim: float
    mc_yr_int_lim: float
    mc_yaw_cutoff: float          # yaw torque low-pass, Hz (ModalAI's PX4 1.14 fork; px4_cascade note C)
    imu_dgyro_cutoff: float
    imu_gyro_ratemax: float
    mc_airmode: float
    ca_rotor0_px: float
    ca_rotor0_py: float
    ca_rotor1_px: float
    ca_rotor1_py: float
    ca_rotor2_px: float
    ca_rotor2_py: float
    ca_rotor3_px: float
    ca_rotor3_py: float
    ca_rotor0_km: float
    ca_rotor1_km: float
    ca_rotor2_km: float
    ca_rotor3_km: float


GAIN_NAMES: tuple[str, ...] = tuple(f.name.upper() for f in dataclasses.fields(Px4Gains))


@dataclass(frozen=True)
class PhysicsParams:
    """Airframe + gains + backend settings. ``source`` = the parameter file's [source] table (provenance)."""
    airframe: AirframeParams
    gains: Px4Gains
    physics_dt_s: float
    rotor_geometry: str                                      # "cad" | "params": plant rotor positions (D4)
    motor_lag: bool                                          # D5
    setpoint_delay_s: float                                  # D7
    upset_tilt_deg: float = 60.0                             # D10
    source: dict = field(default_factory=dict)
    state_delay_s: float = 0.0                               # EFFECT_KEYS (L1.1, L1.2): 0 = off
    state_noise_pos_m: float = 0.0
    state_noise_vel_mps: float = 0.0
    state_noise_att_rad: float = 0.0
    state_noise_rate_rad_s: float = 0.0
    drag_x_n_per_mps: float = 0.0
    drag_y_n_per_mps: float = 0.0
    drag_z_n_per_mps: float = 0.0

    def state_delay_steps(self) -> int:
        """The state delay in whole physics steps: ``state_delay_s / physics_dt_s`` rounded to the nearest (a fitted
        delay is rarely a multiple of the 5 ms step; 0.1482 s -> 30 steps = 0.150 s)."""
        return round(self.state_delay_s / self.physics_dt_s)

    def __post_init__(self) -> None:
        for key in EFFECT_KEYS:
            val = getattr(self, key)
            if isinstance(val, bool) or not isinstance(val, (int, float)) or not math.isfinite(val) or val < 0:
                raise ValueError(f"{key} must be a finite number >= 0, got {val!r}")
        if self.rotor_geometry not in ROTOR_GEOMETRIES:
            raise ValueError(f"rotor_geometry must be one of {ROTOR_GEOMETRIES}, got {self.rotor_geometry!r}")
        n = TICK_S / self.physics_dt_s if self.physics_dt_s > 0 else 0.0
        if self.physics_dt_s <= 0 or abs(n - round(n)) > 1e-9:
            raise ValueError(f"physics_dt_s must divide the {TICK_S} s game tick, got {self.physics_dt_s}")
        if self.setpoint_delay_s < 0:
            raise ValueError(f"setpoint_delay_s must be >= 0, got {self.setpoint_delay_s}")
        if not isinstance(self.motor_lag, bool):
            raise ValueError(f"motor_lag must be true or false, got {self.motor_lag!r}")


def _pairs(v: Any) -> tuple[tuple[float, float], ...]:
    return tuple((float(x), float(y)) for x, y in v)


def load_physics_params(path: str | Path, overrides: dict | None = None) -> PhysicsParams:
    """Read a physics parameter file (absolute, or relative to svg_training/).

    ``overrides`` is typically the [physics] table of configs/s2b.toml: it may set physics_dt_s, rotor_geometry,
    motor_lag, setpoint_delay_s and the ``EFFECT_KEYS`` (its ``params`` and ``fallback_physics_dt_s`` keys are ignored). Gains and the
    airframe cannot be overridden; any other key raises ValueError.
    """
    p = Path(path)
    p = p if p.is_absolute() else ROOT / p
    data = tomllib.loads(p.read_text())
    unknown = sorted(set(data) - {"source", "gains", "airframe", "model"})
    if unknown:
        raise ValueError(f"unknown section(s) in {p.name}: {unknown}")

    g = data["gains"]
    names = {f.name for f in dataclasses.fields(Px4Gains)}
    if set(g) != names:
        raise ValueError(f"[gains] of {p.name}: missing {sorted(names - set(g))}, unknown {sorted(set(g) - names)}")
    gains = Px4Gains(**{k: float(v) for k, v in g.items()})

    a = dict(data["airframe"])
    a_names = {f.name for f in dataclasses.fields(AirframeParams)} - {"rotor_xy_params_m", "rotor_km"}
    if set(a) != a_names:
        raise ValueError(f"[airframe] of {p.name}: missing {sorted(a_names - set(a))}, "
                         f"unknown {sorted(set(a) - a_names)}")
    airframe = AirframeParams(
        mass_kg=float(a["mass_kg"]), inertia_kgm2=tuple(float(x) for x in a["inertia_kgm2"]),
        k_f=float(a["k_f"]), k_m=float(a["k_m"]), omega_max_rad_s=float(a["omega_max_rad_s"]),
        tau_up_s=float(a["tau_up_s"]), tau_down_s=float(a["tau_down_s"]),
        rotor_xy_cad_m=_pairs(a["rotor_xy_cad_m"]),
        # PX4's allocation geometry is the drone's own CA_ROTOR* parameters, taken from [gains] (one source)
        rotor_xy_params_m=tuple((getattr(gains, f"ca_rotor{i}_px"), getattr(gains, f"ca_rotor{i}_py"))
                                for i in range(4)),
        rotor_km=tuple(getattr(gains, f"ca_rotor{i}_km") for i in range(4)))
    if len(airframe.inertia_kgm2) != 3 or len(airframe.rotor_xy_cad_m) != 4:
        raise ValueError(f"[airframe] of {p.name}: inertia needs 3 values and rotor_xy_cad_m 4 rotors")

    model = dict(data.get("model", {}))
    for key, val in (overrides or {}).items():
        if key in IGNORED_OVERRIDES:
            continue
        if key not in OVERRIDABLE:
            raise ValueError(f"unknown override {key!r} (allowed: {OVERRIDABLE})")
        model[key] = val
    bad = sorted(set(model) - set(OVERRIDABLE) - {"upset_tilt_deg"})
    if bad:
        raise ValueError(f"unknown key(s) in [model] of {p.name}: {bad}")
    return PhysicsParams(airframe=airframe, gains=gains, physics_dt_s=float(model["physics_dt_s"]),
                         rotor_geometry=str(model["rotor_geometry"]), motor_lag=model["motor_lag"],
                         setpoint_delay_s=float(model["setpoint_delay_s"]),
                         upset_tilt_deg=float(model.get("upset_tilt_deg", 60.0)), source=dict(data.get("source", {})),
                         **{k: _number(model[k]) for k in EFFECT_KEYS if k in model})


def _number(v: Any) -> Any:
    """A TOML number as float; anything else is passed on unchanged so that PhysicsParams refuses it by name."""
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else v


DEFAULT_SIM_ONLY_GAINS: str = "params/sim_only_yaw_v0.toml"   # = core.game_config.StarlingLayerCfg default
SIM_ONLY_GAIN_NAMES: tuple[str, ...] = ("mc_yawrate_p", "mc_yawrate_i", "mc_yawrate_d")   # the owner's ruling
SIM_ONLY_HEADER: str = "# SIM-ONLY"                    # first line of every sim-only override file
DRONE_GAINS_SOURCE: str = "the drone's own gains (no sim-only override)"


def apply_sim_only_gains(params: PhysicsParams, path: str | Path | None) -> PhysicsParams:
    """Owner's ruling of 16 November 2026: the physics drone flies the AirStack simulator's SIM-ONLY yaw-rate gains.

    ``path`` is a sim-only override file (``params/sim_only_yaw_v0.toml``; absolute or relative to svg_training/)
    or None / "" for the drone's own gains. The file must start with "# SIM-ONLY", carry a [sim_only] ``label``
    that says SIM-ONLY, and set only the yaw-rate P / I / D (``SIM_ONLY_GAIN_NAMES``); anything else raises
    ValueError. Roll and pitch gains, the yaw torque filter and the motor lag stay the drone's. Either way the
    result's ``source["yaw_rate_gains"]`` says which gains are in use (file, sha256 and label, or the drone's own),
    so records and TensorBoard can quote it. The result is never a drone value (iron rule 9).
    """
    if not path:
        return dataclasses.replace(params, source={**params.source, "yaw_rate_gains": DRONE_GAINS_SOURCE})
    p = Path(path)
    p = p if p.is_absolute() else ROOT / p
    raw = p.read_bytes()
    text = raw.decode()
    if not text.startswith(SIM_ONLY_HEADER):
        raise ValueError(f"{p.name}: a sim-only override file must start with {SIM_ONLY_HEADER!r}")
    data = tomllib.loads(text)
    if sorted(data) != ["gains", "sim_only"]:
        raise ValueError(f"{p.name}: needs exactly the sections [sim_only] and [gains], got {sorted(data)}")
    label = str(data["sim_only"].get("label", ""))
    if "SIM-ONLY" not in label:
        raise ValueError(f"{p.name}: the [sim_only] label must say SIM-ONLY")
    bad = sorted(set(data["gains"]) - set(SIM_ONLY_GAIN_NAMES))
    if bad:
        raise ValueError(f"{p.name}: only {SIM_ONLY_GAIN_NAMES} may be overridden, got {bad}")
    gains = dataclasses.replace(params.gains, **{k: float(v) for k, v in data["gains"].items()})
    try:
        rel = str(p.resolve().relative_to(ROOT))
    except ValueError:
        rel = str(p)
    entry = {"file": rel, "sha256": hashlib.sha256(raw).hexdigest(), "label": label,
             "gains": {k: float(v) for k, v in data["gains"].items()}}
    return dataclasses.replace(params, gains=gains, source={**params.source, "yaw_rate_gains": entry})


def load_physics_drone_params(path: str | Path, overrides: dict | None = None,
                              sim_only_gains: str | Path | None = DEFAULT_SIM_ONLY_GAINS) -> PhysicsParams:
    """The physics drone's parameters as the game flies them: ``load_physics_params`` (the drone's values), then
    ``apply_sim_only_gains`` (default: the owner's SIM-ONLY yaw-rate gains; None or "" = the drone's own gains).
    Scripts use this so that they fly the same drone as ``core.physics_layer.load_game_physics_params``."""
    return apply_sim_only_gains(load_physics_params(path, overrides), sim_only_gains)


def yaw_gains_text(params: PhysicsParams) -> str:
    """One line for records and logs: which yaw-rate gains ``params`` carries (see ``apply_sim_only_gains``)."""
    y = params.source.get("yaw_rate_gains")
    g = params.gains
    pid = f"yaw-rate P/I/D {g.mc_yawrate_p:g}/{g.mc_yawrate_i:g}/{g.mc_yawrate_d:g}"
    if isinstance(y, dict):
        return f"{y['label']} ({y['file']}, sha256 {y['sha256'][:12]}): {pid}"
    return f"{y or DRONE_GAINS_SOURCE}: {pid}"


def apply_rate_gain_fallback(params: PhysicsParams, fallback: dict) -> PhysicsParams:
    """The owner's one pre-written fallback (16 Nov 2026, answer 3): scale the listed rate gains, label it SIM-ONLY.

    ``fallback`` is the [fallback_rate_gains] table of configs/s2b.toml (``rate_gain_scale``, ``gains``, ``label``).
    Used only if Task 3's design check finds the real gains unstable; the result is never a drone value (iron rule 9).
    """
    scale = float(fallback["rate_gain_scale"])
    names = {f.name for f in dataclasses.fields(Px4Gains)}
    bad = sorted(set(fallback["gains"]) - names)
    if bad:
        raise ValueError(f"unknown gain(s) in the fallback: {bad}")
    if "SIM-ONLY" not in fallback["label"]:
        raise ValueError("the fallback label must say SIM-ONLY")
    gains = dataclasses.replace(params.gains, **{n: getattr(params.gains, n) * scale for n in fallback["gains"]})
    return dataclasses.replace(params, gains=gains, source={**params.source, "fallback": fallback["label"]})
