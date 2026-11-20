INTERNAL · the lab's working folder for the STE learning track, and the page to read first. The working plan for Claude sessions is [PLAN.md](PLAN.md); reader pages for NUS and others stay in [../README.md](../README.md) and `../docs/`.

# STE learning track

STE (the lab) trains its own Guard team and Strike team policies for the area-denial game: the Guard team holds a
circular zone and the Strike team tries to reach it. A *policy* is the trained program that turns what a drone sees
into a speed command.

The reason is in the six tests on the [front page of svg_training](../README.md). Policies trained with NUS's code
fail under STE drone conditions: the Strike team reaches the zone in 43 of 1,000 games, then in 740 once the safety
filter of AirStack (the flight software, from CMU) is added, then in 983 once drones may change height (3-D). These
counts were observed in the training simulator.

The track runs in parallel with NUS's work and does not wait for it (decision D1); NUS's results plug in when ready.
The goal is a pair of policies that play under rules that can fly, keep the team plan when a drone is lost, and hold
against attackers they did not train against. They are then checked in the AirStack simulator (the flight
software's own simulator) and in a real one-against-one (1v1) flight, each with the owner's approval.

**Phase L0 was approved by the owner on 20 November 2026, with a cap of 19 GPU-h.** The approval covers L0 only:
phases L1 to L9 and every PROPOSED value stay open until their own gates. Task-by-task status:
[status/STATUS_LATEST.md](status/STATUS_LATEST.md).

## Where it stands

Three labels are used on this page. DECIDED: the owner said so. PROPOSED: suggested, not yet ruled. OPEN: waiting
for the owner's ruling. D and P numbers are rows of the [discussion record](DISCUSSION_2026-11-19_20.md).

| Item | Status | Ruled at |
|---|---|---|
| STE runs its own learning track, in parallel with NUS (D1) | DECIDED | — |
| A tag takes out one Guard drone and one Strike drone (D2) | DECIDED, provisional | revisited at gate G0 |
| Training happens in Isaac Lab; the fast engine is for quick experiments (D3) | DECIDED | cost re-checked at gate G0 |
| Policies run on the mission-control laptop, not on the drones (D5) | DECIDED | — |
| Learner: one shared policy per team, drone loss, self-play against a pool (D6) | DECIDED | — |
| Isaac Lab videos show the Starling as it looks in the AirStack simulator (D9) | DECIDED | — |
| Tag radius of 1.6 m, and the zone radius against it (P1, P12) | PROPOSED | gate G0 |
| Where to train, once the cost of D3 is measured: all in Isaac Lab, or the league on the fast engine | OPEN | gate G0 |
| Team sizes: 1v1, 2v1, 3v3 or 5v3 (P9) | OPEN | gate G0 |
| Environments: open arena first, or the construction-site world sooner (P10) | OPEN | gate G0 |
| What the real demo must show (P11) | OPEN | gate G0 |
| Budgets of phases L1 to L9 | OPEN | gate G0 |
| Filter option B (P2) | PROPOSED | end of phase L2 |
| How AirStack is changed (D4) | OPEN | phase L7 |

Two technical calls were made by the lead (the main Claude session) and recorded: the drone's estimator is modelled
as a delay plus noise first (D7), and work on NUS's training recipe is paused (D8); this track does not depend on it.

**The first gate.** Phase L0 is approved (owner, 20 November 2026). It ends at gate G0, where the owner rules on the
game and the route with L0's numbers.

## What is being built

![The training loop inside svg_training: game reset, what each drone sees, one shared policy per team, the command chain, the Starling physics drone in Isaac Lab with the fast engine as its twin, game rules, reward, the learner with its league, evaluation and export; below the boundary of svg_training, the game node on the mission-control laptop, CMU's commander and flight filter, PX4 and the drones](figures/architecture.png)

Green boxes already exist in `svg_training`; blue boxes are to be built; amber dashed boxes wait for a ruling.

**The loop, in words.** A game starts with a number of drones per team and their start positions. Each drone gets its
own view of team-mates, opponents and the zone. The team's policy turns that view into a speed command. The command
passes through a copy of the flight software's command chain: CMU's commander, then the safety filter, which changes
commands so that every pair of drones stays 1.10 m apart. A simulated Starling flies the command. The game rules then
decide who is out and whether a Strike drone reached the zone, and the team gets its reward: a win or a loss. The
learner uses thousands of such games at once to improve both policies. One pass takes 0.6 s of game time.

**After training.** A fixed evaluation suite scores the policies against pass marks written before each run. A policy
that passes is exported as two files: the policy itself and an interface file that states what the policy expects.

**Below the boundary.** Everything above is built inside `svg_training`. The flight side is only specified here; an
AirStack session builds it after the owner approves. The mission-control laptop runs the policy once per drone every
0.6 s and sends the commands through CMU's commander and flight filter to PX4, the flight controller on each drone.
This is tried in the AirStack simulator first, then in a real 1v1 flight with two drones.

**Terms used in the figure.**

| Term | Meaning | Status |
|---|---|---|
| Shared policy | One network copied onto every drone of a team. Each drone feeds it its own view and gets its own command | DECIDED (D6) |
| Team critic | The part of training that scores the whole team's situation. It is used in training only and never flown | DECIDED (D6) |
| PPO | The learning method: a standard algorithm that improves a policy step by step from the games it played | — |
| Self-play | Both teams learn by playing games against each other | DECIDED (D6) |
| Scripted player | A hand-written player that follows fixed rules and does not learn, for example a Guard team that stays parked | exists |
| League | The pool of opponents a team trains against: earlier saved versions of the other team, plus scripted players | DECIDED (D6) |
| Tier 1 | STE's fast game engine: a simplified drone, used for quick experiments and debugging | exists |
| Tier 2 | The Isaac Lab physics drone: a Starling with rotors and PX4-style control loops | exists |
| Estimator effect | A real drone flies on a position estimate that is slightly late and noisy; tier 2 gets a delay-plus-noise model of that | to build |
| Tag | A Guard drone and a Strike drone closer than the tag radius are both out and land. Proposed radius: 1.6 m between centres | PROPOSED (P1) |
| Option B | A safety-filter variant: in a Guard–Strike pair only the Guard drone swerves | PROPOSED (P2) |

## The plan

![Roadmap of phases L0 to L9 with the simulator each uses and where each ends: L0 was approved by the owner on 20 November 2026; L0 ends at gate G0, where the owner rules on the game and the route; L1 to L8 are the intended path with budgets open; L9, documentation, runs alongside](figures/plan_phases.png)

Phase L0 is final and approved. Phases L1 to L9 are the intended path: their tasks, order and budgets are set again at gate G0.
L9, documentation, already runs alongside.

Terms in the table: a *pilot* is a short trial run; a *smoke test* is a very short run that only checks the code
works; a *run of record* is a run whose result is reported and scored against a gate; a *seed* is the random
starting point of a run, so 3 seeds means three independent repeats; *QC* is quality control, the checks before a
merge. The AirStack simulator runs the real PX4 code.

| Phase | What | Simulator | Ends at |
|---|---|---|---|
| L0 Game definition and feasibility | which game to train, whether it is worth learning, whether Isaac Lab can train it and at what cost | tier 1, tier 2 | gate G0 (owner) |
| L1 Drone model | estimator effect, drag, fit to flight logs | tier 2; AirStack simulator logs | the lead (exploratory) |
| L2 Game rules in the training copy | the rules chosen at G0, landing, drone loss, filter option B | tier 1, then tier 2 | owner rules on option B |
| L3 Learner | observation version 0.3, shared policy, team critic, PPO | tier 1 pilot, tier 2 smoke test | owner approves the observation |
| L4 Evaluation suite and gates | test suite, gates file, calibration on known players | tier 1, tier 2 | owner approves gate limits |
| L5 League self-play | pilots, then the runs of record with 3 seeds | as ruled at G0 | owner rules the budget |
| L6 QC and export | scoring, cross-checks, the policy file | tier 1, tier 2 | owner approves the hand-over |
| L7 AirStack side | specifications here; built and played by an AirStack session | AirStack simulator | owner |
| L8 Real flight | a real 1v1 game | real Starlings (two drones) | owner |
| L9 Documentation | status, records, results page | — | owner, for reader pages |

Each result is reported as "observed in the training simulator" until it has flown.

## Phase L0 step by step

![Phase L0 in three lanes: lane A, which game and is it worth learning, runs L0.1, L0.7, L0.8, L0.9, L0.10, L0.11, L0.12; lane B, can Isaac Lab train and at what cost, holds the three probes L0.2, L0.13 and L0.3; lane C, the Starling's look in videos, runs L0.4 then L0.5; all three end in L0.6, gate G0](figures/l0_tasks.png)

L0 builds no learner. It answers three questions, one per lane, and brings the numbers to the owner at gate G0.
A GPU-hour (GPU-h) is one hour of the shared graphics card. INFO means measured, with no pass mark.

| ID and plain name | What it delivers | GPU-h cap |
|---|---|---|
| L0.1 Track set-up: config and test skeleton | the track's settings file, an empty code package, tests of the settings | 0 |
| L0.7 Process tooling and drills | one shared pause log, a status helper, a test of how trainers stop and resume, a wake-up drill and a resume drill | 0 |
| L0.8 Game spec sheet | one page, `GAME_SPEC.md`: every value of the game with its status and source | 0 |
| L0.9 Tag rule for the study: 1-for-1, nearest pair first | a new tag matcher behind a setting that is off by default | 0 |
| L0.10 Scripted players for the study | parked Guard teams; Strike teams that use height and numbers | 0 |
| L0.11 Screening sweep (INFO) | scripted teams against each other, 1,000 games per setting; a shortlist of rule variants | 3 |
| L0.12 Best-response test: is the game worth learning? | each shortlisted variant sorted: trivial for one team, or worth learning | 6 |
| L0.2 Tier 2 speed in contested play | game-steps per second on both tiers, with a learner and both teams playing | 1.5 |
| L0.13 Does tier 2 train at all? | the recipe behind the STE Guard policy, trained on tier 2 beside a tier 1 control | 6 |
| L0.3 STE Guard policy in tier 2 without retraining | how often the tier 1 policy still holds the zone on the Isaac Lab drone | 1.5 |
| L0.4 Side-by-side Starling render | the Isaac Lab Starling beside the AirStack simulator's | 0.2 |
| L0.5 Starling video look fix | clips that keep the Starling's own look, team colour as a small marker | 0.3 |
| L0.6 Gate G0 | one decision page for the owner, with every number above | 0 |

The cap for the whole phase is 19 GPU-h (the task caps sum to 18.5); the work estimate is about 70 hours.

Notes on four tasks:

- **L0.11** starts from one base case (3v3, tag radius 1.6 m, zone radius 1.6 m, the 6.5 m lab arena) and changes one
  thing at a time: team size (1v1, 2v1, 5v3), tag radius (1.2 to 1.8 m), zone size, what a tag costs, arena size. About
  250 settings instead of the full grid of about 3,200. It only screens; it proves nothing about learning.
- **L0.12** trains an *exploiter* for each team: an opponent trained for a short time only to beat one fixed player.
  A variant is trivial for the Guard team if the exploiter Strike team still reaches the zone in fewer than 0.2 of
  the games, and trivial for the Strike team in the mirror case. The 0.2 limit is PROPOSED by the lead and written
  down before the run.
- **L0.13** runs after L0.2, because L0.2 shows how many games tier 2 can hold at once; both arms then use the same
  number of games and the same number of game-steps, fixed before the run.
- **L0.3** starts from the STE Guard policy, which holds the zone in 829 of 1,000 games on tier 1.

**What gate G0 decides.**

| Question | Fed by |
|---|---|
| The tag and the zone: tag radius, zone radius, a margin between them | L0.11, L0.12 |
| What a tag costs: both drones, only the Strike drone, or a probability | L0.11, L0.12 |
| Team sizes to train, and the main size | L0.11, L0.12 |
| Where to train: everything on tier 2, or the league on tier 1 with tier 2 for fine-tuning and evaluation | L0.2, L0.13, L0.3 |
| Environments: open arena first, or the construction-site world sooner | — |
| What the real demo must show | L0.11, 1v1 results |
| A budget ceiling for each of phases L1 to L9 | all of the above |

## What the independent review found

An independent reviewer attacked the first version of the plan, and the lead checked the main claims in the code.
The findings are why L0 became a game-definition phase. Nothing below has been measured yet; each line names its
basis.

| # | Finding | Basis | What the plan does |
|---|---|---|---|
| F1 | Under the proposed tag, the number of drones may decide most games | analysis | L0.11 and L0.12 measure it |
| F2 | The zone radius equals the proposed tag radius (both 1.6 m), so a 1v1 at one height is decided by a tie rule | read in the configs | both radii are swept in L0.11 |
| F3 | The programme's team sizes are 2v1 and 5v3, not the 3v3 of NUS's game; the real demo can only be 1v1 | programme rules | L0 studies all four sizes |
| F4 | The programme asks for realistic 3-D environments; the first plan trained in the open arena only | programme rules | a question for G0 |
| F5 | Today's tag code lets one Guard drone tag every Strike drone in range, and scripted Strike drones never use height | read in the code | L0.9 and L0.10 fix both |
| F6 | Scripted games cannot show that a game is worth learning; only a trained opponent can | review | L0.12 |
| F7 | Tier 2 has never trained anything, and the first tier 2 budget was likely 3 to 10 times too small | reviewer's estimate | L0.2 and L0.13 measure it |
| F8 | The training arena (7.5 m) is not the lab fence (6.5 m) | read in the configs | L0.8 pins the arena; both sizes are swept |
| F9 | A real 1v1 cannot show team play or drone loss, and a scripted Guard drone may already win it | review | a question for G0 |
| F10 | The automation needed tooling that was in no task, and its wake-up mechanism had to be proven | review | L0.7 |

On F1: the proposed tag radius (1.6 m) is wider than the filter distance (1.10 m), so a Guard drone cannot block a
Strike drone without tagging it, and each tag removes one drone from each team. With more Strike drones than Guard
drones, the Strike team would win by trading drones one for one. With equal numbers, parked Guard drones may hold
everything: three of them on a 0.8 m ring cover the whole zone (largest gap 1.53 m, below the tag radius), although
losing one opens a 2.21 m gap.

## How the work runs

![The nine steps of every task: design check, develop, gate written, test run, debug, validate, QC, document, merge, each with who does it; a side panel lists the human gates H1 to H9; a band below states the 30-minute status and its limit](figures/task_lifecycle.png)

Every task moves through the same nine steps. The pass mark (the *gate*) is written and fixed before the run, and
the role that scores a result is never the role that built it. In validation, the control runs come first: a known
good player must pass and a known bad one must fail before any trained policy is scored.

The work runs unattended between *human gates*: points where it stops until the owner decides. Each gate is asked as
one question with options, costs and a recommendation. Work that is not blocked keeps running.

| Gate | The automation stops when |
|---|---|
| H1 Direction | a failed or inconclusive result changes the route |
| H2 Soundness | the idea does not hold as framed: a rule variant is trivial for one team, or tier 2 cannot train |
| H3 Rules | a fixed programme rule, an open ruling, or the gate limits of a run of record are at stake |
| H4 Outside `svg_training` | any AirStack work is needed |
| H5 Outward | a message to NUS or CMU, a push, or a reader page |
| H6 Budget | a cap would be exceeded |
| H7 NUS | NUS changes direction |
| H8 Stuck | two aborted runs on one task |
| H9 Safety | anything that matters for real flights |

The lead decides smaller technical matters alone and records them: settings of pilot runs, debugging fixes, task
order inside a phase.

**Status.** A status is posted every 30 minutes, and at once when a run finishes, a gate gives its verdict,
something fails or a human gate is reached. It carries no invented numbers.

**The limit.** Nothing is scored, launched or reported when no Claude session is alive. Training jobs already
started keep running. A new session reads the state files in [status/](status/), adopts the live jobs and restarts
any job a reboot killed. A resume drill in L0.7 proves this before the first overnight run.

## The team

| Agent | Role |
|---|---|
| lead | the main Claude session: plans, launches, commits and merges |
| `ste-architect` | architecture and interfaces; reviews designs before code |
| `ste-software-engineer` | builds and tests code, test first, inside `svg_training/` only |
| `ste-test-qc-engineer` | writes gates before runs, scores results, checks before merges |
| `ste-technical-writer` | the 30-minute status and every document update |
| `ste-orchestrator` | keeps the process moving unattended; stops at human gates |
| existing advisers | specialist reviews, read-only: [the list](../docs/claude/AGENTS_AND_SKILLS.md) |

## Files in this folder

| Read order | File | What it holds |
|---|---|---|
| 1 | this page | what the track is, the plan and the first tasks |
| 2 | [DISCUSSION_2026-11-19_20.md](DISCUSSION_2026-11-19_20.md) | why: every question, decision (D1 to D9) and open proposal (P1 to P12) |
| 3 | [PLAN.md](PLAN.md) | the working plan for Claude sessions: phases, tasks, gates, budgets |
| 4 | [STANDARDS.md](STANDARDS.md) | the track's rules, on top of [the parent rules](../STANDARDS.md) |
| 5 | [ARCHITECTURE.md](ARCHITECTURE.md) | components, interfaces, what exists and what is new |
| 6 | [CODING_PRACTICES.md](CODING_PRACTICES.md) | how code is written, tested, reviewed and merged |
| 7 | [WORK_BREAKDOWN.md](WORK_BREAKDOWN.md) | every task in detail |
| 8 | [VALIDATION_QC.md](VALIDATION_QC.md) | test levels, gates per stage, the robustness suite |
| 9 | [AUTOMATION.md](AUTOMATION.md) | what wakes the work, launch rules, resume, human gates |
| 10 | [DOCS_AND_STATUS.md](DOCS_AND_STATUS.md) | which pages change when; the 30-minute status |
| 11 | [status/](status/) | the status template; later the latest status and the state files |
| 12 | [agents/](agents/) | the definitions of the agents above |
| — | [figures/](figures/) | the four flowcharts, drawn by [make_ste_learning_figures.py](../scripts/make_ste_learning_figures.py) |

PLAN.md wins where it and a reference page (5 to 10) differ. `drafts/` holds first drafts, kept for the record and
not maintained.

## Rules that never bend

- Write only inside `svg_training/`. AirStack changes are specified here and made by an AirStack session after the
  owner approves.
- Gates are written before a run and never moved.
- A training result is not a flight result.
- Never push (the owner pushes); never `git add -A`; never `--no-verify`.
- NUS's source code is never committed.
- Stop and ask the owner at every human gate.

## What is asked of the owner now

Nothing until gate G0. The two questions asked on 20 November 2026:

| # | Question | Answer |
|---|---|---|
| 1 | Approve phase L0, with a cap of 19 GPU-h, alone on the GPU for its probes? | **approved** (owner, 20 November 2026) |
| 2 | When everything waits on the owner: the full status every 30 minutes, or one line every 2 hours? | not answered; the standing rule holds: the full status every 30 minutes |

Everything else is ruled at its own gate, with numbers: the tag and the zone, what a tag costs, team sizes, where to
train, environments, the demo, the budgets of L1 to L9, filter option B and the AirStack approach.
