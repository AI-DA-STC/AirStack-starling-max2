# Claude handoff: svg_training (vectorised training pipeline)

> **How to use this file.** Read it at the start of a session, after [../../CLAUDE.md](../../CLAUDE.md).
> §4 is the current state, §5 is what is waiting on people. Update both before you stop.
> Last updated: 14 November 2026 (session 1, fourth round: committed to the repository).

## 0. Resume here (for a new session or another Claude account)

Everything needed is in this folder; nothing depends on the previous chat.

1. `cd ~/AirStack-starling-max2/svg_training && claude`, then say: **"Run the train-start skill, read
   docs/claude/HANDOFF.md §0, and continue S0 from the first unticked task."**
2. The owner approved on 14 November 2026: the design; the S0 gates and decision rules in the S0 plan
   (Task 1, `[gates]` and `[decisions]`, unchanged); **subagent-driven execution** (a fresh agent
   builds each task from the plan, a fresh reviewer checks it, the lead verifies by running the tests).
3. Rules while building: write only inside `svg_training/`; commit finished, tested steps with explicit
   paths, never push (builder agents make no git writes; the lead commits); no `pip install`; Python is
   `~/miniconda3/envs/env_isaaclab/bin/python`; tests with `python -m pytest -q` from this folder.
4. Model use the owner prefers: the lead plans and reviews, cheaper models build. He expects usage
   limits to run out quickly, so **update the table below after every task**, before starting the next.
5. A copy of this file is kept at `~/Downloads/claude-handoff-svg-training.md`; refresh it with
   `cp docs/claude/HANDOFF.md ~/Downloads/claude-handoff-svg-training.md` after each update.

**S0 progress** (plan: [../plans/2026-11-14-s0-measure-throughput.md](../plans/2026-11-14-s0-measure-throughput.md))

| Task | What | State | Evidence |
|---|---|---|---|
| 1 | Skeleton, gates, record scaffolding | done | 3 tests pass; reviewed. Approved `configs/s0_benchmark.toml` sha256 `959dc7107f0169a4b05c448575bd5e8690b7180953805fd2a542c0f562e19197` |
| 2 | Analytic shapes | done | reviewed; maths checked independently. Known limit parked for S3: the 24-step ray march is conservative beside surfaces (`runs/sdd/progress.md`) |
| 3 | Distance field | done | reviewed; maths checked independently. Known limit parked for S3: the 24-step ray march is conservative beside surfaces (`runs/sdd/progress.md`) |
| 4 | World, range rays, line of sight | done | reviewed; maths checked independently. Known limit parked for S3: the 24-step ray march is conservative beside surfaces (`runs/sdd/progress.md`) |
| 5 | Placeholder response model, tier 1 benchmark environment | done | reviewed twice; 23 tests pass for Tasks 1–5. Review caught and fixed: Guard drones could reach Strike speed on diagonals (now capped at speed ÷ 1.5 in norm, with a test) |
| 6 | Timing harness, tier 1 benchmark script | done | reviewed (timing logic verified: no hidden sync, clock bounded by synchronises); one fix round (re-runs skip finished points instead of duplicating rows). Whole suite: 64 tests pass |
| 7 | Tier 2 benchmark (Isaac Lab) | code done and reviewed; NEVER RUN | Isaac Lab wiring checked against local source by an expert reviewer, exit paths re-reviewed, 3 fix rounds. The only proof left is the smoke run (plan Task 7 Step 5), which launches Isaac Sim: HELD until the owner confirms he is at the machine or on Ethernet (laptop is on WiFi only) |
| 8 | Record and ledger from results and gates | done | 30 tests pass; reviewed with an attack list, two fix rounds. Reviews closed three ways the record could have shown a false PASS (NaN rate, missing NaN count, negative or duplicated rows). `make_record.py` needs `--seeds` |
| 9 | Run S0 on the laptop, record, gatekeeper | tier 1 half DONE (no record yet); tier 2 half HELD | `runs/2026-11-14_s0_laptop/results.jsonl`: 128 rows, 126 ok, 2 out-of-memory at 65,536 games, no NaN, one code hash `e9a7b4407e58`. To finish S0 after the owner's Isaac go-ahead, from a local terminal or on Ethernet: first plan Task 7 Step 5 (one smoke point), then `bash scripts/run_s0.sh 2026-11-14_s0_laptop 959dc7107f0169a4b05c448575bd5e8690b7180953805fd2a542c0f562e19197` (skips finished points, runs tier 2, writes the record and ledger row T1), then the `train-gatekeeper` agent reads the record. Do not edit code under `source/`, `scripts/`, `configs/` in between (rows carry the code hash) |

