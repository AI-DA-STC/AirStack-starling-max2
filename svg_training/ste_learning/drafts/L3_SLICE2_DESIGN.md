INTERNAL · design addendum for phase L3, slice 2 of the STE learning track: the two-level choice of owner ruling R30 (a team head over team strategies and "free", a drone head per drone over the skills that do not coordinate), built on slice 1; reviewed by two reviewers 24 Nov 2026 (no blocking finding) and revised for the lead's answers · parent note: [L3_TWO_ROUTES_DESIGN.md](L3_TWO_ROUTES_DESIGN.md) (v2 and "Owner's ruling R30"); the ruling: [DISCUSSION §16](../DISCUSSION_2026-11-19_20.md#16-rulings-for-l1-to-l6-owner-24-nov-2026) R30

# L3 slice 2: team strategy with individual drone skills (design addendum, 24 Nov 2026)

Written 24 Nov 2026 by the builder (`ste-software-engineer`, Opus 5.5; the advisor tool consulted before writing and before hand-back), on
branch `l3-slice2` cut from `development` at `c9575314`. Line numbers are of that commit. Nothing here changes the
observation (v0.1, 71 numbers, slice 1 finding 1), the game, the drone model or the velocity route.

Owner's ruling R30 (24 Nov 2026), verbatim: "Team strategy, with individual drone skills which can adapt to the
opponent's strategy." Slice 2 builds the lead's reading of it: one learner, two choice heads per side.

## 1. The two-level choice

Every decision (0.6 s), per side:

- **Team head**: index 0 = **"free"**, then the team strategies in `[players]` order. A team strategy runs **as written
  for every drone of the team** (slice 1's per-team gather, proven equal to the script alone by
  `tests/test_ste_l3_skills.py:171`).
- **Drone head** (one per drone): the skills that do not coordinate. Read only when the team head says "free"; each drone
  then flies its own chosen skill.

**"Non-coordinating", as a testable rule:** a skill whose command for drone i reads nothing of drone i's own team-mates
(the own-team slots of its observation). Under that rule a mix of such skills is each drone doing exactly what its own
script does; only who covers whom changes, which is the tactic the drone heads are meant to learn. From the code:

