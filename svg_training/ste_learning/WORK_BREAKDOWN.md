INTERNAL · reference page of the STE learning track, from the specialist draft `drafts/WORK_BREAKDOWN_draft.md` (20 Nov 2026). **[PLAN.md](PLAN.md) takes precedence** where the two differ; its section 2 lists every change made at integration.
[DISCUSSION_2026-11-19_20.md](DISCUSSION_2026-11-19_20.md) (D1–D9 decided; P1–P8 open). Practices:
[CODING_PRACTICES_draft.md](CODING_PRACTICES.md). Rules: [STANDARDS.md](STANDARDS.md).

# Work breakdown: STE learning track

> **Integration notes (PLAN v2, 20 Nov).** Phase L0 is defined in [PLAN](PLAN.md) §4 and wins over this page: it adds
> **L0.7** (process tooling and drills), **L0.8** (game spec sheet), **L0.9** (1-for-1 tag matcher for the study),
> **L0.10** (scripted players, including Strikes that use height), **L0.11** (screening sweep), **L0.12** (best-response
> test) and **L0.13** (does tier 2 train at all), and changes L0.2 to contested play. **L2.2 does not reuse
> `contact_tags`** (it is not 1-for-1: `core/pair_rules.py:66-69`); the matcher of L0.9 is completed there. L1–L9 below
> are the intended path; tasks, order, sizes (P9) and GPU-hours are re-baselined at gate G0, and every GPU-h figure
> below L0 is an early guess the review judged too low for tier 2.

**How to read this.** Tasks are numbered by phase (L0 … L9) and named in plain words. Hours are hours of work for one
Claude session, **estimates**. GPU-h are on the home RTX 5090, **estimates** unless a record is cited; step 1 (L0.2)
replaces the tier 2 estimates with a measurement. "Gate" names the human decision a task waits on; "none" means the
lead may approve it (owner delegates technical calls). New package and file names (for example `source/svg_training/ste/`)
are PROPOSED until the architecture page fixes them. New learner code stays outside `nus/` (that folder carries the
NUS-value rule G2 and the privacy tests). Unless a task says otherwise, **done** = its tests, written first, pass on
the CPU; the full suite passes; the review checklist of the coding practices is walked; HANDOFF is updated. Every GPU
task follows `train-run` (preflight, gates or an INFO plan written first, videos, record, ledger W row).

**Facts this plan rests on (read in the code, 20 Nov 2026).**
- `core/safety_filter.py` refuses `fixed` rows; the CUDA-graph copy `core/safety_filter_graph.py` must change in step.
- `core/pair_rules.contact_tags` already tags a Guard–Strike pair below a 3-D centre distance, with
  `guard_survives_tag_prob`. Drones that are out are parked at `PARK_M` and leave every filter pair (`core/game.py`,
  `core/starling_layer.py`): "landing while still a filter obstacle" does not exist yet.
- `models/physics_drone.py` refuses `setpoint_delay_s != 0`, and the cascade reads the true state (`_read`). Neither
  `TorchRigidBodyWorld` nor `IsaacWorld` has drag (no damping, S2b D2).
- `scripts/train_standin.py --game nus_hangar` refuses `--motion physics`. Phase 4 row 6 (`scripts/nus_phase4.py --row
  6`) runs the hangar game in Isaac Lab; an unknown player name falls through `nus/players.py` to
  `opponents.scripted.make_strategy`, which loads a skrl run folder, but plays it every tick.
- The STE Guard policy (T41) is skrl IPPO with one network per Guard slot (fixed team size), one decision per 12 ticks
  (`nus/pilot.HeldStrategy`), trained against S20 in the hangar game (needs `configs/local/`, installed by
  `scripts/nus_install_provisional.sh`). Its run folder is git-ignored and exists on this workstation only:
  `~/AirStack-starling-max2-nus-phase5/svg_training/runs/nus_port/phase5/pilots/2026-11-19_nus_phase5_pilot_p1b_run4`.
- The only real log fitted so far for tier 2 timing is log103 (13 Nov, drone_2; T11: 6 held-out legs), fewer than the 8
  held-out steps the stage 1 gate asks for; a run of record needs the NEAR-962 planned-push flight (STANDARDS §5 rule 10).
- Team sizes: STANDARDS §4 proposes 1–5 Guard and 1–3 Strike drones per game (PROPOSED); this plan uses that range.

## Summary

