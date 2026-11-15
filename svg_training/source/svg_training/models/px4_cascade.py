"""PX4 1.14 multicopter control cascade, batched: position -> velocity -> acceleration -> attitude -> rates -> rotors.

Ported line by line from PX4-Autopilot tag ``v1.14.0`` (read with ``git -C ~/PX4-Autopilot show v1.14.0:<path>``),
in PX4's own frames: **NED** world, **FRD** body (S2b plan D3; the ENU/FLU crossing is ``models/frames.py``).
Every vector is [N, M, 3] (N games x M drones), every scalar per drone [N, M]. One call of ``Px4Cascade.step`` runs
the whole cascade once per physics step (D6), reading the true state (no estimator, no transport delay; D7).

Sources (v1.14.0), in cascade order
-----------------------------------
1. ``src/modules/mc_pos_control/PositionControl/PositionControl.cpp`` ``_positionControl``:
   ``v_pos = K_p (p_sp - p)``; ``v_sp = v_ff + v_pos``; ``v_sp.xy = constrainXY(v_pos.xy, v_ff.xy, MPC_XY_VEL_MAX)``;
   ``v_sp.z = constrain(v_sp.z, -MPC_Z_VEL_MAX_UP, MPC_Z_VEL_MAX_DN)``.
2. ``_velocityControl``: ``i.z = constrain(i.z, -g, g)``; ``e = v_sp - v``; ``a_sp = a_ff + K_vp e + i - K_vd v_dot``.
   ``v_dot`` is ``MulticopterPositionControl.cpp``'s ``_vel_{x,y,z}_deriv`` (``lib/controllib/BlockDerivative.cpp``:
   the difference quotient, 0 on the first call after a reset, through ``BlockLowPass``: ``a = b / (1 + b)``,
   ``b = 2 pi MPC_VELD_LP dt``).
3. ``_accelerationControl``: ``body_z = normalise(-a_sp.x, -a_sp.y, g)``; ``limitTilt(body_z, (0, 0, 1), tilt)``;
   ``T = (a_sp.z h / g - h) / body_z.z``; ``T = min(T, -thr_min)``; ``thr_sp = body_z T``; ``h = MPC_THR_HOVER``,
   ``thr_min = max(MPC_THR_MIN, 10e-4)`` (``setThrustLimits``).
4. Rest of ``_velocityControl``: the vertical anti-windup, vertical priority with ``MPC_THR_XY_MARG`` under
   ``MPC_THR_MAX``, the horizontal tracking anti-windup (``arw_gain = 2 / K_vp.x``), ``i += e K_vi dt``.
5. ``ControlMath.cpp`` ``thrustToAttitude`` -> ``bodyzToAttitude(-thr_sp, yaw_sp)``; collective ``c = |thr_sp|``.
6. ``src/modules/mc_att_control/AttitudeControl/AttitudeControl.cpp`` ``update`` (reduced attitude, yaw weight),
   with ``setProportionalGain``'s yaw compensation ``K.z = MC_YAW_P / MC_YAW_WEIGHT`` (see note A) and the rate
   limits ``MC_*RATE_MAX`` in rad/s (``mc_att_control_main.cpp`` ``parameters_updated``).
7. ``src/lib/rate_control/rate_control.cpp`` ``update`` / ``updateIntegral`` with the gains of
   ``MulticopterRateControl.cpp`` (``K P``, ``K I``, ``K D``, ``FF``). ``angular_accel`` is
   ``sensors/vehicle_angular_velocity/VehicleAngularVelocity.cpp`` ``FilterAngularAcceleration``: the difference
   quotient of the rate through ``AlphaFilter`` at ``IMU_DGYRO_CUTOFF`` (see note B).
   The allocator's saturation flags are taken as never set (``setSaturationStatus`` is not modelled), and the drone
   is never "landed" (the integrator always runs).
8. ``src/modules/control_allocator/``: effectiveness ``ActuatorEffectivenessRotors::computeEffectivenessMatrix``
   (axis (0, 0, -1), ``moment = CT r x axis - CT KM axis``, ``thrust = CT axis``), ``matrix::geninv``,
   ``ControlAllocationPseudoInverse::updateControlAllocationMatrixScale`` / ``normalizeControlAllocationMatrix``
   (``_normalize_rpy`` true for a multirotor), then ``ControlAllocationSequentialDesaturation::mixAirmodeDisabled``
   (``MC_AIRMODE`` 0) and ``mixYaw``, then ``clipActuatorSetpoint`` to [0, 1]. Trim and linearisation point are 0.

Simplifications (stated, not tuned)
-----------------------------------
- ``u`` is a share of one rotor's full thrust: ``THR_MDL_FAC`` is taken to linearise the motor exactly. (The drone's
  file has ``THR_MDL_FAC`` 0.9; the rotor model of ``models/starling_airframe.py`` maps u to thrust linearly.)
- ``h`` is the fixed ``MPC_THR_HOVER``; the drone runs the hover-thrust estimator (``MPC_USE_HTE`` 1), which would
  move h towards the plant's own hover command (0.16388 against 0.165); the vertical integrator absorbs the gap.
- No takeoff ramp, no tilt-limit slew, no gyro low-pass (``IMU_GYRO_CUTOFF``, D6), no notch filters, no battery
  scaling (``MC_BAT_SCALE_EN`` 0 on the drone), no actuator slew limit.
- Setpoints must be finite (PX4 allows NaN). For the feed-forwards, PX4's NaN acts as 0 (``addIfNotNanVector3f``),
  so pass 0; for velocity-only control pass ``p_sp = pos``.

Note A: the plan's equation for step 6 writes the gain as ``mc_yaw_p``; v1.14.0's ``setProportionalGain`` divides
the yaw gain by the yaw weight ("compensate for the effect of the yaw weight rescaling the output"), so the port
uses 2.8 / 0.4 = 7.0. Note B: the plan calls the D-term filter a second-order Butterworth; in v1.14.0
``VehicleAngularVelocity.hpp`` declares ``AlphaFilter<float> _lp_filter_acceleration[3]`` (first order,
``alpha = dt / (dt + 1 / (2 pi f_c))``, ``AlphaFilter::setCutoffFreq``), and the port follows the source.

Nothing in ``Px4Cascade.step`` / ``rate_step`` / ``allocate`` reads a tensor on the host; constants are made on the
device in ``__init__``.
"""
from __future__ import annotations

