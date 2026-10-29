# SCENARIOS — the CBF collision filter and the multi-drone flights

> **Who this is for:** anyone in the AI.R / STC lab who wants to understand or run the
> **multi-drone** parts of AirStack — the CBF collision-avoidance filter, the formation profiles,
> the random-goal collision test, the RC-flown-intruder squeeze. No robotics background needed.
> This is **NOT the per-session runbook** ([RUNBOOK.md](RUNBOOK.md) has bring-up order, terminals
> and services): it is the **background, procedure and exit criteria** per scenario, plus our
> corrections to CMU's write-ups. ⚠️ The lab has **ONE** Starling, so every multi-drone scenario
> is a **SIM procedure** with a "Real flight" subsection marked `⏳ blocked on a 2nd Starling (M7)`.
>
> **Read first:** [GLOSSARY.md](GLOSSARY.md) (CBF, scenario, fence…), then [RUNBOOK.md](RUNBOOK.md)
> §A for the sim session this runs in. "The commander" = the `swarm_commander` node; "the panel" =
> the Foxglove SVG Basestation ([BASESTATION.md](BASESTATION.md)); "the real drone" = our Starling 2 Max.
>
> All of it comes from CMU branch `yikuan/SVG_ground_control` @ `cf719f0`, vendored
> **2026-10-07**, bumped **2026-10-20** to `yikuan/SVG_ground_control_dev` @ `b21d28c` (added
> `goal_sequence` and `figure_eight` — rows below, experiment.md C3 / C7 — and put
> `goal_tracking.yaml` back on `goal`). **Sim validation has started** (ledger #1–#4 on
> 2026-10-19, #8 and #13 on 10-20/21 — [record/LEDGER.md](record/LEDGER.md)); **nothing has flown
> on the real drone.** Read every ✅ CMU below as "CMU says so", not "we flew it".

---

*(Unfamiliar term? → [GLOSSARY.md](GLOSSARY.md))*

## 1 · The CBF, in plain terms

A **Control Barrier Function (CBF)** is a math filter sitting between *what the commander wants*
and *what actually goes out to the drones*. Every control tick (20 Hz) the commander computes a
desired velocity per drone — "fly 2.0 m/s toward your goal" — and before those are published the
filter asks: *does any pair of drones get closer than allowed?* If so it finds the **nearest safe
set** and sends that instead. The commander has its foot on the accelerator; the CBF is lane-keep
assist — it does not choose the destination, it nudges the wheel, **as little as possible**.
Three numbers define it (per config, all live-tunable — §3):

| Knob | Plain meaning |
|---|---|
| `cbf_safety_radius_m` (**r**) | Each drone's personal bubble. The filter keeps every pair of **centres** more than **2r** apart. Our configs all ship `r = 0.55` m, i.e. a **1.1 m** minimum centre-to-centre gap. |
| `cbf_alpha` (**α**) | **How early** it starts yielding. **Lower = earlier and gentler**; higher = it lets drones get closer, then corrects hard. All configs ship `2.5`. At α=1.0 with a 1 m/s approach a drone starts yielding ~3.2 m out; at α=2.5, ~2.4 m out (the comment above `cbf_alpha` in [`squeeze_rc_intruder.yaml`](../AirStack/robot/ros_ws/src/svg_ground_control/config/squeeze_rc_intruder.yaml)). |
| `cbf_max_speed_mps` | Ceiling on **every** velocity the filter emits — so also the **dodge authority**: how fast a drone is allowed to jump out of the way. |

**The NEW idea on this branch: "fixed rows."** Older versions split every pairwise correction
50/50 — each drone did half the dodge. That is wrong when one of the two is **not going to
dodge** (an RC-flown intruder, or a drone in `cbf_exempt_drones`): its half of the evasion was
computed, assigned, and never executed, so real separation was half of what the filter believed.
Such a drone is now a **fixed row** — the solver takes its velocity as *ground truth* and may not
adjust it, so the others absorb **100 % of the dodge**. Two flavours:

- **External drone** (`external_drones`) — tracked but never commanded. Pinned at
  `cbf_external_velocity_gain × its measured velocity` (PX4 EKF2, ENU; the `fixed_rows` block of
  [`SwarmCommander.control_loop`](../AirStack/robot/ros_ws/src/svg_ground_control/svg_ground_control/swarm_commander.py)),
  so the others yield **before** it reaches the barrier, not after.
- **Exempt drone** (`cbf_exempt_drones`) — commanded, published uncorrected. Speed-capped first
  (that cap is what flies), then pinned (same function, the exempt block).

A drone may be external **or** exempt, never both (the roster check in `SwarmCommander.__init__`
raises). Only **ACTIVE** drones are eligible for exemption, so climb-out and landing stay
collision-protected (`control_loop`).

**Emergency push-apart.** Drones already inside each other's bubbles = no solution, so the filter
abandons optimality and shoves the violating pairs apart along the line between them, capped at
`cbf_max_speed_mps` ([`_emergency_push_apart` in `cbf_filter.py`](../AirStack/robot/ros_ws/src/svg_ground_control/svg_ground_control/cbf_filter.py)).
Fixed rows are left alone; all-fixed pairs are skipped entirely. Logged as `CBF emergency
push-apart engaged`. **A failure, not a feature — land.**

## 2 · 🚨 Safety brief for every scenario

Read this before any CBF flight, sim or real. It is in addition to [PREFLIGHT.md](PREFLIGHT.md).

- **The CBF is not a motor cutoff.** It clips and re-aims velocity commands. A clipped drone is
  still armed and still flying. The only true cutoff remains **ch8 on the RC**.
- **Two exempt (or external) drones have NO mutual protection.** Both-fixed pairs are *pruned out
  of the solve entirely* (the movable-pair pruning in `cbf_filter.solve_safe_commands`) and skipped by the push-apart (`_emergency_push_apart`) —
  stated nowhere in CMU's docs. **Never exempt two drones at once** unless two separate pilots
  are keeping them apart by eye.
- **An exempt drone's pilot IS its safety authority.** The filter will not save it, and cannot
  protect anything from it beyond what the other drones can do themselves.
- ⚠️ **`cbf_max_speed_mps: 10.0`** is what five CMU real configs ship (`goal_tracking.yaml`,
  `goal_single.yaml`, `squeeze_rc_intruder.yaml`, `goal_sequence.yaml`,
  `figure_eight_rc_intruder.yaml`) — **10 m/s of dodge authority indoors**. CMU's own analysis
  says the room cannot deliver it (§9), but a *dodge* is a short burst and 10 m/s in a net is a
  wall strike. **Drop it before our first real multi-drone flight**: start at `1.0` (what the
  `_ours` configs set for M3/M4, [CONFIG.md](CONFIG.md)) and raise deliberately. (`cbf_sim.yaml`'s
  4.0 is **sim-only — never port to the drone**.)
- **`hold_all` freezes EVERYONE, including an airborne RC-flown drone.** On this branch the
  latch is armed by any **ACTIVE** drone of **any role** — external drones included, judged by
  "fresh odometry and above `land_complete_altitude_m`" (`SwarmCommander.enforce_fence`). A
  silent change from earlier behaviour. The intruder's pilot must be briefed that the autonomous
  drones can all stop dead because *he* clipped a wall.
- **Stale external odometry silently degrades to position-only.** A stale external row falls back
  to **zero velocity** (`control_loop`) with no per-drone warning: the filter then believes the
  intruder is hovering and the holders yield **late**. Watch its odometry rate, not its marker.
- **LEDs all red at once = emergency push-apart → land and investigate** (CMU `README.md`, LED section).
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
*is* (`SwarmCommander.on_parameter_change`). The live set is `_RUNTIME_ATTRS` +
`_SCENARIO_PARAMS` in `swarm_commander.py` — besides the three CBF gains: `teleop_max_speed_mps`,
`goal_lead_m`, `teleop_kp`, `teleop_lead_m`, `teleop_accel_mps2`, `hover_kp`, `hold_lead_m`,
`takeoff_speed_mps`, **`land_settle_s`, `land_disarm_retry_s`, `land_disarm_retries`** (ours,
2026-10-19/20 — §5), `fence_keep_in_gain`, `fence_brake_accel_mps2`, `fence_margin_m`,
`scenario_speed_mps`, `goal_accel_mps2`, `goal_settle_s`, `goal_velocity_only_settle_s`.
**Not live:** `cbf_external_velocity_gain`, `land_speed_mps`, every fence **box**, every name
list, every scenario geometry — yaml edit + relaunch (RUNBOOK §C7). Three gotchas:

- **`POSITIVE_PARAMS`** (the three CBF gains + `fence_keep_in_gain`, `teleop_max_speed_mps`,
  `goal_accel_mps2`) are refused if **≤ 0** or non-finite — `1/gain` is the envelope's lag, so
  zero would divide by it, and a zero stick cap or profile acceleration would freeze the drone.
  **`NON_NEGATIVE_PARAMS`** = `goal_settle_s` (0 allowed: no exponential tail).
- **The scenario keeps its BUILD-time radius.** Raising `cbf_safety_radius_m` in flight changes
  the *filter*, the speed cap and the viz spheres — but **not** the spacing checks the scenario
  made at startup (holder posts, initial layout, goal sampling), which used the yaml value
  (`make_scenario` is called once in `SwarmCommander.__init__`). A runtime bump does **not**
  re-space your goals.
- The panel's **runtime-gain dropdown** does exactly this (`set_parameters` on
  `swarm_commander`) for six of them — the three CBF gains, `teleop_max_speed_mps` (also pushed
  to `safe_teleop`), `goal_accel_mps2`, `goal_settle_s`: pick the gain, slider or number box,
  then **Apply** ([BASESTATION.md](BASESTATION.md) §3.4). The slider ends at a panel setting
  (`cbfSpeedMax` default 3 m/s — `cbf_sim`'s 4.0 is past the end: type it in the number box).

## 4 · Scenario catalogue

`scenario:` in the config picks the nominal-velocity policy — nine are registered in
`scenarios.py` (`_SCENARIOS`): `hover`, `goal`, `random_walk`, `random_goals`, `head_on`,
`antipodal`, `squeeze`, `goal_sequence`, `figure_eight`. Status glyphs: **✅ CMU** = CMU reports
it working · **✅ STE sim** = we ran it in Isaac Sim (ledger number given) · **⏳ STE sim** = our
sim rehearsal, M1, not yet run · **⏳ M7 real** = needs a second Starling.

| Scenario | What it does | Config that ships it | Drones | Status |
|---|---|---|---|---|
| `hover` | Hold fixed `hover_positions`. The baseline; nothing crosses. | `swarm_real.yaml`, `swarm_sim.yaml`, `teleop_*.yaml` | 1–3 | ✅ CMU · ⏳ STE real (M3 re-do) |
| `goal` | Takeoff targets **are** the initial goals; only moves when you retarget (`goal_command` / `goal_xyzt` / `formation_command`). The **only** scenario that honours formation profiles. | `goal_single.yaml` / **`goal_single_ours.yaml`** (1 drone), `goal_tracking.yaml` (3 real, back on `goal` at `b21d28c`), `goal_tracking_original.yaml`; else `scenario:=goal` | any | ✅ CMU · ✅ STE sim steps (ledger #3, old gains) · ⏳ re-run |
| `antipodal` | Every drone crosses the arena centre to the opposite side, re-crossing on arrival. Maximum conflict — the CBF demo. | **`cbf_sim.yaml`** — at **our** speeds since 2026-10-20 (cruise 2.0, cap 4.0, accel 6) | 3 sim | ✅ CMU · ✅ STE sim at 0.6 / 1.2 (ledger #4) · ⏳ at 2.0 / 4.0 |
| `head_on` | Two facing rows swap sides, repeatedly. | — (`scenario:=head_on`) | even N | ✅ CMU · ⏳ STE sim |
| `random_walk` | Each drone wanders on a random heading inside the arena, bouncing off the arena walls; no goals at all. The simplest "everything moves" smoke test. | — (`scenario:=random_walk`) | any | ✅ CMU · ⏳ STE sim |
| `squeeze` | Two "holder" drones sit on posts; a third pushes through the gap between them and the holders yield. | `squeeze_3drone.yaml` (sim), `hybrid_squeeze.yaml`, `squeeze_rc_intruder.yaml` (real) | 3 | ✅ CMU · ⏳ STE sim · ⏳ M7 real |
| `random_goals` | Uniform random goals inside the arena; resample on arrival. The unsupervised collision stress test. **Has a known defect — §7.** | — (`scenario:=random_goals`; `goal_tracking.yaml` shipped it at `cf719f0`, ships `goal` again at `b21d28c`) | 3 | ✅ CMU · ✅ STE sim 2026-10-20/21 (ledger #8, video §7) · ⏳ M7 real |
| `goal_sequence` (new 2026-10-20) | **Scripted goal sets** played automatically: K sets of one goal per drone, laid out so the straight legs cross; the CBF alone deconflicts. Advances when everyone has arrived (or on a timer), loops. `/svg/sequence_command` takes `next` / a step name / `pause` / `resume`. Detail below the table. | `goal_sequence.yaml` (3 real, `keep_in`) — `scenario:=goal_sequence` on `cbf_sim.yaml` needs the `sequence_*` keys copied in | 3 | ✅ CMU · ⏳ STE sim · ⏳ M7 real |
| `figure_eight` (new 2026-10-20) | **Collision-negligent pair + intruder**: drones 0 and 1 fly the SAME figure-eight half a period apart, meet head-on at the crossing every half period and swap lobes — nothing but the CBF between them. Drone 2 hovers as, or is hand-flown as, a CBF-exempt intruder. Detail below the table. | `figure_eight_rc_intruder.yaml` (3 real + pad) | 3 | ✅ CMU · ⏳ STE sim · ⏳ M7 real |

**`goal_sequence` detail.** Sets are `sequence_steps` + one `sequence_<name>` array each, all inside
the arena, pairs ≥ 2r (ends swap head-on, three-way crossing, rotating triangle). The next set
starts once everyone has been within `sequence_arrival_m` for `sequence_dwell_s`, or on a
`sequence_period_s` timer (`sequence_advance`); `/svg/sequence_command` is `std_msgs/String`. Legs
are drawn as `path` markers.

**`figure_eight` detail.** Two touching circles; radius / centre distance / heading / plane tilt /
sense per drone are the `figure_eight_*` params. Drone 2 starts at `figure_eight_intruder_start`.
Carrots are time-parametrised, so a pushed drone is pulled back into the next meeting. Order
`[lobe A, lobe B, intruder]`.

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
`[-2,0,0, 0,0,0, 2,0,0]` match the Isaac spawn of 3 drones; `r 0.55` · `α 2.5` · fence
`[-3,-6,0]..[5,5,3]`, behaviour `hold_all` (the commander's default — the key is not in this
file). **Since 2026-10-20 the file carries OUR speeds** (real-demo numbers, **sim-only — never
port to the drone**): cruise `scenario_speed_mps` **2.0**, cap `cbf_max_speed_mps` **4.0**,
`goal_accel_mps2` **6.0** (CMU shipped 0.6 / 1.2 / 3.0). The sim airframe's PX4 speed limits
were raised in the same commit so PX4 no longer clips at 3 m/s ([CONFIG.md](CONFIG.md) "Sim
airframe"). `ros2 param set` overrides any of the three live.

**Landing, since 2026-10-19/20 (ours).** `land` → every drone enters LANDING and descends at
`land_speed_mps` (1.0 here). At z ≤ `land_complete_altitude_m` (0.15) the commander **keeps
commanding the descent for `land_settle_s`** (2.0 s — the drone is pressed onto the floor), then
sends DISARM. A DISARM the interface rejects ("not landed") is **resent every
`land_disarm_retry_s`** (1.0 s), up to `land_disarm_retries` (5) times; then the drone is declared
IDLE anyway with an ERROR line. Expected log: `landed, disarmed` ×3 on a clean run; on a denied
one, `disarm -> success=False` followed by a retry a second later. All three are **live**
parameters (§3). Why: CMU's instant disarm was DENIED by PX4 in sim and left the drones armed in
failsafe hover (ledger #5); 2026-10-20 the settle alone was accepted on 1 of 3 drones (ledger #8),
2026-10-21 first try ×3 (ledger #13). Values per config and the real-drone caveat (the retry is
inert there): [CONFIG.md](CONFIG.md) ground-side table.

**Procedure (sim — M1).** Open the session with RUNBOOK §A0 (`tools/sim_terminals.sh` →
tabs **Isaac Sim · Interfaces · Commander · Cockpit**), spawn 3 Starling drones in the Isaac Sim
tab (§A1, with `DRONE_USD` + `PX4_VEHICLE_MODEL`), interfaces in the Interfaces tab (§A2), then in
the **Commander tab** (tmux alternative — RUNBOOK §A "Alternatives to the tabs" — pane 2 of the
`bringup` session):

```bash
ros2 launch svg_ground_control ground_control.launch.py \
  config:=$(ros2 pkg prefix svg_ground_control)/share/svg_ground_control/config/cbf_sim.yaml
```

Foxglove Studio next (RUNBOOK §A3, [BASESTATION.md](BASESTATION.md) §2), then in the
**Cockpit tab** (tmux: pane 3): `takeoff`, wait for `holding takeoff position` ×3, `start`.

**Watch for.** In the Basestation 3D view the three drones head for the centre and each visibly
**bends around** the others instead of driving through. The per-drone **CBF chip** reads
`correcting` (amber) during the bend, `clear` otherwise; the commander logs `CBF active on:
drone_1, drone_2 (residual 0.0003)` about once a second; with LEDs on, the corrected drones go
red and back to green.

**Exit criterion (M1).** One full crossing cycle in which (a) minimum centre-to-centre distance
never drops below **1.1 m** (`2r`), (b) every drone keeps reaching the far side — no deadlock,
(c) **`CBF emergency push-apart engaged` never appears**. Then repeat with `scenario:=head_on`. A
push-apart in sim means the geometry or the gains are wrong — fix it here, not in the hangar.
**Status:** ✅ ledger #4 (2026-10-19) at 0.6 / 1.2 with the old gains — min distance **1.02 m**
(8 cm inside the barrier, the CBF's soft margin) · ⏳ **re-run at 2.0 / 4.0** pending
(the next issue in Linear (snapshot: [MILESTONES.md](MILESTONES.md) "Where each project is") — the only to-do list) with
`tools/sim.sh test crossing --ledger N --issue NEAR-787 <run>` ([TEST_STANDARD](TEST_STANDARD.md); 45 s window, live min-distance plots, gated at 1.10 m).

**Real flight.** ⏳ blocked on a second Starling (M7). `cbf_sim.yaml` is sim-only by design; a
real version is a copy with `drone_modes: "real,real,real"`, zero offsets, and a `vmax` sane for
the net (§2).

## 6 · Formation profiles — move the whole swarm with one command

A **formation profile** is a named full set of goals: one `x,y,z` row per drone, world ENU, in
`drone_names` order. One message retargets everybody at once and the CBF deconflicts the crossing.
Declared as `formation_profiles` (the name list) plus a `formation_<name>` flat array each —
shipped as `home`, `line`, `triangle`, `diagonal` in both
[`goal_tracking.yaml`](../AirStack/robot/ros_ws/src/svg_ground_control/config/goal_tracking.yaml)
and [`cbf_sim.yaml`](../AirStack/robot/ros_ws/src/svg_ground_control/config/cbf_sim.yaml) (their
"Formation profiles" blocks).
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
> `scenario.set_goal`, which only `GoalScenario` has (`SwarmCommander.formation_callback`).
> **`cbf_sim.yaml` defines profiles but ships `antipodal`, which ignores them** (at `cf719f0`
> `goal_tracking.yaml` had the same problem with `random_goals`; at `b21d28c` it ships `goal`
> again and its profiles work). You get one startup WARN, `formation_profiles set but scenario
> "antipodal" has no retargetable goals; profiles ignored` (logged where `__init__` builds the
> scenario), and then silence. **Add `scenario:=goal` to the §5 launch command.**

**Exit criterion (M1).** `formation profiles: diagonal, home, line, triangle` at startup (**not**
the "profiles ignored" WARN); three `next` commands walk the swarm through three layouts; every
pair stays > 1.1 m apart in transit; `home` returns everyone. ⚠️ In `goal_tracking.yaml`
`formation_home` does **not** equal its `hover_positions` despite the comment — §9.

**Real flight.** ⏳ blocked on a second Starling (M7) — single-drone "formations" are just goals,
so use RUNBOOK §C.

## 7 · Random-goal CBF collision test — `random_goals`

**What it is.** Each drone gets a uniformly random goal drawn from `arena_low..arena_high`
**inset 10 %** on every axis; within **0.3 m** of it a fresh one is drawn and it flies off again
(`RandomGoalsScenario` in `scenarios.py`). The initial layout is rejection-sampled at least
`2.4 × cbf_safety_radius_m` = **1.32 m** apart, seeded by `scenario_seed`
(`Scenario._random_positions`). Nobody is
exempt, so the CBF is the only thing stopping a collision, unsupervised, for as long as you let
it run. This is the stress test that produced CMU's flight bags.

> ⚠️ **KNOWN DEFECT — goals are sampled with no separation from anything**: not from other
> drones, not from their goals. CMU records it in the random-goals section of
> [`README.md`](../AirStack/robot/ros_ws/src/svg_ground_control/README.md) — in bag
> `run_020444`, **100 of 221 legs** had another drone within **1.5 m** of the goal being flown to
> and **one arrival took 68 s**, the drone parked at the barrier because its goal sat inside
> another drone's bubble. Not a crash risk (the filter holds) but a **liveness** failure: the run
> looks hung. Expect it; do not debug it as a mocap fault.
>
> ⚠️ **`arena_low`/`arena_high` is NOT the geofence** and nothing checks one against the other.
> `goal_tracking.yaml` ships arena `[-3,-3,0.5]..[3,3,2.5]` inside fence
> `[-4.5,-5.2,0]..[5.5,5,3]` — *by hand*. Shrink the arena to your net every time; a 10 % inset
> of a too-big arena is still too big.

**Procedure (sim — M1).** RUNBOOK §A0–A2 to spawn and wire 3 Isaac drones (or
`./svg_teleop.sh hover`, which brings up 3 sim drones in tmux), then in the Commander tab:

```bash
ros2 launch svg_ground_control ground_control.launch.py \
  config:=$(ros2 pkg prefix svg_ground_control)/share/svg_ground_control/config/cbf_sim.yaml \
  scenario:=random_goals
```

This runs at `cbf_sim.yaml`'s speeds — cruise 2.0 m/s, cap 4.0, accel 6 (**sim-only — never port to the drone**).
`takeoff` → `start`, then leave it running and watch. **Exit criterion (M1):** ≥ 5 minutes with
(a) no push-apart, (b) minimum pair distance never below 1.1 m, (c) every drone completing a few
legs — one sitting still for a minute is the defect above; record it and restart. There is **no
dedicated random-goal regression test** (coverage is kinematic, in `test/test_scenarios.py`).
**Done so far:** 2026-10-20 on the dev commander = **ledger #8** — scenario ran clean (CBF active
on all pairs, no push-apart, no breach); the finding was in the *landing* (DISARM accepted on 1 of
3 → the disarm retry, §5). **Video:** [`videos/random_CBF_sim_edited.mp4`](../videos/random_CBF_sim_edited.mp4)
(2026-10-21, 2.0 m/s cruise / cap 4.0 / r 0.55 / α 2.5, 47 s excerpt).

**Real flight.** ⏳ blocked on a second Starling (M7). CMU's recipe (`experiment.md` §C2, the
multi-drone goal-tracking run):
three `MicroXRCEAgent udp4 -p 8888|8889|8892 -v4` (one per drone, own terminal) →
`real_interfaces.launch.py drones:=drone_1,drone_2,drone_3` → `ground_control.launch.py
config:=…/goal_tracking.yaml scenario:=random_goals use_mocap:=true` (the file ships `goal` at
`b21d28c`) → `takeoff` → `start`. Our rig also needs a mocap
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
(its header comment): the pad first, checked before anything arms, then the commander.

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
silently self-contradicting (checked 2026-10-07 at `cf719f0`, re-checked 2026-10-21 at `b21d28c` —
rows that `b21d28c` fixed say so).

| CMU says | On this snapshot / our rig |
|---|---|
| CMU `README.md` (CBF section): "`cbf_filter.py` is a **verbatim port** of `drone_soccer/cbf.py`", "the **unchanged** CBF suite" | **False.** The whole fixed-row mechanism is new: the `fixed` argument of `solve_safe_commands`, the movable mask, pruning that **drops** pairs with no movable drone, speed clamp on movable rows only, fixed rows pinned through both Dykstra phases (`_parallel_dykstra`, `_gauss_seidel_dykstra`), push-apart skipping fixed rows and all-fixed pairs (`_emergency_push_apart`). The fixed-row tests in `test/test_cbf.py` are new too. |
| `cbf_external_velocity_gain` | Documented **nowhere** outside the source. It scales an external drone's measured velocity into its fixed row (`SwarmCommander.control_loop`), default `1.0`, and is **NOT runtime-settable** — yaml + relaunch. |
| `experiment.md` §C2 teaches `goal_tracking.yaml` via per-drone `goal_command`, `speed_command` and formation profiles | At `cf719f0` the file shipped **`random_goals`** (no `set_goal` → every recipe silently did nothing). **Fixed at `b21d28c`: it ships `goal` again**, so §C2 works as written. Keep the `scenario:=goal` habit for `cbf_sim.yaml`, which still ships `antipodal`. |
| `goal_tracking.yaml` comment "goal scenario: takeoff targets = initial goals" above `hover_positions` | Was a dead comment under `random_goals` (takeoff layout came from `Scenario._random_positions`). **True again at `b21d28c`.** Under `random_goals` (`scenario:=`), `hover_positions` is still ignored. |
| `goal_tracking.yaml` `formation_home` commented "= hover_positions: one command brings everyone back" | It is **not** equal. `hover_positions` is `[0,-2,1.2, -1,0,1.2, 0,2,1.2]`; `formation_home` is `[0,-1,1.2, -1,1,1.2, 0,3,1.2]`. (`cbf_sim.yaml`'s pair *does* match.) |
| `cbf_sim.yaml` header advertises "send the WHOLE swarm to a named formation profile" | It ships `scenario: antipodal`, which has no retargetable goals — the profiles are **ignored**. Use `scenario:=goal` (§6). Its `land_speed_mps` comment ("PX4 caps descent at `MPC_Z_VEL_MAX_DN` = 1.0") is stale too — the sim airframe sets 4.0 since 2026-10-20 ([CONFIG.md](CONFIG.md)). |
| `squeeze_rc_intruder.yaml`'s `fence_behavior` comment block describes `keep_in` as "outward speed ≤ gain × distance to the wall" | Stale. It is a **braking envelope** now: full speed until the true braking distance for `fence_brake_accel_mps2`, then brake, with the deceleration fed forward to PX4. The gain only sets the near-wall lag margin. Correct text is ten lines further down in the same file. |
| `experiment.md` "Automated tests" lists 3 pytest files | There are **20** test files (**14** pytest + 6 `functional_*`). Full list in §11. CMU's `README.md` still says "140 tests"; the files hold **158** `def test_` functions and the suite reports **185 passed** (2026-10-20), so some are parametrized — do not treat any count as the pass target, treat "0 failed" as the pass target. |
| `fence_behavior: hold_all` latching | Now latched by any **ACTIVE** drone of **any role**, including an airborne **external** drone (`SwarmCommander.enforce_fence`). A behaviour change CMU does not call out. Brief the intruder's pilot (§2). |
| — (stated nowhere) | **There is no protection between two fixed rows.** Pairs with no movable drone are pruned from the solve and skipped by the push-apart. Two exempt or external drones are on their own. |
| `experiment.md` (geofence analysis) "10 m/s needs ~15.5 m even at 8 m/s² — not in this room" | Agreed — and yet `goal_tracking.yaml`, `goal_single.yaml`, `squeeze_rc_intruder.yaml`, `goal_sequence.yaml` and `figure_eight_rc_intruder.yaml` all ship `cbf_max_speed_mps: 10.0` **and** `goal_accel_mps2: 10.0` (cruise 10.0 / 10.0 / 10.0 / 6.0 / 2.0). Our net is far smaller than CMU's 10 × 9.7 m box. **Lower all three before flying.** |
| `experiment.md` rule: keep `fence_brake_accel_mps2 ≥ goal_accel_mps2` | Those same five real configs ship brake **8** against accel **10**, which violates it — the wall envelope then caps the cruise first. Lower both together. |
| `goal_single.yaml` is "the single-drone goal config" | At `cf719f0` it targeted **`drone_2`**; **`b21d28c` puts it back on `drone_1`** — but it still **exempts** that drone (`cbf_exempt_drones: "drone_1"`: harmless with one drone, yet the filter is then off), ships speeds **10.0** and `land_speed_mps` `0.8` (not the `0.6` we validated), `land_complete_altitude_m` 0.1. Fly **`goal_single_ours.yaml`** instead ([CONFIG.md](CONFIG.md)). |
| Real drones take velocity commands | Default is now **`real_command_mode: trajectory`** → `/{name}/fmu/trajectory_command` (`MultiDOFJointTrajectory`; declared in `SwarmCommander.__init__`, published by `publish_command`). **`px4_interface` must be rebuilt** (`bws --packages-select px4_interface`) or the drone just hovers; `real_command_mode: velocity` restores the old `TwistStamped`. |
| — (goal yaw not documented) | New and undocumented by CMU: `/svg/{name}/goal_xyzt` (`Float64MultiArray [x,y,z,theta_deg]`), the first way to command **yaw** with a goal. |

## 10 · Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `goal_command` / `speed_command` published, drone ignores it | The running scenario has no retargetable goal — `cbf_sim.yaml` ships `antipodal`, and `scenario:=random_goals` / `head_on` / `random_walk` all ignore goals (`goal_tracking.yaml` did too at `cf719f0`). Relaunch with `scenario:=goal` (§4). Also: `start` must have been called. |
| `formation_profiles set but scenario "X" has no retargetable goals; profiles ignored` | Expected on `cbf_sim.yaml` (`antipodal`) or any launch with `scenario:=random_goals`. Relaunch with `scenario:=goal` (§6). |
| A drone refuses to close the last metre to its goal / hangs for a minute | The CBF is holding it off a barrier. Under `random_goals` this is the §7 defect (the goal is inside another drone's bubble). Not a mocap fault. Lower `cbf_safety_radius_m`, or re-seed, or move on. |
| `CBF active on: …` logged continuously, drones crawl | Goals or posts closer than `2r` (1.1 m), or `cbf_alpha` too low (yielding far too early). Re-space the targets, or raise α — remembering the scenario keeps its build-time radius (§3). |
| `CBF emergency push-apart engaged` | Drones already inside each other's bubbles — the QP is infeasible. **Land and investigate** (CMU `README.md`, LED section). All LEDs red is the same message. |
| An exempt/RC drone is shoved backwards instead of pushing through | Its exemption is not in effect. Check the startup roster line for `/cbf-exempt` on that name, that it is **ACTIVE** (climb-out and landing are never exempt — `SwarmCommander.control_loop`), and that `cbf_exempt_drones` spells the name exactly. |
| Holders yield **late**, only once the intruder is on top of them | The intruder's fixed row has zero velocity: its odometry is stale (external) so the filter thinks it is hovering (`control_loop`). Check `ros2 topic hz /drone_3/odometry_conversion/odometry`. |
| Everyone freezes mid-air when only the RC drone misbehaved | `fence_behavior: hold_all` now latches on airborne external/teleop drones too. `land` → `/swarm_commander/reset_fence` → `takeoff` → `start`. |
| `ros2 param set` refused ("read once at startup" / "must be finite and > 0") | Not a live parameter — the message lists what is; or the `POSITIVE_PARAMS` guard rejecting ≤ 0 (`goal_settle_s` alone may be 0). Yaml + relaunch (RUNBOOK §C7). Note a live radius bump does **not** re-space goals (§3). |
| `land` → drones sit on the floor 2 s, then `disarm -> success=False`, retry lines | Working as designed (§5): the settle, then up to 5 retries 1 s apart; PX4's own `COM_DISARM_LAND` often disarms first. If the retries run out the commander goes IDLE with an ERROR — check arming in the sim's `mavros/state` (QGC on the real drone). Floor rocking blocking the land detector was ledger #9 (sim-only `LNDMC_ROT_MAX` 300). |
| Real drone arms and then just hovers, commands look fine | `real_command_mode: trajectory` with a stale `px4_interface`. `bws --packages-select px4_interface`, re-source, relaunch. |
| Fake odometry on real topics, drone lurches | A `test/functional_*.py` is running. **Never with the real stack up** — they publish fake odometry on the live topic names. Kill it and restart the stack. |

## 11 · Technical appendix

Paths relative to `AirStack/robot/ros_ws/src/svg_ground_control/`.

| Piece | Location | Role |
|---|---|---|
| Sim airframe (Starling 2 Max) | `simulation/isaac-sim/assets/robots/starling2max.usd` + Pegasus `Starling2MaxConfig` + PX4 `10090_pegasus_starling2max` | CMU sys-ID dynamics in Isaac Sim; numbers and how to select it: [CONFIG.md](CONFIG.md) "Sim airframe", [RUNBOOK.md](RUNBOOK.md) §A |
| CBF solver | `svg_ground_control/cbf_filter.py` | `filter_velocities` → `build_collision_constraints` + `solve_safe_commands` (movable mask, pruning, speed clamp, `fixed` rows) → `_parallel_dykstra` / `_gauss_seidel_dykstra` → `_emergency_push_apart` |
| Commander | `svg_ground_control/swarm_commander.py` | `SwarmCommander`: external → fixed row and exempt rows in `control_loop` · runtime params `on_parameter_change` / `_apply_parameters` (`_RUNTIME_ATTRS`, `_SCENARIO_PARAMS`, `POSITIVE_PARAMS`, `NON_NEGATIVE_PARAMS`) · formations `formation_callback` · sequence `sequence_callback` · fence latch `enforce_fence` · landing `landing_done` + `land_disarm_step` · snapshot `build_status` |
| Scenario policies | `svg_ground_control/scenarios.py` | `Scenario._random_positions` · `RandomGoalsScenario` · `GoalScenario.set_goal`, `set_all_speeds` · `GoalSequenceScenario` · `FigureEightScenario` · registry `_SCENARIOS` (hover, goal, random_walk, random_goals, head_on, antipodal, squeeze, figure_eight, goal_sequence) · factory `make_scenario` |
| Go-to-goal profile | `svg_ground_control/trajectory.py` | `brake_speed` · `stopping_distance` · `seek_velocity` · `ReferenceTracker` |
| The key configs | `config/cbf_sim.yaml` (3 sim, `antipodal`, nobody exempt, **ours**: cruise 2.0 / vmax 4.0 / accel 6 — sim-only) · `config/goal_tracking.yaml` (3 **real**, `goal` at `b21d28c`, speed/vmax/accel 10.0 ⚠️, `keep_in`) · `config/squeeze_rc_intruder.yaml` (3 real, `drone_3` teleop + exempt, own teleop fence) · `config/goal_sequence.yaml`, `config/figure_eight_rc_intruder.yaml` (new 10-20) | Per-scenario parameters; read once at launch — full matrix in [CONFIG.md](CONFIG.md) |
| CBF telemetry | `/svg/cbf_active` · `/svg/commander_status` | `cbf_active` = `std_msgs/String`, comma-separated names, **every tick** (end of `control_loop`), drives the LEDs and the panel. The status snapshot carries `cbf{alpha, safety_radius_m, max_speed_mps, external_velocity_gain, active, emergency}` and `tuning{teleop_max_speed_mps, goal_accel_mps2, goal_settle_s, scenario_speed_mps}` |
| Goal inputs | `/svg/{name}/goal_command` (PoseStamped) · `/svg/{name}/goal_xyzt` (Float64MultiArray `[x,y,z,theta_deg]`) · `/svg/{name}/speed_command` (Float32) · `/svg/formation_command` (String) | All after `start` only |
| Operator tooling | `scripts/svg_teleop.sh` · `foxglove/svg-basestation/` · `tools/sim_terminals.sh` | `svg_teleop.sh solo\|squeeze\|hover` brings up Isaac + agent + interfaces + commander + pad in tmux; `tools/sim_terminals.sh` is our four-tab session (RUNBOOK §A0). The panel has the six-gain runtime dropdown (α / r / vmax / teleop vmax / goal accel / goal settle), the per-drone CBF chip, the mission chip and the Rosbag switch ([BASESTATION.md](BASESTATION.md)) |

**Tests** — inside the robot container, at the package directory:

```bash
cd ~/AirStack/robot/ros_ws/src/svg_ground_control
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -q -p no:cacheprovider test/
```

Fourteen pytest files (158 `def test_` functions; the suite reports **185 passed** as of
2026-10-20, so some are parametrized — the M1 pass target is **0 failed**, not a count):
`test_cbf.py`, `test_scenarios.py`, `test_exempt.py`, `test_fence_and_position_hold.py`,
`test_feedforward.py`, `test_trajectory.py`, `test_formations.py`, `test_runtime_params.py`,
`test_live_speed.py`, `test_led_packet.py`, `test_teleop_controllers.py`, plus three new since
10-19/20: `test_landing_settle.py` (ours — the settle + disarm retry), `test_bag_recorder.py`
and `test_safe_teleop_sync.py` (CMU dev branch). Plus six closed-loop scripts run by hand
against a live commander: `functional_single_goal_test.py`, `functional_multi_goal_test.py`,
`functional_hybrid_test.py`, `functional_squeeze_test.py`, `functional_squeeze_lag_test.py`,
`functional_fence_test.py`.
🚨 **The `functional_*` scripts publish FAKE odometry onto the live topic names. NEVER run one
with the real stack up** — flyaway risk. Iron rule 4 in [CLAUDE.md](../CLAUDE.md).