| Skill | Reads own-team slots? | Where | List |
|---|---|---|---|
| strike_straight | no (own position only) | `scripted.py:172` | drone |
| strike_flank | no (Guard slots only) | `:189` | drone |
| strike_high, strike_low | no (own position, own height) | `:362-369` | drone |
| strike_sacrifice | **yes** (Strike 0 is the decoy by index; the others circle to the gap it opens) | `:393-417` | team |
| strike_converge | **yes** (every live mate's bearing; run-in waits for all) | `:439-459` | team |
| guard_parked_centre | no (own position; team size only) | `:297-299` | drone |
| guard_mark_edge | no (see below) | `:89-112` | drone |
| guard_mirror | no (same assignment as mark_edge) | `:153-161` | drone |
| guard_parked_ring | **yes** (stations from every live mate's bearing) | `:325-347` | team |
| guard_field | **yes** (pushed off mates within 1.1 m) | `:139-142` | team |

**mark_edge and mirror: non-coordinating (list A; proposed, then ruled by the lead).** The brief's worry is the pairing at `:97`. Read exactly,
Guard i marks live Strike number (i mod S_live) counted in slot order (`_marked`, `:89-102`). Slots are ordered by drone
index and are the same for every observer (`core/observations.py:29-30`). The rank is over the **live Strike drones**;
the Guard's own index is fixed, never re-ranked among live Guards. So a Guard's target depends on its own index and the
Strike drones only, never on what its mates fly. Mixed with other drone skills, a marking Guard marks the same Strike it
would in its own script. mark_edge and mirror also share the one assignment (both call `_marked`), so any mix of the
two keeps the pure scripts' one-to-one cover. Mixed with parked_centre, a Strike goes unmarked: a tactic, not broken
behaviour. The alternative (**list B**: mark_edge and mirror as team strategies) leaves the Guard's drone head
one skill (parked_centre, which with two or more Guards is "hold the start position", `:298`). A one-skill head
chooses nothing, so under B "free" is a fifth team strategy and R30's individual skills disappear for the Guard team.
Both lists are only gate-file lines; **list A, ruled by the lead 24 Nov 2026**.

| Side | Team head (index: 0 = free) | Drone head | Widths |
|---|---|---|---|
| Strike team | free, sacrifice, converge | straight, flank, high, low | T+1 = 3, K_d = 4 |
| Guard team, list A (lead's ruling) | free, parked_ring, field | parked_centre, mark_edge, mirror | 3, 3 |
| Guard team, list B (offered) | free, parked_ring, mark_edge, mirror, field | parked_centre | 5, 1 |

**Gate file.** `[learner] choice = "two_level"` (new value beside slice 1's "team" and "drone"), with optional-key
tables that `learner_spec` (`skills.py:60-80`, which today refuses unknown keys at `:67`) accepts only for that choice:

```toml
[learner]
action = "skills"
choice = "two_level"

[learner.team_strategies]
strike = ["strike_sacrifice", "strike_converge"]
guard = ["guard_parked_ring", "guard_field"]

[learner.drone_skills]
strike = ["strike_straight", "strike_flank", "strike_high", "strike_low"]
guard = ["guard_parked_centre", "guard_mark_edge", "guard_mirror"]

[learner.entropy_scale]          # start value 0.01 per head (lead), fixed in the pilot's gate file before its run
team = 0.01
drone = 0.01
```

(Checked with `tomllib.loads`, 24 Nov 2026.)

Checks at load (ValueError, exit 2): every name a player of that team's `[players]` list; the two lists disjoint, their
union the whole `[players]` list (no player silently dropped); the drone list non-empty; the order inside each list =
its `[players]` order (so one order rule exists); the lists or scales with `choice` "team" or "drone" refused.

**Dispatch.** Slice 1's `SkillDispatch` (`skills.py:104-149`) is reused unchanged with K = the whole `[players]` list
(Strike 6, Guard 5 scripts run every tick, as in slice 1). A new `resolve_two_level(team_a [N, M], drone_a [N, M],
obs [N, M, D]) -> (flown [N, M] long, head_mask [N, M, 2])` maps the leader's team index (t ≥ 1 → its player index;
0 → each drone's drone-skill player index) and returns the masks of §2. The leader rule is slice 1's (`skills.py:146-149`):
the lowest-index **live** drone at the decision's first tick.

## 2. Networks, masks, log-probability, entropy, action space

**Network.** Today's per-slot MLP (`opponents/learned.py:36-46`, one network per slot, `make_skill_models` `:201-205`)
with one output layer of width T+1+K_d (Strike 7, Guard 6 under list A), split into the team logits and the drone
logits: one trunk, two heads. **Every slot carries a team head** (any slot can lead after a tag); only the leader's
flies. Value networks unchanged.

**Start (design choice, lead 24 Nov 2026).** `zero_mean_init` zeroes that layer as in slice 1
(`exploit_train.py:202-204`); then the bias of the team head's "free" logit is set to ln T (T = number of team
strategies, 2 on each side: ln 2 ≈ 0.693), so at the start p(free) = e^b / (e^b + T) = 0.5, each team strategy 0.25,
the drone head uniform. Why: a uniform team head (p(free) = 1/3) would switch the whole team into a random team
strategy two decisions in three in the first updates, so early play would be mostly random switching between
coordinated scripts and the drone heads would see "free" in only a third of the decisions. Half the decisions under
"free" from the start gives both heads a signal. The argmax at the start is unchanged: "free" (strictly the largest
logit) + the first drone skill.

**Head masks (per slot i, per decision; computed by `DecisionEnv.step` on the decision's first observation, returned in
`info["head_mask"]` [N, M, 2]):** team mask L_i = 1 if slot i is the leader, else 0; drone mask F = 1 if the leader's
team choice is "free", else 0. When the team head picks a strategy, every drone head's sample is ignored by the game and
**masked out of the loss**. A non-leader's team-head sample is masked out too (in slice 1's per-team mode it is not).
Masking is unbiased: the masked sample is drawn independently and does not change the game, so its score-function term
has expectation zero; dropping it only removes noise. Until slice 3's absent-drone mask, a slot that is absent at the
decision's start still has F = 1 under "free" and trains on its zeroed observation and the team reward, as the velocity
route's absent slots do today (parity kept).

**Per-head PPO ratios (lead's revision A).** Each head has its own ratio, clipped on its own and weighted by its own
mask, not one joint ratio of the summed log-probabilities (a joint ratio would let one head's step use up the other's
clip range):

- r_team,i = exp(log p_team,i(t_i) − old_team,i), r_drone,i = exp(log p_drone,i(d_i) − old_drone,i);
- policy loss = − mean[ L_i · min(A r_team, A clip(r_team, 1 ± ε)) ] − mean[ F · min(A r_drone, A clip(r_drone, 1 ± ε)) ],
  ε = `ratio_clip`, means over all samples of the minibatch (masked samples add zero and no gradient);
- approx KL per head, kl_h = mean over the samples with that head's mask on of ((r − 1) − log r), logged as
  `Policy / KL team (<agent>)` and `Policy / KL drone (<agent>)`. The KL early stop (`kl_threshold`) and `KLAdaptiveLR`
  use kl_team + kl_drone: the heads are independent, so the sum is the KL of the joint policy over the heads in play.
  The pinned recipe sets neither (both off), but both paths are tested under masking.

The old per-head log-probabilities are stored (memory tensor `head_log_prob`, size 2, float32) beside `head_mask`
(size 2, float32 0/1). skrl's own `log_prob` tensor still gets L·old_team + F·old_drone, so its stock uses stay
meaningful.

**Entropy (slot i):** s_team · L_i · H(p_team,i) + s_drone · F · H(p_drone,i), from `[learner.entropy_scale]` (Strike
max entropies ln 3 and ln 4: not the same scale, hence two numbers). Start value **0.01 per head** (lead 24 Nov 2026),
fixed in the pilot's gate file before its run. Plain minibatch mean over all samples, as the policy loss, so a head
that is active in few samples keeps the same ratio of entropy to policy gradient. **Both scales required and > 0**
(refused at load otherwise, with QC's reason: the pinned recipe's 0.0 switches entropy off and a zero-initialised
categorical head can collapse onto one skill). `[trainer] entropy_loss_scale` (0.0 in the recipe,
`configs/ste_l012/gates.toml:116`, checked effective at `exploit_train.py:217-219`) still applies to the velocity
route only; the two-level update never reads it, and the run record says so.

**Where it is computed.** Stock skrl IPPO stores the log-probability of `act` time
(`skrl/multi_agents/torch/ippo/ippo.py:261,337`), has one ratio and one entropy scale (`:438-453`), so it cannot apply
masks known only after `env.step`. Slice 2 adds:

- `TwoLevelPolicy(Model)` (`opponents/learned.py`, appended so cited lines hold): one network output split into the
  two heads; `act` samples both heads (team first, then drone, the same draw order as `MultiCategoricalMixin`, so that
  under `set_seed` the samples match it) and returns the samples [B, 2] and `outputs["head_log_prob"]` [B, 2];
  `get_entropy` returns per-head entropies [B, 2].
- `TwoLevelIPPO(IPPO)` (`ste/`) **replaces `init` (memory tensors), `act`, `record_transition` and `update`**: `act`
  keeps `outputs[uid]["head_log_prob"]` on the agent (stock `act` keeps only `log_prob`, `ippo.py:254-261`, and
  `Learner.update` drops the outputs, `exploit_train.py:256`); `record_transition` stores `infos["head_mask"][:, i]`
  and the old per-head log-probabilities for slot i; `update` is a copy of skrl 2.1.0's `IPPO.update` (`ippo.py:368-540`)
  with the per-head ratios, KLs and entropy above. It keeps skrl's tracking keys (`Loss / Policy loss (<agent>)`,
  `Loss / Value loss (<agent>)`, `Loss / Entropy loss (<agent>)`, which `Learner.update` reads by the `Loss` prefix,
  `exploit_train.py:275`) and adds `Loss / Entropy team (<agent>)`, `Loss / Entropy drone (<agent>)` and the two KLs.
  It does not track `Policy / Standard deviation` (a categorical head has none; `Learner.update` already skips it for
  the skills route, `:276`). It is also the hook slice 3's absent-drone mask will use (§4). The copy is pinned: the
  module asserts `skrl.__version__ == "2.1.0"`, and a test checks the sha256 of `inspect.getsource(IPPO.update)`, so an
  upgrade of skrl stops the run until the copy is re-read.
- `Learner` (`exploit_train.py:166`) builds `TwoLevelIPPO` for `choice = "two_level"` only. The velocity route and slice
  1's single-head modes stay on stock IPPO, bit for bit.

**Action space skrl sees (per agent):** `MultiDiscrete([T+1, K_d])`: Strike [3, 4], Guard [3, 3] (list A). skrl's
memory stores the occupied size, 2 columns (`skrl/utils/spaces/torch/spaces.py:265-267`), as float32 (slice 1's test
`test_ste_l3_skills.py:305` already covers an index stored as float); the policy's output width is the sum, T+1+K_d.
`DecisionEnv` sets this space where slice 1 sets `Discrete(K)` (`exploit_train.py:84-85`). Observation [N, 71] and value
[N, 1] unchanged.

**Scoring play.** `SkillTeam` (`exploit.py:548-582`) takes the argmax of each head and resolves through the same
`resolve_two_level`. "free" is index 0 and the drone skills follow `[players]` order, so the untrained argmax is
"free + first drone skill" for every drone: **strike_straight / guard_parked_centre, the same step-0 row as slice 1**
(finding 3).

**Limits, stated:** slots 1 and 2 lead only after a tag, so their team heads train little and stay near their start;
this goes away with the shared actor after the pipeline check (v2 correction 2). A team strategy can be switched off
after 0.6 s; the scripts are stateless (`scripted.py:58-60`), so re-entering one later is well defined, but converge,
whose T44 games run 102-162 ticks (slice 1 finding 5), may rarely complete under a learner that switches.

**"Adapts to the opponent's strategy" (R30) is not evidenced by slice 2.** Slice 2 trains against one fixed opponent
script, as slice 1 and L0.12 do (`DecisionEnv`, `exploit_train.py:73-78`): a learner that beats one script has shown
nothing about adapting. The evidence needs the opponent pool of slice 3 (every script of the other team, one drawn per
game, both routes) and a **pooled-opponent row** in the pipeline check's score matrix: the trained team against the
pool mix on the same starts, beside its per-script cells and the worst cell (the headline). A drone or team choice that
changes with the opponent script on the same starts is what "adapts" means there; per-cell choice frequencies are
logged for it.

## 3. Hold rule, training and scoring: unchanged

A choice (both heads) every 12 ticks; the leader and the masks are fixed for the decision; the flown skills run closed
loop every tick (v2 hold rule). Training (`DecisionEnv.step`, `exploit_train.py:87-135`) and scoring (`HeldPlayer`
`exploit.py:509-545`, which holds the resolved choice `[N, M]` and needs no change) go through the same
`resolve_two_level` and `SkillDispatch.act`. A tagged leader keeps its choice to the end of the decision; the next
decision elects the next live drone.

## 4. QC's items before any skills-route training, placed

| QC item (parent note, "Slice 1 merged") | Slice | How |
|---|---|---|
| Explicit entropy scale + `update()` runs with it | **2** | §2: two scales, required, > 0, start 0.01 each; tests 5, 12 |
| Skill names saved and checked at load | **2** | `Learner.state()` gains `skills = {team, players order, team_strategies, drone_skills, free_index = 0, choice}`; `load_state` refuses a mismatch. `agent_final.pt` of the skills route becomes `{"skills": meta, "modules": modules}`: an extra top-level key would break the loaders, which sort keys by integer suffix (`exploit_train.py:340,358`). `skill_team_from_modules` checks the meta against the gate file's lists and refuses a changed order or membership. Velocity layout unchanged |
| Absent-drone mask (v2 list) | **3**, before the pipeline-check run (lead) | Tags make slots absent mid-game even at fixed sizes. It touches both routes (fair comparison) and the velocity golden, so it lands as one setting, default off with off = bit for bit, in `TwoLevelIPPO.update` and a velocity twin of it. Until then absent slots train as in §2 (parity) |
| Velocity scoring-path equality vs the old tree | **2** | Test 8a: a CPU golden of `play_cells` with a fixed velocity team, recorded from the pre-slice-1 commit `8421efdd`, compared with this tree game for game. `ste_score_matrix.py`'s own_replay runs on the current tree only, so it is not this check |
| Drivers wired | **2** for tier 1; **3** for tier 2 (lead accepted) | `scripts/ste_exploit_l012.py`: `:224` and `:300` refusals lifted for `two_level`; `:312` builds through `exploit_train.decision_env`; controls `:332-343`: for the skills route the untrained twin is the first drone skill's script cell (not `zero`), compared game for game; `agent_final.pt` `:511,972` with the meta; videos `:697` through `skill_team_from_modules`; pilot `:1036` gets a `SkillTeam.untrained` (timing of 6 / 5 scripts per tick). `--run0` and `verdict` keep refusing skills (run 0's known answer is the velocity learner's). Single-head modes "team"/"drone" refused for training (library and tests only). Tier 2 (slice 3): `Tier2Gates` (`tier2_train.py:86-97`) carries neither `[players]` nor `[learner]`; slice 3 adds both, `ste_tier2_l013.py:371` through `decision_env`, `:381` (snapshot team), `:465-475` (untrained twin), with the dispatch-equality test. `ste_score_matrix.py`, `ste_vid1_capture.py`, `ste_tier2_score_l18.py`, `ste_cross_tag_l012d.py`: still refuse, now also a two-level run folder (test 18) |
| Held-command arm | **2** (driver and test; no run) | `HeldPlayer`'s command path (`exploit.py:530-536`) already freezes a script's command for 12 ticks. New: `scripts/ste_l3_held_arm.py` plays every script of both teams held (`play_cells(players=..., hold_ticks=12)`) against every script of the other team on T44's starts, beside the closed-loop reference cells; paired counts per cell. Control: hold 1 = the reference game for game. Its run is part of the pipeline check's budget, not this slice |
| Opponent pool (v2 A3; not a QC item) | **3**, before the run (lead) | §2 "adapts"; the pooled-opponent scoring row |
| Export; tier-2 dispatch equality | 3+ | §5 |

**Tests, written first (CPU, small batches):**

1. Config: `two_level` loads list A and list B; refusals (unknown name, overlap, a player in neither list, empty drone
   list, a scale missing or ≤ 0, lists with choice "team"/"drone").
2. Non-coordinating rule: for each drone-list skill, perturbing only the own-team slots of the observation leaves its
   command bit for bit unchanged; for each team-list skill it changes (sacrifice, converge, parked_ring, field), on
   real observations (slice 1's `_team_obs`, `test_ste_l3_skills.py:125`).
3. Fixed-choice replay, both paths (training `DecisionEnv`, scoring `HeldPlayer`):
   (a) team head fixed at each team strategy (2 per side) reproduces that script's T44 cell game for game against
   every opponent script; (b) "free" with every drone on the same drone skill (4 Strike, 3 Guard) reproduces that
   script's T44 cell; (c) "free" with **every mixed combination** (Strike 4³ = 64, Guard 3³ = 27) reproduces a
   composite player written in the test without the dispatch (drone i plays its script's column i), game for game,
   against one opponent per side (g* / s*), at small n (4 games per combination) and a fixed seed; (d) leader rule:
   the slots' team heads disagree and the leader's choice flies; after the leader is tagged, the next live slot's
   choice flies from the next decision.
4. Masks, gradients: on a batch with both mask values, the drone head's weights get zero gradient from samples with
   F = 0 and the team head's from non-leader samples. A **non-leader's team-head sample stays out of the loss**: changing
   its stored action or old log-probability leaves the loss and every gradient bit for bit unchanged. Stored and
   recomputed per-head log-probabilities agree at the first epoch **with the observation scaler in eval mode** (skrl
   updates the scaler in epoch 0, `ippo.py:428-430`, so the stock path's ratio is not exactly 1); on the stock path,
   to rtol 1e-5.
5. Masked loss against a hand-written reference: random masks, s_team ≠ s_drone (e.g. 0.01 and 0.03), random advantages;
   policy loss, entropy loss and per-head KLs of one minibatch equal a plain-torch computation written in the test from
   the formulas of §2.
6. Update copy guard: two updates of `TwoLevelIPPO` against stock IPPO on the same batches, under `set_seed`. A
   per-head ratio is not stock's joint ratio, so the comparison is made where the two coincide: a one-skill drone head
   (K_d = 1, list B's Guard; its log-probability is 0, its ratio 1, its entropy 0, so it adds no gradient) with every
   head mask 1, against stock IPPO with a `CategoricalMixin` policy over the team head, its network initialised from
   ours (trunk and team rows), `entropy_loss_scale = s_team`. Networks, optimiser state and scalers after two updates
   equal to float tolerance (rtol 1e-6; bit for bit expected but not required: the drone term adds a constant to the
   loss). A second case checks the sample order: two-level `act` draws team then drone, as `MultiCategoricalMixin`
   does, so the samples equal the mixin's under the same seed.
7. Save and reload golden: two updates, save (meta included), reload in a fresh process; golden rows (both heads'
   logits, team choice, flown skill, final command) bit for bit; reload refuses a swapped `[players]` order and
   mark_edge moved to the team list. Slice 1's `test_ste_l3_skills.py:338` is updated for the new checkpoint signature
   (`{"skills", "modules"}`).
8. Velocity route unchanged: (a) **scoring golden** against `8421efdd` (above); (b) **training-update golden**: slice
   1's `test_ste_l3_velocity_golden.py:98` (recorded before slice 1) still holds, and a second golden of two velocity
   updates through `Learner` after this slice's `Learner` change, compared with the same fixture; refusal tests hold.
9. Driver: `ste_exploit_l012.py` with a `two_level` gate file runs a tiny CPU run end to end (controls including the
   untrained twin, two updates, final batch, `agent_final.pt` with meta, one CPU clip) and refuses run 0, verdict and
   the single-head modes; the tier-2 loader still refuses (`test_ste_l3_refuse.py:73`, unchanged).
10. Held arm: hold 1 equals the reference cells game for game; hold 12 plays and reports paired counts (small CPU
    batch).
11. Training = scoring: the two-level extension of slice 1's `test_ste_l3_skills.py:260`. The same scrambled two-level
    networks play T44's starts (1) through `decision_env` on a `FixedTrainGame` with skrl's own logits (argmax of each
    head) and (2) through `play_cells` with `HeldPlayer` + `Learner.team()`. Outcome and end step must be equal in
    every game. Power checks: the team choice must switch between "free" and a strategy inside some games, and the
    leader must change after a tag in at least one game.
12. Entropy start: with the scales at 0.01 the two-level `update()` runs; the team-head start bias gives p(free) = 0.5
    (to 1e-6) and the argmax at the start is (free, first drone skill).
13. The pinned copy: `skrl.__version__ == "2.1.0"` and the sha256 of `inspect.getsource(IPPO.update)` equal the values
    recorded when the copy was made.
14. KL paths under masking: with `kl_threshold` set low, the epoch loop stops on the summed per-head KL; with
    `KLAdaptiveLR`, the scheduler is stepped with the mean summed KL; both run without error on a masked batch.
15. `grad_norm_clip` under masking: the clipped gradient norm over policy and value parameters is at most the setting,
    with masked samples present.
16. Memory: `head_mask` and `head_log_prob` exist in every agent's memory with size 2 and dtype float32; a stored row
    equals `info["head_mask"]` and the per-head log-probabilities of that decision.
17. Absent slots: a slot absent at the decision's start under "free" has F = 1 and contributes to the loss (parity,
    until slice 3); the test states this so slice 3 flips it.
18. Guarded scripts: each script that still refuses skills (`ste_score_matrix.py`, `ste_vid1_capture.py`,
    `ste_tier2_score_l18.py`, `ste_cross_tag_l012d.py`) refuses a two-level run folder, and a velocity `agent_final.pt`
    still loads through each.

Test 3 runs the fixed choices through both paths as slice 1's `:171` does. Test 11 is the training = scoring check
with learned choices.

**Goldens (tests 6-8) follow slice 1's rules** (commits `ef1aee98`, `4bee640b`, `c9575314`): computed in a fresh child
process at torch's default thread count (OMP_NUM_THREADS and MKL_NUM_THREADS dropped from the child's environment), keyed
by the CPU capability as the velocity golden is. The `8421efdd` scoring golden is a fixture recorded once, by a script
run from a temporary worktree of that commit, and committed with its recording command; the test never checks out the
old tree.

## 5. Build order, estimate, and what is not in slice 2

Smallest first, each step with its tests before its code:

1. Config and `resolve_two_level` + tests 1, 2, 3; the velocity scoring golden against `8421efdd` (test 8a). About 1 day.
2. `TwoLevelPolicy`, `TwoLevelIPPO`, `Learner` branch, start bias + tests 4-6, 12-17, 8b. About 1.5-2 days (the update
   copy and its tests are most of it).
3. Checkpoint meta, `skill_team_from_modules` checks + test 7 and slice 1's `:338` update. About 0.5 day.
4. `ste_exploit_l012.py` wiring + tests 9, 11, 18. About 1 day.
5. Held-command arm driver + test 10. About 0.25-0.5 day.

**Estimate: 4-5 days** of build and CPU tests, then QC (one reviewer, R22 code build). No GPU. Estimate, not measured.

**Not in slice 2:** the export (ONNX logits [B, T+1+K_d], the ordered lists, a `policy_schema` bump, the scripts'
sha256; v2 B3); the tier-2 driver wiring, its gate-file tables and the dispatch-equality test (slice 3), so no tier-2
skills run; the absent-drone mask (slice 3); the opponent pool of v2 A3 and the pooled-opponent scoring row (slice 3);
the scoring controls rows (uniform-random, best single skill, oracle per cell) and the score-matrix and clip drivers for
skills; the attention encoder and shared actor; observation v0.3 (landing is off in the pipeline check, R32); any
training run.

## Lead's answers (24 Nov 2026, after two reviewers, no blocking finding)

1. mark_edge and mirror: **list A** (drone skills).
2. Tier 2: moves to slice 3, accepted.
3. Absent-drone mask: slice 3, before the pipeline-check run (tags make slots absent mid-game even at fixed sizes).
4. Opponent pool: slice 3, before the run.
5. Entropy: 0.01 per head as the start value, fixed in the pilot's gate file before its run.

Revisions made for the lead (same day): per-head ratios and KLs (A), the team-head start bias (B), "adapts" not
evidenced until the pool and the pooled-opponent row (C), tests 4-8 revised and 12-18 added (D), the subclass's
replaced methods and tracking keys, estimate 4-5 days (E).
