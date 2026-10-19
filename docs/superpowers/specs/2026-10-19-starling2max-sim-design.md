# Starling 2 Max in the SVG Isaac Sim — design

Date: 2026-10-19 · Status: approved in conversation, awaiting written review
Repo: `AirStack-starling-max2` (branch `main`, AirStack snapshot `yikuan/SVG_ground_control` @ `cf719f0`)

## 1. Goal and success criteria

Replace the Iris with a ModalAI Starling 2 Max as the simulated drone in the SVG Isaac Sim,
using CMU's system-identification results, through the **unchanged** launch path
(`svg_multi_drone_single_domain.py` → `spawn_px4_multirotor_node` → PX4 SITL → MAVROS →
`odometry_conversion` → swarm commander).

Success, in order:

1. A cleaned Starling USD whose prim tree differs from the delivered file only in the body
   mesh density and the removed light.
2. One Starling spawns headless, PX4 SITL boots on the new airframe (`SYS_AUTOSTART 10090`
   in the log), arms, takes off and hovers through the normal SVG commander flow; hover
   throttle between 0.30 and 0.45; a 1 m step in x and in z settles without oscillation.
3. The three-drone `cbf_sim.yaml` run (MILESTONES M1 "CBF crossing") completes with the
   Starling model.
4. Iris behaviour is unchanged when the new env vars are not set.

Non-goals: drag identification (CMU did not measure it), VOXL camera / ToF / VIO sensor
models, a Starling mesh for the Basestation 3D view, porting the real drone's rate gains
into SITL (follow-up once hover is clean), rebuilding the Isaac image.

## 2. Inputs

| Quantity | Value | Source |
|---|---|---|
| Mass | 0.557 kg | CMU sys-ID; already in the USD |
| Inertia, body FLU diag (kg·m²) | 0.002943 / 0.001857 / 0.004649 | CMU sys-ID (CAD frame re-ordered); already in the USD |
| Centre of mass | (0.00102, 0.00016, 0.00741) m | CMU sys-ID; already in the USD |
| Rotor positions, body FLU (m) | r0 (+0.095, −0.13), r1 (−0.095, +0.13), r2 (+0.095, +0.13), r3 (−0.095, −0.13), z +0.0195 | USD joints (CMU CAD). PX4 quad-X order FR, BL, FL, BR, same as Iris |
| Rotor constant k_f | 3.964738e-6 N/(rad/s)² | CMU sys-ID |
| Rolling-moment coefficient k_m | 5.38697e-8 N·m/(rad/s)² | CMU sys-ID |
| Motor time constant τ | 0.072 s (55 ms up / 85 ms down) | CMU sys-ID |
| Spin directions | [−1, −1, +1, +1] | Iris convention, matches the rotor order above |
| Rotor speed ceiling | 1450 rad/s (derived) | hover needs √(0.557·9.81/4 / k_f) = 587 rad/s; with PX4 throttle → ω = 1350·u + 100, hover sits at u ≈ 0.36 |
| PX4 `KM` | 0.0136 = k_m / k_f | derived |
| PX4 `MPC_THR_HOVER` | 0.36 | derived from the ceiling above |

Decision recorded: the real drone's PX4 params carry rotor positions ±0.085/±0.0625 that
contradict CMU's CAD. The user chose CMU's values; the sim and the sim airframe use the USD
geometry. (Not applied to the real drone.)

The sys-ID page is committed as `isaac_sim/Starling 2 Max Sys ID Results - Slite.pdf`.

## 3. Components

### 3.1 Asset — `AirStack/simulation/isaac-sim/assets/robots/starling2max.usd`

