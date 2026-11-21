INTERNAL · the master plan of STE's learning track, version 2 (20 Nov 2026, after the independent soundness review).
**Phase L0 is final and APPROVED (owner, 20 Nov 2026: L0 only, cap 19 GPU-h). Phases L1–L9 are the intended path; they
are re-baselined at gate G0, the end of L0, and their budgets are OPEN.** The approval covers no PROPOSED value (the
1.6 m tag, the 0.2 band) and no phase after L0. Task status: `status/STATUS_LATEST.md`. Where this page and a reference page differ,
this page wins. Why each choice: [DISCUSSION](DISCUSSION_2026-11-19_20.md).

# PLAN: STE learning track

## 1. Goal, scope, and what "done" means

**Goal.** A Guard team policy, and the Strike team policies it was hardened against, that:

- play the area-denial game under rules that can fly;
- keep the team plan when a drone is lost (one shared policy per drone);
- are robust to attackers they did not train against (self-play with a pool of opponents);
- are trained with the Isaac Lab Starling (tier 2, with the estimator effect and drag);
- then pass the AirStack simulator and a real flight, both owner-gated.

**Scope.** Everything is built inside `svg_training/`. AirStack work (the flight copy of the filter, the game node,
game configs) is specified here; an AirStack session builds it after the owner approves.

**Done** (track level):

| Stage | Done when |
|---|---|
| Game definition | gate G0 is ruled by the owner on L0's numbers (§5) |
| Training simulator | runs of record PASS gates frozen before the runs |
| Robustness | the robustness suite is reported: held-out attackers, drone loss, the filter-mismatch test |
| Export | the policy file and `interface.toml` are exported and reload-checked |
| AirStack simulator, then real flight | each is run under the owner's approval |
| Docs | the docs and records are current |

Each result is reported as "observed in the training simulator" until it has flown.

## 2. What the soundness review found (20 Nov), and what changed

An independent reviewer attacked version 1 of this plan. The lead checked its main claims in the code. The findings
below are why L0 is now a **game definition phase**. They are the "idea may not be sound as framed" kind the owner
asked to be stopped for.

