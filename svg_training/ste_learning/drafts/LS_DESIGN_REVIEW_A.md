INTERNAL · the report of design reviewer A (learning soundness and gates) on the route 3 execution workflow v3 and the learned-skills plan, 25 Nov 2026, as the reviewer wrote it (Sonnet 5.5, read-only, given the files and not the lead's conclusions); the lead checked its file references against the code and folded the findings into the workflow, whose section 9 is the summary · [LS_EXECUTION_WORKFLOW.md](LS_EXECUTION_WORKFLOW.md)

# Route 3 design review, reviewer A: learning soundness and gates (25 Nov 2026)

A builder reads this file for the detail behind each finding (file and line, the exact change). Figures the reviewer marks as its own estimates are estimates. The workflow reviewed was the first v3 (commit `28184629`); the workflow has since been revised for these findings.

DESIGN REVIEW A (learning soundness and gates). Read-only. Nothing edited, no git command run, no GPU used.

READ IN FULL: scripted.py (all 485 lines); LS_EXECUTION_WORKFLOW.md v3; BRIDGE_PLAN sections 0-4, 5, 6 (Tasks 1-7) and 7-8; skills_gates.toml; pool.py 60-140; core/observations.py 1-110; scoring.pooled_row; the pipeline record (tables, L3.5 run 0, L5, L6.1, "What this does not show").
READ IN PART: skills.py 1-200, LEARNED_SKILLS_ROUTE.md 1-60, L3_TWO_ROUTES_DESIGN.md 1-95, PLAN.md section 1.

Paths below are relative to ~/AirStack-starling-max2-dev/svg_training. "sc" is source/svg_training/opponents/scripted.py.

Verdict: no BLOCKER. Four MAJOR findings (F1 to F4) change the data design, the gate statistic, the LS1.4 reading rule or its measuring cell. Fix them before the gate file is hashed.

## FINDINGS, MOST SERIOUS FIRST

### F1. MAJOR. The distillation data does not cover the states the gate cells play, and the allowed fix round does not address that.
- **Document:** plan section 3 "Data" and workflow section 5 "Stop rules". The data comes from a random two-level choice redrawn every 12 ticks, with the team head uniform over {free, strategy 1, strategy 2}. DAgger rounds (script-flown share 1, 0.5, 0.25, 0) keep the same choice schedule. The one fix round allowed after NOT DISTILLED is "more relabelling rounds or a larger network".
- **Code and numbers:**
  - The four team-reading scripts (guard_parked_ring, guard_field, strike_sacrifice, strike_converge) run only as team strategies, with every drone on the same code. This is the split in `configs/ste_l3/skills_gates.toml` [learner.team_strategies] and [learner.drone_skills]. The gate's fixed-choice cells hold one such code for the whole game.
  - Under a redraw every 12 ticks, a pure-converge path that is h holds deep has probability 3^-(h-1) (the team head has 3 options). Tag games last 36-78 ticks (`ste/exploit_train.py:10`), which is 3 to 6 holds. Deep-path states are therefore about 1 to 10 % of the rows, and uniform subsampling to `keep_rows` keeps that share.
  - Converge's `go` trigger (sc:459) is a conjunction of three angular tolerances of 0.1 rad (GATHER_ANGLE_RAD, sc:251). It fires only in the gathered-on-the-stand-off-circle states, which are the states least covered.
  - DAgger does not fix this. The network's own states are drawn under the same random code schedule, so they are no nearer the pure-strategy manifold.
- **Change:**
  - Data mix per round: at least half the games with the team code held for the whole game, over each of the K codes (the gate's fixed cells), plus per-drone fixed mixes, plus the random redraw schedule.
  - Hard-example sampling instead of uniform subsampling: keep rows in proportion to network error, with a floor for rows near the switches (sacrifice 30-degree entry, converge `go`, ring station swap).
  - Add engineered inputs: polar own position (radius, sin/cos bearing) and each mate's bearing and radius relative to the zone. Converge and ring compute atan2 of mate positions (sc:334, 446-448), and a 3x256 MLP on raw xy has to rebuild those to within about 0.1 rad.
  - Change the stop rule so the one fix round may change the data mix, not only the rounds and size.
  - Report the command error stratified by code held for k holds, and by n_live (1, 2 or 3 live drones).

### F2. MAJOR. The noise-floor rationale (workflow v2 correction 4 and job LS1.5) uses the wrong null for a paired read, and white noise is a poor stand-in for a network's error.
- **Document:** workflow section 8 row 4 ("two independent samples differ by about 22 wins") and the LS1.5 design (bounded random error on commands, sizes 0.01 to 0.1). Plan section 4 limits: per cell within 30 wins, pooled row within 15, RMSE 0.05.
- **What is wrong:**
  - The 22-win figure is the sd of two unpaired samples at p = 0.5, sqrt(2 n p (1-p)). The equivalence read plays the copy and the scripts on the same 1,000 starts, and the scoring is deterministic (`ste/exploit.py:57`, `EXACT`). The null of a paired read is sd(b - c) ≈ sqrt(b + c), where b and c are the games lost and won by the copy relative to the scripts.
  - The measured data say flips from float-level perturbation are few. The L3.1 smoke replays identical policies and shows 0 of 1,000 games differing in 11 of 17 cells and 2 to 5 in the mixed cells (pipeline record, L3.1 table). The "30 of 1,000" limit is therefore a size-of-effect margin, not a noise allowance. It is about 6 sd if the flips are around 20.
  - Per-tick white noise averages out through the drone's velocity response: about 0.05 × 0.5 m/s × sqrt(0.05 s × 4 s) ≈ 0.01 m of displacement. That is an order-of-magnitude estimate of mine, not a measurement.
  - A network's error is systematic: a speed shortfall, a shifted switch angle, a blurred `go`. It is concentrated on a few states, so its RMSE is small while individual games flip.
  - The gate reads only the net difference b - c. Two-sided errors cancel in b - c. Cell win rates near 0 or 1 (for example the 0.079 to 0.176 Strike cells) hide big behaviour change under "within 30".
- **Change (complementary reads, all computable from the same runs):**
  1. Per cell report b, c and the flip count b + c. Gate the flip count too, with a limit set from the dose-response, plus an exact McNemar or sign test on b versus c.
  2. Replace "|diff| ≤ 30" by an equivalence test: the upper 95 % limit of |b - c|/n below the margin, Holm-adjusted over the cells (or a max-|z| check against its null for 150 correlated cells). The owner sets the margin as an effect size (for example 0.03), not as a noise guess.
  3. Add paired continuous outcomes per game: reach or tag time (`end_step` is stored in `PER_GAME`, `exploit.py:46-48`), and the final distance to the zone. These have far more power than win/lose for the same 1,000 games.
  4. Add a closed-loop divergence read: the distance between the network-flown and script-flown trajectories from the same start at 1, 3 and 10 s.
  5. Make the noise-floor job an end-to-end calibration, not a floor: scripts with white noise (specified: i.i.d. per tick, per channel, uniform, seeded) and scripts with systematic perturbations. The systematic set: xy scaled by 0.95, a rotation of 3 degrees, sacrifice ENTRY_HALF_ANGLE 30 to 40, converge GATHER_ANGLE 0.1 to 0.2. Read where the gate starts to fail each.
- **Pooled row:** `scoring.pooled_row` (`ste/scoring.py:316-341`) is the mean of the K cell rates on shared starts. "Within 15 wins" therefore means 0.015 in that mean, which is a sensible scale. The documents should say so.

### F3. MAJOR. The LS1.4 reading rule (workflow section 5) is not defensible with two seeds. The Strike comparison cell has no learning signal.
- **Rule as written:** route 3 is "level with route 2" when both its seeds lie inside or above the spread of route 2's two seeds, widened by the 95 % interval of one read, per cell and on the pooled row.
- **Problems, from the record:**
  1. The 95 % interval of one read (about ±0.03 at 644/1000) is the uncertainty over the 1,000 starts. Both arms are scored on the same starts (`skills_gates.toml` [reference], T44's starts), so that term cancels in a paired difference. It is the wrong ruler. The relevant noise is training-run noise.
  2. A spread from two seeds has 1 degree of freedom. The 95 % interval for sigma is about [0.45 s, 32 s]. If route 2's two seeds land at 640 and 644, the rule demands a route 3 inside ±34 of them in 11 or more cells, for both seeds.
  3. A single final read can land on a dip. Run 0's nine reads are 665, 669, 667, 633, 461, 620, 639, 639, 644 (record "L3.4 and L3.5"). Excluding the 461, their sd is about 18; with it, about 64. The rule scores the final checkpoint only.
  4. I did not compute a false-alarm rate for the rule. It requires both seeds in about 11 cells, so a no-difference copy is likely to be called "not level". Assume a per-seed sd of 18 to 25 games per cell; that figure is my assumption.
  5. **The Strike comparison cell carries no signal.** Route 2 Strike v guard_mark_edge is 176/1000, below the untrained team's 192 and the best script's 192. The driver word is INCONCLUSIVE (record, L5 table). The Guard cell is 813 against a best script of 808, "weak". Being "level with" a non-learning result proves nothing for Strike.
  6. Heads choose almost one code per side (Strike 0.43-0.49 flank and 0.51-0.54 low; Guard mark_edge except against converge, record "Choice shares"). LS1.4 therefore exercises about 3 of the 11 codes and cannot show that the other codes copied well. LS1.2 is the only validation of those.
- **Concrete rule (non-inferiority, not "level"; pre-register in `heads_gates.toml`):**
  - Per-seed score is the mean of the last three checkpoint reads (updates 70, 80, 88), plus the minimum reported.
  - Fix a margin Δ before running. I suggest Δ = 0.04 on the pooled row (about 2 sd of the checkpoint spread excluding the dip; below the 0.068 velocity-minus-skills Guard difference the record calls "above") and Δ = 0.08 per cell.
  - Compare paired on the same starts. PASS ("no evidence of a drop beyond Δ") when mean(route 3 seeds) ≥ mean(route 2 seeds) − Δ AND each route 3 seed ≥ min(route 2 seeds) − Δ.
  - "Below" when the mean is below route 2's by more than 2Δ. Anything between is INCONCLUSIVE, with a third seed per arm announced (0.4 GPU-h each).
  - Never claim "level" from two seeds.
- **Cells to use:** on Strike, make LS1.4-0 (run 0 against the parked Guard, 644 versus untrained 466, which does learn) the primary Strike read. Add per-code choice-share comparison to route 2 as an INFO line.
- **Recipe lock:** LS1.4-P re-runs the pilot's "Strike recipe by the rule". It must not change the recipe of the route 3 arm. Pin the route 2 recipe (`skills_gates.toml` side_overrides) so the arms differ only in `skill_source`.

### F4. MAJOR. The three LS1 controls cannot show that the gate can see a near miss. The positive control skips the new code path.
- **Document:** plan section 4 controls, Task 5 tests.
- **Gaps:**
  - The positive control ("the script-backed dispatch, through the same scoring path, differs in 0 games from T44") exercises only existing code. It never touches the new `NetTwoLevelDispatch` code (slot and code encoding, per-row gather, the alive mask, ordering).
  - The negative controls, an unfitted net and a code-permuted net, are gross misses. They show the gate can fail, not that it fails on a copy that is 5 to 10 % off.
  - The permuted-code control is judged by max |diff| in plan Task 5 (`test_unfitted_and_permuted_networks_miss_the_limit`). That is acceptable, but the derangement must be checked first with the scripts themselves (scripts permuted) so the test is not vacuous.
- **Add:**
  1. An oracle-net positive control: a `SkillNet`-interface object whose forward returns the script commands through the same slot, z and gather path, with 0 differing games.
  2. Graded negative controls: scripts with a 0.05 systematic bias (and a 3-degree rotation) and a shifted switch must FAIL. Scripts with white noise 0.02 must PASS. This gives specificity and sensitivity at the margin the owner sets in R38.
  3. For the permuted control, require "at least N cells miss", with N fixed by running the permuted scripts first.

### F5. MAJOR for Q1/Q2 details. The first-order claim of Q1 is TRUE, but the plan misses four things the network cannot reproduce.
- **True:** every one of the 11 skills is stateless and a function of the drone's own row, its tensor index and the team width. No script reads another drone's row. The only random draw is `RandomActions` (sc:78-82), not a skill. Evidence per script:
  - Own row only: GuardParkedCentre sc:297-299; GuardMarkEdge/GuardMirror via `_marked` sc:89-102; GuardField sc:128-145; GuardParkedRing sc:322-347; StrikeStraight sc:171-172; StrikeFlank sc:183-202; StrikeHigh/Low sc:362-369; StrikeSacrifice sc:390-418; StrikeConverge sc:436-475.
  - Team-mates are rebuilt from the drone's own slots by `_team_slots` (sc:255-264); `reset` is a no-op (sc:58-59).
  - Slot/tensor-index reads: `rank = arange(g) % n_live` (sc:97); `own` diagonal and `idx` (sc:326-327, 331); `is_decoy = arange == 0` (sc:415); converge `idx`, `own`, `ref` (sc:442-443, 456).
  - Team width via `obs.shape[1]`: sc:298 (parked centre is exactly zero in 3v3), sc:323 and 329 (ring), sc:258 (`_team_slots`).
- **Is the slot inferable from the own observation?** Only when the whole team is alive. The own slot is the one team slot with present = 0 (`present` excludes the diagonal, `core/observations.py:74`), and slots 3 and 4 of the Guard pad are always 0. After a loss it is ambiguous. Example, Strike pad slots 5-7: drone 1 with drone 2 dead and drone 2 with drone 1 dead both see slot 5 present and slots 6 and 7 absent. Whether this matters depends on the script: for the scripts that read their index, yes. So the slot one-hot IS needed.
- **Missed dependencies (the network cannot see these):**
  - Game config constants the scripts read: `keepout_strike_m` (sc:190), `keepout_guard_m` (sc:319), `wall_margin_m` (sc:277), the Guard team speed (sc:158), `height_band_m` and the `starling.enabled` flag (sc:359-360). The pin covers only the sha256 of scripted.py. A different game file silently invalidates the copy. Put the game-file sha256 and the rules in the skill network's meta and refuse a mismatch.
  - Inputs no script reads: yaw sin/cos (indices 6-7), time_left (10) and the team flag (11). Zero them at the input, otherwise the network can latch onto them (time_left varies a lot).
  - Pad slots that are constant zero in 3v3 have std 0, so `in_std` must be clamped. The plan's normaliser test only covers the identity default.
  - Exact-zero label: guard_parked_centre's command is exactly 0 in all 3v3 states (sc:298), with no position feedback. Any bias in the network integrates, and an RMSE ≤ 0.05 permits a bias of 0.05. Put a per-skill max-abs tolerance on the zero-label skill (for example max |output| ≤ 0.005), or hard-gate it.
  - Averaging RMSE over all 4 channels dilutes xy errors, because channels 2 and 3 are exactly 0 for 9 of 11 skills (`_pack`, sc:32-35). Define the limit per channel on the active channels, and report max |output| on the always-zero channels (vz and yaw rate for the xy-only skills).

### F6. MINOR/MAJOR (Q2). Discontinuities and saturation.
- **Switches and why MSE blurs them:** MSE fits the conditional mean, so a network is blended across a switch. Switch points: sacrifice `go_in` at 30 degrees (sc:412, `straight` versus tangential `_circle` and `direction` flip at sc:411); converge `go` and `committed` (sc:458-459) and the circle-versus-steer test at 0.5 rad (sc:471); ring `n_live >= g` (sc:345) and the argsort rank with its 2π wrap (sc:334-336), where a swap moves the target station by 120 degrees; mark `found` (sc:112) and the nearest-strike `argmin` flip (sc:134). These are narrow bands and a blend there probably does little harm. The risky ones are the global triggers (converge `go`) because the whole team starts the run-in on them.
- **Saturation:** the scripts' outputs are already inside the [-1, 1] box, so there is no range problem. `steer` and the normalised mixes have norm ≤ 1 (sc:26-29, 144, 160, 288). However strike_high/low clamp vz to exactly ±1 during the climb (sc:366), with xy scaled by `sqrt(1 - vz²)` (sc:367), which has an infinite slope at |vz| = 1. A tanh output cannot reach ±1, so expect systematic error there; use a clipped linear output or a head with an `1.05 * tanh` then clamp. Expect these two to be the worst RMSE skills, and tier 1's vertical response is not fitted anyway (`skills_gates.toml` [players] `z_up_info`).
- **Dead/absent drones:** rows with own alive = 0 are dropped, and the dispatch multiplies by alive, as `_pack` does (sc:32-35). That is correct. But the scripts carry explicit loss branches (ring `nearest`, sc:339-345; converge `n_live >= 2`, sc:474; sacrifice `others_live`, sc:393-394, 417) that appear only after a tag, and tag games are short. Oversample rows with at least one mate absent (target 20 % or more), report error by n_live, and add a gate cell that starts a game with a drone removed. This also covers the track's drone-loss goal for the 3v3-only fit, since "drone loss" here is the absent flag inside the 3-wide tensor, not another team size.

### F7. MAJOR for the held-out set (Q5). The proposed set is partly contaminated and the scripts pinning breaks if scripts are added.
- **Registry and pools:** the registry (sc:205-214, 478-485) holds Guard: mark_edge, mark_inside, field, mirror, parked_centre, parked_ring; Strike: straight, flank, high, low, sacrifice, converge; plus `random` and `zero` (both teams). The pool is the gate file's `[players]` lists without `random` (`ste/pool.py:75-80`; `skills_gates.toml` [players]). Result:
  - `guard_mark_inside` is in no STE pool and no STE skill list. I grepped `configs`, `source` and `scripts`: it appears only in `configs/s2b.toml:64` and S2b video and replay scripts. The claim is true.
  - `zero` is also in neither pool, but it is trivial (and for the Guard in 3v3 it equals guard_parked_centre).
  - No Strike script in the registry is outside the pool. So the workflow's (c) "one Strike script taken out of the self-play pools" is not held out: route 3 Strike teams (saved pool entries) can still fly that script as a code, so the Guard would meet it anyway.
- **`guard_mark_inside` is a weak held-out:** it is `GuardMarkEdge` with FRACTION 0.6 instead of 1.0 (sc:105-122), the same rule as the dominant Guard code. It tests one parameter, not a different strategy. It is useful as a distribution-shift check on the Strike skill net (never seen in distillation data), so add it as an extra cell of the Strike equivalence read.
- **Route 1 teams (T77, T80):** I did not verify these identities. They were trained in the same game, pool and recipe, so they are unseen players, not unseen game conditions.
- **Change:** write 2 new held-out scripts per side before self-play is designed, outside scripted.py, and load them as `package.module:ClassName` (`make_strategy` supports it, sc:226-228). Editing scripted.py changes the pinned sha256 and every skill network is refused at load (plan Task 2, `test_stale_teacher_is_refused`). The same applies to any bug fix in scripted.py after LS1.

### F8. MAJOR as a decision (Q6, R41). Recommendation: self-play on the heads right after LS1.4 as a plumbing and baseline pilot only. The self-play stage proper waits for LS2.
- **For starting early:**
  - The new pool entry for saved teams is a new build (workflow section 2, about 3-5 days). It does not depend on LS2.
  - A saved pool entry is a frozen (heads + skill net) team, so it stays a valid opponent after LS2; only the heads trained against it need retraining.
  - It gives LS2 its baseline: what self-play can reach with fixed skills.
- **Against (what the data say):**
  - Heads-only teams are close to their best fixed script: Guard 813 versus a best script of 808; "+0.008 [+0.001, +0.014] against the best single choice" (record, L6.1 Guard table). Strike does not beat untrained (176 versus 192).
  - The choice shares are almost constant: Strike two codes, Guard one. The strategy space for self-play is nearly one point per side, so cycles are unlikely to show anything.
  - Self-play heads trained on the old skills have to be retrained when LS2 moves the skills.
- **What to measure to decide (before committing GPU-hours):**
  1. Choice-share entropy of the LS1.4 teams per opponent cell. If every cell is below about 1 bit, heads-only self-play has too small a space.
  2. Exploitability: a fresh heads-only exploiter against the frozen LS1.4 team. If its worst-cell gain over the best script is below the margin Δ of F3, self-play adds little before LS2.
  3. The gap to the best fixed mix of scripts (`scripts/ste_l3_run0_ceiling.py`), on the same starts.
  Start the real self-play stage before LS2 only if (1) is above about 1 bit in several cells AND (2) exceeds Δ. Otherwise run LS2 first.

### F9. MINOR to MAJOR (Q7).
1. **Same starts and same pool draws:** keep `[pool] seed = 140001`, the T44 starts and the training seeds identical between the arms. Say so in `heads_gates.toml`. Compare paired per start (the `pooled_row` machinery already holds shared starts).
2. **Reaction-speed advantage:** it carries over unchanged to LS1.4. The skills run closed loop every tick (`skills.py` docstring, hold rule; `L3_TWO_ROUTES_DESIGN.md:84-88`), and the network must run every tick too. What the plan does not check is that a network has no chatter the scripts lack. Add the mean absolute tick-to-tick command change to the fit report and compare to the scripts (matters for the L7 flight hand-over claim).
3. **Absent-drone mask (`mask_absent`):** unchanged for the heads. For the net, the alive mask in `all_codes` and in the per-row `act` path must be tested at the same level (plan Task 1 tests only `all_codes`; the single-code `act` in Task 2 has no dead-drone test).
4. **3v3-only versus the drone-loss goal:** see F6. The net must be tested on states with absent drones; this is cheap.
5. **Entropy:** LS1.4 reuses `entropy_scale` 0.01 per head and `init_log_std -1.6` (`skills_gates.toml` [trainer], [learner.entropy_scale]). That is right for comparing arms. For LS2 the skill net's per-tick Gaussian exploration (std about 0.2) is 4 times the RMSE gate; LS2's note needs the exploration noise and its decay set against the tie weight.
6. **Steps cost:** the net runs on N × M rows rather than a script gather; I estimate the overhead small but did not measure it. The LS1.0 smoke should report ticks per second for the net-backed dispatch against 2.31M game-steps/s of the two-level scripts (record, L3.1).

## THINGS CHECKED AND FOUND CORRECT
- The claim of statelessness and own-row dependence (Q1) holds for all 11 skills. I read every line of scripted.py, including `_marked`, `_team_slots`, `_circle`, `_stand_off_m`, `_pack`.
- Outputs are already within [-1, 1] and `_pack` zeroes dead drones, so the plan's "dead drone gives exact zero" matches the scripts.
- `guard_mark_inside` is in no STE pool (grep of configs, source, scripts) and `pool_members` drops only `random` (`ste/pool.py:75-80`).
- The pooled-row definition (mean of K cell rates on shared starts) makes "within 15 wins" a well-defined 0.015.
- The workflow's cell counts (150 Guard, 130 Strike) agree with `skills_gates.toml` [players] and the 20 mixed combinations.
- Run-0 read series and the record numbers cited in the workflow (813, 176, 644, 461/669) match the pipeline record.

## NOT CHECKED
- `ste/two_level.py` beyond its class list; `exploit_train.py` beyond line 10 and the docstring head; `exploit.play_cells` and the CPU replay speed (so the cost of the CPU equivalence read, and whether it fits, are unverified).
- The Strike pilot recipe rule and how LS1.4-P could change it.
- Whether T77 and T80 are the route 1 velocity teams named in the workflow section 5.
- Any test file, the export path, ONNX, the budget table, the GPU-hour estimates.
- Numerical claims marked as estimates (displacement from white noise, per-seed sd 18-25, flip counts) are my back-of-envelope figures, not measurements. I ran no Python.
- I did not run the scripts to test the switch behaviour; discontinuity statements are from reading the code.
