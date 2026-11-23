INTERNAL · phase L0 of the STE learning track as planned (20 November 2026): its task list, the questions it set out to
answer at gate G0, and the independent review that shaped it. Kept for the record; the phase is done and gate G0 was
ruled on 22 November 2026. Start at [README.md](README.md); what L0 found: [G0_REPORT.md](G0_REPORT.md).

# Phase L0, as planned

## Phase L0 step by step

![Phase L0 in four lanes: lane A, which game and is it worth learning, runs L0.1, L0.7, L0.8, L0.9, L0.10, L0.11, L0.12; lane B, can Isaac Lab train and at what cost, holds the three probes L0.2, L0.13 and L0.3; lane C, the Starling's look in videos, runs L0.4 then L0.5; lane D, real flight on Crazyflies, holds L0.14; all four end in L0.6, gate G0](figures/l0_tasks.png)

*Done; kept as the record of how gate G0 was reached.* L0 built no learner. It answered four questions, one per lane,
and brought the numbers to the owner at gate G0.
A GPU-hour (GPU-h) is one hour of the shared graphics card. INFO means measured, with no pass mark.

| ID and plain name | What it delivers | GPU-h cap |
|---|---|---|
| L0.1 Track set-up: config and test skeleton | the track's settings file, an empty code package, tests of the settings | 0 |
| L0.7 Process tooling and drills | one shared pause log, a status helper, a test of how trainers stop and resume, a wake-up drill and a resume drill | 0 |
| L0.8 Game spec sheet | one page, `GAME_SPEC.md`: every value of the game with its status and source | 0 |
| L0.9 Tag rule for the study: 1-for-1, nearest pair first | a new tag matcher behind a setting that is off by default | 0 |
| L0.10 Scripted players for the study | parked Guard teams; Strike teams that use height and numbers | 0 |
| L0.11 Screening sweep (INFO) | scripted teams against each other, 1,000 games per setting; a shortlist of rule variants | 0.5 |
| L0.12 Best-response test: is the game worth learning? | each shortlisted variant sorted: trivial for one team, or worth learning | 13 |
| L0.2 Tier 2 speed in contested play | game-steps per second on both tiers, with a learner and both teams playing | 0.4 |
| L0.13 Does tier 2 train at all? | the recipe behind the STE Guard policy, trained on tier 2 beside a tier 1 control | 1.6 |
| L0.3 STE Guard policy in tier 2 without retraining | how often the tier 1 policy still holds the zone on the Isaac Lab drone | 1.3 |
| L0.4 Side-by-side Starling render | the Isaac Lab Starling beside the AirStack simulator's | 0.2 |
| L0.5 Starling video look fix | clips that keep the Starling's own look, team colour as a small marker | 0.3 |
| L0.14 Crazyflie route check | one page on flying the game on the lab's Crazyflies: does the STE Guard policy cope with a Crazyflie's slower response, which team sizes fit which arena, and what a Crazyflie session would have to build | 0 |
| L0.6 Gate G0 | one decision page for the owner, with every number above | 0 |

The cap for the whole phase is 19 GPU-h (the task caps sum to 17.3 since 21 Nov 2026, L0.12c; 18.5 before); the work estimate is about 80 hours.

Notes on five tasks:

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
- **L0.14** was added on 20 November 2026 with the owner's yes. The lab has two Starlings, so a Starling flight is a
  1v1 game; it has many Crazyflies (small 30 g drones, flown from a separate repository of the lab), which could show
  the programme's team sizes and play that continues after a tag. The task only checks whether that route is sound:
  nothing is built in the Crazyflie repository and nothing flies. A Crazyflie result would say nothing about the
  Starling itself. Detail: [discussion record](DISCUSSION_2026-11-19_20.md), section 2.16.

**What gate G0 decided** (ruled 22 November 2026; the rulings: [DISCUSSION §14](DISCUSSION_2026-11-19_20.md#14-gate-g0-rulings-owner-22-nov-2026)).

| Question | Fed by |
|---|---|
| The tag and the zone: tag radius, zone radius, a margin between them | L0.11, L0.12 |
| What a tag costs: both drones, only the Strike drone, or a probability | L0.11, L0.12 |
| Team sizes to train, and the main size | L0.11, L0.12 |
| Where to train: everything on tier 2, or the league on tier 1 with tier 2 for fine-tuning and evaluation | L0.2, L0.13, L0.3 |
| Environments: open arena first, or the construction-site world sooner | — |
| What the real demo must show | L0.11, 1v1 results |
| Fleets for real flight: all Starlings (1v1), all Crazyflies, or a mix (P13) | L0.14 |
| A budget ceiling for each of phases L1 to L9 | all of the above |

## What the independent review found

*Kept for the record (20 November 2026, before L0).* An independent reviewer attacked the first version of the plan,
and the lead checked the main claims in the code. The findings are why L0 became a game-definition phase. Each line
names its basis as it stood then; L0 measured them, and gate G0 ruled on them.

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
