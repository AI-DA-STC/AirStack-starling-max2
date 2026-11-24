INTERNAL · design note for phase L3 of the STE learning track: one learner with two action types, so pure RL and the mixed route (RL chooses among hand-written skills) can be compared fairly (owner ruling R19, 24 Nov 2026). APPROVED by the owner 24 Nov 2026 (R26: design, skill list, per drone by default); design reviewed 24 Nov 2026 (two reviewers), revised as v2 in the last section, which supersedes the earlier sections where they differ; one point back to the owner · [../README.md](../README.md); the ruling: [DISCUSSION §16](../DISCUSSION_2026-11-19_20.md#16-rulings-for-l1-to-l6-owner-24-nov-2026)

# L3: one learner, two routes (design note, approved 24 Nov 2026)

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
| Learner | IPPO, today one network per drone slot (`ste/exploit_train.py`; corrected in v2) | the same, with the categorical head |
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

## Owner's ruling and what stays open

1. Two-route design: **approved** (owner, 24 Nov 2026, R26: "yes approve").
2. Skill list as above, per drone by default with per team as a setting: **approved** (R26).
3. Before any L3 code: a design review of this note (two reviewers, R22), covering the previous-choice slot in the
   observation and the masking of absent drones (L2.4: an absent slot still gets the team reward).
4. Observation v0.3 (landing flags, needed once L2.3's landing is switched on in training) is a separate approval.

## v2 after the design review (24 Nov 2026)

Two independent reviewers read this note against the code (A: learning soundness and fair comparison; B: build,
export and the pipeline check). Both found the same two errors in the note, and each found gaps the other did not. What
changes, decided by the lead (technical calls, owner rule) unless marked **owner**:

**Corrections.** (1) There is no previous-action slot: observation v0.1/v0.2 is own position, velocity, yaw, game fields
and slots (`core/observations.py:27-53`). v2 adds **no** previous-choice input to either route (parity: pure RL does not
see its last action either; the scripts are stateless, `opponents/scripted.py:58-60`). (2) Today's learner is **one
network per drone slot**, not a shared actor (`exploit_train.py:137`, `opponents/learned.py:80-84`). The pipeline check
keeps today's MLP and observation v0.2 for both routes; the attention encoder, the shared actor and observation v0.3 of
PLAN §3 come after it, with v0.3's own owner approval. (3) "One setting" is the switch the owner sees, but in code it
selects a different action path: a categorical policy class, its save/load, the adapter's action space and the
evaluation player all change (B, `exploit_train.py:139-148,254-290`, `learned.py:31,49-66,119`,
`envs/skrl_adapter.py:109,150`, `exploit.py:508-558`).

**Hold rule (A1, B1).** A choice is made every 0.6 s (12 ticks), as pure RL's action is. The chosen skill **runs closed
loop every tick** for those 12 ticks (the scripts decide every 0.05 s; that is how a skill would fly). This gives the
mixed route a reaction-speed advantage that is part of what the route is; it is declared, not hidden. The closed-loop
controls below do not separate it, so one scoring-only arm does: each script with its command frozen for 12 ticks,
against the same script closed loop, on the same starts (no training). Training (`DecisionEnv.step`, `exploit_train.py:80-81`) and scoring (`HeldPlayer`,
`exploit.py:508-526`) use the same rule, tested. Tag games typically end in 36–78 ticks (`exploit_train.py:10`), with a long tail (about 220 ticks at the 90th
percentile, L2.5 spec), so a drone makes about 3–18 choices per game: stated so the reader knows how few decisions the
mixed learner gets.

**Opponents (A3).** Both routes train against the **same pool**: every scripted player of the other team, one drawn per
game, the same draw for both routes. Training against one fixed script (L0.12, L1.10) would teach the mixed learner
"always pick the skill that beats it", which is narrow again. The headline stays the worst cell of the full score
matrix.

**Controls in the score matrix (A).** For the mixed route: a uniform-random choice, the best single skill (fixed
choice), and an oracle best skill per cell; for both routes: the step-0 score (untrained). The categorical head starts
uniform over skills (already a decent team); the Gaussian head starts at zero mean, standing still
(`exploit_train.py:141-148`): the step-0 rows make this visible. Entropy settings are given per head (a 4-d Gaussian and
log K are not the same scale). Scoring plays the mean action (Gaussian) and the argmax choice (categorical).

**Masking of absent drones (A4, B6; needed before any drawn-size training).** In a custom PPO step (stock skrl IPPO has
no hook): policy loss, entropy and value loss, GAE and advantage normalisation, the observation scaler
(`exploit_train.py:155`) and the value scaler, all masked by `alive` at the decision. For the categorical head the loss
is masked, not the logits (a -inf logit with zero weight gives a NaN entropy).

**Skill list: unchanged from R26.** Strike K = 6 (straight, flank, high, low, sacrifice, converge), Guard K = 5. One
reviewer proposed dropping high and low as equal to straight; that holds only in a 2-D game (`scripted.py:363`, `if not
self.three_d`). With the Starling layer on, as in every STE game, they fly to the top or bottom of the height band, and
T66 shows them scoring differently (parked at centre holds 68.3 % against straight, 0.0 % against high and low). They
stay, labelled "vertical response not fitted in tier 1".

**Per drone or per team (A Q3, B6): back to the owner.** R26 approved "per drone by default". The reviewers checked the
scripts: several coordinate the team and break when drones mix skills. sacrifice makes Strike 0 the decoy and assumes
the others circle (`scripted.py:394-416`); converge waits until every live mate is in place (`:452-459`); parked on a
ring and field share stations or repel mates on the assumption that all run the same rule (`:325-347`); mark the edge
and mirror pair drones by rank among the live drones (`:97`). Per drone, a mix of these is untested behaviour, not a
tactic. **Lead's recommendation:** per team by default for the pipeline check (one choice for the whole team each
decision, every skill as written); per drone kept as a setting, offered over the skills that do not coordinate (to be
measured before it is used). Until the owner answers, the build makes both modes and the pipeline-check run waits.

**Export (B3).** The mixed artefact is not `ste-policy-1` (`ARCHITECTURE.md:118`, obs[B,81] → action_mean[B,4]). It
needs ONNX logits [B,K], the ordered skill list, a `policy_schema` bump, the sha256 of `scripted.py` and its constants,
team size and drone index, the hold rule, and golden rows (logits, skill, final command). The pipeline check's reload
check runs in a fresh Python process with the scripts loaded; **flying it needs a 20 Hz port of the skills into the game
node, an L7 AirStack change that the owner gates** (`ARCHITECTURE.md:178`).

**Tier 2 (B4).** Feasible: the scripts read only the observation tensor and tier 2 reuses `Learner` and `DecisionEnv`
(`scripts/ste_tier2_l013.py:329-331`); a dispatch-equality test on tier-2 observations comes first.

**First slice (B8), tier 1 only, tests first:** `SkillDispatch` (run all K, gather) and a categorical policy on today's
MLP and value net; tests: a fixed choice j for all drones reproduces script j's T44 cell game for game; training and
scoring use the same hold rule; two updates, then save, reload and golden rows match. Then the tier-2 equality test.
Estimate 1–2 days for this slice only (the attention encoder and v0.3 are not in it).

**What v2 changes from what the owner approved (R26), for the owner to see in one place:** (a) per team as the
default instead of per drone (the one point asked); (b) both routes train against a pool of every scripted opponent,
not one; (c) the pipeline check uses today's per-slot MLP and observation v0.2, with the attention encoder, shared actor
and v0.3 after it; (d) the skills run closed loop under a 0.6 s choice, an advantage declared and measured by the
held-command arm. The skill list is unchanged.

**Found by the first slice's build (24 Nov 2026, branch `l3-slice1`), against v2:** (1) the learner path runs
observation **v0.1** (`OBS_DIM = 71`, interface "0.1"); v0.2 is opt-in and used by the NUS hangar games only, so the
pipeline check runs on v0.1 for both routes. (2) Per team with per-slot networks: the lowest-index live drone at the
decision tick chooses for the team, held for the decision; the other slots' samples are ignored by the game (valid PPO,
noisier signal for those slots). (3) The step-0 row in scoring (argmax) is the first skill's cell (strike_straight /
guard_parked_centre), not a uniform mix; the uniform-random control is a separate row. (4) No entropy setting of its own
for the skills head yet (the recipe's single `entropy_loss_scale` is 0.0): to set in the L3 gate file. (5) Game lengths:
converge cells run longer (T44 medians 102–162 ticks). (6) The drivers build `DecisionEnv` directly, so until they are
wired they must refuse `action = "skills"` (added before merge).
