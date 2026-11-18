INTERNAL · a build plan written for the lab's AI coding assistants; history, not instructions. Results: [../README.md](../README.md).

# NUS port, Phase 5: retraining (route b): NUS's method in PyTorch, then Starling-like drones

**Status: PLAN v3.1 (18 November 2026; v3.1 adds P0's 49,152-game point and the GPU memory risk), after the `train-gatekeeper` reads of v1 and v2 (both PASS WITH FIXES; every fix
applied, change log at the end) and of v3.1 (PASS, 18 Nov ~16:20). Frozen 16:20: `phase5_reference_rebuild`,
`phase5_positive_control`, `phase5_negative_control`, `phase5_method_match`; pilot caps fixed; the other Phase 5
tables stay PROPOSED (`phase5_tier1_training` waits on the owner's observation answer). Only P0 has run (INFO); nothing else built or run.** Written by the lead under
the owner's delegation of 18 November: the Phase 5 decisions D-P5-1 to D-P5-7 are
final and live in the private port plan ("Phase 5 decisions", lab only). Phase 4
is complete (T17 PASS; T18–T20 and T22–T24 INFO; T21 ABORTED). Gate tables: `configs/nus_port.toml` `[gates.phase5_*]`, `status = "PROPOSED"`,
frozen before the first run of the stage they gate (STANDARDS §7). Every new value below is **PROPOSED** unless it is
labelled MEASURED (with its record) or OPEN.

NUS's settings and our results on NUS's code are stated here (owner, 18 November 2026; STANDARDS §2). NUS's source code
is described in words with `file:line` citations into NUS's branch folder
`~/ma_skills-self-play/area-denial-continuous-space-self-play/` ("N/" below; 5090 only), never pasted. Code keeps
reading NUS's values from `configs/local/`.

## 1. Purpose, and what this phase proves

**Goal.** Train our own Guard team (and its sparring Strike team) for the hangar game on Starling-like drones, with
NUS's training method, after a pre-registered test has failed to tell our copy of the method apart from NUS's own
runs.

Phase 4 showed why the frozen NUS policies cannot simply be flown. Observed in the training simulator, the NUS Guard
G19 against the NUS Strike S20 lets the Strike team reach the zone in 9 of 1,000 games in the replica (row 1, T18) and
43 with action hold, our blocking keep-apart rule in place of NUS's push and the drone response (row 3, T20). It is 740 with the all-pairs safety filter (row 4, T22), 983 in 3-D with a 1 mm start jitter
(row 5, T23) and 979 on the Isaac Lab physics drone (row 6, T24). A Guard parked at the zone centre holds 444, 429 and
476 of 1,000 against S20 on rows 4, 5 and 6: the filter itself acts as a wall.

| Stage | Proves, observed in the training simulator | Does not prove |
|---|---|---|
| 5.1 method match (2-D replica) | our PyTorch copy of NUS's alternating best-response MAPPO with the archive pool is not told apart from NUS's three hangar lineages by the pre-registered test (3 v 3 seeds; a broken-learner screen, not an equivalence test) | anything about drones; that the copy is bit-exact or equivalent (random streams differ; with three seeds a side the test can only catch large differences) |
| 5.2 tier 1 training | the copied method trains a Guard team on the hangar game with the Starling layer (commander copy, delay, lag of the EXPLORATORY drone model), the all-pairs safety filter and 3-D, which beats every Guard measured on Phase 4 row 5 against fixed Strike references | a flight result; behaviour on the real drone (the drone model is exploratory, T5 = FAIL); other geometries, team sizes or drop-out |
| 5.3 Isaac Lab cross-check | the chosen 5.2 Guard keeps its result on the physics drone (tier 2) within a stated gap | anything about the AirStack simulator or real flight |
| Pilots P0–P3 | whether a simple learner (the skrl stand-in) finds "use the filter as a wall" (D-P5-7); not gated, INFO records | nothing of record |

Wording rules (STANDARDS §2) apply to every record and figure: "observed in the training simulator", never
"validated"; Strike team, Guard team, reach the zone, hold the zone. Nothing here authorises a flight; flights follow
`docs/PREFLIGHT.md` and `docs/RUNBOOK.md`, and NEAR-962 (the real-drone fit) comes before any of it.

## 2. Facts this plan rests on (read 18 November 2026)

| # | Fact | Source |
|---|---|---|
| F1 | Our NUS reference lineages: `train_self_play`, seeds 1, 2, 3, 8 generations, hangar overrides `spawn_distance = 8.0`, `defender_boundary = 8.0`; seed 2 later resumed in its own folder to 20 generations. No APEX: the config is `train_self_play`, not `train_self_play_apex`, and every log line reads "prior weight 0.000" | `~/nus_jax_runs/2026-11-17_hangar_selfplay_3v3_seed{1,2,3}.cmd.txt`, `…_seed2_to20.cmd.txt` and `.log` (5090 only) |
| F2 | Archive entries exist for all 3 seeds × generations 1–8 (seed 2 to 20): `…/outputs/hangar/2026-11-17_selfplay_3v3_seed{1,2,3}/archive/000k_{defender,attacker}/` with `actor.msgpack`, `config.json`, `metadata.json` | NUS outputs (5090 only) |
| F3 | The existing cross-play matrices use **256 games per pair** (200 in `metadata.json`), with start states that differ per opponent id; the 1,000-game reference does not exist yet | `~/ma_skills-self-play/_probes/selfplay_eval/results.md`, `matrix_raw.json`; NUS_PORT §11 |
| F4 | NUS's three lineages disagree cell by cell: Guard generation 7 against Strike generation 8 gives 0.008 Strike wins for seed 1 and 1.000 for seeds 2 and 3; seed 1's Strike generations 4 and 8 failed against their own pool | `_probes/selfplay_eval/results.md` criteria (a), (b) |
| F5 | Robust signatures across NUS's seeds (256 games): every Strike policy beats the scripted Guard 1.00; every Guard (generations 1–7) holds the scripted Strike in 0.92–0.98 of games; a Guard's mean hold against the other lineages' Strike policies rises with generation in every seed (generation 1 ≈ 0, generation 7 0.57–0.70) | computed from `_probes/selfplay_eval/matrix_raw.json` key `strike_win_matrix_guard_active` (rows Guard s<seed>g<gen>, columns Strike) and keys `guard_vs_apf`, `strike_vs_apf`: for seed s, Guard g, the mean over the Strike columns of seeds ≠ s of (1 − cell) (lead, 18 Nov 2026; INFO, recomputed at 1,000 games in R0) |
| F6 | NUS took 2.75 h of wall clock for 3 seeds × 8 generations run side by side on the 5090 (about 8 min per generation for one job alone, 0.071 s per update) | the three seed logs, first and last time stamps; `…_seed2_to20.log` |
| F7 | Our replica (Phase 2, T15 PASS) steps the 2-D game at 9,450,674 game-steps/s (ticks), 1,000 games × 6 drones | `records/2026-11-18_nus_phase4_rung1_record.md` |
| F8 | The hangar game with the all-pairs safety filter runs at 3,084 game-steps/s (1,000 games × 6 drones, tier 1), against 280,932 without the filter (row 3, T20). MEASURED: 0.32 s per tick, T22's whole-run mean at 1,000 games (an evaluation run); every pair with a game that runs to the time-out took 769–790 s (2,400 ticks); the warm-up estimate of the first ticks was about 0.39 s per tick (22,548 s for 24 × 2,400 ticks). If the cost is per tick (P0 checks this), one 2,400-tick game takes 13–16 min of wall clock however many games run beside it. Every start has a pair inside the filter's keep-out ("start miss" 1000/1000), so the filter never stops early | `records/2026-11-18_nus_phase4_rung4_2_record.md` and `runs/nus_port/phase4/row_4/scores.json` (`seconds` per pair, `meta.estimate_seconds`); `…_rung3_record.md`; T8 for the filter's early stop |
| F17 | **P0 (INFO, pilot, not of record)**, ParkedGuard v S20 arm, row 5 settings, 400 timed ticks: MEASURED 0.3141 s per tick at 1,000 games, 0.4116 at 4,096, 0.4274 at 16,384, 0.4327 at 32,768. The filter takes 94–99 % of the tick: 1,000 sweeps every tick, its early stop never fires, about 82,000 kernel launches per tick, the GPU busy about 19 % of the time. Random-action arm (INFO; its base is artificially cheap): 0.063 at 1,000, 0.161 at 4,096, 0.194 at 16,384. P0 ran from commit `e595bfd3` plus the then-untracked probe script, under the v1 pilot table; its hours go into `runs/nus_port/phase5/pilots/gpu_hours.log` (P0 total 0.368 GPU-h). 49,152 games (ParkedGuard v S20): 0.3609 s per tick, 0.84 × the 16,384 value; random arm at 32,768: 0.2696 (INFO). Each count draws its own starts, so the seconds per tick above 4,096 games read as flat at 0.36–0.43, not as a speed-up at 49,152. **Peak reserved GPU memory is 23–31 GB from 16,384 games up**, against 0.7–2.1 GB allocated: the filter's early-stop re-gather changes tensor shapes, and PyTorch's caching allocator keeps the freed blocks | `runs/nus_port/phase5/p0/probe.json` (`arms.parked_s20`, `arms.random`, `profile`) (5090 only) |
| F9 | `NusHangarGame._draw_starts` returns the same starts tensor at every reset: each slot replays one start for ever. Fine for scoring, wrong for training (STANDARDS §6.4) | `source/svg_training/nus/hangar_game.py` `_draw_starts` |
| F10 | `train_standin.py` is hard-wired to the S2 game: it refuses `preset != "pure"`, loads `s2_game.toml` with `use_local=False`, builds `SvgGame(...)` directly, reads 2 v 1 from its table, trains `("guard",)` only, takes its caps from `[standin_s2b]`, evaluates with a Guard-only live strategy and writes no video | `scripts/train_standin.py:483-560, 654, 720-735, 783` |
| F11 | `make_strategy` loads a stand-in run folder for the Guard team only | `source/svg_training/opponents/scripted.py:221-225` |
| F12 | Interface v0.1 already carries the drone's own height (index 2, absolute z) and 3-D relative position and velocity of every other drone; it does not carry the height band (floor and ceiling of the playing volume), the way it carries the arena half-side for the walls | `source/svg_training/core/observations.py:12-35, 67-71` |
| F13 | The Task 9 stand-in fixes: initial log std −1.6 and frozen noise on the axes that carry no reward (`[standin_v2]`, `starling = ["yaw"]`, so vz is trained in 3-D) | `configs/s2b.toml:108-135` |
| F14 | S2b's tier 1 to tier 2 hold gap limit is 0.10 per cell on 1,000 paired games | `configs/s2b.toml:72` (T13) |
| F15 | The Phase 4 paired starts file (seed 20261119) and the row scores and per-game outcomes are on disk. sha256: `starts.npz` `40c8cc59297f58d5a7c18b2eb89dc67d2c8ec940b8d95243673928cab6cd2a67`; `row_5/scores.json` `5b1f3ed606181443ae6965b4fe080287506a077dc7304a801ec40428237adb8d`; `row_5/per_game.npz` `eddc531e30b165809d4ba30620e83787cf87d686c80ef40cd5b9be3cd8fc715a`; `row_6/scores.json` `8876029efb055b479fbc913f143fbaed05eabdbde8aec51aa165dde00885a86d`; `row_6/per_game.npz` `67ef501676640f6fbedaa73f907c824407ef53bf01ad8b8b85bbe8050655712b`. `per_game.npz` holds `ParkedGuard__S20__outcome` (1,000 games) | `runs/nus_port/phase4/` (5090 only; hashed 18 Nov 2026) |
| F16 | NUS's stage seed = run seed + generation − 1, and a learner's initial weights come from the stage seed and the team code: lineages whose run seeds differ by less than the number of generations share stage seeds. Our reference lineages (seeds 1, 2, 3) share them among themselves (seed 1 generation 3 and seed 3 generation 1 are both Guard learners with stage seed 3, so the same initial weights), so their seed-to-seed spread may be understated | N/ma_skills/runner/ensemble_self_play_runner.py:216; N/ma_skills/runner/fixed_opponent_runner.py:350-369 |

## 3. Decisions taken in this plan (PROPOSED; the owner delegated technical calls, D-P5-5)

| # | Decision | Why |
|---|---|---|
| P5-1 | **APEX is not ported in 5.1.** It may follow later as its own plan | F1: the reference runs never used it |
| P5-2 | **One evaluation engine for both arms**: our replica (T15) with converted NUS actors (Phase 3 gate (a) per entry) and our trained actors, deterministic, on one shared set of starts. NUS's own evaluator at 1,000 games is a cross-check (INFO) | the JAX and PyTorch evaluators draw different starts (F3); one engine removes that difference |
| P5-3 | **The 5.1 rule is statistical over seeds, not per cell.** Per-cell rules only where all three NUS seeds agree; seed-dependent quantities are compared as seed-level means with a two-sample interval | F4: a per-cell "inside NUS's 95 % interval" rule fails NUS against itself. This replaces the wording of D-P5-1 and the port plan's Phase 5 gate ("cross-play within 95 % intervals") |
| P5-4 | **A positive control before our training is scored**: NUS's own code, run seeds 101, 201, 301, scored by the frozen 5.1 rule as if it were ours (C0). It must PASS. **And a negative control** (N0): untrained actors scored as ours must FAIL | C0 shows the rule does not fail a correct copy by seed chance; N0 shows it fails a learner that learned nothing. Seeds are spaced by 100 so no stage seed collides with the reference lineages' (F16) |
| P5-12 | **Our seeds**: 5.1 and its variants 1001, 2001, 3001; the extra seeds after an INCONCLUSIVE 4001, 5001, 6001; 5.2 1001, 2001, 3001 | the same reason as C0's: no stage seed shared with the reference or control lineages (F16); our initialisation uses a different generator anyway, but the spacing keeps the arms apart if that ever changes |
| P5-5 | **5.2 acts once every 12 ticks (0.6 s)** and holds the command, with the game repeating it every tick; γ = 0.99 per decision; 200 decisions per 120 s game | NUS's γ and horizon are per 0.6 s step; keeping them changes one thing at a time. The repeat satisfies the 0.5 s stale-command rule (STANDARDS §3) |
| P5-6 | **5.2 training keeps NUS's reward semantics**: the training game runs to the time-out with a sticky reached flag (the Strike team wins on its first reach, as in our game), with NUS's per-step inside-share penalty, first-reach penalty and potential shaping, zero-sum. Evaluation keeps the programme rule (first reach ends the game). The win/lose outcome is the same either way | NUS's reward gives partial credit for keeping some Strike drones out (N/ma_skills/jax/rewards.py:20-28); dropping it changes the method |
| P5-7 | **5.2's batch shape is decided by data from 5.1.** 5.2's cost is set by the number of ticks played one after another, not by game-steps: every update plays whole games of 2,400 ticks, and the tick cost hardly grows with the game count: P0 measured 0.314 s per tick at 1,000 games and 0.427 at 16,384, so 16 times the games cost 1.36 times the time (F17). Variant 5.1b collects the same episodes per generation as NUS in rollouts of 16,384 games (47 updates per generation instead of 6,000), with NUS's minibatch size and epochs, so the gradient steps per generation stay NUS's; 5.1c does the same with a third of the episodes (16 updates). Both run in 2-D under the 5.1 rule; 5.2 uses the cheapest variant that passes | ESTIMATES from P0's MEASURED rates (§8): per generation on tier 1, NUS's shape about 1,260 h (at 0.314 s per tick; 128 games was not measured), 5.1b about 14.2 h and 5.1c about 5.1 h (at 0.427 s per tick, 16,384 games) |
| P5-8 | **5.2 trains from scratch** (route b), not from the converted policies (that is route c) | D-P5-1 |
| P5-9 | **Fixed layout, fixed 3 v 3, no drop-out** in 5.1 and 5.2 (STANDARDS §6.4 exception: one layout; §7.4 team-size and drop-out groups not applicable) | D-P5-3; the network has no padding, so 3 v 3 only (read from NUS's code); NUS: the method does not support drones dropping out, and a policy trained with one config usually works only with that config (NUS_PORT §3) |
| P5-10 | **5.1 runs without the safety filter** (STANDARDS §6.2 exception), as Phase 4 rows 1–3 did. It is a 2-D method match; nothing from it is exported. 5.2 and 5.3 restore the filter on every pair | D-P5-1, D10 |
| P5-11 | **5.2 actor output is 3-D** (vx, vy, vz; tanh, then projection onto the team's speed ball); yaw rate 0, not an output | D-P5-2 (3-D); yaw carries no reward (F13) |

## 4. Stage 5.1: method match (2-D replica, NUS observation layout `nus_area_denial_v1`)

### 4.1 What is copied (NUS's `train_self_play` as run in F1, described in words)

All numeric settings are NUS's and are read from a new git-ignored `configs/local/nus_method.toml`, written by a script
from the resolved `config.json` of the reference run (Task M1). The values are stated here because NUS agreed they may
be (STANDARDS §2).

**Schedule and pool** (N/ma_skills/runner/ensemble_self_play_runner.py, N/ma_skills/config/train_self_play.yaml):
1. Generations alternate teams: odd generations train the Guard team (NUS "defender", `train_team`), even ones the
   Strike team (`_team`, :153-156). 8 generations per lineage (our command's override; NUS's default is 32).
2. **Fresh learner each generation**: new actor and critic, initialised from the stage seed and the team code
   (N/ma_skills/runner/fixed_opponent_runner.py:350-369); stage seed = run seed + generation − 1 (ensemble_self_play_runner.py:216).
3. Opponents of generation g: every archived entry of the other team if there are at most 15; otherwise the latest 8
   plus 7 drawn without replacement from the older ones, with a NumPy generator seeded by (seed, generation), sorted by
   generation (`select_opponents`, :29-43). The selection is fixed for the whole generation. We use the same NumPy call,
   so the selection is identical for an identical archive.
4. **A permanent scripted slot**: NUS's APF controller of the other team is always in the pool (`include_apf_in_pool`,
   `scripted_opponents` null, so "apf" for both teams). Generation 1 trains against it alone.
5. **Equal blocks**: the rollout batch is split into one contiguous block per slot, learned slots first, APF last
   (N/ma_skills/jax/mpe.py:350-358, 489-497). Batch size = slots × max(8, ceil(128 / slots)) episodes (ensemble_self_play_runner.py:222-226);
   with up to 16 slots that is 128–132 episodes per update.
6. 6,000 updates per generation; each update collects whole 200-step episodes from fresh resets (mpe.py:359-362).
   Frozen opponents act in their saved selection mode (deterministic mean); the learner samples.
7. **Selection, not the last update**: every 2,000 updates and at the end, the learner (mean action) plays 200 games per
   opponent on fresh starts; rank = (geometric mean of per-slot win rates, worst, mean), rounded to 12 digits; the best
   snapshot so far is kept (ensemble_self_play_runner.py:532-572). At generation end the **best** snapshot is archived with its metadata
   (:574-649). A per-slot win-rate EMA (α = 0.01) is logged and stored with the best (:670-674).

**Learner** (N/ma_skills/jax/policy.py, N/ma_skills/jax/nn.py, N/ma_skills/jax/training.py,
N/ma_skills/config/train_mappo_self_play_mpe.yaml):
8. Actor: Dense(256) → residual MLP of width 512 (input Dense, 2 pre-norm residual blocks of LayerNorm, Mish, Dense,
   twice; output Dense(2) with orthogonal 0.01 initialisation); fan-in truncated-normal initialisation elsewhere, zero
   biases (nn.py:29-36, 59-126; policy.py:20-70). Trunk computed in bfloat16, the head in float32; a learned
   state-independent log std per axis, initial −0.5, clipped to [−5, 2]. Phase 3's converted actor
   (`source/svg_training/nus/actor.py`) already reproduces this forward pass.
9. Action: latent = mean + std × noise; action = tanh(latent) × team speed, projected onto the speed disk
   (policy.py:97-108, 202-229). **The latent is stored**; the PPO log probability is the Gaussian density at the stored
   latent, without the tanh Jacobian (it cancels in the ratio) (policy.py:141-156).
10. Critic: same trunk shape on the central state = the game state fields (positions, done flags, step, zone position,
    previous positions, both spawn centres, the reached flag: 5N + 8 numbers) plus a one-hot of the opponent slot,
    padded to 16 slots (mpe.py:29-99). One value per game (team level).
11. Reward, Guard team, per step (rewards.py:8-59; config `trainer.rewards.defender`): potential shaping 0.20 ×
    (γ × summed Strike distance to the zone now − the same before), minus 1.0 × the share of Strike drones inside the
    zone, minus 2.0 on the step of the game's first reach; no time-out bonus. The Strike team gets the exact negative.
    The game always runs 200 steps; the reached flag is sticky; the time limit is the only episode end.
12. GAE with γ 0.99, λ 0.95, bootstrap 0 at the end (training.py:35-63). Advantages normalised over the whole batch and
    clipped to ±20 (`per_slot_advantage_norm` false; :66-76); one team advantage shared by the team's drones.
13. PPO: 4 epochs × 4 minibatches over (time × games) samples, clip 0.1, log-ratio clipped to ±20, entropy coefficient
    0.03 on the **entropy of the squashed policy at fresh reparameterised samples** (policy.py:184-199;
    training.py:226-262), critic loss coefficient 0.5 (squared error, no value clipping). Actor and critic each have
    their own AdamW (weight decay 0.01) behind a global-norm clip of 0.5; learning rates 1e-4 (actor) and 5e-4
    (critic), constant within a generation (train_self_play.yaml overrides the cosine schedule)
    (fixed_opponent_runner.py:289-330).
14. A non-finite metric aborts the run (fixed_opponent_runner.py:862-871).

**Not copied:** the W&B logging, the benchmark opponents, the timing evaluation, APEX and specialists (P5-1),
`generation_gate`, `plateau_restart`, `best_checkpoint` (all disabled for self-play stages, ensemble_self_play_runner.py:229-231).

**Our side.** The environment is the Phase 2 replica (`nus/replica.py`) with the hangar overrides, NUS's observation
(`NusReplica.observe`), and new reward, critic-state and APF-block helpers. Everything in the rollout and the update is
batched over games (STANDARDS §6.1). The frozen opponent pool runs as one batched call over stacked parameters
(`torch.func.stack_module_state` + `vmap`), not a loop over games. A Python loop over the 200 steps of a rollout, the
PPO minibatches and the generations is allowed: it is not a loop over games.

### 4.2 Reference data (R0)

**Freezing.** `[gates.phase5_reference_rebuild]`, `[gates.phase5_positive_control]`, `[gates.phase5_negative_control]`
and `[gates.phase5_method_match]` are frozen together, after the gatekeeper read and before R0 starts. R0 may change
exactly one thing, and only by its pre-registered `loo_check`: statistic 5.1-c from gate to INFO. Nothing else moves.

1. Convert the 24 NUS archive entries (seeds 1–3, generations 1–8) with `scripts/nus_convert_checkpoint.py`. Each entry
   passes Phase 3 gate (a) (max action error ≤ 0.02 units on ≥ 10,000 reference observations, frozen
   `[gates.phase3_converted_policy]`). An entry that fails is reported and leaves the reference set; more than two
   failures stop the stage.
2. Score the 12 Guard × 12 Strike matrix plus both APF columns on the replica: 1,000 games per pairing, one shared start
   set drawn once by the replica's random start rule (seed PROPOSED: 20261120), both teams deterministic. Output
   `runs/nus_port/phase5/reference/matrix_1000.json` and its sha256 (5090 only).
3. Cross-check (INFO): NUS's own evaluator at 1,000 games per pairing on the same 24 entries, through a committed
   `scripts/nus_jax_crossplay.py` (env `nus_jax`, calls NUS's functions, holds none of their code). Report per-cell
   differences; nothing is gated on them.
4. Leave-one-out calibration of the per-entry rule (5.1-c): each NUS entry is checked against the envelope of the other
   eleven of its team. If any fails, statistic 5.1-c becomes INFO. This is decided on NUS data alone, before any of our
   runs.

### 4.3 The gate (`[gates.phase5_method_match]`)

**Arms.** Ours: 3 seeds (1001, 2001, 3001; P5-12) × 8 generations of the copied method. NUS: the 24 entries of F2. Same engine, starts,
game count (1,000 per pairing) and action mode.

**Statistics** (one module, `nus/crossplay.py`, serves the gate, the figures and the record; STANDARDS §7.2):

| Id | Statistic | Rule | Kind |
|---|---|---|---|
| 5.1-a | completion: every seed archives 8 generations; non-finite aborts 0 | all three seeds | gate |
| 5.1-b | learner works (NUS's criterion (a) of `_probes/selfplay_eval/results.md`): a generation fails when its archived best's worst win rate against its own training pool (APF included), re-scored at 1,000 games per opponent, is ≤ 0.5 | no seed has two consecutive failed same-team generations within generations 1–6 | gate |
| 5.1-c | scripted columns: each of our entries' win rate against the other team's APF | inside [lowest Wilson 95 % lower bound, highest Wilson 95 % upper bound] over NUS's 12 entries of the same team (R0); INFO if R0's leave-one-out check fails | gate |
| 5.1-d | cross-lineage strength: for each lineage, the mean over its four Guards of the hold rate against NUS's Strike entries of the **other** lineages (for a NUS seed: the other two seeds; for ours: the mean over the three leave-one-out panels), APF excluded; the same for its four Strikes (reach rate against NUS's Guards) | for each of the two: the 95 % pooled two-sample t interval of (our 3-seed mean − NUS's 3-seed mean), t quantile 2.776 (4 degrees of freedom), contains 0. Seed standard deviations use n − 1; the floor 0.02 is applied to each arm's standard deviation before pooling and before the spread ratio. Our seed value = the mean over the three leave-one-out panels. An entry that fails conversion leaves its panel and its lineage's mean uses the remaining entries, the same way for the reference, C0 and N0 | gate |
| 5.1-e | last-mover share (own-lineage 16-cell matrix, share of cells where the later-trained policy wins), near-shutout share, the generalist band of criterion (b), per-cell JAX-vs-replica differences, curves | reported | INFO |

**Verdict, in this order.** FAIL if 5.1-a, 5.1-b or 5.1-c (when gated) fails, or either 5.1-d interval excludes 0.
Otherwise INCONCLUSIVE if either 5.1-d spread ratio (our floored standard deviation ÷ NUS's floored standard deviation)
exceeds `d_spread_ratio_max` = 4.36. Otherwise PASS. INCONCLUSIVE can only replace a PASS, never a FAIL.

One policy's 5.1-d value rests on 8,000 games (8 opponents × 1,000; sampling error ≤ 0.011 at 95 %) and one lineage's on
32,000 (≤ 0.006), small against the seed-to-seed spread the interval uses. At 256 games NUS's seed values are 0.28,
0.37, 0.44 (Guards) and 0.46, 0.70, 0.75 (Strikes) (F5; recomputed at 1,000 games in R0). With equal spread on our side
the Guard interval is about ±0.19 and the Strike interval about ±0.36. N0 shows the rule catches a learner that learned
nothing; its power against a partly broken learner is not measured; it cannot catch small differences. That limit is stated in the record.

**Why a spread rule, and why 4.36.** A two-sample interval passes more easily the noisier our seeds are, so a large
spread on our side must not count as a PASS. 4.36 = √19: the variance ratio of two samples of three follows F(2, 2),
whose one-sided 5 % point is 19, so a correct copy with NUS's spread is flagged 5 % of the time per statistic. v1's 2.0
would have flagged it 20 % of the time per statistic, about 36 % across the two.

**After an INCONCLUSIVE, fixed now.** Exactly three more seeds of ours (4001, 5001, 6001) are trained. All six are scored
once against the three NUS lineages: 5.1-a to 5.1-c over the six, and 5.1-d with a Welch interval (Welch–Satterthwaite
degrees of freedom) of the difference of means. The spread rule then gives FAIL, not INCONCLUSIVE. That verdict is
final.

**Positive control C0** (`[gates.phase5_positive_control]`): NUS's code, run seeds 101, 201, 301 (P5-4, F16), exactly the
F1 command with the seed and `hydra.run.dir` changed, through `scripts/workstation/run_nus_job.sh`. Its 24 entries are
converted (R0 step 1) and scored by the frozen 5.1 rule as the "ours" arm. C0 must PASS before any of our seeds is
scored.
- C0 FAIL: the rule is wrong, not the port. Stop; the lead writes a new gate version (a new table), gatekeeper read.
- C0 INCONCLUSIVE (scoring is deterministic, so re-scoring would change nothing): follow-up fixed now. NUS's code runs
  three more seeds, 401, 501, 601 (stage seeds 401–408, 501–508, 601–608: no collision with the reference's 1–10, C0's
  101–308, ours or N0's). All six C0 lineages are scored once with a Welch interval on 5.1-d; the spread rule then gives
  FAIL, not INCONCLUSIVE. That verdict is final; a FAIL is handled as below.
- Any rule rewritten after C0 needs a fresh positive control with new seeds before 5.1 is scored.
- Videos: NUS's `eval.py` renders two games per archived entry (NUS's self-play runner writes none, STANDARDS §8).

**Negative control N0** (`[gates.phase5_negative_control]`): three "lineages" of untrained actors (our initialisation,
seeds 7001, 8001, 9001; one fresh actor per generation slot, no training) scored by the frozen 5.1 rule as the "ours"
arm, beside C0. It must FAIL, and specifically **both 5.1-d intervals must exclude 0**. 5.1-a (completion) does not apply
to N0; for 5.1-b each N0 entry is scored against the pool the selection rule would have built from the earlier N0
entries of the other team plus APF. The record gives the verdict of every statistic a to d. If N0 does not fail as
required, the rule cannot catch a learner that learned nothing: stop before 5.1 is scored. Expected, as a pipeline
check (lead's estimate from F5, INFO): Guard difference about −0.37 against a half-width about 0.13; Strike about −0.64
against about 0.25. Scoring only, on the replica: near-zero GPU time. No videos (nothing trained; the record says so).

**Variants 5.1b and 5.1c** (`[gates.phase5_method_variants]`): 3 seeds each (1001, 2001, 3001), the same rule, the
same reference. They run only after 5.1 PASSES.
5.1b: rollouts of 16,384 games per update (PROPOSED), 47 updates per generation so that the episodes per generation
equal NUS's (6,000 × 128 = 768,000); minibatch size (6,400 samples) and epochs (4) as NUS, so each update makes 2,048
gradient steps and a generation about NUS's 96,000; selection evaluation after updates 16, 32 and 47. 5.1c: the same
with 16 updates per generation (a third of the episodes and of the gradient steps), evaluation after updates 8 and 16.
Each variant has its own verdict; INCONCLUSIVE counts as not PASS. They exist only to choose 5.2's batch shape (P5-7);
they make no claim of their own.
The risk they test: each rollout now feeds 2,048 gradient steps instead of 16, so the policy moves much further from
the one that collected the data.

**Videos (STANDARDS §8).** For 5.1, 5.1b and 5.1c: one replica game at every selection evaluation, and two per archived
entry (the first Strike win and the first hold among the first 16 games against its strongest pool member), top-down,
through `viz/replay.render_replay` as `scripts/nus_make_videos.py` does, into `runs/nus_port/phase5/<stage>/seed<s>/videos/`.
Records list them.

## 5. Stage 5.2: tier 1 training (hangar, Starling layer, all-pairs filter, 3-D)

### Training set-up (PROPOSED)

| Item | Setting |
|---|---|
| Game | the hangar game of Phase 4 row 5: fixed arena, zone and 3 v 3; the Starling layer with the fitted EXPLORATORY model (`params/real_exploratory_v0.toml`; T5 = FAIL, it answers more slowly than the real drone); the all-pairs safety filter at the flight stack's keep-out with 1,000 sweeps and `check_every` 8; height free inside the committed band; ±1 mm start-height jitter |
| Starts | drawn fresh for every new game by the replica's start rule (Guards in the start disc, Strike drones on the start ring, random bearings), plus the jitter, in a new `NusHangarTrainGame` (F9). Training generators never reuse the Phase 4 starts seed |
| Observation | interface v0.1 (71 numbers), or v0.2 (v0.1 + the height band, floor and ceiling in m, appended at indices 71–72) approved by the owner 18 Nov ~18:20 (§12 item 1); pilots use v0.1. The critic sees the central state (`build_state`, 61 numbers) plus the 16-wide slot one-hot |
| Action | 3-D (P5-11), one decision every 12 ticks, command repeated every tick (P5-5) |
| Reward | NUS's, in metres, run to the time-out with a sticky reached flag (P5-6); the shaping scale is converted from units with the deploy file's scale |
| Method | the 5.1 copy, unchanged apart from the environment, at the batch shape chosen by 5.1b/5.1c (P5-7) |
| Pool | the archive of the other team plus one permanent scripted slot: NUS's APF of the other team as a strategy (`ApfStrike`/`ApfGuard`, `nus/players.py`). Mix: equal episode blocks per slot, so the scripted share is 1/(learned + 1), from 100 % at generation 1 to 1/16 (STANDARDS §6.3: scripted opponents never leave) |
| Seeds, generations | 3 seeds (1001, 2001, 3001; P5-12), 8 generations each; the gated checkpoints are each seed's last archived Guard (generation 7) and last archived Strike (generation 8) |
| Logged | from the same metrics module as the evaluation (STANDARDS §7.2): Strike reach rate and hold rate per slot, filter intervention share and size, smoothness, same-team closest approach in 3-D, entropy, KL, clip fraction, value loss, non-finite counts; the unfiltered command is what the learner stores (STANDARDS §6.2) |

### Gate (`[gates.phase5_tier1_training]`)

**Evaluation.** Each gated checkpoint is scored on the Phase 4 row 5 settings and the Phase 4 paired starts file (F15),
1,000 games per pairing, Wilson 95 % intervals, through a Phase 5 evaluation runner that reuses `nus/ladder.py`'s
metrics. Hold rate = 1 − Strike reach rate.

**Bars, pre-registered.** A bar is the highest Wilson 95 % upper bound of any Phase 4 row 5 Guard against that Strike,
computed by code from `runs/nus_port/phase4/row_5/scores.json` (T23; sha256 pinned in the gate table, F15). Values for
reading, from the T23 record:

| Gate | Our checkpoint | Against | Best row 5 reference | Bar (pass if our Wilson lower bound is above it) |
|---|---|---|---|---|
| G-1 | Guard, generation 7 | S20 | ParkedGuard holds 429/1000 [0.399, 0.460] | 0.460 |
| G-2 | Guard | ApfStrike | guard_mirror holds 41/1000 [0.030, 0.055] | 0.055 |
| G-3 | Guard | strike_straight | G19, P3G and ParkedGuard (the only row 5 Guards scored against it) hold 0/1000 [0.000, 0.004] | 0.004 |
| G-4 | Guard | strike_flank | G19, P3G and ParkedGuard (the only row 5 Guards scored against it) hold 0/1000 [0.000, 0.004] | 0.004 |
| S-1 | Strike, generation 8 | ParkedGuard | S20 reaches 571/1000 [0.540, 0.601] | 0.601 (reach rate) |
| F-1 | both | all pairings above | fence: **met by construction** on tier 1 and tier 2, because the game clamps every drone into the keep-in box (arena square in x and y, height band in z) after each step (`core/game.py:273-276` calling `nus/hangar_game.py:59-61` and `core/starling_layer.py:121` on tier 1, `core/physics_layer.py:135` on tier 2). A post-clamp breach cannot occur, so F-1 is stated, not measured. INFO instead: the share of drone-ticks where the clamp acted (pre-clamp position outside the box by more than 0.01 m), Task S5. The real-flight fence (AirStack keep-in) is separate and unaffected | by construction |
| F-2 | both | all pairings above | non-finite actions or states | 0 |
| C-1 | control | ParkedGuard v S20 re-scored in the same run | must equal row 5 game by game: `runs/nus_port/phase4/row_5/per_game.npz` key `ParkedGuard__S20__outcome` (sha256 in F15). Tier 1 has repeated exactly across runs: row 5a equalled row 4 in all 12 pairs (T23) | 0 games differ |

**Per seed and over seeds.** A seed passes when G-1 to G-4, S-1 and F-2 all pass (F-1 holds by construction). **5.2 PASSES when at least 2
of 3 seeds pass** and C-1 holds. The record states the count, and the claim is worded by it ("in all three seeds" or
"in two of three seeds"). Fewer than two is a FAIL. A C-1 failure stops the evaluation (`train-debug`) before any
verdict.

**Claim strength.** G-3 and G-4 (bar 0.004) pass with as few as 8 holds in 1,000 games: they show the Guard holds
something where no Phase 4 Guard held anything, not that it holds well. G-1 and S-1 carry the main claim. The record
says so (also for P2's signal).

**INFO in the same run** (STANDARDS §7.4 fixed suite, the groups that apply): our Guards against P3S; our Strikes
against G19, P3G, ApfGuard, guard_mirror and guard_mark_edge; the cross-play
table of every archived generation of each lineage (earlier versions; its own cap, §8); closest approaches, same-team approach, filter
share and size, smoothness, contact (the tier 1 contact distance; every start is already inside the filter's keep-out,
F8, so contact is reported, not gated). Not applicable, with the reason (P5-9): held-out starts and worlds, team sizes,
drop-out.

**Order.** The gated pairings run first, inside the 6 GPU-h evaluation cap. The INFO within-lineage cross-play table
runs only after them, under its own cap of 10 GPU-h; if that cap is not granted at the stop after the gated
pairings, the table is dropped and the record says so.

**Videos.** At every scheduled evaluation one game; for each gated checkpoint two games per gated pairing (the first
Strike win and the first hold among the first 16 slots), top-down from `NusHangarGame`'s video slots, into
`runs/nus_port/phase5/s52/seed<s>/videos/`.

**If 5.2 fails.** Stop for the owner. D-P5-3 named the remedy: revisit the geometry (a larger zone or start disc) as a
new plan; no gate is moved.

## 6. Stage 5.3: Isaac Lab cross-check (tier 2)

- **Checkpoint**, pre-registered: among the seeds that pass every 5.2 gate, the Guard (generation 7) with the highest
  tier 1 hold rate against S20; ties go to the lower seed. The Strike opponents are the 5.2 references.
- **Run**: the Phase 4 row 6 path (`starling.backend = "physics"`, `IsaacWorld`, headless, after
  `scripts/isaac_preflight.sh --approved-headless` exits 0), the same paired starts, 1,000 games per pairing, against
  S20, ApfStrike, strike_straight and strike_flank, plus ParkedGuard v S20 as a control: its reach count must lie inside
  T24's Wilson 95 % interval (524/1000, [0.493, 0.555]); the games that differ from T24 are reported. Nothing shows that
  the physics drone repeats game by game across runs (T24 is one run), so the control is an interval, not an equality.
  A control outside the interval stops the stage before any verdict (`train-debug`). The reference outcomes are
  `runs/nus_port/phase4/row_6/per_game.npz` key `ParkedGuard__S20__outcome` (sha256 in F15).
- **Gate** (`[gates.phase5_isaac_crosscheck]`): X-1, tier 2 hold against S20 has a Wilson lower bound above the highest
  Wilson upper bound of any row 6 Guard against S20 (T24: ParkedGuard 476/1000 held, [0.445, 0.507], bar 0.507);
  X-2, |tier 2 hold − tier 1 hold| ≤ 0.10 for each of the four pairings (the S2b limit, F14); X-3, upsets 0 and
  non-finite 0. The stage limit of STANDARDS §7.7 ("Stage 4: allowed gap", OPEN) is set by this plan for Phase 5 only.
- **Fine-tune only on failure** (X-1 or X-2 fails), **one attempt only**: continue training that Guard on tier 2 with the
  same method against its lineage's frozen Strike archive plus APF, capped at 8 GPU-hours, then re-score with the same
  three gates written into a new gates file before the fine-tune run. After the fine-tune, X-2's tier 1 reference is
  the fine-tuned checkpoint re-scored on tier 1 (the same four pairings). The tier 1 gates of 5.2 are reported on it as
  INFO. A FAIL after the one attempt is final for Phase 5. The trainer cannot run on tier 2 today: Task S9 is built
  only if the trigger fires.
- **Videos**: top-down from the physics drones' positions, two games per pairing; Isaac camera clips with
  `scripts/nus_isaac_clips.py` (optional, INFO). The fine-tune run: one game at each scheduled evaluation, plus two each
  for its final and best checkpoints.

## 7. Pilots P0–P3 (D-P5-7): not gated, INFO records

Each pilot gets a short record headed "pilot, not of record" and an INFO ledger row (STANDARDS §8: one row per run). No
pilot gates anything. All four together use **at most 6 GPU-hours** (wall-clock hours holding the 5090; processes of one
pilot running side by side count once). They run only when no Phase 4/5 job needs the GPU, on a free GPU (`nvidia-smi`,
no AirStack simulator, no NUS JAX job).

**Cap enforcement.** Each pilot runs under a hard wall-clock limit equal to its cap, evaluations included (the process
is stopped at the limit; its last saved networks and record stand). No `--accept-long` for pilots. One running log,
`runs/nus_port/phase5/pilots/gpu_hours.log`, adds up every pilot's GPU-hours across P0–P3; a pilot whose remaining cap
is below the time of one evaluation does not start.

**What a pilot costs** (P0, F17, MEASURED). Training runs at 32,768 games (lead's choice from the ParkedGuard v S20
arm; the random arm is INFO, its base is artificially cheap): 0.4327 s per tick, so a training update of 32 ticks takes
about 13.9 s plus the PPO step (not measured). **Every evaluation costs one whole game, up to 2,400 ticks**: at the
evaluation's 1,000 games or fewer, 0.3141 s per tick, about 12.6 min. `train_standin.py`'s own cap counts training time only, so each pilot's GPU
cap below includes its evaluations: training-time cap = GPU cap − number of evaluations × P0's measured time for one
2,400-tick game. Game counts and steps are PROPOSED; P0's measurement replaces them by the rule given.

| Pilot | What | Settings (PROPOSED) | Games, steps, evaluations | Caps | Promotion signal (→ a gated plan) |
|---|---|---|---|---|---|
| P0 (ran) | throughput probe of the hangar game, row 5 settings, ParkedGuard v S20 and random actions | 1,000 / 4,096 / 16,384 / 32,768 / 49,152 games (49,152 ≈ three 16,384-game seeds side by side, §8); 50 warm-up ticks, then 400 timed ticks | results in F17: 0.3141 / 0.4116 / 0.4274 / 0.4327 / 0.3609 s per tick (ParkedGuard v S20); peak reserved memory 23–31 GB from 16,384 games up | 0.5 GPU-h (used 0.368) | none (INFO). Pilots' game count: 32,768 (the ParkedGuard v S20 arm's largest count within 1.5 × its 1,000-game value; lead's decision to use that arm) |
| P1 | 3 Guard learners v S20 | skrl IPPO stand-in, `[pilot_p1]` in a new `configs/nus_phase5.toml`: `[standin_v2]`'s learner (hidden [128, 128], init log std −1.6, yaw log std frozen, vz trained, lr 3e-4, 32 rollouts, 5 epochs, 4 minibatches, γ 0.99, λ 0.95), the policy acting every tick (stand-in convention), shaping weight 1.0; v0.1 observation; Strike team 100 % S20 | 32,768 games; about 0.87 h of training ≈ at most 225 updates ≈ 7,200 ticks ≈ 236 M game-steps (fewer once the PPO step is counted; `[standin_v2]` used 100 M per seed); 3 evaluations (about 0.63 h): start, half-way (first 256 paired starts), end (all 1,000) | 1.5 GPU-h incl. evaluations | final mean-action hold v S20 on the 1,000 Phase 4 paired starts has a Wilson lower bound above 0.460 (the parked Guard's upper bound, G-1's bar) |
| P2 | Guard learners v scripted Strikes | warm start from P1's final networks; Strike mix in equal game blocks: S20, ApfStrike, strike_straight, strike_flank (S20 kept, so P1's skill is not forgotten) | as P1 (32,768 games, at most about 236 M game-steps, 3 evaluations) | 1.5 GPU-h incl. evaluations | P1's signal still met and the hold v strike_flank has a Wilson lower bound above 0.004 (a low bar: 8 holds in 1,000 pass it) |
| P3 | short self-play | four alternating stages (Guard, Strike, Guard, Strike), each a stand-in run against the frozen earlier stages of the other team plus one APF slot in equal blocks; Guard from P2's final networks, Strike from scratch | 32,768 games; about 0.42 h of training per stage (at most about 108 updates ≈ 3,450 ticks ≈ 113 M game-steps); one evaluation per stage, at its end only (`--no-eval-at-start`) | 2.5 GPU-h for all four, incl. evaluations | the last Guard keeps P1's signal, and the Wilson lower bound of the last Strike's reach rate against the parked Guard is above 0.601 (S-1's bar) |

Total: 0.5 + 1.5 + 1.5 + 2.5 = 6.0 GPU-hours. If P0 shows evaluations longer than 20 min, P1 and P2 drop the half-way
evaluation and P3 drops its first stage; the cap is never raised.

Every pilot: mean actions at evaluation, the paired starts of Phase 4 (row 5) so the numbers sit beside T23's;
TensorBoard; the run folder under `runs/nus_port/phase5/pilots/<name>/`; **videos** from each evaluation's own recording
(one game per evaluation, and two games each for the final and the best checkpoint; STANDARDS §8), so they cost no
extra game. A pilot that meets its signal becomes a gated plan of its own (with 3 seeds) before any claim; a pilot that
does not is recorded as such.

**Entry point.** Pilots run through `scripts/train_standin.py --game nus_hangar --pilot-config configs/nus_phase5.toml
--settings pilot_p1 …` (P1, P2) and a small driver `scripts/nus_pilot_selfplay.py` for P3. None of this exists yet; the
glue is Tasks P-T1 to P-T7.

## 8. GPU budget on the home RTX 5090 (32 GB, shared)

A GPU-hour here is a wall-clock hour in which the job holds the 5090; side-by-side processes of one stage count once.
Before every run: `nvidia-smi` free beyond the 1,024 MiB per foreign process allowed by `isaac_preflight.sh` and
`run_nus_job.sh` (owner, 18 Nov); no AirStack simulator, no flight session. Isaac Lab (5.3) only after
`scripts/isaac_preflight.sh --approved-headless` exits 0. NUS JAX jobs only through `run_nus_job.sh` (logging off,
own `hydra.run.dir`, memory fraction 0.25 per job as in F1); a JAX job (about 1.7 GB) blocks the Isaac preflight, so C0
never overlaps 5.3.

| Stage | Cap (GPU-h, PROPOSED) | Basis |
|---|---|---|
| R0 conversions, reference matrix, JAX cross-check | 1 | conversions on the CPU; 12 × 12 pairings plus both APF columns × 1,000 games on the replica is seconds at F7's rate |
| C0 positive control (3 NUS seeds side by side, then scoring) and N0 negative control (scoring only) | 4 | MEASURED 2.75 h for seeds 1–3 (F6); N0 is seconds on the replica |
| 5.1 timing probe (50 updates) | 0.25 | — |
| 5.1 (3 seeds side by side) | 36 | estimate only: NUS needs 0.071 s per update in JAX (F6); a PyTorch copy at 0.3–1.5 s per update gives 4–20 h per seed for 48,000 updates. The probe decides; above the cap, stop (Task M7 adds CUDA-graph capture of the rollout step first) |
| 5.1b, 5.1c (3 seeds each) | 24 together | fewer, larger updates; probe first |
| Pilots P0–P3 | 6 (0.5 + 1.5 + 1.5 + 2.5, evaluations included) | D-P5-7; §7 |
| 5.2 training | **OPEN; PROPOSED cap 72**, fixed after P0 and 5.1b/c | counted in **ticks played one after another**, because every update and every selection evaluation plays whole 2,400-tick games. Hours per generation = seconds per tick × 2,400 × (updates + selection evaluations per generation); the estimates table below uses P0's MEASURED 0.4274 s per tick at 16,384 games (F17). **Side by side:** the three seeds run side by side only if P0's seconds per tick at 49,152 games is at most 1.5 × its value at 16,384. MEASURED: 0.3609 against 0.4274, ratio 0.84: **the rule passes**. "Side by side" means **one process holding the three seeds' games**, or separate processes only with `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` and `torch.cuda.set_per_process_memory_fraction`, tested first; no other GPU job runs alongside (P0's peak reserved memory, F17). One 49,152-game process only approximates three 16,384-game processes. **At the measured rates only 5.1c side by side fits the cap: about 35 h (42 h if the tick cost is read at the flat band's top, 0.4327).** **Pre-set stop:** if the estimate for 3 seeds × 8 generations at the cheapest passing variant exceeds 72 h, stop for the owner (options: more GPU time, fewer generations, CUDA-graph capture of the filter loop, a training-time filter with fewer sweeps checked against T8's accuracy table) |
| 5.2 evaluation, gated pairings | 6 | the gated pairings first; T22 took 3.03 h for 24 pairings scored one after another |
| 5.2 INFO within-lineage cross-play table | 10 | runs only after the gated pairings; dropped, with a line in the record, if this cap is not granted at that stop |
| 5.3 cross-check | 2 | T24 took 2.09 h for 24 pairings; this is 5 |
| 5.3 fine-tune (only if triggered) | 8 | — |

**Recomputed estimates for 5.2 training** (ESTIMATES from P0's MEASURED rates, F17; 2,400 ticks per game; 8 generations):

| Shape | Updates + selection evaluations per generation | Seconds per tick used | Hours per generation | 3 seeds, one after another | 3 seeds side by side |
|---|---|---|---|---|---|
| NUS's (128 games) | 6,000 + 3 | 0.3141 (1,000 games; 128 not measured) | ≈ 1,260 | ≈ 30,000 h | not considered |
| 5.1b (16,384 games) | 47 + 3 | 0.4274 | ≈ 14.2 | ≈ 342 h | 266.7 × 0.3609 ≈ 96.2 h: over the cap |
| 5.1c (16,384 games) | 16 + 2 | 0.4274 | ≈ 5.1 | ≈ 123 h: over the cap | 96 × 0.3609 ≈ **34.6 h** (MEASURED 49,152-game rate); ≈ 41.5 h at 0.4327, the top of the flat band; inside the 72 h cap |

Every runner prints an estimate from a warm-up before it starts (`[ladder] warmup_ticks` pattern) and refuses to start
above its cap without `--accept-long` (never for pilots, §7); records quote measured rates only (STANDARDS §8: games, drones per game, tier,
GPU).

## 9. Tasks for the implementer (test first, `train-change`; implementer writes, lead reviews)

Order matters. **Tasks marked ★ block pilot P1**; they come first so the pilots can run while the method port is built.

0. **Gatekeeper read of this plan and of the `[gates.phase5_*]` tables** (v1 read: PASS WITH FIXES, applied in v2);
   the decisions and the owner question of §12. Nothing else starts before it.

**Pilot glue (P1 can start after ★ tasks):**

- ★ **P-T1 throughput probe** `scripts/nus_phase5_probe.py --games 1000,4096,16384,32768,49152 --out runs/nus_port/phase5/p0/`:
  builds `NusHangarGame` with row 5 (`hangar_cfg` + `configs/nus_phase4.toml` row "5"), times ticks, writes `probe.json` (primary output: seconds per tick at each game count).
  Test: CPU, tiny counts, marker local files (`tests/_nus_phase4_fixture.py`); G2 literal scan widened to it. Then run
  P0.
- ★ **P-T2 training starts** `source/svg_training/nus/train_game.py:NusHangarTrainGame(NusHangarGame)`: `_draw_starts`
  draws fresh starts per game with `NusReplica.reset`'s rule (batched, a `torch.Generator` from the run seed), scaled to
  metres, at the flying height plus a fresh jitter; recording off by default. Tests: two resets give different starts;
  the start distribution's radii and bearings match the replica's (moments, 10,000 draws); a fixed seed is
  reproducible; no Python loop over games (the step-loop lint of earlier tasks).
- ★ **P-T3 `train_standin.py` hooks** (existing tests in `tests/test_train_standin.py` stay green; the default path is
  bit-identical, shown by a test on the S2 game with a fixed seed):
  - `--game {s2,nus_hangar}` (default `s2`) and `--pilot-config` (default `configs/nus_phase5.toml`), with
    `SETTINGS_TABLES` extended by `pilot_p1`, `pilot_p2`, `pilot_p3_guard`, `pilot_p3_strike`;
  - one function `build_games(args, st, device, seed) -> (cfg, train_game, eval_game, team_sizes)`: the `s2` body is
    today's code moved; the `nus_hangar` body is `source/svg_training/nus/pilot.py:pilot_games(...)` (row 5 settings,
    `NusHangarTrainGame` for training, `NusHangarGame` on the first `--eval-games` slots of the Phase 4 starts file for
    evaluation);
  - the `preset == "pure"` refusal and the `use_local=False` load apply to `--game s2` only; the NUS path reads the
    local files through the `nus/` loaders;
  - team sizes, `train_teams` (`guard` or `strike`), opponents (registry names or `module:Class` specs such as
    `svg_training.nus.players:RefStrike`, split in equal game blocks) and the wall-clock cap come from the table;
  - `--warm-start <run folder>` (P2, P3) and `--no-eval-at-start` (P3; the default keeps today's `evaluate(0)`);
  - the trained team made a parameter where it is hard-coded today: the `LiveGuard` evaluation strategy
    (`team = "guard"`, line 720) becomes a live strategy of the trained team; `play_match(eval_game, live,
    eval_strike, …)` (line 783) takes the teams in the right order; `SvgSkrlEnv(game, train_teams=("guard",),
    opponents={"strike": …})` (line 560) takes both from the table; `interface.toml`'s `"team": "guard"` (line 654)
    and its `preset`, `game_config` and `local_file` fields describe the NUS game (local files named by sha256 only,
    through `nus/outputs.write_record`'s rules);
  - per-behaviour hold rates (`eval_slices`) built from the table's opponent mix for either team.
  Tests: CPU, 32 games, 3 v 3, marker local files, both teams; the refusal messages; `test_standin_ignores_local_file`,
  `test_standin_config_unchanged` and `test_default_settings_unchanged` unchanged and green.
- ★ **P-T4 pilot videos**: at each evaluation the eval game keeps its video slots; `viz/replay.render_replay` writes one
  game per evaluation and two for the final and best checkpoints into `runs/<name>/videos/`. Test: files appear under
  `tmp_path/runs/`, nothing outside `runs/`.
- ★ **P-T5 configs** `configs/nus_phase5.toml`: `[pilot_p1]`, `[pilot_p2]`, `[pilot_p3_*]` (no partner value; the G2/
  privacy scans cover it) and `[probe]`. Test: tables load, caps sum to ≤ 6 GPU-h.
- **P-T6 Strike-team stand-in loading** (P3 only): `make_strategy` accepts a stand-in run folder for the Strike team
  when its `interface.toml` says `team = "strike"` (`opponents/learned.py`, `opponents/scripted.py:221-225`); test both
  teams and the refusal on a mismatch.
- **P-T7 P3 driver** `scripts/nus_pilot_selfplay.py`: runs the four stages in order, each a `train_standin.run(...)` call
  with the previous stages as opponents plus `ApfStrike`/`ApfGuard`; one GPU-hour ledger. Test: CPU, tiny counts.

**Method port (5.1):**

- **M1 privacy first.** `configs/nus_method.template.toml` (every value `"LOCAL"`), `scripts/nus_make_local_method.py`
  (reads a reference run's resolved `config.json`, writes `configs/local/nus_method.toml`, refuses `--out` outside
  `configs/local/`), loader `nus/method_cfg.py` (refuses missing, unknown, `"LOCAL"`, wrong-type keys). Widen the G2
  literal scan, `protected_numbers` and the G4 marker chain to every new `nus/` module and script of this plan.
- **M2 replica training environment** `nus/replica_train.py`: batched reset (random starts), joint step, NUS observation,
  the central state in NUS's field order plus the slot one-hot, NUS's reward and the zero-sum split, reached and
  inside-count flags, APF actions for the scripted block (`nus/apf.py`). Parity: extend `scripts/nus_record_fixtures.py`
  (env `nus_jax`, CPU) to record rewards and central states; test our values within 1e-4 units (positions) and 1e-5
  (rewards) on 100 recorded episodes.
- **M3 learner** `nus/mappo.py`: trainable actor (the `nus/actor.py` network, bfloat16 trunk), critic, sampling with the
  stored latent, log probability, transformed entropy, GAE, advantage normalisation, the PPO update, the two AdamW
  optimisers with clipping. Tests: hand-computed values for each formula; a **one-update parity test** on a batch
  recorded from NUS's `policy_update` (exported by a committed `scripts/nus_jax_export_update.py`, env `nus_jax`): same
  initial parameters, one epoch, one minibatch, no shuffling; losses within 1e-3 relative and parameter changes within
  bfloat16 tolerance (PROPOSED 2e-2 relative on the update's norm).
- **M4 self-play loop** `nus/selfplay.py`: archive, `select_opponents` (the same NumPy call; a test against a table of
  selections recorded once from NUS's function, indices only, in `tests/data/`), batch-size formula, team alternation,
  stage seeds, stacked-parameter opponent inference, evaluation and ranking, best snapshot, archive writing, EMA, resume
  from alternating checkpoints, non-finite abort. Tests on the CPU with tiny counts.
- **M5 evaluation module** `nus/crossplay.py`: batched matrix scoring on the replica (shared starts, deterministic,
  pairings stacked), statistics 5.1-a to 5.1-e, Wilson intervals, the pooled t interval, the per-arm floor, the spread
  ratio and the verdict order (FAIL, then INCONCLUSIVE, then PASS), the six-seed Welch follow-up, the leave-one-out check,
  the untrained-actor arm of N0, the figure inputs. The figure script `scripts/make_nus_phase5_figures.py` imports it and computes nothing itself. Tests:
  hand-made matrices with known verdicts, including the zero-variance floor.
- **M6 reference build R0** `scripts/nus_phase5_reference.py` and `scripts/nus_jax_crossplay.py`; conversions with
  `nus_convert_checkpoint.py` and `nus_export_reference.py` (a `--archive-entry` loop over the 24 entries). Output only
  under `runs/nus_port/phase5/reference/`.
- **M7 trainer** `scripts/nus_selfplay_train.py --seed <s> --variant {nus,5.1b,5.1c} --out runs/nus_port/phase5/s51/…`
  with `--probe-updates 50`, the cap check, resume, videos per archived entry, the record draft. Rollout step made
  CUDA-graph capturable if the probe misses the cap. Tests: CPU smoke of two generations with tiny counts.
- **M8 runs**: C0 (NUS run seeds 101, 201, 301, then scoring) and N0, then 5.1 (seeds 1001, 2001, 3001; after an
  INCONCLUSIVE, 4001, 5001, 6001), then, only after 5.1 PASSES, 5.1b and 5.1c. Records and ledger rows.

**Tier 1 training (5.2) and the cross-check (5.3):**

- **S1 training game** for 5.2: `NusHangarTrainGame` with the decision period and command repeat, the run-to-time-out
  training mode with the sticky reached flag (evaluation keeps the first-reach end), and 3-D actions. Tests: hold of 12
  ticks; outcome equal to the first-reach rule on 1,000 CPU games with scripted players; the reached flag stays set.
- **S2 interface** (only after the owner's answer to question 1): `core/observations.py` v0.2 (two numbers appended,
  no index moved), `INTERFACE_VERSION`, HANDOFF, PLUG_IN. Tests: indices 0–70 unchanged; NUS players unaffected.
- **S3 reward and critic state** in metres for the hangar game (shaping scale converted from units by the deploy
  file's scale, G2). Tests against the replica's reward on matched positions.
- **S4 method on the game**: `nus/selfplay.py` takes an environment object (replica or hangar game) with the same
  interface; trained players registered in `nus/players.py` (`TrainedGuard`, `TrainedStrike` bound to a run folder).
- **S5 evaluation runner** `scripts/nus_phase5_eval.py --stage {5.2,5.3}`: reuses `nus/ladder.py`'s metrics and the
  Phase 4 starts file, writes `gates.toml` first, applies the bars from the T23/T24 `scores.json`, runs the control
  pair (row 5: game by game against `per_game.npz`; row 6: inside T24's interval), refuses non-finite values, writes
  scores, videos and the record draft. It adds the INFO **clamp-share metric** that stands beside F-1: the
  share of live drone-ticks whose pre-clamp position lies outside the keep-in box by more than 0.01 m, recorded inside
  the batched step. Tests on the CPU, row 6 with `TorchRigidBodyWorld`; a clamp test: a drone moved 0.02 m outside the
  box counts one clamped drone-tick, a drone moved 0.005 m outside or kept inside counts none, and after the step every
  drone is inside the box.
- **S6 5.2 runs** (after the budget stop rule of §8 is cleared and after the owner's interface answer, §12), **S7 5.2 evaluation**, **S8 5.3 run**, **S9** the
  tier 2 fine-tune path, built only if 5.3's trigger fires.
- **D1 docs**: `docs/NUS_PHASE5_RESULTS.md` with figures from `scripts/make_nus_phase5_figures.py` (numbered captions),
  NUS_PORT §12, HANDOFF §0/§4/§5, PLUG_IN, TRAINING; the private port plan and `_notes/` outside git. Before merge: the laptop
  privacy scans and every diff and commit message read by eye.

## 10. Risks, unknowns and stop points

| Risk | Check that exposes it | Stop |
|---|---|---|
| The hangar game is too slow to train on with the filter busy from tick 0 (F8) | P0 (game count scaling) and the 5.1b/5.1c verdicts | §8 pre-set stop before 5.2 |
| A correct copy fails the 5.1 rule by seed chance | C0 positive control | C0 FAIL → new gate version and a fresh control before 5.1 is scored; C0 INCONCLUSIVE → seeds 401, 501, 601, six-lineage Welch verdict, final |
| The 5.1 rule cannot catch a learner that learned nothing | N0 negative control | N0 not FAIL → stop before 5.1 is scored |
| NUS's reference lineages share initial weights (F16), so their spread is understated and the 5.1-d interval is narrower than it should be | stated in the record | — |
| The 5.1 rule is too weak to catch a subtle mismatch (wide intervals with 3 seeds) | stated in the record; M3's one-update parity and M2's environment parity carry the fine-grained evidence | — |
| The PyTorch copy is far slower than JAX | 5.1 timing probe | above the 36 GPU-h cap: stop, CUDA graphs first |
| bfloat16 differences between JAX and PyTorch | M3 tolerance; outcomes compared, not bits | — |
| Self-play cycles ("last mover wins") and the gated generation-7 Guard is the loser of a cycle | 5.2 cross-play table (INFO); 2-of-3 seed rule | 5.2 FAIL → owner |
| The Guard learns to sit inside the Strike drones' filter keep-out (the parked behaviour) rather than a strategy; collapse of filter intervention or of movement | filter share and Guard 0 drift per checkpoint; videos | — |
| The exploratory drone model is slower than the real drone, so 5.2 learns against a laggier drone | T5 = FAIL is restated in every record; NEAR-962 | — |
| Over/under passing in 3-D (T13) is learned on tier 1 only through the 1 mm jitter | 5.3 X-2 gap | 5.3 fine-tune trigger |
| Interface change v0.2 | owner question 1 (§12) | no 5.2 run before the answer |
| GPU memory: from 16,384 games up the peak **reserved** memory is 23–31 GB against 0.7–2.1 GB allocated (F17); three separate 16,384-game processes could exhaust the 32 GB card or starve another job | side-by-side seeds run as one process holding all three seeds' games; separate processes only with `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` and `torch.cuda.set_per_process_memory_fraction`, tested first; no other GPU job alongside; every record states peak allocated and reserved memory | a failed memory test → seeds one after another (the stop rule of §8 then fires) |
| The tick cost is the filter's (F17: 94–99 % of the tick, 1,000 sweeps every tick, about 82,000 kernel launches, the GPU busy about 19 %) | INFO: a training-time filter speed-up (CUDA-graph capture of the 8-sweep blocks with a fixed-shape re-gather, or fewer sweeps) could cut the tick cost several-fold. It would be its own gated task, checked against T8's accuracy table; no budget here assumes it | — |
| Short NUS numbers slipping into git | G2/G4 scans, privacy tests, eyes on every diff | — |

Stop points (each ends with a record read by the lead, and the owner where marked): after R0, C0 and N0 (owner reads
C0 and N0);
after 5.1 (owner; a FAIL stops Phase 5 route b); after P0 and 5.1b/c (the 5.2 budget rule); after 5.2 (owner);
after 5.3. Any FAIL is recorded as FAIL; an aborted run writes an ABORTED record.

## 11. Records and ledger rows (STANDARDS §8)

Ledger rows written on the 5090 take the **next free W number at run time** (the other worktree may append rows first);
the lead renumbers them to T numbers at merge. Each record names its simulator on its first line and gives the §8
fields: purpose, commit, configs and the sha256 of every local file, seeds, machine, games at once, game-steps/s with
games, drones per game, tier and GPU, gates with PASS or FAIL, videos.

| Run | Record | Ledger result |
|---|---|---|
| R0 reference rebuild | `records/<date>_nus_phase5_r0_reference_record.md` | PASS/FAIL (Phase 3 gate (a) per entry) |
| C0 positive control | `…_nus_phase5_c0_positive_control_record.md` | PASS/FAIL/INCONCLUSIVE |
| N0 negative control | `…_nus_phase5_n0_negative_control_record.md` | PASS (the rule FAILED the untrained arm) / FAIL |
| 5.1 method match | `…_nus_phase5_s51_method_match_record.md` (and `…_s51_followup_record.md` after an INCONCLUSIVE) | PASS/FAIL/INCONCLUSIVE; the follow-up PASS/FAIL |
| 5.1b, 5.1c | `…_nus_phase5_s51b_record.md`, `…_s51c_record.md` | PASS/FAIL/INCONCLUSIVE under the 5.1 rule (decides 5.2's batch only) |
| P0–P3 | `…_nus_phase5_pilot_p<k>_record.md`, headed "pilot, not of record" | INFO |
| 5.2 tier 1 training | `…_nus_phase5_s52_tier1_record.md` (training and evaluation) | PASS/FAIL |
| 5.3 Isaac Lab cross-check | `…_nus_phase5_s53_isaac_record.md` | PASS/FAIL |
| 5.3 fine-tune (if any) | `…_nus_phase5_s53_finetune_record.md` | PASS/FAIL |

Each stage writes `runs/nus_port/phase5/<stage>/gates.toml` before it starts: a verbatim copy of its
`[gates.phase5_*]` table, the sha256 of `configs/nus_port.toml`, and the sha256 of every reference file it reads.

## 12. Decisions

1. **Interface for 5.2: v0.2 (owner approved, 18 Nov 2026 ~18:20).** v0.1 already carries the drone's height and 3-D
   relative positions (F12); v0.2 appends the height band, floor and ceiling in m, at indices 71–72, so the policy knows
   the vertical limits as it knows the walls. Pilots use v0.1. `[gates.phase5_tier1_training].observation` is set.
2. **5.2 passes on 2 of 3 seeds** (decided by the lead): self-play is volatile (F4), and the record words the claim by
   the count.
3. **C0 runs** (decided by the lead; about 3 h of the 5090 with NUS's code): without it a 5.1 FAIL cannot be told
   apart from a rule that is too strict.
4. **NUS message** (D-P5-6): the draft is in `~/ma_skills-self-play/_notes/nus_message_phase5_draft.md` (private, 5090
   only); the owner approved it 18 Nov ~18:20 and sends it.

## 13. Not in Phase 5

APEX and specialists; other geometries, team sizes, drop-out; the contact-tag track; the AirStack simulator, any flight,
a ROS 2 node, an `interface.toml` for export (S5), any change to CMU's filter or an AirStack config (the flight-side
altitude lock of D-P5-2 stays the owner's and CMU's question). Nothing here authorises a flight.

## Change log

**v2 (18 November 2026), after the `train-gatekeeper` read of v1 (PASS WITH FIXES).** Required fixes, by number:

1. 5.1 verdict order written down: FAIL (a, b, c when gated, or a 5.1-d interval excluding 0), then INCONCLUSIVE (spread),
   then PASS; INCONCLUSIVE only replaces a PASS (§4.3, `pass_rule`).
2. `d_spread_ratio_max = 4.36` (√19, one-sided 5 % point of F(2, 2)), with the reason (2.0 flagged about 0.36 across two
   statistics); the follow-up after an INCONCLUSIVE fixed: seeds 4001, 5001, 6001, six seeds scored once with a Welch
   interval, then FAIL, not INCONCLUSIVE; final.
3. C0 INCONCLUSIVE: re-scored once unchanged, then Phase 5 route b stops for the owner; any rule rewrite after C0 needs a
   fresh control with new seeds.
4. C0 seeds 101, 201, 301 and our seeds 1001, 2001, 3001 (F16: stage seeds and shared initial weights); P5-12.
5. 5.1-d defined exactly: n − 1 standard deviations, the 0.02 floor per arm before pooling and before the ratio, t quantile
   2.776, our seed value = mean over the three leave-one-out panels, the same handling of failed conversions for all
   arms.
6. The R0, C0 (and N0) and 5.1 tables are frozen together before R0; R0 may only turn 5.1-c into INFO through `loo_check`.
7. §1 no longer says "faithful": 5.1 is a pre-registered broken-learner screen, not an equivalence test.
8. Fence breach defined (keep-in box of row 5, any tick, per game), added to Task S5 with a test; F-1 reads it.
9. C-1 compares with `row_5/per_game.npz` key `ParkedGuard__S20__outcome`, game by game.
10. Full sha256 of `starts.npz`, `row_5`/`row_6` `scores.json` and `per_game.npz` pinned (F15 and the gate tables).
11. G-3/G-4 references named: G19, P3G and ParkedGuard, the only row 5 Guards scored against those Strikes.
12. Interface: v0.1, or v0.2 if the owner approves; no 5.2 run before the answer; pilots v0.1 (§5, §9 S6, §10, toml
    `observation = "OPEN: …"`).
13. §12 rewritten as decisions (Q2, Q3 decided by the lead, Q4 the owner sends) and one open owner question (Q1); task 0
    points at §12.
14. Header: T18–T20 and T22–T24 INFO, T21 ABORTED.
15. F8: 280,932 game-steps/s without the filter (row 3, T20).
16. Cost labels: 0.32 s per tick MEASURED (T22 mean, 1,000 games); time-out pairs 769–790 s; first ticks about 0.39 s;
    the budget uses 0.39 until P0 reports; 1,300 h / 10.8 h / 3.9 h marked ESTIMATES; P5-7 and §8 agree; pilot steps
    recomputed at 0.39.
17. Three seeds side by side only if P0's seconds per tick at 49,152 games is at most 1.5 × the 16,384-game value; P0
    adds 49,152 games.
18. Pilot caps enforced: hard wall-clock limit per pilot, evaluations included; no `--accept-long`; one GPU-hour log;
    no start below one evaluation's time. P3's signal uses the Wilson lower bound of reach.
19. 5.2's gated pairings run first inside the 6 GPU-h cap; the INFO within-lineage cross-play table has its own 10 GPU-h
    cap and is dropped (stated) if not granted.
20. 5.3: a control outside the interval stops before any verdict; after a fine-tune, X-2's tier 1 reference is the
    fine-tuned checkpoint re-scored on tier 1; one fine-tune attempt only.
21. Videos: one game per selection evaluation in 5.1/5.1b/5.1c; C0 two games per archived entry; the 5.3 fine-tune at
    each scheduled evaluation plus final and best.
22. INCONCLUSIVE counts as not PASS for the variants; 5.1b and 5.1c run only after 5.1 PASSES.

Optional fixes taken: a negative control N0 with its own gate table (P5-4, §4.3); the reference lineages' shared initial
weights noted (F16, §10); the claim strength of G-3/G-4/P2 worded (§5, §7); P5-3 noted as replacing D-P5-1's wording;
pilots called "not gated, INFO records"; 5.2's training-curve rates from the same metrics module as the evaluation.

**v3 (18 November 2026), after the `train-gatekeeper` read of v2 (PASS WITH FIXES).** Fixes, by number:

1. N0 made precise: it must fail with both 5.1-d intervals excluding 0; 5.1-a does not apply; 5.1-b scores each entry
   against the pool the selection rule would have built from earlier N0 entries plus APF; the record gives every
   statistic's verdict. §4.3 now says what N0 shows and what it does not; expected margins noted as a pipeline check.
2. C0 INCONCLUSIVE: "re-scored once" removed (scoring is deterministic); follow-up fixed now with NUS seeds 401, 501, 601
   (stage seeds checked: no collision), six lineages scored once with a Welch interval, then FAIL, final.
3. F-1 is met by construction (the game clamps every drone into the box each step, `nus/hangar_game.py:59-61`,
   `core/physics_layer.py:135`); the INFO clamp share (pre-clamp position outside by more than 0.01 m) and its test stay in
   Task S5; the real-flight fence is separate.
4. P0's measured rates entered (F17); pilots train at 32,768 games (ParkedGuard v S20 arm; the random arm INFO); the 0.39
   budget figure replaced by 0.4274 (16,384) and 0.4327 (32,768); 5.1b, 5.1c, 5.2 and pilot estimates recomputed (the
   table in §8); P5-7's sentence uses the measured numbers; a marked placeholder for the 49,152 point, with the rule that
   seeds run one after another if it is not measured and that one 49,152 process only approximates three of 16,384; P0's
   provenance (commit `e595bfd3` plus the then-untracked probe script, v1 pilot table) and its GPU-hour log entry.
5. INFO risk: a training-time filter speed-up could cut the tick cost several-fold; its own gated task, checked against
   T8; assumed in no budget.

**v3.1 (18 November 2026), P0 finished.** The 49,152-game point is in F17 and §8 (0.3609 s per tick, 0.84 × the 16,384
value, so the side-by-side rule passes; s per tick read as flat at 0.36–0.43 above 4,096 games, not a speed-up); P0 used
0.368 GPU-h. The §8 placeholder is filled: 5.1c with the seeds side by side ≈ 34.6 h (41.5 h at 0.4327), 5.1b ≈ 96.2 h.
New risk and mitigation: peak reserved GPU memory 23–31 GB from 16,384 games up (the filter's re-gather and the caching
allocator); "side by side" now means one process holding the three seeds' games, or separate processes only with
expandable segments and a per-process memory fraction, tested first, and no other GPU job alongside (§8, §10).
