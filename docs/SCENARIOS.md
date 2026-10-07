# SCENARIOS — the CBF collision filter and the multi-drone flights

> **Who this is for:** anyone in the AI.R / STC lab who wants to understand or run the
> **multi-drone** parts of AirStack — the CBF collision-avoidance filter, the formation profiles,
> the random-goal collision test, the RC-flown-intruder squeeze. No robotics background needed.
> This is **NOT the per-session runbook** ([RUNBOOK.md](RUNBOOK.md) has bring-up order, terminals
> and services): it is the **background, procedure and exit criteria** per scenario, plus our
> corrections to CMU's write-ups. ⚠️ The lab has **ONE** Starling, so every multi-drone scenario
> is a **SIM procedure** with a "Real flight" subsection marked `⏳ blocked on a 2nd Starling (M7)`.
> All of it comes from CMU branch `yikuan/SVG_ground_control` @ `cf719f0`, vendored
> **2026-10-07**, and **none of it is validated by this lab yet** — validation happens at STE.
> Read every ✅ below as "CMU says so", not "we flew it".

---

*(Unfamiliar term? → [GLOSSARY.md](GLOSSARY.md))*

## 1 · The CBF, in plain terms

A **Control Barrier Function (CBF)** is a math filter sitting between *what the commander wants*
and *what actually goes out to the drones*. Every control tick (20 Hz) the commander computes a
desired velocity per drone — "fly 1.2 m/s toward your goal" — and before those are published the
filter asks: *does any pair of drones get closer than allowed?* If so it finds the **nearest safe
set** and sends that instead. The commander has its foot on the accelerator; the CBF is lane-keep
assist — it does not choose the destination, it nudges the wheel, **as little as possible**.
Three numbers define it (per config, all live-tunable — §3):

| Knob | Plain meaning |
|---|---|
| `cbf_safety_radius_m` (**r**) | Each drone's personal bubble. The filter keeps every pair of **centres** more than **2r** apart. Our configs all ship `r = 0.55` m, i.e. a **1.1 m** minimum centre-to-centre gap. |
| `cbf_alpha` (**α**) | **How early** it starts yielding. **Lower = earlier and gentler**; higher = it lets drones get closer, then corrects hard. All configs ship `2.5`. At α=1.0 with a 1 m/s approach a drone starts yielding ~3.2 m out; at α=2.5, ~2.4 m out ([`squeeze_rc_intruder.yaml:134-137`](../AirStack/robot/ros_ws/src/svg_ground_control/config/squeeze_rc_intruder.yaml)). |
| `cbf_max_speed_mps` | Ceiling on **every** velocity the filter emits — so also the **dodge authority**: how fast a drone is allowed to jump out of the way. |

**The NEW idea on this branch: "fixed rows."** Older versions split every pairwise correction
50/50 — each drone did half the dodge. That is wrong when one of the two is **not going to
dodge** (an RC-flown intruder, or a drone in `cbf_exempt_drones`): its half of the evasion was
computed, assigned, and never executed, so real separation was half of what the filter believed.
Such a drone is now a **fixed row** — the solver takes its velocity as *ground truth* and may not
adjust it, so the others absorb **100 % of the dodge**. Two flavours:

- **External drone** (`external_drones`) — tracked but never commanded. Pinned at
  `cbf_external_velocity_gain × its measured velocity` (PX4 EKF2, ENU;
  [`swarm_commander.py:1810-1825`](../AirStack/robot/ros_ws/src/svg_ground_control/svg_ground_control/swarm_commander.py)),
  so the others yield **before** it reaches the barrier, not after.
- **Exempt drone** (`cbf_exempt_drones`) — commanded, published uncorrected. Speed-capped first
  (that cap is what flies), then pinned (`:1865-1889`).

A drone may be external **or** exempt, never both (`:556-561` raises). Only **ACTIVE** drones are
eligible for exemption, so climb-out and landing stay collision-protected (`:1860-1867`).