| ID | Name | Depends on | Hours | GPU-h | Gate |
|---|---|---|---|---|---|
| L0.1 | Track set-up: config and test skeleton | — | 3 | 0 | none |
| L0.2 | Tier 2 speed in contested play (PLAN §4; was "Step 1a") | L0.7 | 6 | 1.5 | P3 |
| L0.3 | STE Guard policy in tier 2 without retraining (was "Step 1b") | L0.2 | 6 | 1.5 | P3 |
| L0.4 | Side-by-side Starling render | — | 3 | 0.2 | P4 |
| L0.5 | Starling video look fix | L0.4 | 4 | 0.3 | owner looks at stills (D9) |
| L0.6 | Gate G0: one decision page for the owner (PLAN §5; was "Decision: tier 2 training affordable?") | every L0 task | 1 | 0 | **owner** |
| L0.7–L0.13 | added by PLAN v2: process tooling and drills, game spec sheet, tag rule for the study, scripted players, screening sweep, best-response test, does tier 2 train at all | see [PLAN](PLAN.md) §4 | see PLAN §4 | 0 / 0 / 0 / 0 / 3 / 6 / 6 | see PLAN §4 |
| L0.14 | Crazyflie route check (added 20 Nov 2026 with the owner's yes; PLAN §4, DISCUSSION §2.16) | L0.1; the T41 run folder | 10 | 0 | none; feeds P13 at G0 |
| L1.1 | State delay and noise in tier 2 | L0.1 | 8 | 0.2 | none |
| L1.2 | Drag in tier 2 | L0.1 | 5 | 0.2 | none |
| L1.3 | Fit delay, noise and drag to real logs | L1.1, L1.2 | 8 | 0 | none now (exploratory); NEAR-962 flight (owner) for the run of record |
| L1.4 | AirStack-simulator velocity-step logs | — | 4 | sim ~1 h | P5 (owner not flying) |
| L1.5 | Tier 2 against the AirStack simulator, same airframe settings | L1.1, L1.4 | 6 | 0.3 | owner (SIM-ONLY values in tier 2, STANDARDS §5 rule 2) |
| L1.6 | Batched PyTorch estimator (only if needed) | L1.5, NEAR-962 | 20 | 0.5 | lead decision |
| L2.1 | Filter option B in the training copy | L0.1 | 10 | 0.3 | P2 for runs of record |
| L2.2 | Tag at 3-D centre < 1.6 m, 1-for-1 | L0.1 | 6 | 0 | P1 for runs of record |
| L2.3 | Landing drones stay filter obstacles | L2.2 | 8 | 0.2 | P1 (part of the tag rule) for runs of record |
| L2.4 | Drone loss and random team size in the game | L2.3 | 5 | 0 | P7 for flight relevance |
| L2.5 | Parked-Guard control and scripted opponents under the new rules | L2.1–L2.4 | 5 | 0.5 | none (INFO) |
| L2.6 | Scripted games, tier 1 against tier 2, new rules | L1.3, L2.5 | 4 | 1.5 | none (INFO) |
| L3.1 | Entity observation (interface v0.3) | L2.3 | 6 | 0 | owner (interface version) |
| L3.2 | Attention encoder and shared actor | L3.1 | 8 | 0 | none |
| L3.3 | Team critic | L3.2 | 4 | 0 | none |
| L3.4 | PPO learner for the shared actor | L3.3 | 10 | 0 | none |
| L3.5 | Fast-engine trainer and pilot against scripted opponents | L3.4, L2.5 | 8 | 2 | none (pilot, INFO) |
| L3.6 | Tier 2 path for the trainer | L3.5, L1.3 | 6 | 1 | none (smoke) |
| L4.1 | Evaluation suite | L2.5, L3.2 | 12 | 0 | none |
| L4.2 | Gates file for the track's runs of record | L4.1 | 3 | 0 | owner approves limits |
| L4.3 | Calibration of the suite on known players | L4.1 | 3 | 2 | none (INFO) |
| L5.1 | League: pool, snapshots, matchmaking | L3.4 | 10 | 0 | none |
| L5.2 | Self-play trainer with resume, cap and videos | L5.1, L3.6 | 10 | 0 | none |
| L5.3 | League pilot on the fast engine | L5.2, L4.3 | 4 | 3 | none (pilot) |
| L5.4 | League pilot on tier 2 | L5.3 | 4 | 6 | none (pilot) |
| L5.5 | Runs of record, 3 seeds, tier 2 | L5.4, L4.2 | 6 | 36 | gates frozen, P1, P2 ruled |
| L5.6 | Debugging allowance | as needed | 16 | 4 | none |
| L6.1 | Score runs of record against the gates | L5.5 | 6 | 6 | none |
| L6.2 | Cross-checks: tier 1 v tier 2, option B v even split | L6.1 | 4 | 3 | none (INFO) |
| L6.3 | Export policy file and interface.toml | L6.1 | 6 | 0 | owner (hand-over) |
| L7.1 | AirStack-side specs: game node, filter option B, game configs | L2.1–L2.3, L3.1 | 8 | 0 | owner approves plan; AirStack session builds |
| L7.2 | AirStack-simulator 1v1 | L7.1 built, L6.3 | 6 | sim ~2 h | owner; AirStack session |
| L8.1 | Real 1v1 | L7.2, PREFLIGHT update | 6 | 0 | owner (flight) |
| L9.1 | Session documentation (running) | every task | ~10 % | 0 | none |
| L9.2 | Track results page and STANDARDS updates | L6.1 | 10 | 0 | owner (large doc change) |

Totals (estimates): about 270 hours of work plus about 10 % for documentation (about 295 h); about 70 GPU-h, of which 36
are the runs of record, plus about 3 h with the AirStack simulator holding the GPU (L1.4, L7.2).

## L0 Set-up and step 1 measurement

**L0.1 Track set-up: config and test skeleton.** Goal: one place for the track's settings and a test file that pins
them. Files: `configs/ste_learning.toml` (sections filled by later tasks; each value labelled), `source/svg_training/
ste/__init__.py`, `source/svg_training/ste/config.py` (frozen dataclasses, unknown keys raise), `tests/test_ste_config.py`.
Tests first: unknown key raises; every value has a status label comment. Done: tests pass on CPU; full suite unchanged.
Depends: —. 3 h. Gate: none. Lead, 20 Nov 2026: in L0.1 the file holds only `[track]` and `[budget]` (the L0 caps; since G0, 22 Nov 2026, also
`[budget_l1_l2]`, the L1 + L2 cap of 13 GPU-h and the L1 task caps); the
game sections arrive with the tasks that implement them, so "defaults reproduce today's game" is tested at L0.9, where
the first game setting (`[tag]`) exists. The game's values live in `configs/ste_game.toml` (L0.8).

**L0.2 Tier 2 speed in contested play (P3; was "Step 1a").** PLAN §4 wins over the text below: both teams play (not
random actions), with a learner in the loop, at 3v3 and the G0 candidate sizes, tier 2 and tier 1. Goal: how many game-steps per second tier 2 gives with a
learner in the loop, so D3's cost is known. Files: `scripts/ste_speed_probe.py` (rollout + PPO update timing with the
existing skrl stand-in on the S2 game, `--motion physics` and `--motion starling`, 3v3, 1,024 / 2,048 / 4,096 games, a
fixed number of updates per point, one process per point), `tests/test_ste_speed_probe.py` (argument checks, refusal
without `--headless`, CPU dry run on the torch world). Tests first: refuses without preflight; the CPU path writes a
row with games, drones per game, tier and device. Done: INFO record (no gates, planned in writing first) with
game-steps/s per point for both tiers on the same machine, GPU memory, and the ratio against the laptop figure
(DISCUSSION §2.6: ~2.7×, 5v3 random actions); ledger W row. Depends: L0.1. 6 h; 1.5 GPU-h. Gate: P3.

