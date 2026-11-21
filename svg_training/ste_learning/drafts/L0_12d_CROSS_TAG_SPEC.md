INTERNAL · spec written by the lead 22 Nov 2026 ~04:55, before any scoring (owner: "ok if u think 1 is worth it then go").

# L0.12d Cross-tag check: the 1.6 m-trained players in the 1.15 m game (INFO)

**Question.** How well do strategies trained at tag 1.6 m (record T46, base variant) play when the tag is 1.15 m (the
safety filter's 1.10 m keep-out + 0.05 m)? Feeds G0 row 1 (tag distance): a 1.6 m strategy flown in a 1.15 m game.

**What is scored (scoring only, no training), tier 1, laptop RTX 5070 Ti, T44's 1,000 scoring starts** (the L0.12b
reference `configs/ste_l012b/screen_reference.npz`, sha256 pinned in `configs/ste_l012b/gates.toml`):

| Cell | Game | Guard team | Strike team | Compared with |
|---|---|---|---|---|
| X1 | tag_1p15 (`configs/ste_l011/tag_1p15.toml`) | T46 base trained Guard (`…l012_base_guard/agent_final.pt`) | strike_straight (s* at 1.15 m) | T54 trained-at-1.15 Guard 572; script guard_field 645 |
| X2 | tag_1p15 | guard_field (g* at 1.15 m) | T46 base trained Strike (`…l012_base_strike/agent_final.pt`) | T55 trained-at-1.15 Strike 134; script strike_straight 355 |
| X3 (INFO) | tag_1p15 | guard_mark_edge (the base g*, the opponent it trained against) | T46 base trained Strike | — |
| X4 (INFO, added 22 Nov ~05:45 before any scoring, from the results-and-plan panel and QC 2) | base (tag 1.6 m) | guard_field | T46 base trained Strike | separates opponent from tag: with C2 (mark_edge, 1.6 m), X2 (field, 1.15 m) and X3 (mark_edge, 1.15 m) it completes tag × opponent; the T46 Strike never trained against guard_field; T44 script cell guard_field v strike_straight at 1.6 m = 716 holds / 284 reaches |
| C1 control | base (`configs/ste_l011/base.toml`) | T46 base trained Guard | strike_straight | must equal T46's own evaluation game for game (913) |
| C2 control | base | guard_mark_edge | T46 base trained Strike | must equal T46's own evaluation game for game (636) |
| C3 control | tag_1p15 | guard_field | strike_straight | must equal the screen reference cell (645 / 355) game for game |
| C4 control | base | guard_field | strike_straight (and any other script cells in X4's batch) | must equal T44's reference cells game for game (716 / 284) |

Run folders of T46 (read-only, not in git): `/home/jeremychia/AirStack-starling-max2-l12/svg_training/runs/2026-11-21_ste_l012_base_{guard,strike}/`
(agent_final.pt, gates.toml, run.json, eval_final.npz). Decision hold = the gate's `decision_ticks` (12 = 0.6 s), as trained.
Controls use the same exactness rules as `scripts/ste_vid1_capture.py` (exact keys equal; closest approach within the
L0.11 `same_seed_closest_tol_m` on CUDA). **Any control not PASS: no number of X1–X3 is reported (exit non-zero).**

**Reported (INFO, no pass/fail gate):** for X1–X3: wins of 1,000 with Wilson 95 % intervals, Guards left in holds, game
length median, unchosen-tag shares (pushed together, filter active), and for X1/X2 paired counts against the 1.15 m
script cell on the same starts. Reading words fixed now: "1.6 m strategy at 1.15 m: N of 1,000 (interval) against the
1.15 m-trained team's M and the script's S"; no category, no "validated"; one seed per side, one opponent, one start set;
observed in the training simulator.

**Budget.** Charged to task L0.12 (cap 13, used 9.674): launch with `scripts/ste_job.py launch --task L0.12 --gpu-h 0.2`.
Expected well under 0.1 GPU-h. Alone on the GPU.

**Clips** use the clip seed's own starts on the CPU (as L0.12), not the 1,000 scoring starts; the record says so.

**Outputs.** `runs/<date>_ste_l012d_cross_tag/`: results.json, results.md, per-game npz, 2-D clips (one win and one loss
of X1 and of X2, with the height panel, as the L0.12 driver draws them), the record `records/<date>_ste_l012d_cross_tag_record.md`
(next T number: T56) and its ledger row.