**Emergency push-apart.** Drones already inside each other's bubbles = no solution, so the filter
abandons optimality and shoves the violating pairs apart along the line between them, capped at
`cbf_max_speed_mps` ([`cbf_filter.py:512-549`](../AirStack/robot/ros_ws/src/svg_ground_control/svg_ground_control/cbf_filter.py)).
Fixed rows are left alone; all-fixed pairs are skipped entirely. Logged as `CBF emergency
push-apart engaged`. **A failure, not a feature — land.**

## 2 · 🚨 Safety brief for every scenario

Read this before any CBF flight, sim or real. It is in addition to [PREFLIGHT.md](PREFLIGHT.md).

- **The CBF is not a motor cutoff.** It clips and re-aims velocity commands. A clipped drone is
  still armed and still flying. The only true cutoff remains **ch8 on the RC**.
- **Two exempt (or external) drones have NO mutual protection.** Both-fixed pairs are *pruned out
  of the solve entirely* (`cbf_filter.py:198-216`) and skipped by the push-apart (`:512-549`) —
  stated nowhere in CMU's docs. **Never exempt two drones at once** unless two separate pilots
  are keeping them apart by eye.
- **An exempt drone's pilot IS its safety authority.** The filter will not save it, and cannot
  protect anything from it beyond what the other drones can do themselves.
- ⚠️ **`cbf_max_speed_mps: 10.0`** is what all three real configs ship (`goal_tracking.yaml`,
  `goal_single.yaml`, `squeeze_rc_intruder.yaml`) — **10 m/s of dodge authority indoors**. CMU's
  own analysis says the room cannot deliver it (§9), but a *dodge* is a short burst and 10 m/s in
  a net is a wall strike. **Drop it before our first real multi-drone flight**: start at `1.0` (the value CONFIG.md sets for M3/M4)
  (the `cbf_sim.yaml` value) and raise deliberately.
- **`hold_all` freezes EVERYONE, including an airborne RC-flown drone.** On this branch the
  latch is armed by any **ACTIVE** drone of **any role** — external drones included, judged by
  "fresh odometry and above `land_complete_altitude_m`" (`swarm_commander.py:1493-1507`). A
  silent change from earlier behaviour. The intruder's pilot must be briefed that the autonomous
  drones can all stop dead because *he* clipped a wall.
- **Stale external odometry silently degrades to position-only.** A stale external row falls back
  to **zero velocity** (`:1810-1825`) with no per-drone warning: the filter then believes the
  intruder is hovering and the holders yield **late**. Watch its odometry rate, not its marker.
- **LEDs all red at once = emergency push-apart → land and investigate** (`README.md:328-329`).
  Red on one or two drones is normal CBF activity. Related: **keep goals and holder posts more
  than 2r = 1.1 m apart** — closer is permanently infeasible and nobody ever arrives.

## 3 · Runtime gains — tuning while airborne

The three CBF gains are **live**. Container shell:

```bash
ros2 param set /swarm_commander cbf_alpha 4.0              # yield later, harder
ros2 param set /swarm_commander cbf_safety_radius_m 0.8    # wider berth
ros2 param set /swarm_commander cbf_max_speed_mps 1.5      # dodge/flight speed cap
```

They apply **on the next control tick**. Anything not live is refused with a reason naming what
*is* (`swarm_commander.py:920-1033`). Also live: `teleop_max_speed_mps`, `goal_lead_m`,
`teleop_kp`, `teleop_lead_m`, `teleop_accel_mps2`, `hover_kp`, `hold_lead_m`,
`takeoff_speed_mps`, `fence_keep_in_gain`, `fence_brake_accel_mps2`, `fence_margin_m`,
`scenario_speed_mps`, `goal_accel_mps2`, `goal_settle_s`, `goal_velocity_only_settle_s`.
**Not live:** `cbf_external_velocity_gain`, every fence **box**, every name list, every scenario
geometry — yaml edit + relaunch (RUNBOOK §C7). Three gotchas:

- **`POSITIVE_PARAMS`** (the three CBF gains + `fence_keep_in_gain`) are refused if **≤ 0** or
  non-finite — `1/gain` is the envelope's lag, so zero would divide by it.
- **The scenario keeps its BUILD-time radius.** Raising `cbf_safety_radius_m` in flight changes
  the *filter*, the speed cap and the viz spheres — but **not** the spacing checks the scenario
  made at startup (holder posts, initial layout, goal sampling), which used the yaml value
  (`swarm_commander.py:92-94`). A runtime bump does **not** re-space your goals.