import math

import torch
from torch import Tensor

from .frames import quat_mul_wxyz, rotmat_to_quat_wxyz
from .physics_params import G_MPS2, Px4Gains

FLT_EPSILON: float = 1.1920929e-07          # C's FLT_EPSILON, as PX4 uses it
CA_ROTOR_CT: float = 6.5                    # CA_ROTOR0..3_CT in the drone's file (PX4 default); cancels in the
                                            # normalised mix, kept so the effectiveness matrix is PX4's own
I_FACTOR_RATE_RAD_S: float = math.radians(400.0)   # rate_control.cpp updateIntegral


# ----------------------------------------------------------------------------------------------- ControlMath.cpp
def constrain_xy(v0: Tensor, v1: Tensor, max_mps: float) -> Tensor:
    """ControlMath::constrainXY (ControlMath.cpp:122-184), batched over [..., 2].

    ``v0`` has priority (the position term), ``v1`` is added only as far as the norm ``max_mps`` allows.
    """
    def norm(v: Tensor) -> Tensor:
        return v.norm(dim=-1, keepdim=True)

    def unit(v: Tensor) -> Tensor:                   # matrix::normalized(): v / |v| (no guard; branches below pick)
        return v / norm(v).clamp_min(1e-30)

    s01 = v0 + v1
    n0 = norm(v0)
    u1 = unit(v1)
    m = (u1 * v0).sum(-1, keepdim=True)
    c = (v0 * v0).sum(-1, keepdim=True) - max_mps * max_mps
    s = -m + torch.sqrt((m * m - c).clamp_min(0.0))
    out = v0 + u1 * s                                                       # general case
    out = torch.where(n0 < 0.001, unit(v1) * max_mps, out)                  # v0 is zero
    out = torch.where(norm(v1 - v0) < 0.001, unit(v0) * max_mps, out)       # the two vectors are equal
    out = torch.where(n0 >= max_mps, unit(v0) * max_mps, out)               # v0 alone too big
    return torch.where(norm(s01) <= max_mps, s01, out)                      # fits: the sum


