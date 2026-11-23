INTERNAL · spec of task L1.8 (the 1.6 m-trained players re-scored on the new tier-2 drone), written before the run and kept as written · [../README.md](../README.md); the task's place in the plan: [costed plan draft](L1_L9_COSTED_PLAN_DRAFT.md), row L1.8

Written by the lead 23 Nov 2026 ~04:20, before the L1.8 run (main track; costed draft row L1.8).

# L1.8: T46's 1.6 m-trained players re-scored on the new tier-2 drone (INFO)

**Question.** Do the strategies trained at tag 1.6 m in tier 1 (T46: Guard holds 913 v strike_straight, Strike reaches
636 v guard_mark_edge) keep their results on the tier-2 Isaac Lab drone, without and with the estimate error fitted in
L1.3 (T63, EXPLORATORY)?

**Conditions** (tier 2, base game, T44's 1,000 starts, every cell against every script of the other team; one start
set): (1) error off; (2) nominal error (position 0.0099 m / 1.2 s, velocity 0.022 m/s / 1.3 s, attitude 0.0027 rad /
2.0 s); (3) conservative (2× sigma, same taus); (4) tier-1 reference from T46/T44 files (no new run). (2) and (3) share
seeds and error draws (paired).

**Reading words, fixed now (no category, no "validated"):**
- (1) v (4): "on the tier-2 drone with no estimate error the 1.6 m Guard team holds N (tier 1: 913)" — a difference
  between two simulators, not an effect of the error.
- (2) and (3) v (1): if a player's cell interval (Wilson 95 %) does not overlap the error-off interval, "the fitted
  estimate error changes the result: N against M"; otherwise "the result holds with the estimate error (nominal /
  conservative)". Paired counts reported, labelled not pre-registered. Worst cell first.
- Limits: one network per side, one start set, EXPLORATORY error values from one hover log, tier 2 is not the AirStack
  simulator, nothing flown.

**Controls (any not PASS: no numbers):** the tier-1 replay of the layout equals T46/T44 game for game; two same-seed
copies in "off" are identical; the C-1a agreement control as the driver defines it.

**Budget:** task L1.8, cap 0.9 for the run (task cap 1.2); expected about 0.6 GPU-h; laptop RTX 5070 Ti, alone on the GPU.
