# S2 design: the game, varied arena sizes, and a plug-in point for NUS's strategy

> Status: DRAFT for the owner's approval, 15 November 2026. Nothing in it is built.
> It replaces the S2 row of [../DESIGN.md](../DESIGN.md) §8 ("One against one") once approved.

## 1. Why

The Strike vs Guard strategy that will fly comes from **NUS**, not from this lab. NUS's code is not here
yet, so nobody knows how their strategy is trained or what software it uses. Their published work on
this game is "skills + plays + a planner", which may not be standard reinforcement learning at all.

So S2 builds the **track, not the runner**: a game that runs thousands of copies at once on the GPU,
with the real drone's response and the real collision filter, on arenas of different sizes, and a
scoring tool that rates any strategy. When NUS's code arrives it should plug in with little work.

Second, smaller aim (owner, 15 November): a **side quest** in which NEAR Lab trains its own Guard and
Strike strategies, as research into the lab's own capability. It uses the same game and plug-ins.

This reverses the order of uses in [../DESIGN.md](../DESIGN.md) §5: use 2 (partner strategies) becomes
the main use; use 1 (our own team strategies) becomes the side quest.

## 2. Goals, non-goals, anti-goals

**Goals**

1. **Game rules in tier 1**: zone, contact tags, Strike scoring, game end, drop-outs, the Guard-survives
   switch, all as in [../../STANDARDS.md](../../STANDARDS.md) §4, as tensor operations over all games.
2. **Varied sizes**: every game draws its own arena size and zone size and place (section 4).
3. **A plug-in point** that does not assume a training method (section 5).
4. **A scoring tool** that plays any strategy against scripted opponents (or against another strategy)
   and reports results per size band and per team size.
5. **Scripted opponents** for both teams, so a strategy can be scored before any other strategy exists.
6. **A faster safety filter**: fast enough to train with, checked against the same four checks as T2.
7. **A stand-in trainer** that proves the whole path works end to end (game → plug-in → learning →
   saved strategy → scoring tool). It is a pipe test, labelled as such, never "the policy".

**Non-goals for S2**: NUS's training method itself; obstacles and worlds (E1 onwards, S3–S4); the
tier 2 version of the game; the ROS 2 policy node (S5); self-play leagues for the side quest.

**Anti-goals** (would make S2 a failure even if it runs):

- an interface tied to one training library, so NUS must rewrite their code to use it;
- stand-in or side-quest results quoted as flight results, or as NUS's results;
- per-game Python loops in the step (STANDARDS §6).

## 3. Approaches

| | What | Trade-off |
|---|---|---|
| **A (chosen by the owner, 15 November)** | game + random sizes + library-neutral plug-in + scoring tool + faster filter + stand-in trainer | ready for whatever NUS sends; the stand-in learns something basic only |
| B | A plus our own full team trainer | much work that NUS's code may replace; kept as the side quest after S2 |
| C | wait for NUS's code | nothing gets built meanwhile |

## 4. Varied sizes

Each game draws, at every reset:

| Item | Range (Claude's call, a config value) | Why |
|---|---|---|
| Arena, square, side length | 4 m to 16 m | 4 m = the lab's keep-in fence (`teleop_real_ours.yaml`: ±2 m); 16 m stands in for the hangar until its flying space is measured |
| Flying height band | 0.5 m to 1.8 m, fixed | the lab's goal box (`goal_two_ours.yaml`); height is not scored (STANDARDS §4) |
| Zone radius | 10 % to 25 % of the side length | keeps the zone sensible at every scale; NUS's balanced ratio replaces it when known |
| Zone centre | anywhere at least one zone radius plus 0.5 m from every wall | the zone never touches a wall |

The scoring tool reports three **size bands** separately: lab (4–6 m), middle (6–10 m), large
(10–16 m). Fixed named scenarios (for example a 4 m lab arena with the zone in the middle) exist only
for scoring, never for training (STANDARDS §6 rule 4).

## 4b. Game rules for S2 (Claude's calls; each is a config switch, because NUS's exact game is unknown)

| Item | Default | Switch |
|---|---|---|
| Strike win | the first Strike drone inside the zone ends the game | or: count time Strike drones spend inside the zone over the full 60 s |
| Guard win | no Strike drone reached the zone: all Strike drones tagged, or 60 s ran out | — |
| Headline number | **hold rate**: share of games the Guard team wins, with its interval | per size band, per team size, per `guard_survives_tag_prob` 0 / 1 |
| Starts | Strike drones on a ring near the walls; Guard drones on a ring around the zone | or: anywhere (STANDARDS §4 working rule) |
| Arena wall and height band | the drone stops at the wall, like the flight stack's keep-in fence (`fence_behavior: "keep_in"`) | or: the drone leaves the game |
| Drop-outs | STANDARDS §4 working rule (a random removal time in a set fraction of games), fraction 0 by default | fraction is a config value |
| Drone model | `real_exploratory_v0`, labelled exploratory everywhere, swapped for the fitted one after the next real flight | any named parameter set |
| Speeds | Strike 0.5 m/s, Guard 0.33 m/s (the real stick cap, as tier 1 uses now); in 60 s a Guard drone crosses 20 m, more than the largest arena | cap is a config value up to the commander's cap |

## 5. The plug-in point

Three layers, so NUS can use whichever fits their code:

1. **The batched game itself** (the core): plain PyTorch tensors, all games at once, per-drone
   observation and action as in STANDARDS §3 (action `[vx, vy, vz, yaw_rate]` in `[-1, 1]`, scaled by
   the team's speed cap; observation as proposed there, without range rays in the open arena).
   Anything that can call `reset()` and `step(actions)` on tensors can drive it.
2. **A strategy contract** for scoring: a strategy is called **once per team per step** with the
   observations of all that team's drones in all games, and returns all their actions. It may keep its
   own memory between steps and is told which games just reset. A learned network, a scripted rule or
   a central planner (as NUS's "plays" may be) all fit; a per-drone policy is the special case that
   treats each drone alone. The scoring tool only needs this.
3. **Adapters to common training libraries**: one multi-agent adapter (skrl, already installed, used
   by the stand-in) and one single-team Gymnasium vector adapter (the other team is played by a fixed
   strategy). More adapters are added when NUS's code shows what it needs.

What a drone may know about other drones stays OPEN (STANDARDS §3): S2 gives every drone the full state
of every drone, behind one switch so a limited view can be added later without changing the layout.

## 6. Faster safety filter

T4 measured the filter at 1,000 sweeps: about 10,000 game-steps per second at 4,096 games, too slow.
S2 tries cheaper settings (fewer sweeps, stopping early once nothing changes, others the builder
finds) and keeps the fastest one that is **no worse than T2 on all four of T2's checks**, measured on
T2's 2,000 recorded scenes. The speed target is written before the measurement in the S2 plan.
If no cheaper setting passes, S2 is not blocked: the run is recorded as a FAIL with the numbers, the
fastest setting and the 1,000-sweep setting are both offered, and the owner rules (as he did for T2).

## 7. When S2 is done

1. Unit tests for the game rules pass without Isaac, including hand-worked cases (a tag, a score, a
   drop-out, a game running out of time, each at the smallest and the largest arena).
2. The scoring tool gives the hand-worked answer on the fixed scenarios.
3. The chosen filter setting meets the speed target and is no worse than T2 on T2's checks.
4. The stand-in trainer, on this laptop, ends with a Guard strategy that scores better against the
   scripted Strike drones than random actions do, by a margin and over a number of seeds written in
   the plan before the run. This proves the pipe, nothing about strategy quality.
5. A one-page guide for a partner: how to plug a strategy or a training method in, with a worked
   example using the stand-in.

The old S2 end condition ("a trained Guard tags scripted Strike at a set rate, which decides the
control level") moves to the side quest.

## 8. Decided by the owner

- 15 November 2026: NUS's strategy is the main use; NEAR Lab's own strategies are a research side quest.
- 15 November 2026: arena sizes vary, as a test.
- 15 November 2026: approach A.
- Earlier rules unchanged: STANDARDS §3 and §4 FIXED rows (actions, rate, teams, speed ratio, filter
  within a team only, tag = contact, Strike leaves after a tag, `guard_survives_tag_prob`).

## 9. Left to the builder (the S2 plan)

Exact tensor layouts, file names, the scripted opponents' behaviours, the stand-in's algorithm and
settings, the filter speed target and the margin for check 4 (both written before any run), and the
order of tasks. The game length stays 60 s unless the plan argues otherwise.