Build bookkeeping (rulings, briefs, reports, snapshots) is in `runs/sdd/`; its ledger is `runs/sdd/progress.md`.
S0 was built before the folder was tracked: each task was reviewed from a file diff against a snapshot (`bash runs/sdd/tools.sh`).
Tasks 2–4 are built and reviewed together. No Isaac Sim launch before the lead checks `docker ps` and
that the owner is at the machine or on Ethernet.

What the final review found that matters to the owner: (1) a cold laptop GPU made two repeats differ by 22 % at the smallest sweep point, so warm-up becomes at least 50 steps AND 2 s (gates and config untouched); (2) one distance routine in the tier 1 stand-in dominated open-arena timing (being replaced, with a before/after measurement); (3) rows now carry a hash of the code because the folder is untracked; (4) `gnome-remote-desktop-daemon` holds 611 MiB of GPU compute memory on this laptop, a sign a remote-desktop session may be active.

**Tier 1 observed, 14 November 2026** (training simulator, tier 1, RTX 5070 Ti laptop; stand-in drone model, no safety filter, no policy network; NOT yet a record). Best mean over two repeats:

| Case (5 Guard against 3 Strike unless said) | Game-steps per second | At games |
|---|---|---|
| open arena, 1 against 1 | 86.9 million | 65,536 |
| open arena | 12.2 million | 65,536 |
| distance field the size of the construction-site crop | 9.3 million | 16,384 |
| 10 obstacles | 3.5 million | 4,096 |
| 50 obstacles | 0.90 million | 1,024 |
| 10 obstacles + line of sight | 0.50 million | 4,096 |
| distance field + 32 range rays | 0.33 million | 4,096 |
| 10 obstacles + 32 range rays | 64,000 | 1,024 |
| full sensing: field + 10 obstacles + 32 rays + line of sight | 48,000 (0.38 million drone-steps) | 1,024 |

- Decision rule "tier 1 can do bulk training on this machine" (≥ 50,000 drone-steps per second with full sensing): met, 384,000. Simulator stepping for 2 billion drone-steps: about 1.5 GPU-hours, a lower bound (no policy, no learning update, no safety filter).
- Full sensing costs about 250 times the open arena. The hot spot is range rays against per-game obstacles (the ray march evaluates every obstacle at every step); rays against the baked field alone are about five times cheaper. This is the first thing to optimise in S3.
- **Waiting on the owner — the repeat gate.** One point misses the approved 10 % repeat gate: 1 against 1, open arena, 256 games, spread 18 % (every other point ≤ 8.5 %). At 256 games the 200 timed steps last about a tenth of a second. As the approved config stands, the record will say FAIL on that gate. The lead may not change a gate or the pinned config; options for the owner: accept the FAIL as written, or approve a new config for a new run in which the timed window is at least 200 steps and at least 2 s.

