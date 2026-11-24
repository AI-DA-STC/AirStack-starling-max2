INTERNAL · design addendum for phase L3, slice 2 of the STE learning track: the two-level choice of owner ruling R30 (a team head over team strategies and "free", a drone head per drone over the skills that do not coordinate), built on slice 1; DRAFT for the lead and the slice's design review, no code yet · parent note: [L3_TWO_ROUTES_DESIGN.md](L3_TWO_ROUTES_DESIGN.md) (v2 and "Owner's ruling R30"); the ruling: [DISCUSSION §16](../DISCUSSION_2026-11-19_20.md#16-rulings-for-l1-to-l6-owner-24-nov-2026) R30

# L3 slice 2: team strategy with individual drone skills (design addendum, 24 Nov 2026)

Written 24 Nov 2026 by the builder (`ste-software-engineer`, Opus 5.5; advisor Fable 5.2 consulted before writing), on
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
| guard_mark_edge | no (see below) | `:89-112` | drone (proposed) |
| guard_mirror | no (same assignment as mark_edge) | `:153-161` | drone (proposed) |
| guard_parked_ring | **yes** (stations from every live mate's bearing) | `:325-347` | team |
| guard_field | **yes** (pushed off mates within 1.1 m) | `:139-142` | team |

**mark_edge and mirror: proposed non-coordinating (list A).** The brief's worry is the pairing at `:97`. Read exactly,
Guard i marks live Strike number (i mod S_live) counted in slot order (`_marked`, `:89-102`). Slots are ordered by drone
index and are the same for every observer (`core/observations.py:29-30`). The rank is over the **live Strike drones**;
the Guard's own index is fixed, never re-ranked among live Guards. So a Guard's target depends on its own index and the
Strike drones only, never on what its mates fly. Mixed with other drone skills, a marking Guard marks the same Strike it
would in its own script. mark_edge and mirror also share the one assignment (both call `_marked`), so any mix of the
two keeps the pure scripts' one-to-one cover. Mixed with parked_centre, a Strike goes unmarked: a tactic, not broken
behaviour. The alternative (**list B**: mark_edge and mirror as team strategies) leaves the Guard's drone head
one skill (parked_centre, which with two or more Guards is "hold the start position", `:298`). A one-skill head
chooses nothing, so under B "free" is a fifth team strategy and R30's individual skills disappear for the Guard team.
Both lists are only gate-file lines; A is proposed.

| Side | Team head (index: 0 = free) | Drone head | Widths |
|---|---|---|---|
| Strike team | free, sacrifice, converge | straight, flank, high, low | T+1 = 3, K_d = 4 |
| Guard team, list A (proposed) | free, parked_ring, field | parked_centre, mark_edge, mirror | 3, 3 |
| Guard team, list B (offered) | free, parked_ring, mark_edge, mirror, field | parked_centre | 5, 1 |

**Gate file.** `[learner] choice = "two_level"` (new value beside slice 1's "team" and "drone"), with optional-key
tables that `learner_spec` (`skills.py:60-80`, which today refuses unknown keys at `:67`) accepts only for that choice:

```toml
[learner]
action = "skills"
choice = "two_level"
team_strategies = { strike = ["strike_sacrifice", "strike_converge"], guard = ["guard_parked_ring", "guard_field"] }
drone_skills = { strike = ["strike_straight", "strike_flank", "strike_high", "strike_low"],
                 guard = ["guard_parked_centre", "guard_mark_edge", "guard_mirror"] }
entropy_scale = { team = <set at the gate file>, drone = <set at the gate file> }
```

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
logits: one trunk, two heads. `zero_mean_init` zeroes that layer as in slice 1 (`exploit_train.py:202-204`), so both heads
start uniform. **Every slot carries a team head** (any slot can lead after a tag); only the leader's flies. Value
networks unchanged.

**Head masks (per slot i, per decision; computed by `DecisionEnv.step` on the decision's first observation, returned in
`info["head_mask"]` [N, M, 2]):** team mask L_i = 1 if slot i is the leader, else 0; drone mask F = 1 if the leader's
team choice is "free", else 0. When the team head picks a strategy, every drone head's sample is ignored by the game and
**masked out of the loss**. A non-leader's team-head sample is masked out too (in slice 1's per-team mode it is not).
Masking is unbiased: the masked sample is drawn independently and does not change the game, so its score-function term
has expectation zero; dropping it only removes noise.

**Joint log-probability (slot i):** log π_i = L_i · log p_team,i(t_i) + F · log p_drone,i(d_i). A sample with both
masks 0 has ratio exactly 1 and no gradient.

**Entropy (slot i):** s_team · L_i · H(p_team,i) + s_drone · F · H(p_drone,i), with the two scales from `[learner]
entropy_scale` (Strike max entropies log 3 and log 4: not the same scale, hence two numbers). Both terms and the policy
loss use the **plain minibatch mean over all samples**, as stock skrl, so a head that is active in few samples keeps the
same ratio of entropy to policy gradient. **Both scales required and > 0** (refused at load otherwise, with QC's
reason: the pinned recipe's 0.0 switches entropy off and a zero-initialised categorical head can collapse onto one
skill). `[trainer] entropy_loss_scale` (0.0 in the recipe, `configs/ste_l012/gates.toml:116`, checked effective at
`exploit_train.py:217-219`) still applies to the velocity route only; the two-level update never reads it, and
the run record says so.

**Where it is computed.** Stock skrl IPPO stores the log-probability of `act` time (`skrl/multi_agents/torch/ippo/ippo.py:261,337`)
and has one entropy scale (`:447-448`), so it cannot apply masks known only after `env.step`. Slice 2 adds:

- `TwoLevelPolicy(Model)` (`opponents/learned.py`, appended so cited lines hold): `act` returns the two samples
  [B, 2], `outputs["head_log_prob"]` [B, 2] and `log_prob` = the masked sum when `inputs["head_mask"]` is given (all
  ones at `act` time); `get_entropy` returns per-head entropies [B, 2].
- `TwoLevelIPPO(IPPO)` (`ste/`): `init` adds a memory tensor `head_mask` (size 2); `record_transition` takes
  `infos["head_mask"][:, i]` for slot i and stores the **masked** old log-probability computed from `head_log_prob`;
  `update` is a copy of skrl 2.1.0's `IPPO.update` (`ippo.py:368-...`) with two changes: `head_mask` is sampled with the
  batch and passed to `policy.act`, and the entropy term is the one above. It is also the hook slice 3's absent-drone
  mask will use (§4).
- `Learner` (`exploit_train.py:166`) builds `TwoLevelIPPO` for `choice = "two_level"` only. The velocity route and slice
  1's single-head modes stay on stock IPPO, bit for bit.

**Action space skrl sees (per agent):** `MultiDiscrete([T+1, K_d])`: Strike [3, 4], Guard [3, 3] (list A). skrl's
memory stores the occupied size, 2 columns (`skrl/utils/spaces/torch/spaces.py:265-267`), as float32 (slice 1's test
`test_ste_l3_skills.py:305` already covers an index stored as float); the policy's output width is the sum, T+1+K_d.
`DecisionEnv` sets this space where slice 1 sets `Discrete(K)` (`exploit_train.py:84-85`). Observation [N, 71] and value
[N, 1] unchanged.

**Scoring play.** `SkillTeam` (`exploit.py:548-582`) takes the argmax of each head and resolves through the same
`resolve_two_level`. "free" is index 0 and the drone skills follow `[players]` order, so the untrained (zero-logit)
argmax is "free + first drone skill" for every drone: **strike_straight / guard_parked_centre, the same step-0 row as
slice 1** (finding 3).

**Limits, stated:** slots 1 and 2 lead only after a tag, so their team heads train little and stay near uniform; this
goes away with the shared actor after the pipeline check (v2 correction 2). A team strategy can be switched off after
0.6 s; the scripts are stateless (`scripted.py:58-60`), so re-entering one later is well defined, but converge, whose T44
games run 102-162 ticks (slice 1 finding 5), may rarely complete under a learner that switches.

## 3. Hold rule, training and scoring: unchanged

A choice (both heads) every 12 ticks; the leader and the masks are fixed for the decision; the flown skills run closed
loop every tick (v2 hold rule). Training (`DecisionEnv.step`, `exploit_train.py:87-135`) and scoring (`HeldPlayer`
`exploit.py:509-545`, which holds the resolved choice `[N, M]` and needs no change) go through the same
`resolve_two_level` and `SkillDispatch.act`. A tagged leader keeps its choice to the end of the decision; the next
decision elects the next live drone.

## 4. QC's items before any skills-route training, placed

| QC item (parent note, "Slice 1 merged") | Slice | How |
|---|---|---|
| Explicit entropy scale + `update()` runs with it | **2** | §2: two scales, required, > 0; test 5 |
| Skill names saved and checked at load | **2** | `Learner.state()` gains `skills = {team, players order, team_strategies, drone_skills, free_index = 0, choice}`; `load_state` refuses a mismatch. `agent_final.pt` of the skills route becomes `{"skills": meta, "modules": modules}`: an extra top-level key would break the loaders, which sort keys by integer suffix (`exploit_train.py:340,358`). `skill_team_from_modules` checks the meta against the gate file's lists and refuses a changed order or membership. Velocity layout unchanged |
| Absent-drone mask (v2 list) | **3** | It touches both routes (fair comparison) and the velocity golden, so it lands as one setting, default off with off = bit for bit, in `TwoLevelIPPO.update` and a velocity twin of it, before the pipeline-check run. Until then a tagged slot under "free" still trains on its zeroed observation and the team reward, as the velocity route does today (parity kept). R32 rules no drawn sizes, so absence comes from tags only |
| Velocity scoring-path equality vs the old tree | **2** | Test 8: a CPU golden of `play_cells` with a fixed velocity team (outcome, end_step, tags), recorded in a child process from the pre-slice-1 commit `8421efdd`, compared with this tree game for game. `ste_score_matrix.py`'s own_replay runs on the current tree only, so it is not this check |
| Drivers wired | **2** (tier 1 enabled; tier 2 wired, still refused) | `scripts/ste_exploit_l012.py`: `:224` and `:300` refusals lifted for `two_level`; `:312` builds through `exploit_train.decision_env`; controls `:332-343`: for the skills route the untrained twin is the first drone skill's script cell (not `zero`), compared game for game; `agent_final.pt` `:511,972` with the meta; videos `:697` through `skill_team_from_modules`; pilot `:1036` gets a `SkillTeam.untrained` (timing of 6 / 5 scripts per tick). `--run0` and `verdict` keep refusing skills (run 0's known answer is the velocity learner's). Single-head modes "team"/"drone" refused for training (library and tests only). Tier 2: `ste_tier2_l013.py:371` builds through `decision_env`, `:381` and `:465-475` take the skills team and its twin, but `tier2_train.py:138` keeps refusing a skills gate file, its message changed to "until the tier-2 dispatch-equality test". No tier-2 skills run starts before that test (slice 3). `ste_score_matrix.py`, `ste_vid1_capture.py`, `ste_tier2_score_l18.py`, `ste_cross_tag_l012d.py`: still refuse |
| Held-command arm | **2** (driver and test; no run) | `HeldPlayer`'s command path (`exploit.py:530-536`) already freezes a script's command for 12 ticks. New: `scripts/ste_l3_held_arm.py` plays every script of both teams held (`play_cells(players=..., hold_ticks=12)`) against every script of the other team on T44's starts, beside the closed-loop reference cells; paired counts per cell. Control: hold 1 = the reference game for game. Its run is part of the pipeline check's budget, not this slice |
| Export; tier-2 dispatch equality | 3+ | §5 |

**Tests, written first (CPU, small batches):**

1. Config: `two_level` loads list A and list B; refusals (unknown name, overlap, a player in neither list, empty drone
   list, a scale missing or ≤ 0, lists with choice "team"/"drone").
2. Non-coordinating rule: for each drone-list skill, perturbing only the own-team slots of the observation leaves its
   command bit for bit unchanged; for each team-list skill it changes (sacrifice, converge, parked_ring, field), on
   real observations (slice 1's `_team_obs`, `test_ste_l3_skills.py:125`).
3. Fixed-choice replay, both paths (training `DecisionEnv`, scoring `HeldPlayer`):
   (a) team head fixed at each team strategy (2 per side) reproduces that script's T44 cell game for game against every
   opponent script; (b) "free" with every drone on the same drone skill (4 Strike, 3 Guard) reproduces that script's T44
   cell; (c) "free" with **every mixed combination** (Strike 4³ = 64, Guard 3³ = 27) reproduces a composite player
   written in the test without the dispatch (drone i plays its script's column i), game for game, against one opponent
   per side (g* / s*); (d) leader rule: the slots' team heads disagree and the leader's choice flies; after the leader is
   tagged, the next live slot's choice flies from the next decision.
4. Masks: on a batch with both mask values, the drone head's weights get zero gradient from samples with F = 0, the
   team head's from non-leader samples; at the first epoch of the first update the ratio is exactly 1 (stored and
   recomputed masked log-probabilities agree).
5. Entropy: `update()` runs with both scales; the tracked per-head entropy terms equal a hand computation on the same
   batch.
6. Update copy guard: with all head masks forced to 1 and s_team = s_drone = s, two updates of `TwoLevelIPPO` equal stock
   IPPO with a `MultiCategoricalMixin` policy (reduction "sum") and `entropy_loss_scale = s`, to float tolerance (rtol
   1e-6: the entropy sums are taken in a different order); bit for bit for the policy-loss path with s = 0 on both.
7. Save and reload golden: two updates, save (meta included), reload in a fresh process; golden rows (both heads' logits,
   team choice, flown skill, final command) bit for bit; reload refuses a swapped `[players]` order and mark_edge moved
   to the team list.
8. Velocity route unchanged: slice 1's velocity golden (`test_ste_l3_velocity_golden.py:98`) and refusal tests hold;
   the scoring golden against `8421efdd` above.
9. Driver: `ste_exploit_l012.py` with a `two_level` gate file runs a tiny CPU run end to end (controls including the
   untrained twin, two updates, final batch, `agent_final.pt` with meta, one CPU clip) and refuses run 0, verdict and the
   single-head modes; the tier-2 loader still refuses with the new message.
10. Held arm: hold 1 equals the reference cells game for game; hold 12 plays and reports paired counts (small CPU batch).

Training = scoring is tests 3 (both paths, same games) and 9 (the driver's final batch through `HeldPlayer`).

## 5. Build order, estimate, and what is not in slice 2

Smallest first, each step with its tests before its code:

1. Config and `resolve_two_level` + tests 1, 2, 3 (fixed choices, no learning). About 0.5 day.
2. `TwoLevelPolicy`, `TwoLevelIPPO`, `Learner` branch + tests 4, 5, 6. About 1 day (the update copy and its guard test
   are most of it).
3. Checkpoint meta, `skill_team_from_modules` checks + test 7. About 0.25 day.
4. Velocity scoring golden against `8421efdd` + test 8 (independent; can go first). About 0.25 day.
5. `ste_exploit_l012.py` wiring, tier-2 build path, + test 9. About 0.5-0.75 day.
6. Held-command arm driver + test 10. About 0.25-0.5 day.

**Estimate: about 3 days** of build and CPU tests, then QC (one reviewer, R22 code build). No GPU. Estimate, not
measured.

**Not in slice 2:** the export (ONNX logits [B, T+1+K_d], the ordered lists, a `policy_schema` bump, the scripts' sha256;
v2 B3); the tier-2 dispatch-equality test and so any tier-2 skills run; the absent-drone mask (slice 3); the opponent
pool of v2 A3 (both routes, one script drawn per game; slice 3, see below); the scoring controls rows (uniform-random,
best single skill, oracle per cell) and the score-matrix and clip drivers for skills; the attention encoder and shared
actor; observation v0.3 (landing is off in the pipeline check, R32); any training run.

## Open questions for the lead

1. **mark_edge and mirror:** list A (drone skills, proposed) or list B? Under B the Guard team has no individual skill
   to choose (one-skill drone head).
2. **Tier 2 in slice 2:** this note wires the tier-2 build path but keeps tier-2 skills runs refused until the
   dispatch-equality test (slice 3). The brief named tier 2 among the drivers to wire; enabling it before that test
   would allow an unverified run.
3. **Absent-drone mask:** slice 3 before the pipeline-check run (proposed), or, since R32 rules out drawn sizes, after
   the pipeline check?
4. **Opponent pool (v2 A3)** is not in QC's list or this brief, but both routes need it before the pipeline-check run:
   slice 3 with the mask?
5. **Entropy scale values** for the gate file (both > 0 is enforced; the values are a gate-file call, written before the
   run).
