INTERNAL · design note for phase L3, slice 3 of the STE learning track: the absent-drone mask (both routes), the opponent pool for training and its pooled scoring row, and the skills route in tier 2; DRAFT for the lead and the slice's design review, no code yet · parent notes: [L3_TWO_ROUTES_DESIGN.md](L3_TWO_ROUTES_DESIGN.md) (v2), [L3_SLICE2_DESIGN.md](L3_SLICE2_DESIGN.md) (slice 2, run 0 for the skills route)

# L3 slice 3: absent-drone mask, opponent pool, tier 2 (design, 24 Nov 2026)

Written 24 Nov 2026 by the builder (`ste-software-engineer`, Opus 5.5), on branch `l3-slice3` cut from `development` at
`cef8d0ee`; line numbers are of that commit. All three items were placed before the pipeline-check run by the lead
(slice 2 design, "Lead's answers" 3 and 4; tier 2 accepted for slice 3). Nothing here changes the observation (v0.1),
the game, the drone model or a gate file of record; every new behaviour is a setting, default off, with off = bit for
bit.

## 1. The absent-drone mask (v2 "Masking of absent drones", both routes)

**What is absent.** A slot whose own-alive flag is 0 in its observation at the decision's first tick
(`ObsView.alive`, `core/observations.py:40`; a tagged or removed drone's observation is all zeros except team and alive,
`:68-69`). The flag is already in the memory: skrl stores the raw observations and applies the scaler in the update
(`skrl/multi_agents/torch/ippo/ippo.py:330-339`, `:429`), so the mask is read from the stored observations,
`alive_t = observations[t, :, ObsView.alive] > 0.5`, and needs no new memory tensor. A slot tagged during a decision
is live for that decision (it acted); it is absent from the next. Tags are permanent within a game, so a slot's absent
run always lasts to its game's end (the restart at the decision boundary, `exploit_train.py:132`, brings it back).

**Why it matters (and is not only drawn sizes).** At the fixed 3v3 of the pipeline check (R32), tags make slots absent
mid-game: an absent slot today trains on its all-zero observation with the team's reward (every drone of a team gets
the team's value, `core/rewards.py:17-22`), the same reward whatever it "does". Its samples are noise in the policy
gradient, and they move the observation scaler towards zero and the advantage statistics.

**The setting.** `[learner] mask_absent = true | false` (absent: false), legal for both routes
(`ste/skills.learner_spec` gains the key; `LearnerSpec.mask_absent`), so one line switches it for the pair of runs.
Off: today's learners exactly (the velocity route on stock skrl IPPO, `exploit_train.py:260`; `TwoLevelIPPO` as
merged).

**What is masked, when on** (per agent, per sample, weight a_t = alive at the decision):

| Item | Today | Masked |
|---|---|---|
| Policy loss | mean over all samples (`ippo.py:453-459`; two-level `ste/two_level.py:60-82`) | mean over the live samples of the minibatch: sum(a·term) / max(sum a, 1) |
| Entropy | mean over all samples (`ippo.py:448`; two-level per head) | the same live-sample mean (so the policy-to-entropy ratio is kept) |
| Value loss | MSE over all samples (`ippo.py:470`) | live-sample mean of the squared (clipped) error |
| GAE | `compute_gae` over every step (`ippo.py:23-64`) | live steps as today; an absent tail passes its team's rewards through (below) |
| Advantage statistics | mean and std over all samples (`ippo.py:62`) | over the live samples only; absent samples' advantages set to 0 |
| Observation scaler | updated on every row in epoch 0 (`ippo.py:429`) | updated on the live rows only (skrl's `RunningStandardScaler._parallel_variance(mean, var, count)`, `running_standard_scaler.py:50-68`, fed the live rows' mean, variance and count; then applied with `train=False`) |
| Value scaler | updated on all values and returns (`ippo.py:402-403`) | the same, live rows only |

**GAE through an absent tail (the one design choice in this item).** A live step t followed by the slot's death
should still be credited with what its team then won or lost (a sacrifice drone's tag can win the game), but the
values of the absent steps are the critic's output on all-zero observations, which is no longer trained. So, per
slot, backwards over the rollout: on an absent step the effective value is the discounted reward-to-go,
V_eff(t) = r_t + γ·not_done_t·V_eff(t+1), and its advantage is 0 (λ = 1 through the tail: no learned value is
read there). The last live step then has A = r + γ·V_eff(next) − V(s) + 0. A tail cut by the rollout's end (the game
still running, the slot absent) is bootstrapped with the **mean last value of the team's live slots** (each slot
receives the team's reward, so a live mate's critic estimates the same return); the mean is gathered across the team's
agents in a `post_interaction` override before the per-agent updates (`ippo.py:349-366` loops the updates over the
agents). With no live mate (possible only for the Guard team: a game ends only when no Strike drone is live,
`core/game.py:317`), the slot's own value at its last live step in the rollout; a slot absent for the whole rollout
has no live sample, so nothing reads its bootstrap. Alternative kept open (question 1): leave the critic unmasked
(it learns one constant value of "absent") and mask only the policy, entropy, advantage statistics and observation
scaler; simpler, but departs from v2's list.