def limit_tilt(body_z: Tensor, max_rad: float) -> Tensor:
    """ControlMath::limitTilt (ControlMath.cpp:53-68) with ``world_unit = (0, 0, 1)``, as PX4 passes it.

    ``body_z`` [..., 3] unit vector -> the same azimuth, at most ``max_rad`` from (0, 0, 1).
    """
    dot = body_z[..., 2:3]
    angle = torch.acos(dot.clamp(-1.0, 1.0)).clamp_max(max_rad)
    rej = torch.cat((body_z[..., :2], torch.zeros_like(dot)), dim=-1)      # body - (body . w) w
    parallel = (rej * rej).sum(-1, keepdim=True) < FLT_EPSILON
    x_unit = torch.cat((torch.ones_like(dot), torch.zeros_like(dot), torch.zeros_like(dot)), dim=-1)
    rej = torch.where(parallel, rej + x_unit, rej)                          # corner case: rejection(0) = 1
    rej_unit = rej / rej.norm(dim=-1, keepdim=True)
    w = torch.cat((torch.zeros_like(dot), torch.zeros_like(dot), torch.ones_like(dot)), dim=-1)
    return torch.cos(angle) * w + torch.sin(angle) * rej_unit


def bodyz_to_rotmat(body_z: Tensor, yaw_ned: Tensor) -> Tensor:
    """ControlMath::bodyzToAttitude (ControlMath.cpp:70-120): desired body z [..., 3] + yaw [...] -> R_sp [..., 3, 3].

    R_sp is body (FRD) -> world (NED); its columns are the desired body x, y, z axes.
    """
    zero = torch.zeros_like(yaw_ned)
    small = (body_z * body_z).sum(-1, keepdim=True) < FLT_EPSILON          # zero vector: safe level value
    body_z = torch.where(small, torch.cat((body_z[..., :2], torch.ones_like(body_z[..., 2:])), dim=-1), body_z)
    body_z = body_z / body_z.norm(dim=-1, keepdim=True)
    y_c = torch.stack((-torch.sin(yaw_ned), torch.cos(yaw_ned), zero), dim=-1)
    body_x = torch.linalg.cross(y_c, body_z)
    body_x = torch.where(body_z[..., 2:] < 0.0, -body_x, body_x)            # keep nose to front while inverted
    flat = body_z[..., 2:].abs() < 0.000001
    down = torch.stack((zero, zero, torch.ones_like(zero)), dim=-1)
    body_x = torch.where(flat, down, body_x)
    body_x = body_x / body_x.norm(dim=-1, keepdim=True)
    body_y = torch.linalg.cross(body_z, body_x)
    return torch.stack((body_x, body_y, body_z), dim=-1)


