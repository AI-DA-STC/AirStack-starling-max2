Simulator: training simulator, tier 1 (fast engine; Starling layer: commander copy, safety filter on every pair, fitted PX4 response, exploratory); study tag on (P1); CPU (RTX 5090 workstation). Observed in the training simulator; not a flight result.

# 2026-11-24_ste_l19_screen record

## Purpose

STE task L1.9, step 1 (main track, INFO, no gate): the scripted one-against-one screen. The real flight plan is a 1v1
game on the two Starlings (gate G0 ruling R12), and this is the first look at the game in that format: every Guard
script against every Strike script, 1v1, at the 1.6 m tag and the 1.15 m tag. Spec
`ste_learning/drafts/L1_9_10_SPEC.md` (frozen 24 Nov 2026, commit `242953c5`). Owner ruling R20 (24 Nov 2026): L1.9 stops
after the screen; the 1v1 training waits for the owner's word.

## Commit and config

Commit `4010dededf13` on `development`. Gate file `configs/ste_l1/l19_screen_gates.toml`, sha256
`fd79fd861e9f32bddf6ad3ddb317286b20109213e09ee685da8642f82c9ecef1` (pinned at launch; copy in the evidence folder).
`scripts/ste_sweep_l011.py`, device CPU, seed 110000, 1,000 games per cell, 2,400 ticks (120 s); fitted PX4 response
with a 0.1482 s response delay (`params/real_exploratory_v0.toml`); effective time 164 s of the 1.5 h cap. Launched by
`scripts/ste_job.py launch --task L1.9 --gpu-h 0`; exit 0.

## Controls

All 11 hold (tag fires, reach fires, same seed twice, stand-still never reaches, zero tags with the tag off or tiny,
one-for-one tags, paired starts, no non-finite actions). Table in `results.md`.

## Result (INFO): hold rate of the Guard drone, of 1,000 games (Wilson 95 %)

| Guard script | v straight | v flank | v high* | v low* | 1.6 m: worst hold | 1.15 m: v straight | v flank | v high* | v low* |
|---|---|---|---|---|---|---|---|---|---|
| parked at centre | 68.3 % | 55.2 % | 0.0 % | 0.0 % | 0.0 % | 0.0 % | 0.0 % | 0.0 % | 0.0 % |
| parked on a ring | 42.5 % | 50.4 % | 39.0 % | 37.1 % | 37.1 % | 23.0 % | 47.2 % | 19.5 % | 15.8 % |
| mark the edge | 100.0 % | 100.0 % | 100.0 % | 100.0 % | **100.0 %** | 84.3 % | 89.6 % | 88.7 % | 89.2 % |
| mirror | 100.0 % | 100.0 % | 100.0 % | 100.0 % | 100.0 % | 84.1 % | 88.2 % | 88.7 % | 89.2 % |
| field | 100.0 % | 100.0 % | 100.0 % | 100.0 % | 100.0 % | 84.3 % | 89.6 % | 88.7 % | 89.2 % |

\* strike_high and strike_low: tier 1's vertical response is not fitted (`s2b.toml` z_up_info); read with care. Columns
1–4 are the 1.6 m game. With one Strike drone, the team scripts sacrifice and converge fly as straight (not played).

The screen's own reading (gate file [shortlist]): both 1v1 variants are "ruled out because Guard-trivial looking: a
scripted Guard holds against every scripted Strike". At 1.6 m the best Guard's worst hold is 1.00 and the best Strike's
worst reach 0.00; at 1.15 m 0.84 and 0.16 (157 games).

**Plain reading.** One against one, any Guard that moves (mark the edge, mirror, field) stops every scripted Strike at
the 1.6 m tag (worst cell 1,000 of 1,000, 99.6–100.0 %), and about 84–90 % of them at 1.15 m. The 1v1 game as set today
is lopsided towards the Guard. Likely cause (a hypothesis, not tested): a single Strike drone has no team-mate to draw
the Guard away, and the Guard needs only to come within the tag distance once.

**Cross-check with T44** (spec): T44's 1v1 cell (`size_1v1`, [record](2026-11-21_ste_l011_screen_record.md)) read best
Guard's worst hold 1.0 and best Strike's worst reach 0.0; this screen's base_1v1 reads the same summary. **Cell by cell
it is not checked:** T44's per-cell results are on the laptop only (its run folder is not on the 5090). One cell is
known both ways: the spec quoted T44's 1v1 parked-at-centre v straight as 307 reaches (from the laptop's data); this
screen shows 317. The intervals overlap, but a CPU replay of the same game and seed would match game for game, so the
two may differ in game file or starts, or the quoted 307 may be from another cell: unresolved. To do on the laptop:
compare every base_1v1 cell with T44's `size_1v1` cells before the L1.9 reference is made from this screen.

**Check 2b of the spec** (before any run 0): the base_1v1 cell parked-at-centre v straight shows 317 reaches of 1,000,
below the 950 limit, so run 0 could be launched. It was not: owner hold R20.

## What it means for the 1v1 training (for the owner, R20)

Training a 1v1 Guard at 1.6 m can only be a ceiling read (spec): the scripts already hold every game, so a gain over
them is impossible by construction. Training a 1v1 Strike at 1.6 m
would ask whether learning finds a way past a Guard that scripts never beat; that is a fair question but a narrow one.
The lead's recommendation: do not run L1.9's 1v1 training as specified; first decide whether the 1v1 flight game needs
different rules to be a contest (for example a smaller tag, a larger arena, a faster Strike, or a Strike start nearer the
zone), and screen those on the CPU, as this run did, before any GPU hour. That is a game-rules decision for the owner.
**No L1.9 run was started:** run 0, Guard, Strike and the L1.9 score matrices stay held (R20); new screens run only if
the owner asks.

## What this does not show

Scripts only, no trained team; tier 1 only (no Isaac Lab drone); one start set; the vertical Strike scripts are not
fitted in tier 1. A trained Strike could find what the scripts do not.

## GPU-hours and files

0 GPU-h (CPU). Evidence in `records/evidence/2026-11-24_ste_l19_screen/`: `results.md` (every cell), `controls.json`,
`gates.toml`, `hold_composition.png`, three clips (`guard_mark_edge_v_strike_straight.gif`,
`guard_field_v_strike_flank.gif`, `guard_mirror_v_strike_low.gif`, the 1.15 m game). Run folder
`runs/2026-11-24_ste_l19_screen/` (not in git).