- Derived from `isaac_sim/starlingmax2.usd` (CMU's file, 98 MB, body mesh 1.2 M faces).
- Body mesh decimated to ≈ 50 k faces with `trimesh` (quadric decimation) run under the
  Isaac image's Python; points/faces written back into the same `Mesh` prim so the
  `PhysicsMeshCollisionAPI` (convex hull) and material binding are untouched.
- `/vehicle/defaultLight` removed (it would be instanced once per drone).
- Everything else untouched: `/vehicle` articulation root, `/vehicle/body` (mass, inertia,
  CoM), `/vehicle/body/body` mesh prim (the ZED/lidar fixed-joint anchor), `rotor0..3`,
  `joint0..3`, rotor meshes and colliders.
- Acceptance: the prim-tree dump (`dump_usd.py`) of old vs new differs only in body-mesh
  face/point counts and the missing light; file size a few MB.
- The original stays in `isaac_sim/` and is gitignored (just under GitHub's 100 MB limit;
  not worth committing).

### 3.2 Dynamics — vendored Pegasus extension

Files under `AirStack/simulation/isaac-sim/extensions/PegasusSimulator/extensions/pegasus.simulator/pegasus/simulator/`:

- `logic/thrusters/lagged_quadratic_thrust_curve.py` — subclass of
  `QuadraticThrustCurve`; the commanded rotor velocity is passed through a first-order lag
  `ω += dt/τ · (ω_cmd − ω)` with `τ` from config (default 0 = no lag, i.e. identical to the
  parent). Rotor forces and rolling moment computed from the lagged ω.
- `logic/vehicles/multirotors/starling2max.py` — `Starling2MaxConfig(MultirotorConfig)`
  setting `thrust_curve = LaggedQuadraticThrustCurve({rotor_constant: [k_f]*4,
  rolling_moment_coefficient: [k_m]*4, rot_dir: [-1,-1,1,1], max_rotor_velocity: [1450]*4,
  time_constant: 0.072})`; drag left at the Pegasus default `LinearDrag([0.5, 0.3, 0.0])`.
- `logic/vehicles/multirotors/__init__.py` (or a new `registry.py`) —
  `VEHICLE_CONFIGS = {"iris": MultirotorConfig, "starling2max": Starling2MaxConfig}`.
- `ogn/python/nodes/OgnPegasusMultirotorNodeBase.py:create_multirotor` — choose the config
  class by the USD file's stem (`os.path.splitext(os.path.basename(usd_file))[0].lower()`),
  falling back to `MultirotorConfig` for unknown names, so Iris is unchanged. Log the choice.
- No change to the OGN node schema (`.ogn` / Database), so saved graphs stay valid.
- Unit test `tests/test_lagged_thrust_curve.py` (plain pytest, numpy only): with τ = 0 the
  output equals the parent class; with τ = 0.072 a step reaches 63 % of the target after
  one τ; force = k_f·ω².

### 3.3 PX4 airframe — `AirStack/simulation/isaac-sim/px4/airframes/10090_pegasus_starling2max`

Modelled on `10015_gazebo-classic_iris`:

```
. ${R}etc/init.d/rc.mc_defaults
param set-default CA_AIRFRAME 0
param set-default CA_ROTOR_COUNT 4
param set-default CA_ROTOR0_PX  0.095   # FRD: USD FLU y negated
param set-default CA_ROTOR0_PY  0.13
param set-default CA_ROTOR0_KM  0.0136
param set-default CA_ROTOR1_PX -0.095
param set-default CA_ROTOR1_PY -0.13
param set-default CA_ROTOR1_KM  0.0136
param set-default CA_ROTOR2_PX  0.095
param set-default CA_ROTOR2_PY -0.13
param set-default CA_ROTOR2_KM -0.0136
param set-default CA_ROTOR3_PX -0.095
param set-default CA_ROTOR3_PY  0.13
param set-default CA_ROTOR3_KM -0.0136
param set-default MPC_THR_HOVER 0.36
param set-default PWM_MAIN_FUNC1 101 … FUNC4 104
```

Rate and position gains: inherited from `rc.mc_defaults` (what the Iris uses) for the first
flights. The file is a plain shell script read by `rcS` at SITL start, so it is **bind-mounted**
into the container by one line in `simulation/isaac-sim/docker/docker-compose.yaml`:

```
- ../px4/airframes/10090_pegasus_starling2max:/isaac-sim/PX4-Autopilot/build/px4_sitl_default/etc/init.d-posix/airframes/10090_pegasus_starling2max:ro
```

Verified 2026-10-19: `rcS:51-61` resolves `PX4_SIM_MODEL` by listing that directory, which is
a plain directory (not a symlink) in image `v0.18.0_isaac-sim` (PX4 v1.16.1).

### 3.4 Launch wiring — `simulation/isaac-sim/launch_scripts/svg_multi_drone_single_domain.py`

- `DRONE_USD = os.environ.get("DRONE_USD", <current Iris path>)`.
- `PX4_VEHICLE_MODEL = os.environ.get("PX4_VEHICLE_MODEL", "gazebo-classic_iris")`, passed as
  `px4_vehicle_model=` to `spawn_px4_multirotor_node`.
- The real-drone avatar (`spawn_avatar`) references the same `DRONE_USD`.
- ZED mount offset: `[0.12, 0.0, -0.03]` when `DRONE_USD` names the Starling (frame half the
  size of the Iris), else unchanged.
- Fix the lidar import (`spawn_ouster_lidar` → `spawn_rtx_lidar.add_rtx_lidar_subgraph`).
- Container path for the asset: `/isaac-sim/AirStack/simulation/isaac-sim/assets/robots/starling2max.usd`
  (the repo is already mounted at `/isaac-sim/AirStack`).

Resulting operator command (RUNBOOK §A T1), new vars in front:

```
DRONE_USD=/isaac-sim/AirStack/simulation/isaac-sim/assets/robots/starling2max.usd \
PX4_VEHICLE_MODEL=pegasus_starling2max \
NUM_ROBOTS=3 SVG_DOMAIN_ID=1 PLAY_SIM_ON_START=true ISAAC_SIM_HEADLESS=true … svg_multi_drone_single_domain.py …
```

### 3.5 Docs

- RUNBOOK §A: the two env vars, with the Iris default stated.
- CONFIG: a "Sim airframe (Starling 2 Max)" row listing the constants, the derived ceiling and
  hover throttle, and the CMU PDF as source; a "sim rotor geometry vs real params" note.
- MILESTONES M1: two new sub-tests ("Starling model hover + step" and the CBF crossing on the
  Starling model); §3b audit rows for the new files.
- SCENARIOS §11 (technical appendix): pointer to the sys-ID numbers.
- `AirStack/README.md` (snapshot note): list the local additions (airframe file, Pegasus
  config, launch env vars) as "ours, not upstream".

## 4. Data flow (unchanged shape)

Isaac physics (USD mass/inertia, rotor forces from the lagged thrust curve) → Pegasus PX4
backend (HIL sensors over MAVLink `tcpin:4560+i`) → PX4 SITL with the Starling airframe →
MAVROS (`launch_sim_interfaces.sh`) → `odometry_conversion` → swarm commander → velocity
setpoints back through MAVROS → PX4 → actuator controls → thrust curve.

## 5. Verification plan

1. **Asset**: prim-tree diff; file size; open in Isaac (headless spawn) without PhysX
   cooking warnings for the body collider.
2. **Dynamics unit test**: pytest on the lag curve (no Isaac needed).
3. **Single-drone hover** (headless, `NUM_ROBOTS=1`): PX4 console shows the 10090 airframe;
   `ros2 topic echo /drone_1/interface/mavros/state` → `connected: true`; commander
   `takeoff` → hover; read hover throttle from the MAVROS actuator/attitude-target topic;
   `goal_single_ours.yaml`-style step of 1 m in x then z; inspect the odometry trace for
   overshoot and ringing. Pass: hover throttle 0.30–0.45, steps settle within 2 s, no growing
   oscillation.
4. **Regression**: same launch with the env vars unset → Iris spawns and flies as before.
5. **M1 row**: `cbf_sim.yaml` three-drone antipodal crossing on the Starling model; ledger
   entry with date.

## 6. Risks and fallbacks

- Iris default rate gains may ring on a 7:1 thrust-to-weight airframe → scale `MC_*RATE_K`
  down in the airframe file (0.5 first), re-run step 3.
- Decimation may distort the convex hull → switch the body collider to
  `convexDecomposition` as the Iris uses.
- `trimesh` quadric decimation needs the `fast_simplification` wheel inside the Isaac image →
  install it into the image's Python for the one-off conversion, or decimate with Blender on
  the host if available; the converted USD is what gets committed, so the tool is not a
  runtime dependency.
- Rotor joints in the Starling USD attach to `/vehicle/body` (the Xform) rather than the mesh
  as the Iris does → PhysX resolves both to the same rigid body; verify the propeller spin
  visual works, otherwise retarget `body0` to `/vehicle/body/body` in the cleaned USD.

## 7. Files touched

New: `assets/robots/starling2max.usd`, `px4/airframes/10090_pegasus_starling2max`,
`pegasus/simulator/logic/thrusters/lagged_quadratic_thrust_curve.py`,
`pegasus/simulator/logic/vehicles/multirotors/starling2max.py`, lag-curve test,
`isaac_sim/Starling 2 Max Sys ID Results - Slite.pdf` (committed), `isaac_sim/.gitignore`.

Modified: `OgnPegasusMultirotorNodeBase.py`, `multirotors/__init__.py`,
`svg_multi_drone_single_domain.py`, `simulation/isaac-sim/docker/docker-compose.yaml`,
`docs/RUNBOOK.md`, `docs/CONFIG.md`, `docs/MILESTONES.md`, `docs/SCENARIOS.md`,
`AirStack/README.md`.