**L0.3 Step 1b: STE Guard policy in tier 2 without retraining (P3).** Goal: does the T41 policy (829 / 1,000 against S20
on tier 1) keep its hold rate on the Isaac Lab physics drone? Input: the T41 run folder (workstation only, path above).
Files: `scripts/ste_transfer_check.py` (loads the run folder as `SkrlPolicyStrategy` behind `HeldStrategy`, 12 ticks,
so it is not played every tick as the row 6 fall-through would; plays row 6 conditions on the 1,000 Phase 4 paired
starts; parked Guard on the same starts as the control), `tests/test_ste_transfer_check.py` (CPU, torch world, two
games: the held strategy repeats each command for 12 ticks; the paired starts load). Tests first as listed. Done: INFO
record with hold rate and Wilson interval against S20 and the parked Guard (row 6 parked Guard: 524, T24), games that
differ from tier 1, two videos; ledger W row. Depends: L0.1. 6 h; 1.5 GPU-h. Gate: P3.

**L0.4 Side-by-side Starling render (P4).** Goal: show where the Isaac Lab clip differs from the AirStack simulator's
Starling. Files: `scripts/make_starling_compare.py` (renders `starling2max.usd` headless with and without team paint,
two camera angles), output under `runs/`. The AirStack-simulator side uses existing footage or a still the owner
provides; we do not start the simulator for this. Tests: a CPU test of the argument handling only. Done: one figure
with both views and a 2–4 sentence caption naming the likely causes checked. 3 h; 0.2 GPU-h. Gate: P4.