- The **SVG Basestation** panel's CBF slider row does exactly this (`set_parameters` on
  `swarm_commander`) — slider, number box, then that row's **Apply**.

## 4 · Scenario catalogue

`scenario:` in the config picks the nominal-velocity policy. Status glyphs: **✅ CMU** = CMU
reports it working · **⏳ STE sim** = our sim rehearsal, M1, not yet run · **⏳ M7 real** =
needs a second Starling.

| Scenario | What it does | Config that ships it | Drones | Status |
|---|---|---|---|---|
| `hover` | Hold fixed `hover_positions`. The baseline; nothing crosses. | `swarm_real.yaml`, `swarm_sim.yaml`, `teleop_*.yaml` | 1–3 | ✅ CMU · ⏳ STE real (M3 re-do) |
| `goal` | Takeoff targets **are** the initial goals; only moves when you retarget (`goal_command` / `formation_command`). The **only** scenario that honours formation profiles. | *none ship it any more* — use `scenario:=goal` | any | ✅ CMU · ⏳ STE sim |
| `antipodal` | Every drone crosses the arena centre to the opposite side, re-crossing on arrival. Maximum conflict — the CBF demo. | `cbf_sim.yaml` | 3 sim | ✅ CMU · ⏳ STE sim |
| `head_on` | Two facing rows swap sides, repeatedly. | — (`scenario:=head_on`) | even N | ✅ CMU · ⏳ STE sim |
| `squeeze` | Two "holder" drones sit on posts; a third pushes through the gap between them and the holders yield. | `squeeze_3drone.yaml` (sim), `hybrid_squeeze.yaml`, `squeeze_rc_intruder.yaml` (real) | 3 | ✅ CMU · ⏳ STE sim · ⏳ M7 real |
| `random_goals` | Uniform random goals inside the arena; resample on arrival. The unsupervised collision stress test. **Has a known defect — §7.** | `goal_tracking.yaml` | 3 | ✅ CMU · ⏳ STE sim · ⏳ M7 real |

**Override the scenario without editing the yaml** — how you get `goal` or `head_on` out of a
config that ships something else. Container shell:

```bash
ros2 launch svg_ground_control ground_control.launch.py \
  config:=$(ros2 pkg prefix svg_ground_control)/share/svg_ground_control/config/cbf_sim.yaml \
  scenario:=head_on
```

## 5 · CBF demonstration in sim — `cbf_sim.yaml`

**The point of this config.** `goal_tracking.yaml` used to be the CBF demo and demonstrated
nothing: it exempted all three drones (filter off) and ran `goal`, whose initial goals *are* the
takeoff spots, so `start` changed nothing. `cbf_sim.yaml` is that file with three fixes —
`drone_modes: "sim,sim,sim"`, `cbf_exempt_drones: ""` (**every** drone filtered, the whole point),
and `scenario: "antipodal"` so they are forced through each other. Offsets
`[-2,0,0, 0,0,0, 2,0,0]` match the Isaac spawn of 3 drones; `r 0.55` · `vmax 1.2` · `α 2.5` ·
speed `0.6` · fence `[-3,-6,0]..[5,5,3]`, behaviour `hold_all` (the commander's default — the key
is not in this file).

**Procedure (sim — M1).** RUNBOOK §A T1 (spawn 3 Isaac drones) and T2 (`bringup` tmux: pane 0
build, pane 1 interfaces), then in pane 2 — the commander:

```bash
ros2 launch svg_ground_control ground_control.launch.py \
  config:=$(ros2 pkg prefix svg_ground_control)/share/svg_ground_control/config/cbf_sim.yaml
```

Foxglove Studio next (RUNBOOK §A T3, [BASESTATION.md](BASESTATION.md) §2), then the cockpit in
pane 3: `takeoff`, wait for `holding takeoff position` ×3, `start`.

**Watch for.** In the Basestation 3D view the three drones head for the centre and each visibly
**bends around** the others instead of driving through. The per-drone **CBF chip** reads
`correcting` (amber) during the bend, `clear` otherwise; the commander logs `CBF active on:
drone_1, drone_2 (residual 0.0003)` about once a second; with LEDs on, the corrected drones go
red and back to green.