# ------------------------------------------------------------------------------------------- control allocation
def allocation_matrix(g: Px4Gains) -> Tensor:
    """[4, 6] float32 CPU: PX4 v1.14's normalised pseudo-inverse mix for the drone's CA_ROTOR* geometry.

    Rows = rotors 0..3, columns = (roll, pitch, yaw torque, thrust x, y, z), as ``_mix`` in
    ``ControlAllocationPseudoInverse``. Built in float64 once (not in the step); move it to the device once.
    """
    cols = []
    for i in range(4):
        x, y = getattr(g, f"ca_rotor{i}_px"), getattr(g, f"ca_rotor{i}_py")
        km = getattr(g, f"ca_rotor{i}_km")
        axis = (0.0, 0.0, -1.0)
        # moment = ct (r x axis) - ct km axis, r = (x, y, 0): r x (0, 0, -1) = (-y, x, 0)
        moment = (CA_ROTOR_CT * -y, CA_ROTOR_CT * x, -CA_ROTOR_CT * km * axis[2])
        thrust = tuple(CA_ROTOR_CT * a for a in axis)
        cols.append(moment + thrust)
    eff = torch.tensor(cols, dtype=torch.float64).T                          # [6, 4]
    mix = torch.linalg.pinv(eff)                                             # [4, 6], matrix::geninv
    # updateControlAllocationMatrixScale, _normalize_rpy = true (ActuatorEffectivenessMultirotor)
    nz_roll = (mix[:, 0].abs() > 1e-3).sum()
    nz_pitch = (mix[:, 1].abs() > 1e-3).sum()
    roll_scale = torch.sqrt((mix[:, 0] ** 2).sum() / (nz_roll / 2.0)) if nz_roll > 0 else torch.tensor(1.0)
    pitch_scale = torch.sqrt((mix[:, 1] ** 2).sum() / (nz_pitch / 2.0)) if nz_pitch > 0 else torch.tensor(1.0)
    scale = torch.ones(6, dtype=torch.float64)
    scale[0] = scale[1] = torch.maximum(roll_scale, pitch_scale)
    scale[2] = mix[:, 2].max()
    scale[5] = 1.0                                                           # THRUST_Z default for empty axes
    for axis_idx in (2, 1, 0):
        col = mix[:, 3 + axis_idx].abs()
        nz = (col > FLT_EPSILON).sum()
        scale[3 + axis_idx] = col.sum() / nz if nz > 0 else scale[5]
    # normalizeControlAllocationMatrix
    if scale[0] > FLT_EPSILON:
        mix[:, 0] /= scale[0]
        mix[:, 1] /= scale[1]
    if scale[2] > FLT_EPSILON:
        mix[:, 2] /= scale[2]
    if scale[3] > FLT_EPSILON:
        mix[:, 3:] /= scale[3:]
    mix = torch.where(mix.abs() < 1e-3, torch.zeros_like(mix), mix)
    return mix.to(torch.float32)


def _desat_gain(vec: Tensor, u: Tensor, u_max: float) -> Tensor:
    """computeDesaturationGain: ``vec`` [4], ``u`` [..., 4] -> gain [..., 1] (k_min + k_max, both start at 0)."""
    strong = vec.abs() >= 0.2                                     # weak actuators are skipped
    safe = torch.where(strong, vec, torch.ones_like(vec))
    k_lo = torch.where(strong & (u < 0.0), (0.0 - u) / safe, torch.zeros_like(u))
    k_hi = torch.where(strong & (u > u_max), (u_max - u) / safe, torch.zeros_like(u))
    k = torch.cat((k_lo, k_hi), dim=-1)
    return k.amin(-1, keepdim=True).clamp_max(0.0) + k.amax(-1, keepdim=True).clamp_min(0.0)


def _desaturate(u: Tensor, vec: Tensor, increase_only: bool = False, u_max: float = 1.0) -> Tensor:
    """desaturateActuators: one full step along ``vec`` then half of the next; skipped if increase_only and gain < 0."""
    gain = _desat_gain(vec, u, u_max)
    keep = gain >= 0.0 if increase_only else torch.ones_like(gain, dtype=torch.bool)
    gain = torch.where(keep, gain, torch.zeros_like(gain))
    u = u + gain * vec
    gain2 = 0.5 * _desat_gain(vec, u, u_max)
    gain2 = torch.where(keep, gain2, torch.zeros_like(gain2))
    return u + gain2 * vec


def allocate(torque_n: Tensor, thrust_n: Tensor, mix: Tensor) -> Tensor:
    """Normalised torque [N, M, 3] + collective thrust [N, M] (>= 0) -> rotor commands u [N, M, 4] in [0, 1].

    ``mixAirmodeDisabled`` then ``mixYaw`` (ControlAllocationSequentialDesaturation.cpp:173, :206), then the clip.
    The thrust setpoint is (0, 0, -thrust_n) in FRD, as ``thrustToAttitude`` makes it; ``mix`` is
    ``allocation_matrix(g)`` on the step's device and dtype.
    """
    roll, pitch, yaw, thr_z = mix[:, 0], mix[:, 1], mix[:, 2], mix[:, 5]
    u = (roll * torque_n[..., 0:1] + pitch * torque_n[..., 1:2] + thr_z * (-thrust_n.unsqueeze(-1)))
    u = _desaturate(u, thr_z, increase_only=True)        # only reduce thrust
    u = _desaturate(u, roll)
    u = _desaturate(u, pitch)
    # mixYaw
    u = u + yaw * torque_n[..., 2:3]
    u = _desaturate(u, yaw, u_max=1.0 + (1.0 - 0.0) * 0.15)   # allow some yaw response at maximum thrust
    u = _desaturate(u, thr_z, increase_only=True)
    return u.clamp(0.0, 1.0)