**L0.5 Starling video look fix (D9).** Goal: videos show the Starling as it looks in the AirStack simulator. Files:
`source/svg_training/compat/isaaclab_232.py` (`_add_drone_visuals`: keep the model's materials; team colour as a small
ring or marker), `configs/s2b_video_scenes.toml` (style key), `scripts/make_s2b_video.py`. Tests first: the existing
"visual changed the physics body" check still passes; the style key is checked on load; an `isaac`-marked smoke clip. Done:
one re-rendered clip and still beside the AirStack look; owner says it reads right. 4 h; 0.3 GPU-h. Gate: owner look.

**L0.6 Gate G0 (was "Decision after step 1").** PLAN §5 wins over the text below: one decision page with every L0
number; the owner rules on the tag and the zone, what a tag costs, team sizes, where to train, environments, the demo
and the budgets of L1 to L9. Version 1's text: if L0.2 shows tier 2 cannot reach the planned budget (L5.5) the lead brings options to
the owner: train on tier 1 with tier 2 only for pilots and evaluation, or shorter tier 2 runs started from a tier 1
policy. D3 stands unless the owner changes it.

## L1 Drone model: estimator effect and drag (D7)

### Phase L1 (in work, 22 Nov 2026)

Approved with L2 at gate G0 ([DISCUSSION §14](DISCUSSION_2026-11-19_20.md#14-gate-g0-rulings-owner-22-nov-2026)): one cap of 13 GPU-h for L1 + L2. The task list is the L1 table of the
[costed draft](drafts/L1_L9_COSTED_PLAN_DRAFT.md) (section 3). Config caps are `configs/ste_learning.toml`
`[budget_l1_l2.task_cap_gpu_h]` (lead's split, PROPOSED; they sum to 9.1 after the side-track spec and its addenda raised L1.11 to 1.2 and L1.13 to 2.1 and added L1.14 (0.3 from L1.9) and L1.15 (0.3 from L1.10)); the draft's figures are estimates.

| Task | Draft estimate (GPU-h) | Config cap (GPU-h) |
|---|---|---|
| L1.0 5090 checks and speed re-measure | 0.3–0.5 | 0.5 |
| L1.1 State delay and noise in tier 2 | 0.2 | 0.2 |
| L1.2 Drag in tier 2 | 0.2 | 0.2 |
| L1.3 Fit delay, noise and drag to real logs (CPU) | 0 | 0 |
| L1.4 AirStack-simulator velocity-step logs (P5, approved) | about 1 h of simulator time | 0 |
| L1.5 Tier 2 against the AirStack simulator | 0.3 | 0.3 |
| L1.6 Batched estimator (only if needed) | 0–0.5 | 0.1 (0.4 moved to L1.13, 22 Nov) |
| L1.7 Same effects in tier 1 | 0–0.1 | 0.1 |
| L1.8 T46's base policies re-scored on the new tier 2 | 0.1–1.2 | 1.2 |
| L1.9 1v1 best-response read at tag 1.6 m, plus a scripted 1v1 screen also at 1.15 m | 0.5–1.9 | 1.6 (0.3 moved to L1.14, 22 Nov) |
| L1.10 Tag drawn within 1.5–1.7 m, 3v3, both sides | 1.0–1.2 | 0.9 (0.3 moved to L1.15, 22 Nov) |
| L1.11 Strike team trained against guard_field at 1.6 m (side track: separates the opponent from the tag) | about 0.6 | 1.2 |
| L1.12 T46's 1.6 m Guard team scored against every Strike script (side track) | minutes (under 0.1) | 0.1 |
| L1.13 Shorter-training-clock Strike run at 1.15 m (side track; clock value set in its spec) | about 0.7 (two arms, spec v2; used 1.29 for training, plus re-scores at the other clock) | 2.1 |
| L1.14 Time-left test: T52 and arm A scored with the time-left input changed (side track, scoring only; spec addendum 2) | about 0.2 | 0.3 |
| L1.15 Delay check: T55, T54 and guard_field v strike_straight re-scored at response delay 0 and 0.30 s (side track, scoring only; spec addendum 3) | about 0.2 | 0.3 |

The task texts below (L1.1–L1.6) are version 1's; the costed draft adds L1.0 and L1.7–L1.13; the side-track spec adds L1.14 and L1.15.

**L1.1 State delay and noise in tier 2.** Goal: the PX4 cascade sees a delayed, noisy state as with EKF2. Files:
`source/svg_training/models/estimator_effect.py` (ring buffer of past states in physics steps, seeded Gaussian noise per
quantity, batched), `models/physics_drone.py` (`_read` passes through it), `models/physics_params.py` (new keys
`state_delay_s`, `state_noise_*`, default 0), `params/starling_physics_v1.toml` (new file; `v0` untouched),
`tests/test_estimator_effect.py`. Tests first: default 0 = today bit for bit; a delay of k physics steps returns the state
of k steps earlier exactly; noise mean and spread within sampling tolerance with a fixed generator; reset fills the
buffer with the reset state; same results on `TorchRigidBodyWorld` and (marked `isaac`) `IsaacWorld`. Done: tests pass;
throughput cost measured (≤ 10 %). 8 h; 0.2 GPU-h. Gate: none.

**L1.1b Estimator model shape (new, 22 Nov 2026, from the L1.1 code review).** A pure delay on the whole state is the
wrong shape for EKF2: its output predictor hands the controllers current-time states, and a CPU check showed the z loop
(MPC_Z_P 5 × MPC_Z_VEL_P_ACC 8) goes unstable at about 0.117 s of feedback delay (limit cycles of 0.36 m at 0.10 s and
1.42 m at 0.15 s; attitude delayed as well: tilt 0.92 rad at 0.15 s). Change: never delay attitude; model the estimate's
error (slow, correlated noise, e.g. a Gauss–Markov process per quantity) with at most a small residual delay; pass the
game seed to the noise (today every run draws the same noise); L1.3 fits error statistics, not a transport delay. The
0.1482 s of params/real_exploratory_v0.toml stays the tier-1 command-to-motion delay. Tests first. Gate: none.
Built (23 Nov 2026, branch `ste-l1-1b`): `models/estimator_effect.py` adds a first-order Gauss–Markov error per
quantity (position, velocity, attitude as a small body rotation; keys `state_error_*` with sigma and tau, 0 = off,
OPEN in v1), drawn from its stationary distribution at each reset; body rates keep white gyro noise. Attitude is never
delayed (`state_delay_att_s` must be 0); `state_delay_s` is a residual delay of position and velocity, refused above
0.05 s (fixed in code). The game seed reaches the noise (`PhysicsLayer`, both replays, `SvgGame.reset(seed)`).
`scripts/l1_model_check.py`'s "on" arm uses the error model; its smoke adds error statistics and a hover check.
Tests: `tests/test_estimator_error.py`. CPU hover with made-up values (0.02 m / 0.5 s, 0.02 m/s / 0.2 s, 0.005 rad /
0.5 s), observed in the training simulator (torch world): RMS 0.039 m, largest 0.115 m, tilt 0.030 rad, no upset.

**L1.1c Second-order estimate error (new, 23 Nov 2026, from L1.3's fit, T63).** The real hover error swings back
(position ζ ≈ 0.28, ωn ≈ 0.97 rad/s, mostly z; a damped second-order process fits about 16–20× better than first order to
6 s, and first order is rougher step to step). Option: a second-order Gauss–Markov term per axis beside the first-order
one, default off; fit from the NEAR-962 logs before use. Also: a ULog-path test that catches a flipped ENU z sign. Gate:
none. Not started.

**L1.2 Drag in tier 2.** Goal: a linear drag force (form taken from Pegasus's simple drag, read only) computed in our
wrench path so both worlds get it. Files: `models/starling_airframe.py` or `models/physics_drone.py` (drag force added
before `apply_wrench_b`), `models/physics_params.py` (`drag_*`, default 0, OPEN value), `tests/test_drag.py`. Tests
first: off = today bit for bit; zero velocity gives zero drag (hover unchanged); a constant push reaches the analytic
terminal speed in the torch world. 5 h; 0.2 GPU-h. Gate: none.

**L1.3 Fit delay, noise and drag to real logs.** Goal: values for `starling_physics_v1.toml` from real flight
(STANDARDS §5 rule 10). Since L1.1b the estimator part is fitted as error statistics: sigma and correlation time tau
per quantity (`state_error_*`) from the logs, not a transport delay. Files:
`scripts/fit_estimate_error.py` (the error statistics; built 23 Nov, record T63, EXPLORATORY), `tests/test_fit_estimate_error.py`; drag and the stage-1 limits still to fit; a record. Tests first: recovers known error
statistics (sigma, tau) and drag from a synthetic log made by the torch world. Data: the 13 Nov drone_2 log (T11) now;
the NEAR-962 planned-push flight when flown. Done: record against the stage 1 limits (held-out RMS ≤ 0.10 m/s, t63 error
≤ 0.10 s; FIXED). With log103 alone (6 held-out legs, fewer than 8) the values are labelled EXPLORATORY, like
`params/real_exploratory_v0.toml`, and `starling_physics_v1.toml` says so; pilots (L3.5–L5.4) train on it. The runs of
record (L5.5) train on a set refitted to the NEAR-962 flight if it has flown by then; otherwise the owner decides
whether L5.5 goes ahead on the exploratory set, and the records say which. 8 h. Gate: none now; NEAR-962 is an owner
flight.

**L1.4 AirStack-simulator velocity-step logs (P5).** Goal: steps through real PX4 and real EKF2. How: run (never edit)
`tools/sim.sh` through `scripts/record_steps.sh` (approved exception, STANDARDS §1). Files: none new in code; the logs
and a record. Done: logs with the airframe settings named; record. 4 h; the simulator holds the GPU about 1 h. Gate: P5,
and only when the owner is not flying or demoing.

**L1.5 Tier 2 against the AirStack simulator, same airframe settings.** Goal: isolate the estimator's effect. Files:
`params/airstack_sim_physics_v0.toml` (SIM-ONLY values, comparison only, never a training set), `scripts/
compare_sim_steps.py`, tests on recorded fixtures. Known confounds to remove or name (STANDARDS §5 rules 1 and 8): PX4
1.16.1 in the simulator against 1.14 in the cascade, the speed-only MAVROS route against the trajectory setpoint, and the
simulator's PX4 clock running about 1.9 times the commander's. Done: INFO record: tier 2 with and without L1.1's delay
against the simulator's steps, each confound stated. 6 h; 0.3 GPU-h. Gate: owner, because tier 2 would fly SIM-ONLY
airframe values (STANDARDS §5 rule 2 allows them only by owner ruling, precedent 16 Nov).

**L1.6 Batched PyTorch estimator (only if needed).** Only if L1.3, L1.5 and NEAR-962 show delay plus noise is not
enough (D7 step 4). A simplified batched EKF in `models/`, tested on CPU against hand-worked cases. ~20 h. Gate: lead.

## L2 Game rules in the training copy (§2.9, §2.14)

**L2.1 Filter option B in the training copy.** Goal: in Guard–Strike pairs only the Guard gives way; team-mate pairs
keep the even split; when the Guard cannot escape, the even split returns as an emergency rule. Files: `core/
safety_filter.py` (per-pair share instead of the `fixed` refusal), `core/safety_filter_graph.py` (same change, or refuse
the setting), `core/starling_layer.py` (`filter_kwargs`), `models/command_chain.py`, the game config
(`[filter] share = "equal" | "guard_yields"`, default `"equal"`; pairs with a landing drone stay equal, as in the
architecture draft), `tests/test_safety_filter_option_b.py`. Tests first:
`"equal"` equals today bit for bit on the T2 parity scenes; DISCUSSION §2.9 desk cases as fixtures (Strike 0.5 m/s into a
still Guard: Strike unchanged, Guard takes the whole correction; Guard–Guard still 50/50); closest approach ≥ 1.10 m
minus the tracking tolerance; the emergency fallback triggers only above its residual. Done: tests pass on both filter
paths; cost measured. 10 h; 0.3 GPU-h. Gate: P2 before any run of record uses it.

**L2.2 Tag at 3-D centre < 1.6 m, 1-for-1.** Goal: the study tag of L0.9 (`[tag] mode = "nearest_pair_1for1"` on the
partner preset, `pair_rules.proximity_tags`; built, off by default) made the rule of the trained game: filter on every
pair, a tag when a live Guard–Strike pair is closer than `[tag] radius_m` (1.6 m first, 1.15 m after L2; ruled at G0, 22 Nov 2026) in 3-D; both drones out (D2,
`guard_survives_tag_prob` = 0). Files: `core/game_config.py` (`TagCfg`), `core/game.py`, `configs/ste_game.toml`,
`tests/test_tag_rule.py`. Tests (L0.9 has them): 1.59 m tags, 1.61 m does not; tags come before the zone test; off is
today's game bit for bit; `partner` and `contact` presets unchanged (existing config tests pass). 6 h. Gate: P1, ruled at G0 (owner, 22 Nov 2026; STANDARDS §4 "Tag" changed).

**L2.3 Landing drones stay filter obstacles.** Goal: a tagged or lost drone descends at the land speed (0.6 m/s, real
`_ours` configs, MEASURED) and stays in every filter pair until it is down, then is parked. It no longer acts or scores.
Files: `core/game.py` (a `landing` mask beside `alive`), `core/starling_layer.py` and `core/physics_layer.py` (pairs
include landing drones; their command is the descent), `tests/test_landing.py`. Tests first: a landing drone keeps
other drones ≥ 1.10 m away; it reaches the floor in the expected time; it neither tags nor scores. 8 h; 0.2 GPU-h.
Gate: none from P1 (ruled at G0, 22 Nov 2026; landing is part of the tag rule).

**L2.4 Drone loss and random team size.** Goal: games with 1–5 Guard and 1–3 Strike drones drawn per game (STANDARDS §4,
PROPOSED; 3v3 the main size), and a drone
removed mid-game (it lands as in L2.3). Files: `core/game.py` (`schedule_dropout` used, `dropout_fraction` > 0 in
`configs/ste_game.toml`), start draws over padded slots, `tests/test_drone_loss.py`. Tests first: masks right for every
size; observations show absent drones with present = 0; drop-out at the drawn step. 5 h. Gate: P7 decides whether this
is part of the flown game.

**L2.5 Parked-Guard control and scripted opponents under the new rules.** Goal: check the risk that a 1.6 m tag favours
a Guard that stands still; make the scripted Strike behaviours (straight, flank, feint, dodge) run with the study tag on (`[tag] mode`).
Files: `opponents/scripted.py` (any missing behaviour), `tests/test_scripted_tag.py`, an INFO record. Done: parked Guard
hold rate with and without the tag, option B on and off, 1,000 games each, tier 1. 5 h; 0.5 GPU-h.

**L2.6 Scripted games, tier 1 against tier 2, new rules.** Goal: the fast engine still predicts tier 2 (T13 repeated
with tag, option B, delay and drag). INFO record. 4 h; 1.5 GPU-h.

## L3 Learner: shared policy, team critic, drone loss (D6)

**L3.1 Entity observation (interface v0.3).** Goal: per drone, its own state plus lists of team-mates and of the other
team, each entry with relative position, relative velocity, present flag and landing flag (the architecture draft
proposes v0.2 plus 8 landing flags = 81 numbers, built from state, opt-in like `obs_v02`).
Files: `core/observations.py`, `tests/test_observations_v03.py`. Tests first: v0.1 and v0.2 unchanged; entries match the
game state; absent entries all zero with present 0. 6 h. Gate: owner (interface version, STANDARDS §3 rule 3).

**L3.2 Attention encoder and shared actor.** Files: `ste/policy_net.py`, `tests/test_ste_policy_net.py`. Tests first: shuffling
entries leaves the output unchanged (≤ 1e-6); changing values in absent entries changes nothing; works for 1–5 drones
per team; output in `[-1, 1]`; one network serves every drone of a team; an export-and-reload round trip (the format
L6.3 will use) gives the same actions, so the first serialisation is not left to L6.3. 8 h.

**L3.3 Team critic.** Files: `ste/learner.py` (or its own module, as the architecture fixes), tests. Centralised value over all drones (training only, STANDARDS §3 rule
2), same order-independence tests. 4 h.

**L3.4 PPO learner for the shared actor.** Files: `ste/learner.py`, `tests/test_ste_learner.py`. Tests first: GAE against a
hand-computed case; drones that are absent or landing add nothing to the loss; a non-finite metric aborts with the
checkpoint kept; same seed gives the same update on CPU. 10 h.

**L3.5 Fast-engine trainer and pilot.** Files: `scripts/ste_train.py` (tier 1 first; decision hold; videos;
`train_log.jsonl`; cap; exit codes 2/3/4), `tests/test_ste_train.py` (CPU smoke of the whole path in seconds). Pilot:
against scripted Strike drones only; INFO record; must beat the parked Guard. 8 h; 2 GPU-h.

**L3.6 Tier 2 path for the trainer.** `--motion physics` through the existing adapter; preflight; smoke on the 5090;
throughput against L0.2. 6 h; 1 GPU-h.

## L4 Evaluation suite and gates (before any run of record)

**L4.1 Evaluation suite.** Files: `ste/evaluate.py`, `scripts/ste_evaluate.py`, tests on CPU. Groups: STANDARDS §7.4
(scripted opponents, starts, team sizes plus one outside, drop-out, cross-play, safety, smoothness, tier 1 v tier 2)
plus tag count and closest approach, the parked-Guard control, option B on and off. 1,000 games per condition, Wilson
95 % intervals, one metrics module. The Environments group (held-out layouts and world) is reported as "not built" while
the track plays the open arena only (open question to the owner; STANDARDS §4 asks for realistic environments). 12 h.

**L4.2 Gates file.** `configs/ste_learning.toml [gates.*]` with a FROZEN flag that the trainer checks; limits proposed in
the plan, read by `train-gatekeeper`, approved by the owner before the first run of record. 3 h. Gate: owner.

**L4.3 Calibration.** Suite on known players (parked Guard, scripted, the T41 policy): passes what it should, fails an
untrained policy (the C0/N0 pattern). INFO. 3 h; 2 GPU-h.

## L5 League self-play (D6)

**L5.1 League.** Files: `ste/league.py`, tests. Snapshots of both teams, scripted opponents never removed (STANDARDS
§6.3), matchmaking weighted towards opponents the learner loses to; mix written in the run. Tests: pool never drops a
scripted entry; weights follow win rates; state saves and reloads. 10 h.

**L5.2 Self-play trainer.** `scripts/ste_train.py` league mode: resume, GPU cap, videos per evaluation, GPU-hours log.
Tests: CPU smoke with two generations; resume gives the same result as no stop. 10 h.

**L5.3 / L5.4 League pilots.** Fast engine (3 GPU-h), then tier 2 (6 GPU-h, to be replaced by L0.2's figure). Watch for
cycling in the cross-play table. INFO records.

**L5.5 Runs of record.** 3 seeds on tier 2 with frozen gates. ~36 GPU-h (estimate). Gate: gates frozen; P1 and P2 ruled.

**L5.6 Debugging allowance.** `train-debug` sessions (flat reward, NaN, cycling, slow steps). 16 h; 4 GPU-h.

## L6 QC and export

**L6.1 Score runs of record** (`train-evaluate`), gatekeeper reading, records and ledger rows. 6 h; 6 GPU-h.
**L6.2 Cross-checks.** Tier 1 v tier 2; policy trained with option B, played with the even split as flown today (informs
P2). INFO. 4 h; 3 GPU-h.
**L6.3 Export** (`train-export`). Files: `scripts/ste_export.py`, tests. A policy file loadable without the training code,
`interface.toml` complete (STANDARDS §3 rule 1), reload check giving the same actions, per-drone time on the laptop CPU.
A new export dependency (for example ONNX) needs the owner. 6 h.

## L7 AirStack side (owner-gated; another session builds)

**L7.1 Specs.** Written in `svg_training` only (for example `ste_learning/specs/`): the game node (loads the policy and
`interface.toml`, one decision per drone per 0.6 s from that drone's view, 20 Hz commands through CMU's commander, tag
detection, landing the tagged pair, drop-out rule), the flight-copy filter change (option B, off by default, equal-output
test over every existing scenario), `*_game` configs, one "experimental, not for flight" page, a `CHANGES.md` entry.
The owner approves; an AirStack session builds (D4). Starts once the rules (L2.1–L2.3) and the interface (L3.1) are
settled, so the AirStack side is not left to the end; only the final hand-over waits for L6.3. 8 h.

**L7.2 AirStack-simulator 1v1.** The `tools/sim.sh` exception covers velocity steps only, so this runs under the owner's
approval or in the AirStack session. Our part: the policy, the scenario, the expected numbers from the training
simulator, the stage 6 gap limit written before the run. 6 h.

## L8 Real flight

**L8.1 Real 1v1.** Owner-gated: PREFLIGHT updated, owner approves. Our part: expected numbers, a draft test card, a
log-analysis script. The first tag lands both drones (§2.9). 6 h.

## L9 Documentation

**L9.1 Running.** HANDOFF at every session end; a record and ledger row per run; the technical writer's status. ~10 %
of each task.
**L9.2 Results page and rule updates.** A Read page with generated figures and GIFs; GLOSSARY terms; STANDARDS rows
changed only after the owner rules on P1, P2, P7 (proposed first, as a large doc change). 10 h.
