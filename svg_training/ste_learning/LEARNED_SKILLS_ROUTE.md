READ · The learned-skills route, the third route of the STE learning track: what it is, why it was added, its steps and their order, and how a trained team is used. The execution plan behind it: [execution workflow, third version](drafts/LS_EXECUTION_WORKFLOW.md); the track as a whole: [README.md](README.md); the slides: [figures/learned_skills_route.pptx](figures/learned_skills_route.pptx).

# The learned-skills route

The STE learning track trains two drone teams for the area-denial game: the Guard team holds a circular zone and the
Strike team tries to reach it. The *learned-skills route* is a way of training them in which the drones learn their own
individual skills and their own team strategy, starting from the hand-written ones. It was adopted as the track's third
route on 25 November 2026 ([DISCUSSION, R35](DISCUSSION_2026-11-19_20.md)). Its aim is a policy that is useful on
the drones, not a pipeline check, and the plan sets no GPU-hour cap on it: each job states its hours before launch.
The build was approved on 25 November 2026 and is in work. Nothing of it has been built, trained or flown yet.

Terms used on this page:

- *Policy*: the trained program that turns what a drone sees into a speed command.
- *Script*: a hand-written behaviour for one drone or a whole team, for example "sit on the zone edge between the
  centre and the Strike drone marked" (`opponents/scripted.py`).
- *Team strategy*: a script that coordinates the whole team (parked on a ring, field, sacrifice, converge).
- *Drone skill*: a script that does not read the drone's team-mates (mark the edge, mirror, flank).
- *Head*: the part of a policy that makes one choice. The *team head* chooses a team strategy or "free"; under "free",
  each drone's *drone head* chooses its own skill.
- *Skill code*: a number that names one skill; the skill network reads it as an input.
- *Gate*: a pass mark written before a run and never moved after it.
- *Distil*: fit a network to imitate another behaviour.
- *Self-play*: training a team against saved and present teams, not only against scripts (called LS4 on earlier
  versions of this page).
- *GPU-hour*: one hour of one graphics card. A figure marked "asks" is what a job states before launch, not a result.

## Architecture at a glance