# ---------------------------------------------------------------------------------------------- quaternion helpers
def _conj(q: Tensor) -> Tensor:
    return torch.cat((q[..., :1], -q[..., 1:]), dim=-1)


def _canonical(q: Tensor) -> Tensor:
    """matrix::Quaternion::canonical: the sign that makes the first component with |.| > FLT_EPSILON positive."""
    big = (q.abs() > FLT_EPSILON).to(q.dtype)
    lead = torch.gather(q, -1, big.argmax(-1, keepdim=True))        # first True (argmax returns the first maximum)
    return torch.where(lead < 0.0, -q, q)


def _quat_between(src: Tensor, dst: Tensor) -> Tensor:
    """matrix::Quaternion(src, dst): the shortest rotation taking ``src`` [..., 3] to ``dst`` (eps 1e-5), WXYZ."""
    cr = torch.linalg.cross(src, dst)
    dot = (src * dst).sum(-1, keepdim=True)
    corner = (cr.norm(dim=-1, keepdim=True) < 1e-5) & (dot < 0.0)
    a = src.abs()
    e = torch.eye(3, dtype=src.dtype, device=src.device)
    ax_x = e[0].expand_as(src)
    ax_y = e[1].expand_as(src)
    ax_z = e[2].expand_as(src)
    pick = torch.where(a[..., 0:1] < a[..., 1:2],
                       torch.where(a[..., 0:1] < a[..., 2:3], ax_x, ax_z),
                       torch.where(a[..., 1:2] < a[..., 2:3], ax_y, ax_z))
    cr = torch.where(corner, torch.linalg.cross(src, pick), cr)
    w = torch.where(corner, torch.zeros_like(dot),
                    dot + torch.sqrt((src * src).sum(-1, keepdim=True) * (dst * dst).sum(-1, keepdim=True)))
    q = torch.cat((w, cr), dim=-1)
    return q / q.norm(dim=-1, keepdim=True)