| # | Finding | Evidence | Effect on the plan |
|---|---|---|---|
| F1 | **Head-count may decide most games under the proposed tag.** The proposed tag (1.6 m, 1-for-1) is wider than the filter distance (1.10 m), so a Guard cannot block a Strike without tagging it, and each tag removes one drone from each side. With more Strikes than Guards the Strike team wins by trading. With equal numbers, parked or slightly moving Guards may hold everything: three Guards parked on a 0.8 m ring cover the whole zone (worst gap 1.53 m < 1.6 m), although losing one opens a 2.21 m gap | analysis, not measured: lead's geometry script, 20 Nov; zone test is a cylinder (`core/game.py:314-315`), the tag a sphere | L0 measures it across team sizes and rule variants (L0.11, L0.12) before any learner is built |
| F2 | **The zone radius equals the proposed tag radius** (1.6 m = 4.0 units × 0.4 m/unit), so a 1v1 at one height is decided by the tie rule (tags before the zone test) | `configs/local/nus_rules.toml`, `nus_deploy.toml`; `core/game.py:14-15` | zone radius and tag radius are both swept (L0.11); a margin between them is an option at G0 |
| F3 | **The programme's team sizes are 2v1 and 5v3** (FIXED, "team sizes of interest"), not the 3v3 of NUS's game; the real demo can only be 1v1 (two drones) | `../STANDARDS.md` §4; DISCUSSION §2.9 | L0 studies 1v1, 2v1, 3v3 and 5v3; the owner picks the target sizes at G0 (P9) |
| F4 | **The parent rule "games are played in realistic 3-D environments, the construction-site world first" is FIXED**; version 1 silently trained in the open arena only | `../STANDARDS.md` §4 "Environments" | recorded as open question P10 for G0; the open arena is the first build step, as the rule itself allows |
| F5 | **Today's tag code is not 1-for-1**: one Guard tags every Strike in range (`hit.any`); scripted Strikes fly flat (vertical speed 0), so over/under entries are never tested | `core/pair_rules.py:60-70`; `opponents/scripted.py:32-35` | L0.9 builds a 1-for-1 nearest-pair matcher; L0.10 adds Strikes that use height |
| F6 | **A scripted sweep cannot prove a game is worth learning**; only a best response can | review | L0.12 trains short exploiters; its verdict band is written before the run |
| F7 | **Tier 2 has never trained anything**, and the tier-2 budget of version 1 was likely 3–10× too small (reviewer's estimate): the STE Guard policy alone took 579 M game-steps (2.14 GPU-h, tier 1, one team, one fixed opponent) | T14 FAIL; T41 | L0.2 measures contested play (not random actions); L0.13 tests that tier 2 trains at all; the L1–L9 budgets are OPEN until G0 |
| F8 | **The training arena (7.5 m) is not the lab fence (6.5 m)**; landed drones stay filter rows in flight but are parked away in training | `configs/local/nus_hangar.toml`; `../STANDARDS.md` §4; `swarm_commander.py:2027` | the game spec sheet (L0.8) pins the arena; both sizes are in the sweep |
| F9 | **A real 1v1 cannot show team play or drone loss**, and a scripted Guard may already win 1v1 | review | L0.11 includes scripted 1v1 baselines; what the demo must show is open question P11 for G0 |
| F10 | Automation needs tooling that was in no task (one pause log, a status helper, a trainer contract), and the wake-up mechanism must be proven, not assumed | AUTOMATION §6; version 1 named an unverified tool | L0.7; §8 states only verified mechanisms |

**Other changes kept from version 1:**

- One change per gate.
- A convergence statistic in the option B gate (T31).
- Decisions labelled honestly (D4 OPEN; P1 and P2 PROPOSED).
- Sensitive material stays private.
- Test levels are named T-U (unit), T-I (integration), T-Ii (Isaac-marked), T-X (tier cross-checks), T-S (AirStack
  simulator) and T-R (real flight), so they do not collide with task IDs.

**Ruling on P2 (filter option B) moves out of L0.** Option B is built in L2, so its numbers come at the L2 gate.

## 3. Phases

| Phase | Status | What | Math library | Simulator | Ends at |
|---|---|---|---|---|---|
| **L0 Game definition and feasibility** | **APPROVED (owner, 20 Nov 2026), in work** | which game the track trains; is it worth learning; can tier 2 train, and at what cost | PyTorch | STE game engine (tier 1), Isaac Lab (tier 2) | **gate G0**: the owner rules on the game and the route, with numbers |
| L1 Drone model | intended | estimator effect (delay + noise), drag, fit to logs, comparison with the AirStack simulator | PyTorch | Isaac Lab (tier 2), AirStack simulator (logs only) | lead (exploratory until the NEAR-962 flight) |
| L2 Game rules in the training copy | intended | the rules chosen at G0, landing obstacles, drone loss, filter option B with its convergence gate | PyTorch | tier 1, then tier 2 | gate per change; **P2 ruling** |
| L3 Learner | intended | observation v0.3, attention encoder, shared actor, team critic, PPO | PyTorch | tier 1 pilot, tier 2 smoke | owner approves observation v0.3 |
| L4 Evaluation suite and gates | intended | suite, gates file, calibration on known players | PyTorch | tier 1, tier 2 | owner approves gate limits |
| L5 League self-play | intended | pilots, then runs of record (3 seeds) | PyTorch | as ruled at G0 | gates frozen; budget ruled |
| L6 QC and export | intended | scoring, cross-checks, policy file | PyTorch | tier 1, tier 2 | owner approves hand-over |
| L7 AirStack side | intended | specs here; build and AirStack-simulator games by an AirStack session | PX4 | AirStack simulator (real PX4 + EKF2) | owner (D4) |
| L8 Real flight | intended | real 1v1 | PX4 | real Starlings (2 drones) | owner |
| L9 Documentation | running | status, records, results page, STANDARDS updates after rulings | — | — | owner for reader pages |

## 4. Phase L0 in detail (final)

Order of work: L0.1 → L0.7 → L0.8 → L0.9 → L0.10 → L0.11 → L0.12 for the game. In parallel, where the GPU allows:
L0.2 first, then L0.13 and L0.3 for tier 2, and L0.4 → L0.5 for the Starling look. L0.14 (added 20 Nov 2026 with the owner's yes) runs on the CPU beside them. L0.6 closes the phase at gate G0. Every task
follows §6. Detail of the tasks that existed in version 1 is in [WORK_BREAKDOWN](WORK_BREAKDOWN.md).

| ID | Plain name | What it delivers | GPU-h cap | Gate |
|---|---|---|---|---|
| L0.1 | Track set-up: config and test skeleton | `configs/ste_learning.toml`, `ste/` package skeleton, config tests; the rows of the reference pages that still carry version 1's values (the 3.5 GPU-h step-1 row in AUTOMATION, the old L0.2 and L0.6 wording in WORK_BREAKDOWN, gate G-B in VALIDATION_QC) are brought in line, because the agents read those pages | 0 | none |
| L0.7 | Process tooling and drills | **one shared pause log** (today `gpu_pause.sh` writes into the NUS-method worktree); a tested **status helper** for `status/state.json` (lock, atomic write, boot id); the **trainer contract** as a test (the same command resumes; SIGINT checkpoints; distinct exit codes for done, cap-stop, NaN); a **wake-up drill** and a **resume drill** run before the first overnight job | 0 | none |
| L0.8 | Game spec sheet | one page, `GAME_SPEC.md`: for the game this track trains, each of zone radius and shape, height band, arena, starts, game length, speeds, team sizes, tag rule, filter mode, with **value, status (FIXED / MEASURED / PROPOSED / OPEN) and source**; and `configs/ste_game.toml` holding the same values. Today's numbers come from NUS's hangar files and the S2 game; the sheet says which the track uses | 0 | none (it lists, it does not decide) |
| L0.9 | Tag rule for the study: 1-for-1, nearest pair first | a new matcher behind `[tag]` settings (off by default = today's game bit for bit), separate from the `[filter]` setting; CPU tests first (1.59 m tags, 1.61 m does not; one Guard takes one Strike per pass; tags before the zone test). Tagged drones are removed; landing as filter obstacles is L2 | 0 | none |
| L0.10 | Scripted players for the study | Guards: parked at the centre, parked on a ring (new), plus the existing `guard_mirror`, `guard_mark_edge`, `guard_field`. Strikes: the existing straight and flank (flat), plus new ones that use height and numbers: enter at the top or bottom of the height band; one sacrifices, the others enter the gap; all arrive together from spread bearings | 0 | none |
| L0.11 | Screening sweep (INFO) | scripted Guards against scripted Strikes, 1,000 games per cell, tier 1. **Design: a base case plus one factor changed at a time**, not the full grid (the full grid is about 3,200 cells, roughly a day of GPU). Base case: 3v3, tag radius 1.6 m, zone radius 1.6 m, `guard_survives_tag_prob` 0, the 6.5 m lab arena; every Guard script against every Strike script (about 25 cells). Then, each alone against the base: team sizes 1v1, 2v1, 5v3; tag radius 1.2 / 1.4 / 1.8 m; zone radius one larger (PROPOSED 2.4 m); `guard_survives_tag_prob` 1 (the parent FIXED row requires both ends to be reported); the 7.5 m arena. About 250 cells; at the measured tier-1 rate with the filter on (about 90,000 game-steps a second, T8 and T41) roughly 2 hours (estimate). A screen only: it shortlists the rule variants for L0.12 | 3 | lead picks the shortlist and records why, before L0.12 |
| L0.12 | Best-response test: is the game worth learning? | for each shortlisted variant (at most 3), two short trainings on tier 1, each capped at 1 GPU-h (about 300 M game-steps at 3v3, the point where pilot P1b already held 0.758): an **exploiter Strike** against the best scripted Guard, and an **exploiter Guard** against the best scripted Strike. Gate written first (limits PROPOSED by the lead): the variant is **Guard-trivial** if the exploiter Strike's reach rate stays below 0.2 (Wilson upper bound); **Strike-trivial** if the exploiter Guard's hold rate stays below 0.2; **worth learning** otherwise. Controls: an untrained exploiter (must do worse than the trained one) and the parked Guard. **Gate changed by the lead before any run (LEAD CALL 21 Nov 2026):** T44's best scripts already sit far from 0.2 at tag 1.2 m and 1.4 m, so the band is read on the better of script and trained exploiter for each side, and the measured quantity is the exploiter's gain over the best script on T44's own starts, with Wilson intervals; a Strike recipe fallback (the game's distance shaping) is pre-registered and is used when neither pilot recipe probe shows a reach (the probes no longer stop the Strike runs). **LEAD CALL 21 Nov 2026 (QC N-1):** the learner positive control is **run 0**, the chosen Strike recipe trained against the parked Guard at the budget and cap of a run of record and read at pre-listed checkpoints (PASS, FAIL at the full budget, INCONCLUSIVE at the cap); the Strike runs launch only if run 0 reads PASS (a FAIL is never overridden; the Strike side is then INCONCLUSIVE: the trainer did not learn the easy Strike task at the run budget); the Guard runs do not depend on it: gate file `configs/ste_l012/gates.toml`. **Trainer built and verified on the CPU (21 Nov 2026):** a new driver, `scripts/ste_exploit_l012.py` (not `train_standin.py`), trains either side at 3v3 on the committed L0.11 game files with the tag on, one decision per 0.6 s, under the run contract; its evaluation replays T44's cells game for game on the CPU. The 6 GPU-h and the hours below stay estimates until the GPU pilot. **DONE 21 Nov 2026 (T46 INFO, T47 ABORTED; 3.37 GPU-h):** run 0 PASS; base and tag 1.4 m worth learning on both sides (trained Strike team +0.444 and +0.412 over the best script, trained Guard team +0.105 and +0.075); tag 1.2 m incomplete (one side only: the trained Strike run stopped one update short, T47; its scripts alone already sit above the gate's 0.2 band on both sides, so neither side is trivial by that band); observed in the training simulator. **L0.12b Bubble tag check DONE 21 Nov 2026** (owner-approved tag 1.15 m = the filter's 1.10 m keep-out + 0.05 m; charged to L0.12, 1.59 GPU-h; T50 screen INFO, T51 INFO, T52 ABORTED): scripts 645 / 355 as at 1.2 m; run 0 PASS; trained Guard team 466, below the script (weak); the Strike run stopped two updates short (cap sized from other rule sets); tag 1.15 m incomplete: one side only | 6 | **G0** |
| L0.2 | Tier 2 speed in contested play | game-steps per second on the 5090, tier 2 and tier 1, 3v3 (and the G0 candidate sizes), with a learner in the loop and both teams playing (not random actions), at 1,024 / 2,048 / 4,096 games; alone on the GPU. **DONE 21 Nov 2026 (T48 INFO, 0.294 GPU-h; cap 1.4 set before the run):** on the RTX 5070 Ti laptop, 3v3 training rate tier 1 51k–208k and tier 2 10k–67k game-steps/s from 1,024 to 8,192 / 16,384 games at once; tier 2 4.9–5.3× slower at 3v3; every point fitted; observed in the training simulator | 1.5 | P3 |
| L0.13 | Does tier 2 train at all? | the STE Guard policy's recipe (pilot P1b) trained on tier 2, beside a fresh tier-1 control with **the same number of game-steps and the same number of games at once**. Tier 2 cannot hold P1b's 32,768 games at once (it used 5–7 GB at 4,096 games, T12), so the games-at-once figure is the largest that L0.2 shows fits (PROPOSED 8,192). The step count is fixed in the gate before the run: 300 M game-steps if L0.2's rate lets both arms fit the cap, otherwise the largest count that fits. Needs a small new probe, because `train_standin --game nus_hangar` refuses the physics drone. Gate: tier 2 "trains" if its final hold rate (1,000 games, Wilson lower bound) is above the parked Guard's upper bound on tier 2; reaching the cap before the step count is itself a result (too slow). **LEAD CALL 21 Nov 2026 (the game):** the task moves from P1b's recipe in the hangar game to the STE game: the L0.12 Guard run's recipe (the T41 recipe, one decision per 0.6 s) on the L0.11 base game (tag 1.6 m, 3v3), exploiter Guard team against strike_straight, because L0.12 is the STE track's own learning test and its tier 1 numbers exist (base Guard 913 of 1,000 holds at 554 M game-steps, 16,384 games at once, T46); the gate is kept in substance. **Built and verified on the CPU (21 Nov 2026):** gate file `configs/ste_l013/gates.toml` (written before any run: both arms 16,384 games at once, L0.2's largest tier 2 fit, one seed, 48 updates = 301,989,888 game-steps; caps tier 1 0.75 h, tier 2 2.5 h with the final phase reserved, so a slow arm reads TOO_SLOW, never ABORTED); driver `scripts/ste_tier2_l013.py` (arm t1, then arm t2 headless on one Isaac world whose first games carry every tier 2 evaluation; physics agreement check C-1a on every launch; tier 1 replay of T44's parked-Guard cell; t1's networks also scored on tier 2) and record writer `scripts/make_ste_l013_record.py`; a smoke gate file (one update per arm, full size) comes first. GPU hours stay projections (about 1.6 h tier 2, 0.3 h tier 1) until the smoke. **DONE 21 Nov 2026 (T53 PASS, 1.53 GPU-h; on the L0.12 base game and Guard recipe, LEAD CALL):** at the same 302 M game-steps tier 2 holds 832 of 1,000 (parked 538) and tier 1 836 (parked 534); each arm's networks move to the other tier within 22 games (one training seed, one opponent, one start set (T44's first 1,000)); tier 2 about 5× slower per game-step (1.29 against 0.24 GPU-h); observed in the training simulator | 6 | P3; **G0**; after L0.2 |
| L0.3 | STE Guard policy in tier 2 without retraining | hold rate of the tier-1-trained policy (829 of 1,000, T41) on the Isaac Lab drone, same starts, parked Guard as control (row 6: Strike reaches 524, T24). **DONE 21 Nov 2026 (T49 INFO, 1.240 GPU-h; cap 1.4 set before the run):** 856 of 1,000 holds on tier 2 against 831 on tier 1 (paired lost 51 / gained 76); higher on tier 2 in this set (856 v 831; one policy, one opponent, one start set; p = 0.033 uncorrected), no claim of a general difference; parked control 525 reaches; observed in the training simulator | 1.5 | P3 |
| L0.4 | Side-by-side Starling render | the Isaac Lab Starling beside the AirStack simulator's, with and without team paint | 0.2 | P4 |
| L0.5 | Starling video look fix | clips keep the Starling's own look; team colour as a small marker | 0.3 | owner looks at stills (D9) |
| L0.14 | Crazyflie route check | one page for gate G0 on flying the game on the lab's Crazyflies ([DISCUSSION](DISCUSSION_2026-11-19_20.md) §2.16): **(1)** the STE Guard policy (T41) scored in tier 1 on the CPU with a Crazyflie-like response beside the Starling's (INFO, planned in writing first; a sensitivity test, not a Crazyflie model: the logged Crazyflie trails its setpoint by about 0.56 s under its default controller, the fitted Starling response is about 0.15 s late); **(2)** which team sizes fit which arena at the Starling's 1.10 m filter distance, from the Crazyflie repository's offline planner (read-only use; the 20 Nov runs repeated with the planner's seeds and written up); **(3)** the specification of what a Crazyflie session would build: one adapter core (observation builder, decision hold, action scaling), a state-to-observation golden fixture, the rule plug-in. Nothing is written in the Crazyflie repository and nothing flies in this task. Needs the T41 run folder (in the PROVISIONAL bundle since 20 Nov: `scripts/nus_install_provisional.sh`) | 0 | none; feeds **P13** at G0 |
| L0.6 | **Gate G0** | one decision page for the owner with every number above (§5) | 0 | **owner** |

**L0 budget: at most 19 GPU-h** (the task caps above sum to 18.5), alone on the GPU for the speed and training probes. Work estimate
about 80 hours.

## 5. Gate G0: what the owner rules, with L0's numbers

| Question | Feeds on | Options the page will carry |
|---|---|---|
| **P1 / P12 The tag and the zone.** Tag radius, zone radius, a margin between them | L0.11, L0.12 | a variant that L0.12 found worth learning; or no proximity tag (filter only); or a larger zone |
| **D2 revisit: what a tag costs.** 1-for-1 (current), the Guard survives, or a probability | L0.11, L0.12 (both ends reported) | keep; or change if 1-for-1 makes head-count decide the game |
| **P9 Team sizes.** The programme's 2v1 and 5v3, NUS's 3v3, the demo's 1v1 | L0.11, L0.12 per size | the trained size range and the main size |
| **D3 cost: where to train.** | L0.2, L0.13, L0.3 | everything on tier 2; or league on tier 1 with fine-tuning and evaluation on tier 2; with the GPU-hours each implies (reviewer's early estimate for tier 2 from scratch: 3–10× the 36 GPU-h of version 1) |
| **P10 Environments.** The parent FIXED rule asks for realistic 3-D environments | — | open arena first, construction-site world as a later phase; or sooner |
| **P11 What the real demo must show.** | L0.11 1v1 baselines | a learned 1v1; a scripted 1v1; team play shown in the AirStack simulator only |
| **P13 Fleets for real flight.** All Starlings (1v1), all Crazyflies, or a mix in one game | L0.14; L0.11 and L0.12 per size | each fleet alone, Crazyflies first at Starling metres, the Starling 1v1 as planned (lead's recommendation); or that plus one mix later (Starling Guards against Crazyflie Strikes); or a Crazyflie-sized game with its own training (a second training programme) |
| **Budget** for L1–L9 | all of the above | a ceiling per phase |

After G0 the lead re-baselines L1–L9 (tasks, order, budgets), updates this page and WORK_BREAKDOWN, and the
documentation follows.

## 6. How each task moves: develop → test run → debug → validate → QC → document

| Step | What happens | Who | Exit |
|---|---|---|---|
| 1. Design check | the interface and the touched modules are reviewed against [ARCHITECTURE](ARCHITECTURE.md) | `ste-architect` (read-only) | design OK, or a change to ARCHITECTURE |
| 2. Develop | test first; behind a setting whose default is bit-identical to today; CPU tests with the PyTorch world as oracle ([CODING_PRACTICES](CODING_PRACTICES.md)) | `ste-software-engineer`, in its own worktree (this track's builder; `train-implementer` stays the builder for other work) | unit and integration tests green |
| 3. Gate written | metric, games, seeds, controls and verdict order are written and hashed **before** any run ([VALIDATION_QC](VALIDATION_QC.md) §0) | `ste-test-qc-engineer` drafts; the lead writes the gate file | gate hash recorded |
| 4. Test run | preflight, budget, pause-aware launch, detached with a watcher ([AUTOMATION](AUTOMATION.md) §2.2) | lead with `ste-orchestrator` | exit code, logs, videos recorded in the run |
| 5. Debug | evidence first; one fix at a time, never in parallel (`train-debug`; VALIDATION_QC §4) | lead + `ste-software-engineer` | fixed, or an ABORTED record; two ABORTED → human gate H8 |
| 6. Validate | controls first (positive must PASS, negative must FAIL), then the result against the frozen gate | `ste-test-qc-engineer`, independent of the builder | PASS / FAIL / INCONCLUSIVE / INFO |
| 7. QC | merge checklist: the **full** CPU suite (never a subset: on 19 Nov a merge after a doc-only subset left a rule test failing on `main` until 20 Nov), docs check, record and ledger row, GIFs, gate hash unchanged, nothing outside `svg_training/` (VALIDATION_QC §5) | `ste-test-qc-engineer` | QC OK |
| 8. Document | record, ledger row, status, the right doc sections ([DOCS_AND_STATUS](DOCS_AND_STATUS.md)) | `ste-technical-writer` | docs current |
| 9. Merge | rebase on `development`, tests, ff-only merge into `development`, mirror updated; reader pages only with the owner's yes | lead | "Ready to push" in the status |

## 7. Human gates: when the automation stops and asks the owner

The full list H1–H9 is in [AUTOMATION](AUTOMATION.md) §3. In short:

| Gate | Triggers |
|---|---|
| H1 Direction | a FAIL or INCONCLUSIVE that changes the route |
| H2 Soundness | a rule variant is trivial for one side; tier 2 cannot train; self-play cycles; the strategy depends on the attackers' filter; drone loss breaks the team; a policy exploits a simulator artefact |
| H3 Rules | FIXED rows, P1, P2, P7, P9, P10; gate limits for runs of record |
| H4 Outside `svg_training` | any AirStack work |
| H5 Outward | NUS/CMU messages, pushes, reader pages |
| H6 Budget | a cap would be exceeded |
| H7 NUS | NUS changes direction in a way that touches this track |
| H8 Stuck | two ABORTED on one task |
| H9 Safety | anything that matters for real flights (for example drones stacked vertically: downwash is modelled in no simulator) |

**G0 is the first planned stop.** Each gate is asked as one question with options, costs and a recommendation, and
says what keeps running meanwhile. Everything not blocked keeps running; the blocked branch does CPU work only.

**The lead decides alone and records** (owner delegation of technical training calls): settings and gate limits of
pilots and INFO runs, debugging fixes, task order inside a phase, retries within the failure rules.

## 8. Automation: what wakes the work

| Trigger | Mechanism | Status |
|---|---|---|
| A job ends | trainers run detached and write an `exit_code` file; a background watcher's completion notifies the session | **verified**: used all through the NUS port |
| Heartbeat every 30 min | a background timer job whose completion notifies the session; re-armed each time | **verified by a 2-minute drill on 20 Nov**; L0.7 built `scripts/ste_job.py` and its drills ([AUTOMATION](AUTOMATION.md) §7), to be run on each machine before its first detached GPU job |
| Fallback | a timer at each job's expected end + 15 min, and every 3 h | same mechanism |
| Subagent finishes | its completion notification | verified |
| Session scheduling tools (wake-ups, cron) | may replace the timer | not relied on until a drill shows they work |

**Limit, stated plainly:** nothing is scored, launched or reported when no Claude session is alive. Detached trainers
keep running. A new or resumed session reads `status/RESUME.md` and `status/state.json`, adopts live jobs, and
relaunches jobs killed by a reboot from their recorded commands (AUTOMATION §2.3). The resume drill in L0.7 proves
this before the first overnight run.

**Stage 5.1 lesson.** It finished at 21:06 on 19 Nov and was scored only when the owner asked at 22:00, because no
watcher was armed. Every launch now arms its watcher in the same step.

## 9. Budgets

| Item | Budget | Status |
|---|---|---|
| **L0** (§4 caps) | **19 GPU-h** | **FIXED: approved by the owner, 20 Nov 2026** (task split PROPOSED by the lead; `configs/ste_learning.toml`) |
| L1–L9 | OPEN | set at G0 from L0.2 and L0.13. Version 1 guessed ≈ 60 GPU-h; the review estimates tier-2 training from scratch at 3–10× that, and counted costs version 1 left out (3 seeds at the learner stage, six exploiter trainings, a second training for the filter-mismatch study) |
| Per job | wall clock = cap × 1.5, pauses excluded; progress check at launch + 45 min; no launch below 50 GB free disk | PROPOSED |

The GPU is shared:
- Short pilots and speed tests run alone; multi-seed runs may run side by side.
- The owner's `gpu_pause.sh` pauses are respected and logged.
- Nothing trains while the AirStack simulator or a flight session is up.

## 10. Status every 30 minutes

The `ste-technical-writer` writes it from `status/state.json`, run logs, the GPU state and git (live `main` against
the mirror). It is posted in the chat in the owner's format:

- three tables (phases with math library and simulator; the current phase task by task; other workstreams);
- "Next" and "Waiting on you";
- a bold "Ready to push" line while main has unpushed commits.

`status/STATUS_LATEST.md` is overwritten and `status/LOG.md` is appended to. Events trigger an update at once: a run
finishes, a gate verdict, a failure, a human gate reached. No invented numbers. An ETA comes only from rates measured
in the run, marked "est.". When everything waits on the owner and the GPU is idle, the update shrinks to one line
every 2 hours (PROPOSED; the owner may prefer the full update regardless). Template:
[status/STATUS_TEMPLATE.md](status/STATUS_TEMPLATE.md).

## 11. Commits, merges and documents

- This folder reached `main` on 20 Nov (the owner asked for the documentation there); since the evening of 20 Nov the
  work lands on `development`, the branch both machines share (`../CLAUDE.md`, "Two machines, one working branch"). It holds no NUS source, names or
  private messages. L0 was approved by the owner on 20 Nov 2026; no later phase starts without its own approval.
- Code, tests, records and ledger rows are ff-merged to `development` by the lead after QC. Reader pages go to
  `development` only with the owner's yes; `main` moves only on the owner's word.
- Status files are committed at session end. HANDOFF §0 gets a dated line per session.
- Every gated run records its videos in the run; every result shown in docs has a GIF.
- Agent files are copied into `../.claude/agents/` (with `git add -f`) at the same merge.

## 12. What the owner is asked now

| # | Question | Recommendation |
|---|---|---|
| 1 | Approve phase L0 (game definition and feasibility) with a cap of 19 GPU-h, alone on the GPU for its probes? | yes. **ANSWER: approved (owner, 20 Nov 2026)** |
| 2 | Heartbeat when everything waits on you: the full update every 30 min, or one line every 2 h? | one line every 2 h. **ANSWER: none; the standing rule holds (full update every 30 min)** |

The merge of this folder to `main`, with its README, flowcharts and agent files, was asked for by the owner on 20 Nov
and is done with this version.

Everything else (tag and zone, what a tag costs, team sizes, where to train, environments, the demo, the L1–L9
budget, filter option B, the AirStack approach) is ruled at its gate, with numbers.

## 13. Main risks

| Risk | Check | If it happens |
|---|---|---|
| The proposed rules make the game trivial for one side (F1, F2) | L0.11, L0.12 | G0: another variant (radius, margin, what a tag costs, sizes), or no proximity tag |
| Tier 2 cannot train, or costs too much (F7) | L0.2, L0.13 | G0: league on tier 1 with tier 2 for fine-tuning and evaluation |
| A scripted Guard is enough for the demo (F9) | L0.11 1v1 | G0: the demo shows a scripted 1v1; learning is shown in simulation |
| Option B makes the filter fail to converge | L2 gate (T31 statistic) | keep the equal split for training |
| The strategy depends on attackers running our filter | robustness suite | H2 |
| Self-play cycles or forgets | league with a pool and a held-out set | change the mix (lead); H1 if it persists |
| The exploratory drone model misleads | L1, the NEAR-962 flight | refit; H9 if it matters for flights |
| The session dies or context is lost overnight | L0.7 resume drill; state in files | a new session resumes from `status/` and HANDOFF |