![The whole route on one picture, in three bands. Every game: what each drone sees goes to the heads (every 0.6 s: a team strategy for all drones, or "free" and each drone picks), which pass a skill code to the skill network; the skill network also reads what the drone sees and which drone it is, every tick, and outputs a velocity; the safety filter, which also takes the opponent team, and the game step follow, and the next observation closes the loop. Training only: the game outcome becomes the reward of the learning step, which copies the teacher scripts in LS1 and is reinforcement learning in the head training and from LS2, and updates the heads and, from LS2, the skills. After training: when each team's gates pass, a Guard team export and a Strike team export, each heads plus skill network](figures/ls_architecture.png)

Read from top left to bottom right. The top band runs in every game, during training and after it; the middle band
exists only in training; the bottom band is what comes out. Teal parts are learned, grey parts are hand-written and
unchanged; the dashed arrow is teaching, used in training only. The learning step is a supervised copy of the
scripts in LS1, then reinforcement learning (PPO) on the heads and, from LS2, on the skills.

## Three routes, one game

![Three lanes, one per route, each from what a drone sees to a velocity command and then into one shared box, the safety filter and the game. Pure RL: a learned policy network outputs the velocity. Skills route: learned team and drone heads choose which hand-written script flies. Learned-skills route: the same learned heads choose a skill code and a learned skill network flies it. Learned boxes are teal, hand-written boxes grey](figures/ls_three_routes.png)

| Route | What is learned | What is hand-written | Built |
|---|---|---|---|
| Pure RL (velocity route) | the whole policy: it outputs a velocity | nothing in the policy | yes (L3) |
| Skills route | when to use which script, and which drone uses which | every movement | yes (L3) |
| Learned-skills route | the choices, then the skills, then new skills and team patterns | the scripts, only as teachers | no |

All three share the game, the safety filter that keeps every pair of drones apart, the scoring and the export. They
differ only in what turns a drone's view into a command.

## Why a third route

The skills route can never fly a movement that no script contains. Its ceiling is the best mix of scripts: in the
L3–L6 pipeline check, the best fixed choice of the Strike team's skills reached the zone in 604 of 1,000 games against
the parked Guard team, and the trained skills team reached it in 644 ([pipeline-check record](../records/2026-11-25_ste_l3_l6_pipeline_record.md),
one seed, observed in the training simulator). The pure RL route can learn any movement but starts from random
flight and keeps no structure: its behaviour has no names to check, count or explain.

The learned-skills route keeps the structure of the skills route (named skills, team strategies, two heads) and makes
the skills themselves learnable. Every step starts from the exact behaviour of the step before, so no stage starts
from random flight.

## Five steps, in this order

![Five step boxes, LS1 Distil, Head training, LS2 Fine-tune, Self-play and LS3 Free codes, joined by gate diamonds; under each a card with what is learned, its gate or expectation and its GPU-hour ask or a note that its own design note brings the hours](figures/ls_four_stages.png)

The order is LS1, head training, LS2, self-play, LS3. Each step starts from the one before. The stage names LS1, LS2 and
LS3 are unchanged; self-play is the stage called LS4 League on earlier versions of this page.

| Step | What is learned | Starts from | Gate or expectation | GPU-hours |
|---|---|---|---|---|
| **LS1 Distil** | a copy of every script, as codes of one *skill network* per team | the scripts | the copy and the scripts play the same starts; the read counts the games that change, not only the difference in wins; the pass limits are set before the run from a calibration read | asks 0.9 |
| **Head training** (job group LS1.4) | the heads again, on the skill network, for both teams | LS1 | scores about as the skills route's are the expected outcome; no new strategy is expected | asks 4.0 (two seeds per arm, clips included) |
| **LS2 Fine-tune** | the skills and the heads, in turns, with a tie that keeps each code near its script, weakened step by step | head training | to be written in its design note; proposed: above the best fixed mix of scripts, each code still recognisable | its design note |
| **Self-play** | which code each drone gets, against saved and present teams | LS2 or, if the pilot shows room, head training | to be written in its design note; read against opponents never trained against, including new held-out scripts | its design note |
| **LS3 Free codes** (last, an extension) | skill codes with no script, rewarded for being distinct and useful | self-play | to be written in its design note; proposed: the new codes are chosen and raise the worst result | its design note |

A step that fails its gate stops the route there, and every step before it is still a usable result. After LS1 alone,
each team's skill network exports as an ONNX file, with no port of the scripts into the flight software; a complete
team, heads and skill network trained together, comes from the head training. LS1 and the head
training are planned job by job; LS2, self-play and LS3 come back with their own design notes and hours. The GPU-hour
figures are asks, not results.

*Distil* means fitting a network to copy another behaviour. The copy is fitted on the states the scripts reach and
then on the states the copy itself reaches, labelled by the scripts, so it stays right when its own small errors take
it off the scripts' path.

**LS1's gate.** The copy and the scripts play the same starts. The read counts the games that change between them, not
only the difference in wins, because two copies of one behaviour change few games and a difference in wins can hide
errors that cancel. The pass limits are not set yet: they are set before the run, from a calibration read of scripts
against deliberately changed scripts.

**What the head training can and cannot show.** The skill network imitates the scripts, so heads trained on it are
expected to score about as the skills route's. That outcome shows that the copy can carry training. A new strategy is
not expected before LS2.

**When self-play starts.** It has two parts. A pool entry that loads a saved team is built early, and a pilot runs
right after the head training. The full stage starts before LS2 only if the pilot's three measurements show room: how
varied the trained teams' choices are per opponent, how much a fresh opponent gains against a frozen trained team over
the best script, and the gap to the best fixed mix of scripts on the same starts. Otherwise it starts after LS2. The
marks of the three measurements are fixed in the pilot's design note.

## Inside one decision: two speeds

![Two bands. The upper band, every 0.6 s: what each drone sees, the team head, the drone heads. The lower band, every 0.05 s: the skill network, fed with one code per drone and taught by the hand-written scripts, then the safety filter and the game step, which loops back to what each drone sees](figures/ls_one_decision.png)

Every 0.6 s the heads give each drone a skill code, held for 12 ticks. Every tick (0.05 s) the skill network turns the
drone's view, its slot in the team and its code into a velocity. The skill code is the only link between the two
speeds. This matches the skills route, where a chosen script also runs every tick for its 0.6 s.

The drone's slot is an input because several scripts depend on which drone is running them (in *sacrifice*, Strike 0 is
always the decoy), and the 71 numbers a drone sees do not state its own index. One network shared by all drones of a
team needs to be told.

## How a new team strategy appears

![A loop: the team gives out skill codes, thousands of games are played against opponents that adapt, the outcome is scored, and the learning step makes the choices that came before wins more likely; beside it, three sources of new strategy](figures/ls_new_strategy.png)

Nobody writes the new strategy. The team gives out skill codes, thousands of games are played at once, and the learning
step (PPO, the reinforcement-learning method the track uses) makes the choices that came before wins more likely. In
self-play the opponents adapt as well: when one team finds a pattern that wins, the other team's training pushes against
it, and the first team has to find something else.

New strategy can come from three places:

1. **A new mix of existing skills**: two Guards mark, one holds the centre; no script does this.
2. **A new switching rule**: hold the ring while one Strike drone charges alone, and mark when two close in on one side.
   This is the likely answer to *sacrifice*, whose decoy draws the nearest Guard to open a gap.
3. **New skills, then new roles**: LS2 changes how a skill flies; LS3, last, adds skills no script has, and new
   combinations become possible.