**Composition with the two-level head masks (slice 2).** The effective head mask is the product
h'_t = h_t · a_t (team mask L·a, drone mask F·a), stored as today in `head_mask` and multiplied in the update, so
`two_level_policy_terms` (`ste/two_level.py:60`) takes h' and the live-sample count as its denominator. The leader is
live by construction (`skills.py:265`, `resolve_two_level`), except when no drone of the team is live: then the
leader is the last slot on all-zero observations (slice 2's case, Guard team only); with the mask on, L·a = 0 and
F·a = 0 for every slot, so that decision trains nothing (correct: nobody flies). Off, it trains as today (slice 2,
test 17).

**Where.** A `MaskedIPPO(IPPO)` (`ste/masked_ippo.py`) whose `update` and `post_interaction` are the masked copies,
built only when `mask_absent` is on (the velocity route); `TwoLevelIPPO` takes the same masked pieces as functions
(`masked_gae`, `masked_scaler_update`, the live-sample means), switched by the same flag. Both pinned to skrl 2.1.0 as
slice 2's copy is (`two_level.py` `IPPO_UPDATE_SHA256`). **Off = bit for bit**: the velocity route keeps stock IPPO
(no copy runs), `TwoLevelIPPO` keeps its merged branch, so the velocity goldens (training
`tests/test_ste_l3_velocity_golden.py`, scoring `tests/test_ste_l3_velocity_scoring_golden.py`) and slice 2's goldens
are untouched; tests assert it.

## 2. The opponent pool for training (v2 A3) and the pooled scoring row

**What.** Both routes train against a pool: every scripted player of the other team (the gate file's `[players]` list
of that team; optionally a named subset, `[pool] players`), one drawn per game, uniform. Training against one fixed
script teaches "pick the skill that beats it" (v2 A3), and "adapts to the opponent's strategy" (R30) is not evidenced
without it (slice 2 design §2).

**The same draws for both routes.** Which games end, and when, differ between the routes, so a draw "at each restart
from one generator" would give the two routes different opponents. Instead the draw is a function of the game's
identity: the k-th game of slot g plays opponent `pool_draw(seed, g, k) mod K`, an integer hash (splitmix64-style
mixing in int64 tensor ops) of (pool seed, slot, game counter). Both routes see the same opponent for the same
(slot, k), whatever the timing; the counter advances only at the decision-boundary restart (`exploit_train.py:132`),
never at the core's tick-level reset of a stale game (`envs/skrl_adapter.py:156`), whose ticks are not trained.

**Batched, no per-game loop.** `OpponentPool` (a strategy, `ste/pool.py`): K stateless scripts (`opponents/scripted.py`
reads only the observation, `:58-60`), a per-game index `draw [N]` and counter `k [N]` (long tensors). `act(obs)` runs
every script on the batch and gathers each game's (`torch.stack` then `torch.gather`, as `SkillDispatch.act`,
`skills.py:150-155`); `reset(games)` keeps the draw (tick-level); `redraw(games)` advances k and draws for the masked
games (called by `DecisionEnv.step` after its restart, `exploit_train.py:132-134`, beside the opponents' `reset`). The
cost is K script calls per tick instead of one (K = 5 Guard, 6 Strike scripts; the pilot measures it).

**Settings and the driver.** `[pool] enabled = true`, `seed = <int>` (its own, not another seed of the gate file),
optional `players`; run 0 never uses it (its opponent is the parked Guard by definition). `build_learner`
(`scripts/ste_exploit_l012.py`) gives `DecisionEnv` the pool; `trained_against` logs `OpponentPool(<names>)` and the
train log records the per-update share of each opponent. The evaluation batch keeps its named opponent cell (the
maximin pick, for continuity with L0.12), and the final INFO batch already plays every script of the other team on the
same 1,000 starts (`info_cells`).

**The pooled-opponent row (pipeline check).** No new games: on the scoring starts, game j is assigned opponent
`pool_draw(score_seed, j, 0) mod K` (recorded), and the pooled row takes game j's result from that opponent's cell of
the final and INFO batches; reaches or holds with a Wilson interval, beside the per-script cells and the worst cell
(the headline). A choice log per cell (team-head share of each strategy, drone-head share of each skill) shows whether
the choice changes with the opponent on the same starts, which is what "adapts" means here. `ste/scoring.pooled_row`;
the driver's `results_of` adds it for a run trained on the pool.

## 3. The skills route in tier 2

**The gap (slice 2 design §4).** `Tier2Gates` (`ste/tier2_train.py:86-97`) has no `[players]` and no `[learner]`
(`_SECTIONS` `:64-79`), and `load_gates` refuses any skills table (`:138`). The L0.13 driver builds `DecisionEnv`
directly (`scripts/ste_tier2_l013.py:371`), loads snapshots and the final team as velocity teams (`:381`, `:766`), and
its untrained control is "the untrained exploiter = the zero-mean team" (`:473`).

**Tables to add** (to the tier-2 gate file of the pipeline check; the L0.13 files of record stay as they are):
`[players]` (the same two lists as tier 1's gate file, checked equal to it), `[learner]` (the same table as tier 1's
skills gate file: route, lists, scales, `mask_absent`), and `[pool]` if the run trains on it. `Tier2Gates` gains
`players` and `learner` (optional: absent = the velocity route, the L0.13 files still load); `skills.check_two_level`
runs at load; the refusal at `:138` stays for slice 1's single-head modes.

**Driver changes.** `:371` through `exploit_train.decision_env`; `SNAPSHOT_KEYS` (`tier2_train.py:60`) keep the skill
meta with the snapshot, and `:381`, `:766` load through `skill_team_from_modules`; the untrained control at `:473`
becomes "the untrained team = the first drone skill's script on the same tier" for the skills route, as tier 1's
(`ctl_untrained_is_first_skill`).

**The dispatch-equality test on tier-2 observations** (CPU, the PyTorch reference world, `tier2_train.py:226`,
`--dry-cpu`): (a) on observations recorded from a tier-2 game, `TwoLevelDispatch.act` with each fixed choice equals
the chosen scripts' own commands bit for bit; (b) tier-2 fixed-choice replay: each team strategy and each uniform
drone skill, played as a two-level team on tier 2, equals that script played on tier 2 game for game (tier 2 against
tier 2; no T44 cell exists for tier 2), plus a sample of mixed "free" combinations against the composite player;
(c) training = scoring on tier 2 (slice 2's test 11 on the reference world). On Isaac Lab (the GPU tier 2) the same
(b) runs once as a smoke under `train-run`, at the lead's go; no tier-2 skills run of record before it passes.

## 4. Build order, tests (written first), estimate, and what stays for later

1. **Mask, the pieces** (`masked_gae`, `masked_scaler_update`, live-sample means): hand references on synthetic
   batches (an absent tail, a cut tail with and without a live mate, all-absent rollouts); mask off = stock
   `compute_gae` and stock scaler bit for bit. About 1 day.
2. **Mask in the learners** (`MaskedIPPO`, `TwoLevelIPPO`, the setting): an absent sample's stored action, old
   log-probability, value and observation change no weight and no scaler statistic (bit for bit); a live sample still
   does; the velocity goldens and slice 2's goldens unchanged with the setting off; the no-live-Guard decision trains
   nothing when on (slice 2's test 17 flipped under the setting); end-to-end update with absent slots and finite
   losses. About 1-1.5 days.
3. **Opponent pool**: `pool_draw` uniformity (chi-square on 10^5 draws) and route independence (the same (slot, k) →
   the same opponent under two different end patterns); `OpponentPool.act` equals each game's own script; the counter
   advances at the boundary restart only; a single-script pool equals today's fixed opponent bit for bit; the driver
   logs the mix. About 1 day.
4. **Pooled row**: derived from the cells by the recorded assignment, checked against a direct replay of the assigned
   opponents on a small CPU batch; the choice log. About 0.5 day.
5. **Tier 2**: the tables and their load checks (a two-level tier-2 gate file loads; lists unequal to tier 1's are
   refused); the dispatch-equality tests (a)-(c) on the reference world; the L0.13 driver end to end on `--dry-cpu`
   with a skills gate file; the L0.13 files of record load unchanged. About 1.5 days.

**Estimate: about 5-6 days** of build and CPU tests, then QC (one reviewer); no GPU, except the Isaac smoke of 3(b)
at the lead's go. Estimate, not measured.

**Not in slice 3:** the export (ONNX logits, the ordered lists, `policy_schema`, the scripts' sha256; v2 B3); the
attention encoder, shared actor and team critic (PLAN §3; they would also lift the "slots 1-2 rarely lead" limit);
observation v0.3 (landing is off in the pipeline check, R32); drawn team sizes and scheduled drop-outs (not ruled,
R32; the mask is ready for them); the score-matrix, clip and cross-tag drivers for the skills route and the verdict
(they still refuse); the pipeline-check runs themselves.

## Open questions for the lead

1. **The critic under the mask:** v2's list masks the value loss and the value scaler, which needs the reward-to-go
   pass-through and the mates' bootstrap above. The simpler alternative leaves the critic unmasked (it learns one
   value for "absent") and masks only the policy, entropy, advantage statistics and observation scaler. Proposed: the
   full v2 list as above.
2. **Pool membership:** every script of the other team (proposed), or a subset named in `[pool] players`? And should
   the run's named evaluation opponent stay the maximin pick (proposed, for continuity), or become the pooled row
   only?
3. **Pool draw:** uniform per game (proposed), or weighted (for example towards the opponents the learner currently
   loses to, which is a curriculum, not a pool)?
4. **Tier 2 scope in this slice:** the Guard-side L0.13 arms only (the tier-2 driver trains the Guard side, as built),
   or also a Strike-side tier-2 arm for the skills route?