**Exit criterion (M1).** One full crossing cycle in which (a) minimum centre-to-centre distance
never drops below **1.1 m** (`2r`), (b) every drone keeps reaching the far side — no deadlock,
(c) **`CBF emergency push-apart engaged` never appears**. Then repeat with `scenario:=head_on`. A
push-apart in sim means the geometry or the gains are wrong — fix it here, not in the hangar.

**Real flight.** ⏳ blocked on a second Starling (M7). `cbf_sim.yaml` is sim-only by design; a
real version is a copy with `drone_modes: "real,real,real"`, zero offsets, and a `vmax` sane for
the net (§2).

## 6 · Formation profiles — move the whole swarm with one command

A **formation profile** is a named full set of goals: one `x,y,z` row per drone, world ENU, in
`drone_names` order. One message retargets everybody at once and the CBF deconflicts the crossing.
Declared as `formation_profiles` (the name list) plus a `formation_<name>` flat array each —
shipped as `home`, `line`, `triangle`, `diagonal` in both
[`goal_tracking.yaml:99-113`](../AirStack/robot/ros_ws/src/svg_ground_control/config/goal_tracking.yaml)
and [`cbf_sim.yaml:101-113`](../AirStack/robot/ros_ws/src/svg_ground_control/config/cbf_sim.yaml).
Container shell, any time **after `start`**:

```bash
ros2 topic pub --once /svg/formation_command std_msgs/msg/String "{data: triangle}"
ros2 topic pub --once /svg/formation_command std_msgs/msg/String "{data: home}"
ros2 topic pub --once /svg/formation_command std_msgs/msg/String "{data: next}"
```

`next` is **reserved** (it cannot be a profile name) and steps through the profiles in the listed
order, wrapping; naming one explicitly re-anchors the cycle there. External drones are skipped (no
goal to retarget); an unknown name is ignored with a warning listing the valid ones.

> ⚠️ **The trap: profiles are ONLY honoured by the `goal` scenario.** The mechanism needs
> `scenario.set_goal`, which only `GoalScenario` has (`swarm_commander.py:775-810`, `:1312-1338`).
> **Both configs that define profiles ship a scenario that ignores them** — `cbf_sim.yaml` ships
> `antipodal`, `goal_tracking.yaml` ships `random_goals`. You get one startup WARN,
> `formation_profiles set but scenario "random_goals" has no retargetable goals; profiles
> ignored` (`:808-810`), and then silence. **Add `scenario:=goal` to the §5 launch command.**

**Exit criterion (M1).** `formation profiles: diagonal, home, line, triangle` at startup (**not**
the "profiles ignored" WARN); three `next` commands walk the swarm through three layouts; every
pair stays > 1.1 m apart in transit; `home` returns everyone. ⚠️ In `goal_tracking.yaml`
`formation_home` does **not** equal its `hover_positions` despite the comment — §9.

**Real flight.** ⏳ blocked on a second Starling (M7) — single-drone "formations" are just goals,
so use RUNBOOK §C.

## 7 · Random-goal CBF collision test — `random_goals`

**What it is.** Each drone gets a uniformly random goal drawn from `arena_low..arena_high`
**inset 10 %** on every axis; within **0.3 m** of it a fresh one is drawn and it flies off again
(`scenarios.py:238-274`). The initial layout is rejection-sampled at least
`2.4 × cbf_safety_radius_m` = **1.32 m** apart, seeded by `scenario_seed` (`:172`). Nobody is
exempt, so the CBF is the only thing stopping a collision, unsupervised, for as long as you let
it run. This is the stress test that produced CMU's flight bags.