It shows in the choice logs, in clusters of code patterns over many games and in clips, and is named after the fact. It
may also not appear: a team can settle on one fixed choice, or beat only the opponents it trained against. The gates
check both, against the best fixed mix of scripts and against opponents never trained against.

## After training: two separate team policies

![Four kinds of Strike opponent (a hand-written script, outside code, a trained Strike team, a hand-flown drone in flight) feed a match against the exported Guard team; the match gives a score per opponent, and an opponent that wins joins the training pool for the next run](figures/ls_after_training.png)

- Each team is exported on its own: the two heads and the skill network, as ONNX files with an `interface.toml` that
  lists the skills, the team size and the hold rule. The Guard team's export can be used without the Strike team's and
  the reverse.
- A policy reads only positions and velocities of the drones, the zone and the clock. It does not know what flies the
  other team, so any player that obeys the game's rules can face it: a script of `opponents/scripted.py`, outside code
  named as `package.module:ClassName` ([PLUG_IN_YOUR_CODE](../docs/PLUG_IN_YOUR_CODE.md)), a trained team, or in
  flight a hand-flown drone.
- In the training simulator such a match is 1,000 games in seconds. A match against opponents the team never trained
  against is the held-out attacker test of the robustness suite. An opponent that wins can be added to the training
  pool of the next run.
- Flight is phases L7 (AirStack simulator) and L8 (real drones), each gated by the owner. Nothing here has flown; real
  Starling games are one against one.

## What a useful policy still needs beyond this route

| A useful policy needs | What this route gives | What is missing |
|---|---|---|
| Robustness to attackers it did not train against | the self-play step | a new build: the opponent pool takes script names only, so a saved team cannot be a training opponent today; the pool entry for saved teams does not exist yet |
| A held-out test | nothing today: every Strike script is in the training pool | new scripts, two per side, written for it, outside the teachers' file and before self-play is designed |
| Holding the team plan when a drone is lost | partly: one skill network is shared by a team's drones and is fitted with a drone absent | a shared actor (one policy shared by a team's drones) and training at drawn team sizes |
| Training on the Isaac Lab drone (tier 2) | no: the route trains on the fast engine (tier 1) | a separate task: a tier-2 score of the trained team, then tier-2 training |

## What changes in the code

The pipeline stays: the game, the opponent pool, the scoring, the run contract, the GPU-hour ledger, the job launcher,
the clips and the export path. Every driver builds its skills through one function, `skills.two_level_dispatch`, so one
setting, `[learner] skill_source = "net"`, swaps the scripts for the skill network everywhere; its default,
`"scripts"`, keeps today's behaviour bit for bit. The hand-written scripts are frozen from the first distillation on:
each skill network records a fingerprint of them.

| Piece | What it is | Used by |
|---|---|---|
| Skill network | one network per team: the drone's view, its slot and a skill code in, a velocity out; saved with refusals for a wrong team, skill list or game file | LS1 and every later step |
| Distillation | data collection, the supervised fit and the relabelling rounds | LS1 |
| Cell module | the games of the equivalence read, for either team | LS1 |
| Calibration read | scripts against deliberately changed scripts, to set the pass limits | LS1 |
| Equivalence read | the copy against the scripts on the same starts | LS1 |
| Training driver's control | the control "the untrained team equals its first skill" compared on the skill network, not the script | head training |
| Export and its reload check | the skill network as an ONNX file, and a reload check that accepts it | LS1, head training |
| Reader | reads the head training: this route against the skills route, seed by seed | head training |
| Pool entry for saved teams | a saved team as a training opponent | self-play (later) |
| Skill-level learner | trains the skills by the game reward, with the tie to the scripts | LS2 (later) |

Self-play and LS2 are new builds; LS1 and the head training change existing pipeline files. Nothing in this table is
built yet.

## Where it stands

| Item | State |
|---|---|
| The route | adopted, 25 November 2026 |
| GPU-hour cap | none; each job states its hours before launch |
| Design review (two reviewers) | done, 25 November 2026 |
| The build | approved, 25 November 2026; in work |
| LS1 pass limits and the head-training margin | not set; set before any run, after the calibration read |
| Code and runs | none yet |
| Execution workflow: what is added to the pipeline and which jobs run | third version, reviewed: [execution workflow](drafts/LS_EXECUTION_WORKFLOW.md) |

Files: the workflow, [execution workflow](drafts/LS_EXECUTION_WORKFLOW.md); the task-level plan of LS1,
[LS1 plan](drafts/LEARNED_SKILLS_BRIDGE_PLAN.md) (older than the workflow; where they differ the workflow applies);
the slides, [learned-skills route slides](figures/learned_skills_route.pptx) (editable PowerPoint flowcharts with
speaker notes), drawn by [the deck script](../scripts/make_ste_learned_skills_deck.py), which also renders the
pictures on this page.