# ------------------------------------------------------------------------------------------------------ cascade
class Px4Cascade:
    """PX4 1.14's cascade for N games x M drones, one physics step per ``step`` call (NED / FRD).

    After a step, for logging and tests: ``vel_sp`` [N, M, 3], ``acc_sp`` [N, M, 3], ``thr_sp`` [N, M, 3],
    ``r_sp`` [N, M, 3, 3], ``rates_sp`` [N, M, 3] (rad/s), ``torque_n`` [N, M, 3] (normalised), ``collective``
    [N, M] (share of full thrust), ``u`` [N, M, 4]. State: ``vel_int`` and ``rate_int`` (integrators), and the two
    derivative filters (``vel_dot``, ``ang_acc``).

    ``tilt_max_deg`` overrides ``MPC_TILTMAX_AIR`` (D11's INFO variant); ``dtype`` (default float32) is an
    addition to the plan's signature, as in ``TorchRigidBodyWorld``.
    """

    def __init__(self, n: int, m: int, g: Px4Gains, dt_s: float, device, tilt_max_deg: float | None = None,
                 dtype: torch.dtype = torch.float32) -> None:
        self.g = g
        self.n, self.m = n, m
        self.dt_s = dt_s
        self.device = torch.device(device)
        self.dtype = dtype
        kw = dict(device=self.device, dtype=dtype)

        def vec(*v: float) -> Tensor:
            return torch.tensor(v, dtype=dtype).to(self.device)

        # position / velocity (MulticopterPositionControl::parameters_update)
        self._k_pos = vec(g.mpc_xy_p, g.mpc_xy_p, g.mpc_z_p)
        self._k_vel_p = vec(g.mpc_xy_vel_p_acc, g.mpc_xy_vel_p_acc, g.mpc_z_vel_p_acc)
        self._k_vel_i = vec(g.mpc_xy_vel_i_acc, g.mpc_xy_vel_i_acc, g.mpc_z_vel_i_acc)
        self._k_vel_d = vec(g.mpc_xy_vel_d_acc, g.mpc_xy_vel_d_acc, g.mpc_z_vel_d_acc)
        self._arw_gain = 2.0 / g.mpc_xy_vel_p_acc
        self._tilt_max_rad = math.radians(g.mpc_tiltmax_air if tilt_max_deg is None else tilt_max_deg)
        self._thr_hover = g.mpc_thr_hover
        self._thr_min = max(g.mpc_thr_min, 10e-4)
        self._thr_max = g.mpc_thr_max
        b = 2.0 * math.pi * g.mpc_veld_lp * dt_s                         # BlockLowPass
        self._veld_a = b / (1.0 + b)
        # attitude (AttitudeControl::setProportionalGain, setRateLimit)
        yaw_w = min(max(g.mc_yaw_weight, 0.0), 1.0)
        self._yaw_w = yaw_w
        k_yaw = g.mc_yaw_p / yaw_w if yaw_w > 1e-4 else g.mc_yaw_p
        self._k_att = vec(g.mc_roll_p, g.mc_pitch_p, k_yaw)
        self._rate_lim = vec(math.radians(g.mc_rollrate_max), math.radians(g.mc_pitchrate_max),
                             math.radians(g.mc_yawrate_max))
        # rates (MulticopterRateControl::parameters_updated): K multiplies P, I, D; FF stands alone
        k = (g.mc_rollrate_k, g.mc_pitchrate_k, g.mc_yawrate_k)
        self._rate_p = vec(*(ki * p for ki, p in zip(k, (g.mc_rollrate_p, g.mc_pitchrate_p, g.mc_yawrate_p))))
        self._rate_i = vec(*(ki * p for ki, p in zip(k, (g.mc_rollrate_i, g.mc_pitchrate_i, g.mc_yawrate_i))))
        self._rate_d = vec(*(ki * p for ki, p in zip(k, (g.mc_rollrate_d, g.mc_pitchrate_d, g.mc_yawrate_d))))
        self._rate_ff = vec(g.mc_rollrate_ff, g.mc_pitchrate_ff, g.mc_yawrate_ff)
        self._rate_int_lim = vec(g.mc_rr_int_lim, g.mc_pr_int_lim, g.mc_yr_int_lim)
        # D-term filter (AlphaFilter::setCutoffFreq at the loop rate; note B)
        self._dgyro_alpha = dt_s / (dt_s + 1.0 / (2.0 * math.pi * g.imu_dgyro_cutoff)) \
            if 0.0 < g.imu_dgyro_cutoff < 0.5 / dt_s else 1.0
        self.mix = allocation_matrix(g).to(dtype).to(self.device)              # [4, 6], once

        # state
        self.vel_int = torch.zeros(n, m, 3, **kw)
        self.rate_int = torch.zeros(n, m, 3, **kw)
        self.vel_dot = torch.zeros(n, m, 3, **kw)                # BlockLowPass state
        self._vel_prev = torch.zeros(n, m, 3, **kw)
        self.ang_acc = torch.zeros(n, m, 3, **kw)                # AlphaFilter state
        self._omega_prev = torch.zeros(n, m, 3, **kw)
        self._deriv_ready = torch.zeros(n, m, 1, device=self.device, dtype=torch.bool)
        # logs
        self.vel_sp = torch.zeros(n, m, 3, **kw)
        self.acc_sp = torch.zeros(n, m, 3, **kw)
        self.thr_sp = torch.zeros(n, m, 3, **kw)
        self.r_sp = torch.eye(3, **kw).expand(n, m, 3, 3).clone()
        self.rates_sp = torch.zeros(n, m, 3, **kw)
        self.torque_n = torch.zeros(n, m, 3, **kw)
        self.collective = torch.zeros(n, m, **kw)
        self.u = torch.zeros(n, m, 4, **kw)

    def reset(self, mask: Tensor) -> None:
        """Where ``mask`` [N, M]: integrators 0; derivative filters at rest (output 0, first difference skipped)."""
        k = mask.unsqueeze(-1)
        zero = torch.zeros_like(self.vel_int)
        self.vel_int = torch.where(k, zero, self.vel_int)
        self.rate_int = torch.where(k, zero, self.rate_int)
        self.vel_dot = torch.where(k, zero, self.vel_dot)
        self.ang_acc = torch.where(k, zero, self.ang_acc)
        self._deriv_ready = self._deriv_ready & ~k

    # ------------------------------------------------------------------------------------------- the step
    def step(self, p_sp: Tensor, v_ff: Tensor, a_ff: Tensor, yaw_sp: Tensor, yawspeed_ff: Tensor,
             pos: Tensor, vel: Tensor, r_ned_frd: Tensor, omega_frd: Tensor) -> Tensor:
        """One physics step of the whole cascade. All NED / FRD, SI units.

        p_sp, v_ff, a_ff, pos, vel [N, M, 3]; yaw_sp (rad), yawspeed_ff (rad/s) [N, M]; r_ned_frd [N, M, 3, 3]
        (body -> world); omega_frd [N, M, 3] (rad/s). Returns u [N, M, 4] (rotor commands in [0, 1]).
        """
        g = G_MPS2
        dt = self.dt_s
        ready = self._deriv_ready

        # 1. _positionControl
        v_pos = (p_sp - pos) * self._k_pos
        v_sp_xy = constrain_xy(v_pos[..., :2], v_ff[..., :2], self.g.mpc_xy_vel_max)
        v_sp_z = (v_ff[..., 2:] + v_pos[..., 2:]).clamp(-self.g.mpc_z_vel_max_up, self.g.mpc_z_vel_max_dn)
        v_sp = torch.cat((v_sp_xy, v_sp_z), dim=-1)

        # velocity derivative (BlockDerivative + BlockLowPass), before the controller as in Run()
        raw = torch.where(ready, (vel - self._vel_prev) / dt, torch.zeros_like(vel))
        self.vel_dot = self._veld_a * raw + (1.0 - self._veld_a) * self.vel_dot
        self._vel_prev = vel

        # 2. _velocityControl
        vel_int = torch.cat((self.vel_int[..., :2], self.vel_int[..., 2:].clamp(-g, g)), dim=-1)
        e = v_sp - vel
        acc_sp = a_ff + e * self._k_vel_p + vel_int - self.vel_dot * self._k_vel_d

        # 3. _accelerationControl
        body_z = torch.cat((-acc_sp[..., :2], torch.full_like(acc_sp[..., 2:], g)), dim=-1)
        body_z = limit_tilt(body_z / body_z.norm(dim=-1, keepdim=True), self._tilt_max_rad)
        thr = (acc_sp[..., 2:] * (self._thr_hover / g) - self._thr_hover) / body_z[..., 2:]
        thr = thr.clamp_max(-self._thr_min)
        thr_sp = body_z * thr

        # 4. anti-windup and saturation (rest of _velocityControl)
        e_z = e[..., 2:]
        stop_z = ((thr_sp[..., 2:] >= -self._thr_min) & (e_z >= 0.0)) | ((thr_sp[..., 2:] <= -self._thr_max) & (e_z <= 0.0))
        e_z = torch.where(stop_z, torch.zeros_like(e_z), e_z)
        thr_xy = thr_sp[..., :2]
        thr_xy_norm = thr_xy.norm(dim=-1, keepdim=True)
        thr_max_sq = self._thr_max * self._thr_max
        alloc_xy = thr_xy_norm.clamp_max(self.g.mpc_thr_xy_marg)
        thr_z = torch.maximum(thr_sp[..., 2:], -torch.sqrt(thr_max_sq - alloc_xy * alloc_xy))
        thr_max_xy_sq = thr_max_sq - thr_z * thr_z
        thr_max_xy = torch.sqrt(thr_max_xy_sq.clamp_min(0.0))
        thr_xy = torch.where(thr_xy_norm > thr_max_xy, thr_xy / thr_xy_norm.clamp_min(1e-30) * thr_max_xy, thr_xy)
        thr_sp = torch.cat((thr_xy, thr_z), dim=-1)
        acc_prod = thr_xy * (g / self._thr_hover)
        acc_xy = acc_sp[..., :2]
        acc_lim = torch.where((acc_xy * acc_xy).sum(-1, keepdim=True) > (acc_prod * acc_prod).sum(-1, keepdim=True),
                              acc_prod, acc_xy)
        e_xy = e[..., :2] - self._arw_gain * (acc_xy - acc_lim)
        e = torch.cat((e_xy, e_z), dim=-1)
        e = torch.where(torch.isfinite(e), e, torch.zeros_like(e))           # setZeroIfNanVector3f
        self.vel_int = vel_int + e * self._k_vel_i * dt

        # 5. thrustToAttitude
        r_sp = bodyz_to_rotmat(-thr_sp, yaw_sp)
        collective = thr_sp.norm(dim=-1)

        # 6. AttitudeControl::update
        rates_sp = self._attitude(r_ned_frd, r_sp, yawspeed_ff)

        self.vel_sp, self.acc_sp, self.thr_sp, self.r_sp, self.collective = v_sp, acc_sp, thr_sp, r_sp, collective
        # 7.-8. rates and allocation
        return self.rate_step(rates_sp, omega_frd, collective)

    def _attitude(self, r: Tensor, r_sp: Tensor, yawspeed_ff: Tensor) -> Tensor:
        """AttitudeControl::update: R [N, M, 3, 3], R_sp, yawspeed [N, M] -> rate setpoint [N, M, 3] (FRD, rad/s)."""
        q = rotmat_to_quat_wxyz(r)
        qd = rotmat_to_quat_wxyz(r_sp)
        e_z = r[..., :, 2]
        e_z_d = r_sp[..., :, 2]
        qd_red = _quat_between(e_z, e_z_d)
        corner = (qd_red[..., 1:2].abs() > 1.0 - 1e-5) | (qd_red[..., 2:3].abs() > 1.0 - 1e-5)
        qd_red = torch.where(corner, qd, quat_mul_wxyz(qd_red, q))
        q_mix = _canonical(quat_mul_wxyz(_conj(qd_red), qd))
        mw = q_mix[..., 0:1].clamp(-1.0, 1.0)
        mz = q_mix[..., 3:4].clamp(-1.0, 1.0)
        zero = torch.zeros_like(mw)
        q_yaw = torch.cat((torch.cos(self._yaw_w * torch.acos(mw)), zero, zero,
                           torch.sin(self._yaw_w * torch.asin(mz))), dim=-1)
        qd = quat_mul_wxyz(qd_red, q_yaw)
        qe = quat_mul_wxyz(_conj(q), qd)
        eq = 2.0 * _canonical(qe)[..., 1:]
        rate_sp = eq * self._k_att + r[..., 2, :] * yawspeed_ff.unsqueeze(-1)   # q.inversed().dcm_z() = R^T e3
        return torch.maximum(torch.minimum(rate_sp, self._rate_lim), -self._rate_lim)

    def rate_step(self, rates_sp: Tensor, omega_frd: Tensor, collective: Tensor) -> Tensor:
        """RateControl::update + allocation: rate setpoint [N, M, 3], rate [N, M, 3] (FRD, rad/s), collective [N, M].

        Also the entry point of the design check's rate-loop test (it skips the outer loops). Returns u [N, M, 4].
        """
        dt = self.dt_s
        ready = self._deriv_ready
        # angular acceleration: difference quotient through the AlphaFilter (VehicleAngularVelocity)
        raw = torch.where(ready, (omega_frd - self._omega_prev) / dt, torch.zeros_like(omega_frd))
        self.ang_acc = (1.0 - self._dgyro_alpha) * self.ang_acc + self._dgyro_alpha * raw
        self._omega_prev = omega_frd
        self._deriv_ready = torch.ones_like(ready)

        e = rates_sp - omega_frd
        torque = e * self._rate_p + self.rate_int - self.ang_acc * self._rate_d + rates_sp * self._rate_ff
        # updateIntegral (saturation flags never set; never landed)
        i_factor = (1.0 - (e / I_FACTOR_RATE_RAD_S) ** 2).clamp_min(0.0)
        rate_i = self.rate_int + i_factor * self._rate_i * e * dt
        rate_i = torch.maximum(torch.minimum(rate_i, self._rate_int_lim), -self._rate_int_lim)
        self.rate_int = torch.where(torch.isfinite(rate_i), rate_i, self.rate_int)
        torque = torch.where(torch.isfinite(torque), torque, torch.zeros_like(torque))   # vehicle_torque_setpoint

        self.rates_sp, self.torque_n = rates_sp, torque
        self.u = allocate(torque, collective, self.mix)
        return self.u