> ⚠️ **KNOWN DEFECT — goals are sampled with no separation from anything**: not from other
> drones, not from their goals. CMU records it at
> [`README.md:208-211`](../AirStack/robot/ros_ws/src/svg_ground_control/README.md) — in bag
> `run_020444`, **100 of 221 legs** had another drone within **1.5 m** of the goal being flown to
> and **one arrival took 68 s**, the drone parked at the barrier because its goal sat inside
> another drone's bubble. Not a crash risk (the filter holds) but a **liveness** failure: the run
> looks hung. Expect it; do not debug it as a mocap fault.
>
> ⚠️ **`arena_low`/`arena_high` is NOT the geofence** and nothing checks one against the other.
> `goal_tracking.yaml` ships arena `[-3,-3,0.5]..[3,3,2.5]` inside fence
> `[-4.5,-5.2,0]..[5.5,5,3]` — *by hand*. Shrink the arena to your net every time; a 10 % inset
> of a too-big arena is still too big.

**Procedure (sim — M1).** RUNBOOK §A T1/T2 to spawn and wire 3 Isaac drones (or
`./svg_teleop.sh hover`, which brings up 3 sim drones in tmux), then in pane 2:

```bash
ros2 launch svg_ground_control ground_control.launch.py \
  config:=$(ros2 pkg prefix svg_ground_control)/share/svg_ground_control/config/cbf_sim.yaml \
  scenario:=random_goals
```

`takeoff` → `start`, then leave it running and watch. **Exit criterion (M1):** ≥ 5 minutes with
(a) no push-apart, (b) minimum pair distance never below 1.1 m, (c) every drone completing a few
legs — one sitting still for a minute is the defect above; record it and restart. There is **no
dedicated random-goal regression test** (coverage is kinematic: `test/test_scenarios.py:20,52`).

**Real flight.** ⏳ blocked on a second Starling (M7). CMU's recipe (`experiment.md:1028-1033`):
three `MicroXRCEAgent udp4 -p 8888|8889|8892 -v4` (one per drone, own terminal) →
`real_interfaces.launch.py drones:=drone_1,drone_2,drone_3` → `ground_control.launch.py
config:=…/goal_tracking.yaml use_mocap:=true` → `takeoff` → `start`. Our rig also needs a mocap
body + EKF2 params + unique DDS domain per drone ([MOCAP.md](MOCAP.md) §6.3),
`cbf_max_speed_mps` off 10.0, and arena = the net.

## 8 · RC-intruder squeeze — `squeeze_rc_intruder.yaml`

**What it is.** Three real drones. `drone_1` / `drone_2` are **holders**: the commander parks them
on two posts 2.2 m apart (`squeeze_holder_positions [0.5, ±1.1, 1.4]`) and the CBF makes them
yield. `drone_3` is **TELEOP** — a human flies it through the gap on a gamepad (`safe_teleop` →
`/svg/drone_3/teleop_command`) and it is **`cbf_exempt_drones: "drone_3"`**: its stick goes out
uncorrected and the holders absorb the entire evasion. Deliberate — a *filtered* intruder is
pushed backwards at the gap and never gets through. Guard rails: `teleop_max_speed_mps 3.0` (the
approach speed the holders must absorb), `teleop_accel_mps2 5.0` (stick ramp), and its **own
smaller teleop fence** `[-3.3,-4.0,1.0]..[4.3,4.2,2.8]` inside the `keep_in` geofence
`[-4.5,-5.2,0]..[5.5,5.0,3.0]` (brake 8 m/s², gain 2 — the commander refuses to start if the
teleop fence is not inside it). `cbf_max_speed_mps: 10.0` ⚠️ (§2). Launch is **two terminals**
(`:12-17`): the pad first, checked before anything arms, then the commander.

**Procedure (sim rehearsal — M1).** The sim analogue is not this file (it is all-real) but
`swarm_sim.yaml` + `scenario:=squeeze teleop_drones:=drone_3`, which `svg_teleop.sh` wires up
([TELEOP.md](TELEOP.md) §4 for the gamepad). Laptop:

```bash
cd ~/AirStack-starling-max2/AirStack/robot/ros_ws/src/svg_ground_control/scripts
./svg_teleop.sh squeeze          # Isaac + agent + interfaces + commander + pad, in tmux
./svg_teleop.sh takeoff ; ./svg_teleop.sh start    # then control is on the sticks
./svg_teleop.sh monitor          # live sticks + commanded velocity
./svg_teleop.sh land ; ./svg_teleop.sh stop
```