**Packaging (14 November 2026, third round).** The folder is COMMITTED: `2daf942` on `main` (change-log
CHG-0068), mirror updated (one commit ahead of GitHub; the owner pushes after checking the repository is
private). It is a top-level component of the repository. `docker/build.sh` builds `svg-training:isaaclab-2.3.2` on NVIDIA's `nvcr.io/nvidia/isaac-lab:2.3.2`
(26 GB download, once) and adds pytest plus two launchers, `svg-python` and `svg-isaaclab`, that keep exit codes
(Isaac Sim's own `python.sh` turns every failure into exit 1). Tests: host 108 passed; container 106 passed,
2 skipped (host-only). `scripts/run_s0.sh` works in both places (`SVG_PY`, `SVG_ISAACLAB`, `SVG_IN_CONTAINER`).
The tier 1 rows in `runs/2026-11-14_s0_laptop/` carry code hash `e9a7b4407e58`; the packaging changed
`scripts/run_s0.sh`, so finishing that run now would mix two code versions (the record warns). Re-run tier 1
before the record: it takes about 15 minutes, and it is needed anyway if the owner approves a new config for the
repeat gate.

State values: not started · building · built, in review · done (tests quoted) · blocked (why).

## 1. Summary

Jeremy (Robotics AI Engineer, NEAR Lab, ST Engineering) wants training for the Strike vs Guard game to
run in parallel on a GPU. On 14 November 2026 a first session read the flight stack and the programme
website, ran web research on drone training in Isaac Lab, proposed a pipeline, and the owner chose an
approach. This folder now holds the rules, the design, the research digest, the diagrams, and the
agents and skills for the work. **No training code exists and nothing has been run.**

## 2. Read these first

| File | Why |
|---|---|
| [../../CLAUDE.md](../../CLAUDE.md) | hard rules, environment, how a session runs |
| [../../STANDARDS.md](../../STANDARDS.md) | interface, game specification, drone models, gates, records |
| [../DESIGN.md](../DESIGN.md) | seven stages, two tiers, four uses, build order |
| [../RESEARCH.md](../RESEARCH.md) | evidence with sources |
| [AGENTS_AND_SKILLS.md](AGENTS_AND_SKILLS.md) | which agent or skill to use for what |
| `~/Downloads/claude-handoff-vectorised-drone-training.md` | the earlier chat that started this (11 November 2026) |

## 3. Non-negotiables

1. Write only inside `svg_training/`. Ask the owner before anything outside it.
2. Never push. Commit finished, tested work with explicit paths (CLAUDE.md rule 2).
3. Drone numbers flow from the drone to the trainer, never back.
4. A simulator result is "observed in the training simulator", not "validated".
5. Gates before runs; never moved.
6. Programme wording: Strike team, Guard team, tag, reach the zone, drone team.

## 4. Current state

**How to talk to the owner.** Start from the high-level picture, then go deeper step by step. Use
standard professional terms. Prefer simple diagrams and tables, readable at page width. He is new to
this simulation and training stack. He dislikes walls of text. He asked to be consulted before
anything uncertain is executed, and told about anything that could affect other sessions' work.

**Decided by the owner, 14 November 2026.**

| Decision | Choice |
|---|---|
| What the pipeline is for | team strategy; hosting partner strategies; low-level flight control; camera-based behaviour ("future work, not a priority at the moment") |
| Build approach | C: two tiers sharing one game ([DESIGN §4](../DESIGN.md)) |
| Isaac Lab version | 2.3.2 now; 3.0 later on the RTX 5090 machine |
| Folder | `svg_training` in the live clone `~/AirStack-starling-max2` (he first wrote "IssacLab") |
| Packaging (third round, same day) | "the point is to add a training pipeline to airstack": the folder is committed as a top-level component of the repository, like `localisation/`, with a `docker/` image carrying Isaac Lab (option A); its agents and skills are committed too ("yes commit agents") |
| Models | Fable orchestrates; if it runs out, Opus at high effort |
| Fourth round (15 November) | repository may be public ("its just a training pipeline doesnt need to be private"); new S0 config approved (timed window at least 200 steps and at least 2 s); Isaac Lab launch approved ("ok do it"; he is remote with the laptop behind him); after a tag both drones leave by default |
| Design | approved ("yup looks good"), with the four answers below |
| Tag | physical contact between a Guard drone and a Strike drone; no tag radius. His words: "the end goal is to have physical interdiction between strike team and guard team drones" |
| Safety filter | only between drones of the same team |
| Environments | "different real-ish environments", the construction-site world as the example; he asked for research on more realistic ones and whether it affects training |
| Velocity-step logs | this pipeline may run `tools/sim.sh` |
| Training hardware | "eventually" an RTX 5090, RTX PRO 6000 or RTX 6000 Ada |

The priority order among the four uses (strategy, partners, flight control, cameras) is Claude's
reading of his answer, not his words; confirm it if it matters.

**The earlier handoff's three open questions, answered.**

| Question | Answer |
|---|---|
| What is being trained? | the four uses above |
| Which Isaac Sim and Isaac Lab? | Isaac Sim 5.1.0, Isaac Lab 2.3.2 + 25 commits → the 2.x cloning API (`clone_environments`, `GridCloner`) |
| Which AirStack simulation profile, how many drones? | Isaac Sim + Pegasus + PX4 v1.16.1, three drones by default, PX4 time about 1.3 times wall-clock |

**Session 1 (14 November 2026): what was done.**
- Read `~/AirStack-starling-max2` and the website repository; six agents (two repository readers, one
  local Isaac Lab inspector, three web researchers).
- Checked that a new top-level folder cannot break another session's commit: the pre-commit hook reads
  staged paths only and the docs checker does not scan it.
- Built the diagram deck (10 slides) and, after the owner's choices, wrote `CLAUDE.md`,
  `STANDARDS.md`, `docs/DESIGN.md`, `docs/RESEARCH.md`, this file, six agents and six skills.
- Nothing outside this folder was edited. Nothing was committed.

**Session 1, second round (same day): what the owner's answers changed.**
- Contact tags and a per-team safety filter are now FIXED in STANDARDS §4. Contact distance in tier 1
  is 0.50 m, measured from the drone's USD.
- Three more research tasks: the construction-site world on disk, sources of realistic environments,
  and how clutter and contact change training. Results are in RESEARCH §9–10 and DESIGN §7.
- A realistic environment does affect training: drones lose sight of each other, cost rises, one
  layout is not enough, and sensing becomes the speed limit. DESIGN §7 has the environment ladder.
- Published comparisons found velocity-commanded drones touch an agile drone far less often than
  thrust-and-body-rate ones. S2 measures this here; the fallback is a final-approach skill on tier 2.
- Build steps keep their names S0–S5 but now carry environments: S2 open arena, S3 random blocks and
  columns, S4 the construction-site world with the tier 2 cross-check.

**Calls Claude made in that round, for the owner to correct:** a drone that touches a structure
leaves the game and avoiding structures is learned (the flight stack has no obstacle avoidance);
the policy senses its surroundings through range rays; files baked from the construction-site asset
stay out of git; real flights of a contact policy should start with a virtual contact distance.

**Facts found that the design rests on** (sources in STANDARDS §3–5 and RESEARCH):
- A strategy sends velocity + yaw rate in the world frame, 20 times a second, into the ground
  controller; today's plug-in point is `/svg/{name}/teleop_command`.
- The safety filter is one centralised node, about 550 lines of Python, keep-out 1.10 m.
- Isaac Lab 2.3.2 offers a multirotor at motor-thrust level, multi-agent environments and skrl's
  IPPO and MAPPO; it has no velocity controller and no self-play. Both are ours to build.
- Isaac Lab 3.0 (20 October 2026) adds batched velocity controllers and a velocity-command
  navigation task, needs Isaac Sim 6.2 and a newer GPU driver.
- No measured throughput exists for quadrotor teams in Isaac Lab.
- The repository holds no Strike vs Guard game code.

## 5. Open items

| Item | Who | Needed before |
|---|---|---|
| A pair mask in CMU's safety filter, so that a contact tag can fly at all; and a flight safety case for deliberate contact | owner + CMU (outside this folder) | any flight of a contact policy |
| The zone's size and place in each world; the playing volume | owner | S2 |
| Licence of the construction-site asset (an Unreal Engine asset pack exported by the lab; no licence file found) | owner | before anything made from it leaves the lab |
| What the real drone senses its surroundings with: a known map, or an on-board range sensor | owner | S3 |
| Control level for contact tags: stay at velocity, or add a final-approach skill at thrust and body rates | owner, on the S2 numbers | after S2 |
| When real-drone velocity-step logs can be flown (simulator logs: approved, by running `tools/sim.sh`) | owner | the `real` parameter set |
| Compute budget: GPU-hours per run and in total | owner, after S0 | S2 |
| Who approves each `gates.toml` (proposed: the owner, in each step's plan) | owner | S0 |
| Arena sizes in metres (lab, hangar, outdoor) and zone radius | owner + NUS | S2 |
| What a drone may observe about others (full state, or shared with delay and loss) | owner + partners | S2 |
| How a drop-out is simulated | owner + partners | S4 |
| Written velocity contract with NUS and CMU (Linear NEAR-874, NEAR-875) | owner + NUS + CMU | use 2, S5 |
| Tell UPenn and NUS about this pipeline; UPenn already has an Isaac Lab environment | owner | early |
| Access to a training workstation (RTX 5090, RTX PRO 6000 or RTX 6000 Ada); its driver and Isaac versions | owner | S0 on that machine |
| Build and try the image on the training workstation (`docker/build.sh`, then `docker/run.sh`) | owner + Claude | S0 on that machine |
| A ROS 2 policy node inside the AirStack tree | owner (separate approval) | S5 |
| Rotor positions for tier 2: sim CAD or the drone's parameters | owner | S4 |
| Drone speed limit: the parameter file says 3 m/s, `docs/CONFIG.md` says 20 m/s | read the live drone | S1 |
| Driver 595 with AirStack's Isaac Sim 5.1 | untested | any move to Isaac Lab 3.0 on a machine that also runs AirStack |

**Not verified** (carry these as doubts, not facts): every throughput estimate for Isaac Lab; the
Isaac Lab 3.0 release details beyond what RESEARCH cites; the links in RESEARCH (collected by web
research agents; open one before quoting it outside the lab); the axis order of the inertia values;
the velocity response (0.15 s + 0.55 s), which comes from one CMU log at 5 m/s, not from our drones;
whether PX4's position controller differs between 1.14 (drone) and 1.16.1 (AirStack simulator).

**Independent checks run in session 1.** A builder check of the design and a review by the agent that
wrote the agents and skills found five wrong statements (simulator speed cap, arena box, delay
figure, Isaac Lab velocity controller, one speed cap in the filter); all five are corrected in
STANDARDS and DESIGN. Their open questions are in the table above.

## 6. How to continue

1. Run the `train-start` skill.
2. The design is approved. A change to it goes through the owner first.
3. The S0 plan is written: [../plans/2026-11-14-s0-measure-throughput.md](../plans/2026-11-14-s0-measure-throughput.md)
   (9 tasks, not started). Its `[gates]` and `[decisions]` need the owner's approval before the first
   run; then build it with `train-implementer`, test first, and have `train-gatekeeper` read the record.
4. One step at a time, S0 to S5. Each ends on a record and a ledger row.
5. For a design question, brief the adviser agents in parallel with the files, not your conclusion;
   reconcile; show the owner; then build.
6. Model split the owner prefers: the lead plans, orchestrates and reviews; other models execute.

## 7. Source material

| Source | Where |
|---|---|
| Flight stack, configs, records | this repository, read-only from here |
| Starling system identification | `isaac_sim/Starling 2 Max Sys ID Results - Slite.pdf` |
| Drone PX4 parameters | `starling_1_indoor_params.params` |
| Safety filter | `AirStack/robot/ros_ws/src/svg_ground_control/svg_ground_control/cbf_filter.py` |
| Ground controller | same package, `swarm_commander.py`, `trajectory.py`, `fence.py` |
| Programme, game, wording rules | `~/Documents/GitHub/Strike-Versus-Guard` (`content/programme/`, `STANDARDS.md`) |
| Programme reports | `~/Documents/GitHub/Strike-Versus-Guard-sources` — **confidential**: point to them, do not copy from them |
| Isaac Lab | `~/IsaacLab` (2.3.2), conda `env_isaaclab` |
| Linear plan snapshot | `docs/plans/2026-11-13-project-plan-linear.md` in this repository |
