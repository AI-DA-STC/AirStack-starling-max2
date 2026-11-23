INTERNAL · design note for phase L3 of the STE learning track: one learner with two action types, so pure RL and the mixed route (RL chooses among hand-written skills) can be compared fairly (owner ruling R19, 24 Nov 2026). DRAFT for the owner; no code is written until the owner approves it · [../README.md](../README.md); the ruling: [DISCUSSION §16](../DISCUSSION_2026-11-19_20.md#16-rulings-for-l1-to-l6-owner-24-nov-2026)

# L3: one learner, two routes (design note, DRAFT)

Written 24 Nov 2026 by the lead, before any L3 code. Observation v0.3 is not approved by the owner; this note does not
change the observation.

## What the owner asked

"I have not decided yet, i will need to try both eventually to see which is better" (R19). L3 to L6 are a **pipeline
check** (R23, cap 20 GPU-h): one short seed per route, scored the same way, exported and reloaded.

## The two routes

| | Pure RL (today's learner) | Mixed route |
|---|---|---|
| What the network outputs, per drone, per 0.6 s decision | a velocity command (vx, vy, vz, yaw rate) in [-1, 1] | a choice of one hand-written skill out of K |
| What flies | the network's command | the chosen skill's command for that drone (`opponents/scripted.py` `act(obs)`) |
| Policy head | Gaussian (today) | categorical over K skills |
| Learner | IPPO, shared actor per team (`ste/exploit_train.py`) | the same, with the categorical head |
| Observation | v0.2 (73 numbers), unchanged | the same v0.2 |
| What it can learn | any movement the drone can fly | only when to use which skill; never a movement no skill makes |

Everything else is shared: the game, the drone model, the filter, the scoring matrices, the run contract, the export
path. A route is one setting in the gate file (for example `[learner] action = "velocity" | "skills"`), so the two runs
differ in that line only.

## The skill set (to be approved by the owner at the start of L3, decision 7)

Proposed from the scripts that already exist and already score well in some cell (T44, T56, T66, T67):

- Guard skills: mark the edge, mirror, field, parked on a ring, parked at the centre (5).
- Strike skills: straight in, flank, high*, low*, sacrifice, converge (6); \*not fitted vertically in tier 1.

The team scripts (field, sacrifice, converge) coordinate the team; chosen per drone, a mix of team scripts can break that
coordination. Two options, both cheap to build: (a) **per drone** (each drone picks its own skill; the default), (b)
**per team** (one choice for the whole team each decision). Proposal: build (a), keep (b) as a setting.

How often a choice is made: every decision (0.6 s) or held for H decisions. Proposal: every decision, with the previous
choice in the observation slot that today holds the previous action (no layout change: K choices encoded in the same
four numbers is not possible, so the slot carries the chosen skill's own command; to be checked in the design review).

## How the two are compared (fair by construction)

- Same game (the 3v3 tag game ruled at G0), same opponents, same seed count (one per side per route in the pipeline
  check), same game-steps budget per run, same score matrix against every script of the other team.
- Pass marks set before the runs (L4), the same for both: the reading words of L1.10 (above / below / not
  distinguishable from the best script, per cell).
- The headline is the **worst cell**, not the trained opponent's cell: the L0 and L1 runs (T46, T56, T67) show that a
  pure-RL team beats the scripts against the opponent it trained on and loses clearly elsewhere (the L1.10 Strike team:
  681 against its training opponent, 39 against field Guards). The mixed route's expected strength is exactly that
  worst cell; its expected weakness is the best cell.

## Costs (estimates, labelled as such)

- Build: the categorical head and the skill dispatch are small (all K skills are run each step on the batch and the
  chosen one is gathered; K forwards of cheap scripts, vectorised). Estimate 1–2 days of build and tests.
- GPU: the mixed route likely needs fewer game-steps to learn (a smaller choice), so the pipeline-check seed may be
  shorter; both routes get the same budget anyway so the comparison stays fair. Inside the 20 GPU-h of R23.

## Open, for the owner

1. Approve the two-route design (decision 7, start of L3).
2. Approve the skill list, and per drone v per team.
3. Observation v0.3 (landing flags, needed once L2.3's landing is switched on in training) is a separate approval.