The sim intruder is exempt via the **scenario** (`squeeze_intruder_cbf_exempt: true`, default)
rather than `cbf_exempt_drones` — the two are unioned, so the behaviour is identical.

**Exit criterion (M1).** With the stick pressed steadily through the gap: both holders visibly
**back off before** the intruder reaches them (that is the fixed-row velocity term working), the
intruder passes **through**, holder-to-intruder distance stays ≥ 1.1 m, the holders return to
their posts, no push-apart. Repeat with a fast stick jab. An intruder pushed *back* at the gap
means its exemption is not in effect.

**Real flight.** ⏳ blocked on a second Starling (M7) — and on a **second briefed pilot**: one on
the gamepad flying the intruder, a separate safety pilot with the RC and a thumb on ch8. Three
drones = three agent ports, mocap bodies, EKF2 param sets and DDS domains. Before that day fix
`cbf_max_speed_mps`, and brief the gamepad pilot that a fence latch or a `hold` can freeze the
holders around him (§2).

## 9 · Corrections to CMU's `experiment.md` / `README.md` / configs for OUR rig

CMU's docs are the source of truth for everything not listed here. These are wrong, stale, or
silently self-contradicting on the `cf719f0` snapshot (checked 2026-10-07).

| CMU says | On this snapshot / our rig |
|---|---|
| `README.md:300` "`cbf_filter.py` is a **verbatim port** of `drone_soccer/cbf.py`"; `:294` "the **unchanged** CBF suite" | **False.** The whole fixed-row mechanism is new: `fixed` argument (`cbf_filter.py:140`), movable mask (`:183`), pruning that **drops** pairs with no movable drone (`:198-216`), speed clamp on movable rows only (`:242`), fixed rows pinned through both Dykstra phases (`:322-379`), push-apart skipping fixed rows and all-fixed pairs (`:512-549`). `test/test_cbf.py:111,125,144,163` are the new tests for it. |
| `cbf_external_velocity_gain` | Documented **nowhere** outside the source. It scales an external drone's measured velocity into its fixed row (`swarm_commander.py:1810-1825`), default `1.0`, and is **NOT runtime-settable** — yaml + relaunch. |
| `experiment.md:976-1066` (§C2) teaches `goal_tracking.yaml` via per-drone `goal_command`, `speed_command` and formation profiles | `goal_tracking.yaml` now ships **`scenario: random_goals`**. Under `random_goals` there is no `set_goal`, so **every one of those recipes silently does nothing** (formations get one WARN; goals are ignored). Add `scenario:=goal` to the launch to follow §C2 as written. |
| `goal_tracking.yaml:81-82` comment "goal scenario: takeoff targets = initial goals" above `hover_positions` | Dead comment. Under `random_goals` the takeoff layout comes from `_random_positions` (`scenarios.py:172`), not `hover_positions`. |
| `goal_tracking.yaml:100` `formation_home` commented "= hover_positions: one command brings everyone back" | It is **not** equal. `hover_positions` is `[0,-2,1.2, -1,0,1.2, 0,2,1.2]`; `formation_home` is `[0,-1,1.2, -1,1,1.2, 0,3,1.2]`. (`cbf_sim.yaml`'s pair *does* match.) |
| `cbf_sim.yaml:49-51` header advertises "send the WHOLE swarm to a named formation profile" | It ships `scenario: antipodal`, which has no retargetable goals — the profiles are **ignored**. Use `scenario:=goal` (§6). |
| `squeeze_rc_intruder.yaml:163-170` describes `keep_in` as "outward speed ≤ gain × distance to the wall" | Stale. It is a **braking envelope** now: full speed until the true braking distance for `fence_brake_accel_mps2`, then brake, with the deceleration fed forward to PX4. The gain only sets the near-wall lag margin. Correct text is 10 lines further down at `:172-179`. |
| `experiment.md:1525-1529` "Automated tests" lists 3 pytest files | There are **17** test files (11 pytest + 6 `functional_*`). Full list in §11. `README.md:291` claims "140 tests"; the files hold **126** `def test_` functions, so some are parametrized — do not treat 140 as the pass target, treat "0 failed" as the pass target. |
| `fence_behavior: hold_all` latching | Now latched by any **ACTIVE** drone of **any role**, including an airborne **external** drone (`swarm_commander.py:1493-1507`). A behaviour change CMU does not call out. Brief the intruder's pilot (§2). |
| — (stated nowhere) | **There is no protection between two fixed rows.** Pairs with no movable drone are pruned from the solve and skipped by the push-apart. Two exempt or external drones are on their own. |
| `experiment.md:884-887` "10 m/s needs ~15.5 m even at 8 m/s² — not in this room" | Agreed — and yet `goal_tracking.yaml`, `goal_single.yaml` and `squeeze_rc_intruder.yaml` all ship `cbf_max_speed_mps: 10.0` **and** `scenario_speed_mps: 10.0` **and** `goal_accel_mps2: 10.0`. Our net is far smaller than CMU's 10 × 9.7 m box. **Lower all three before flying.** Also honour `experiment.md:888`: keep `fence_brake_accel_mps2 ≥ goal_accel_mps2`, or the wall envelope caps the cruise first — the real configs ship brake **8** against accel **10**, which violates it. |
| `goal_single.yaml` is "the single-drone goal config" | It now targets **`drone_2`**, not `drone_1`, and exempts it (`cbf_exempt_drones: "drone_2"` — harmless with one drone). On our rig the body is `drone_1`: edit `drone_names` or it reports "no odometry" forever. Its `land_speed_mps` is also `0.8`, not the `0.6` we validated ([CONFIG.md](CONFIG.md)). |
| Real drones take velocity commands | Default is now **`real_command_mode: trajectory`** → `/{name}/fmu/trajectory_command` (`MultiDOFJointTrajectory`, `swarm_commander.py:415-418`). **`px4_interface` must be rebuilt** (`bws --packages-select px4_interface`) or the drone just hovers; `real_command_mode: velocity` restores the old `TwistStamped`. Also new and undocumented in our docs: `/svg/{name}/goal_xyzt` (`Float64MultiArray [x,y,z,theta_deg]`), the first way to command **yaw**. |

## 10 · Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `goal_command` / `speed_command` published, drone ignores it | The config ships `random_goals` (`goal_tracking.yaml`) — that scenario has no retargetable goal. Relaunch with `scenario:=goal` (§4). Also: `start` must have been called. |
| `formation_profiles set but scenario "X" has no retargetable goals; profiles ignored` | Expected on `cbf_sim.yaml` (`antipodal`) and `goal_tracking.yaml` (`random_goals`). Relaunch with `scenario:=goal` (§6). |
| A drone refuses to close the last metre to its goal / hangs for a minute | The CBF is holding it off a barrier. Under `random_goals` this is the §7 defect (the goal is inside another drone's bubble). Not a mocap fault. Lower `cbf_safety_radius_m`, or re-seed, or move on. |
| `CBF active on: …` logged continuously, drones crawl | Goals or posts closer than `2r` (1.1 m), or `cbf_alpha` too low (yielding far too early). Re-space the targets, or raise α — remembering the scenario keeps its build-time radius (§3). |
| `CBF emergency push-apart engaged` | Drones already inside each other's bubbles — the QP is infeasible. **Land and investigate** (CMU `README.md:328`). All LEDs red is the same message. |
| An exempt/RC drone is shoved backwards instead of pushing through | Its exemption is not in effect. Check the startup roster line for `/cbf-exempt` on that name, that it is **ACTIVE** (climb-out and landing are never exempt, `:1860-1867`), and that `cbf_exempt_drones` spells the name exactly. |
| Holders yield **late**, only once the intruder is on top of them | The intruder's fixed row has zero velocity: its odometry is stale (external) so the filter thinks it is hovering (`:1810-1825`). Check `ros2 topic hz /drone_3/odometry_conversion/odometry`. |
| Everyone freezes mid-air when only the RC drone misbehaved | `fence_behavior: hold_all` now latches on airborne external/teleop drones too. `land` → `/swarm_commander/reset_fence` → `takeoff` → `start`. |
| `ros2 param set` refused ("read once at startup" / "must be finite and > 0") | Not a live parameter — the message lists what is; or the `POSITIVE_PARAMS` guard rejecting ≤ 0. Yaml + relaunch (RUNBOOK §C7). Note a live radius bump does **not** re-space goals (§3). |
| Real drone arms and then just hovers, commands look fine | `real_command_mode: trajectory` with a stale `px4_interface`. `bws --packages-select px4_interface`, re-source, relaunch. |
| Fake odometry on real topics, drone lurches | A `test/functional_*.py` is running. **Never with the real stack up** — they publish fake odometry on the live topic names. Kill it and restart the stack. |

## 11 · Technical appendix

Paths relative to `AirStack/robot/ros_ws/src/svg_ground_control/`.

| Piece | Location | Role |
|---|---|---|
| CBF solver | `svg_ground_control/cbf_filter.py` | `filter_velocities` → barrier constraints + pruning + parallel/Gauss-Seidel Dykstra + push-apart. `fixed` rows: `:140`, `:183`, `:198-216`, `:242`, `:322-379`, `:512-549` |
| Commander | `svg_ground_control/swarm_commander.py` | External→fixed row `:1810-1825` · exempt rows `:1865-1889` · runtime params `:920-1033` · formations `:775-810`, `:1312-1338` · fence latch `:1493-1507` |
| Scenario policies | `svg_ground_control/scenarios.py` | `_random_positions :172` · `RandomGoalsScenario :238-274` · `GoalScenario.set_goal :488`, `set_all_speeds :496` · registry `_SCENARIOS :518` |
| Go-to-goal profile | `svg_ground_control/trajectory.py` | `brake_speed :53` · `stopping_distance :64` · `seek_velocity :70` · `ReferenceTracker :92` |
| The three configs | `config/cbf_sim.yaml` (NEW, 3 sim, `antipodal`, nobody exempt, vmax 1.2) · `config/goal_tracking.yaml` (now 3 **real**, `random_goals`, speed/vmax/accel 10.0, `keep_in`) · `config/squeeze_rc_intruder.yaml` (NEW, 3 real, `drone_3` teleop + exempt, own teleop fence) | Per-scenario parameters; read once at launch |
| CBF telemetry | `/svg/cbf_active` · `/svg/commander_status` | `cbf_active` = `std_msgs/String`, comma-separated names, **every tick** (`:1909-1917`), drives the LEDs and the panel. The status snapshot carries `cbf{alpha, safety_radius_m, max_speed_mps, external_velocity_gain, active, emergency}` |
| Goal inputs | `/svg/{name}/goal_command` (PoseStamped) · `/svg/{name}/goal_xyzt` (Float64MultiArray `[x,y,z,theta_deg]`) · `/svg/{name}/speed_command` (Float32) · `/svg/formation_command` (String) | All after `start` only |
| Operator tooling | `scripts/svg_teleop.sh` · `foxglove/svg-basestation/` | `svg_teleop.sh solo\|squeeze\|hover` brings up Isaac + agent + interfaces + commander + pad in tmux. The panel has the CBF slider row (α / r / vmax), the per-drone CBF chip and the mission chip |

**Tests** — inside the robot container, at the package directory:

```bash
cd ~/AirStack/robot/ros_ws/src/svg_ground_control
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -q -p no:cacheprovider test/
```

Eleven pytest files (126 `def test_` functions; `README.md:291` says "140 tests", so some are
parametrized — the M1 pass target is **0 failed**, not a count): `test_cbf.py`,
`test_scenarios.py`, `test_exempt.py`, `test_fence_and_position_hold.py`, `test_feedforward.py`,
`test_trajectory.py`, `test_formations.py`, `test_runtime_params.py`, `test_live_speed.py`,
`test_led_packet.py`, `test_teleop_controllers.py`. Plus six closed-loop scripts run by hand
against a live commander: `functional_single_goal_test.py`, `functional_multi_goal_test.py`,
`functional_hybrid_test.py`, `functional_squeeze_test.py`, `functional_squeeze_lag_test.py`,
`functional_fence_test.py`.
🚨 **The `functional_*` scripts publish FAKE odometry onto the live topic names. NEVER run one
with the real stack up** — flyaway risk. Iron rule 4 in [CLAUDE.md](../CLAUDE.md).
