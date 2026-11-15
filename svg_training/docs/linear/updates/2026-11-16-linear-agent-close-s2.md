# Linear update — 2026-11-16, close S2 and open S2b (Isaac Lab)

Instructions for the Linear agent, in the **nearlab** workspace (team NEAR Lab), project **Isaac Lab Pipeline for
NUS Strategy Training**. Apply every step below. Delete nothing. Use titles and comments exactly as written. Change
no existing title. Check Linear before each step: if a status, comment, milestone or issue is already in place, do
not repeat it. Every issue in this project is assigned to me (HweHuang Chia), with **no cycle and no due date**.

Evidence is in the repo https://github.com/AI-DA-STC/AirStack-starling-max2, folder `svg_training/`
(`docs/S2_RESULTS.md`, `records/LEDGER.md`). Write "ledger row T8", never "#T8".

## Part 1 · Set to Done, each with its comment (milestone S2 · Game and plug-in point)

**NEAR-963 "Game core: thousands of games at once, varied arena and zone sizes"**

> 2026-11-16. Done. The game runs thousands of games at once with random arena (4–16 m) and zone sizes; NUS's rules
> are the main game, contact tags stay for the side quest; the Starling layer adds the fitted drone model and CMU's
> collision filter on every pair. Every part reviewed; a bug at the arena walls was found in review and fixed.
> Results: `svg_training/docs/S2_RESULTS.md`.

**NEAR-964 "Check the drone model against the 12 Nov rosbag"**

> 2026-11-16. Done with a FAIL, ledger row T5. Worst leg 0.120 m/s against a 0.10 m/s limit; the timing check
> failed mainly because of how the check fed the setpoint (joined as in the original fit, the three clean pushes
> fit within 0.05 m/s); the fourth leg is a 408 s gap in the recording. The model stays exploratory until a
> planned-pushes flight (NEAR-962).

**NEAR-965 "Faster collision filter, checked against CMU's"**

> 2026-11-16. Done, ledger row T8 PASS: same answers as the full filter on all 2,000 test scenes, about 121,000
> game-steps/s for 5 v 3 at 4,096 games (target 100,000), against 9,900 before; about 90,000 averaged over a whole
> game (information only). The speed-error limit was read at its 4 written decimals (owner's ruling). Ledger row T7
> is an aborted first attempt, stopped to put in the wall fix.

**NEAR-966 "Scoring tool and scripted opponents"**

> 2026-11-16. Done. Scoring tool and five scripted Guard and two scripted Strike tactics; reference runs ledger rows
> T6 and T9 (T9 on the fixed walls). Crowded 5 v 3 games still bring drones to 0.75–0.80 m near walls: a limit of
> CMU's filter, which does not know the walls, shared with the real commander.

**NEAR-967 "Plug-in point for a partner's strategy, with a written guide"**

> 2026-11-16. Done. skrl and Gymnasium adapters and the partner guide `svg_training/docs/PLUG_IN.md`, with runnable
> examples a test executes; checked by a newcomer read-through. The worked example with the stand-in trainer comes
> with NEAR-968.

**NEAR-969 "S2 results page"**

> 2026-11-16. Done: `svg_training/docs/S2_RESULTS.md`, after a final review of the whole stage and one fix wave.

Set milestone **S2 · Game and plug-in point** target date to **2026-11-16**.

## Part 2 · Create a milestone and move issues into it

Create milestone **S2b · Game on Isaac Lab drones**, placed after S2, description:

> The S2 game on rigid-body Starling drones in Isaac Lab, with a PX4-like velocity controller using the real drone's
> gains, compared with the fast PyTorch simulator; the stand-in trainer on both simulators, logged to TensorBoard;
> an Isaac Lab video of the game.

Move into it, keeping title, status and comments:
- **NEAR-968** "Stand-in trainer: prove the training pipe end to end" (status stays Backlog), with this comment:
  > 2026-11-16. Moved to S2b by the owner: it runs on both simulators (PyTorch as a control, then Isaac Lab), with
  > TensorBoard logging, so training is proven on the simulator that matters.
- **NEAR-973** "Cross-check the fast simulator against full drone physics in Isaac Lab" (status stays Backlog), with
  this comment:
  > 2026-11-16. Moved from S4 to S2b: the owner pulled the Isaac Lab work forward.

## Part 3 · Create two issues in S2b

**"Wrap the S2 game as an Isaac Lab environment with a PX4-like controller"** — status **In Progress**.

> The same S2 game (rules, observations, scoring, plug-in point) on rigid-body Starling drones in Isaac Lab 2.3.2,
> headless, with a PX4-like velocity controller using the real drone's gains, also registered as a standard Isaac Lab
> task. Done when (target): the Isaac drones agree with the fast simulator on step tests and scripted games within the
> limits written before the runs.

**"Isaac Lab video of the game"** — status Backlog.

> A few scripted games rendered headless to MP4 on Isaac Lab Starlings (2 v 1 and 5 v 3), captioned "training
> simulator, scripted strategies, not a real flight". Done when (target): the clips are in `svg_training/docs/media/`.

## Part 4 · Write the sync record

Write a Markdown file named `2026-11-16-linear-sync-record-4.md`. State only what Linear now holds:

- every issue of the project: NEAR id, title, milestone, status, assignee, cycle, due date;
- each comment added here, and whether it was added now or already present;
- the milestones with target dates and progress;
- anything not applied, and why.
