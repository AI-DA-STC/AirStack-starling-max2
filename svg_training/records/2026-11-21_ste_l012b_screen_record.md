Simulator: training simulator, tier 1 (fast engine; Starling layer: commander copy, safety filter on every pair, fitted PX4 response, exploratory). Observed in the training simulator; not a flight result.

# 2026-11-21_ste_l012b_screen record

## Run notes

- **Never suspend the machine during a GPU job** (no closed lid, no sleep): the cap clock and the GPU-hour ledger are wall clock less the owner's gpu_pause.sh pauses only, so a suspend counts in full against the cap and is billed as GPU-hours (tooling task L07-SUSPEND). Say here whether the machine was suspended during the run.
- **Finding L011-F1**: the scripted players decide every tick (0.05 s), not at the sheet's 0.6 s decision period (timing.decision_s). This sweep measures scripted play at 0.05 s. L0.12's trainers must fix their decision period explicitly (T41's recipe used 12 ticks = 0.6 s).

## Purpose

STE task L0.12b scripted screen (INFO): every scripted Guard against every scripted Strike in tag_1p15 on T44's starts (loaded from the gate file's reference file, replayed as a control), with L0.11's controls; g* and s* by L0.11's rule for L0.12b's best-response runs, and the unchosen-tag shares per cell (INFO, defined in the gate file).

## Commit

`0d2438b6997e1660338f4bf5b3e663efaf71ab4b` (working tree not clean)

## Config

- Gate file `configs/ste_l012b/screen_gates.toml`, sha256 `881375f054a78ae33c7fd330e271a4e3b27a0a1cf3d58eca4b893cdca8ce2479` (copy in the run folder: `gates.toml`).
- Game `tag_1p15`: `configs/ste_l011/tag_1p15.toml`, sha256 `b2e09683f7088964a7d1ca15dfc9c98d1e04c15e96b14196d6971afb75f27580`.
- Game `base`: `configs/ste_l011/base.toml`, sha256 `96e0e7f61a49999da54eee81a544bf64c519cd80833f0dcdfa2a07edfc10cc4d`.
- Game `tag_10m`: `configs/ste_l011/tag_10m.toml`, sha256 `816892b3524829f6fda1646bcea12f0030a713fc7106a50ea1c34727f6fabe78`.
- Game `zone_2p4_tag_off`: `configs/ste_l011/zone_2p4_tag_off.toml`, sha256 `86613ffd577fa58f56d865d5527d145a181cfa55335a227d583f83933c60ccd7`.
- Game `tag_0p05`: `configs/ste_l011/tag_0p05.toml`, sha256 `be8d5b2ef7dc58958c329374370aea026fa7a650950564a3e3dc3b04bcc4db33`.
- Game `tag_off`: `configs/ste_l011/tag_off.toml`, sha256 `fae94c1f36ec026b4e9778fbb497b576d5dce0b8f67b443b1ed7e77512d000e1`.
- 1000 games per cell, 30 cells per batch, at most 2400 ticks per game; device cuda.

- Closest 3-D approach (results.md): among drones still in the game after the tag step (a pair tagged on a step is out before the distance is taken: core/game.py; QC M-3).

## Model parameter set

Tier 1 Starling layer: `params/real_exploratory_v0.toml` (fitted PX4 response, exploratory); safety filter on every pair, 1000 sweeps, check every 8.

## Seeds

Game seed 110000 for every batch (paired starts: T44's first 1000 starts, loaded from the reference file, tiled over the cells); Guard players seed + 101, Strike players seed + 202.

## Machine

jeremychia-Legion-Pro-7-16IAX10H; GPU NVIDIA GeForce RTX 5070 Ti Laptop GPU; torch 2.7.0+cu128; Python 3.11.15. Exit code 0 (DONE). Effective time 717 s of a 0.75 h cap. job l012b_screen (task L0.12), asked 0.75 GPU-h, used 0.200 GPU-h (shared ledger).

## Games at once

1000 x up to 30 cells per batch; 9 batches played; sizes 3v3.

## Steps per second

213,148 game-steps per second over all batches (150,400,000 game-steps in 706 s, tier 1, NVIDIA GeForce RTX 5070 Ti Laptop GPU); per batch, with games and drones per game, in `results.md` (Batches).

## Gates

Verdict: **INFO (no gates on the screen; every control PASS)**.

The screen is INFO: no pass mark. The controls, written in the gate file before the run, gate the reading:

| Control | Status | Detail |
|---|---|---|
| ctl_tag_fires_3v3 | PASS | 1000 games: 3 tags each, all ended at step 1 |
| ctl_reach_fires_3v3 | PASS | 1000 reaches in 1000 games |
| ctl_reference_replay | PASS | 30 cells replay the reference's cells on its starts |
| ctl_same_seed | PASS | 30000 games equal |
| ctl_stand_still | PASS | 0 reaches in 5000 games |
| ctl_still_3v3 | PASS | 0 tags in 1000 games |
| ctl_tiny_tag | PASS | 0 tags in 10000 games |
| ctl_tag_off | PASS | 0 tags in 30000 games |
| tags_one_for_one | PASS | every played game one for one |
| paired_starts | PASS | 1 start setting(s), one set of starts each |
| no_nonfinite_actions | PASS | 0 non-finite actions |

Cut by the projection: none.

## Shortlist for L0.12 (rule: gate file [shortlist])

**tag_1p15**; without the z_up_info columns: tag_1p15. The lead picks the shortlist and records why before L0.12 (PLAN.md row L0.11).

Carried whatever the rule says: tag_1p15 (the gate file's [shortlist] always).

| Variant | H | g* | R | s* | d | |
|---|---|---|---|---|---|---|
| tag_1p15 | 0.645 | guard_field | 0.355 | strike_straight | 0.355 | reference (eligible) |
| no proximity tag (INFO; ctl_tag_off) | 0.0 | guard_parked_centre | 1.0 | strike_high | 0.0 | INFO reference, never shortlisted (P1 is the owner's at G0) |

## Hold composition (QC check 2 after T44)

| Group | holds | holds that ran to the time-out | holds leaving no Guard | game length, median of cell medians / largest cell p90 (s) |
|---|---|---|---|---|
| ctl_tag_fires_3v3 | 1000 | 0 | 1000 | 0.05 / 0.05 |
| ctl_reach_fires_3v3 | 0 | 0 | 0 | 1.40 / 1.40 |
| ctl_reference_replay | 22058 | 0 | 22058 | 3.05 / 13.21 |
| tag_1p15 | 13237 | 0 | 13237 | 3.60 / 14.00 |
| ctl_same_seed | 13237 | 0 | 13237 | 3.60 / 14.00 |
| ctl_stand_still | 5000 | 2035 | 2965 | 11.85 / 120.00 |
| ctl_still_3v3 | 0 | 0 | 0 | n/a / n/a |
| ctl_tiny_tag | 2047 | 2047 | 0 | 3.10 / 120.00 |
| ctl_tag_off | 7661 | 7661 | 0 | 4.08 / 120.00 |

## Unchosen tags (INFO, L0.12b)

Pushed together (the main share): on the tag's tick the safety filter's correction closed the pair faster than the players' own commands. Filter active (an upper bound: the filter also brakes a pair a player closed on purpose): the filter corrected either drone of the pair on that tick (> 1e-3 m/s). At the filter edge: the pair's 3-D distance was at most 1.11 m (the filter distance plus the gate's margin). Per cell: results.md.

| Group | tags | pushed together (share) | filter active (share) | at the filter edge (share) |
|---|---|---|---|---|
| ctl_tag_fires_3v3 | 3000 | 0 (0.000) | 0 (0.000) | 0 (0.000) |
| ctl_reach_fires_3v3 | 0 | - | - | - |
| ctl_reference_replay | 81948 | 8814 (0.108) | 12178 (0.149) | 0 (0.000) |
| tag_1p15 | 64325 | 629 (0.010) | 63377 (0.985) | 0 (0.000) |
| ctl_same_seed | 64325 | 629 (0.010) | 63377 (0.985) | 0 (0.000) |
| ctl_stand_still | 8930 | 799 (0.089) | 3680 (0.412) | 0 (0.000) |
| ctl_still_3v3 | 0 | - | - | - |
| ctl_tiny_tag | 0 | - | - | - |
| ctl_tag_off | 0 | - | - | - |


## Figures and videos

Figures from the run's own results.json by `scripts/make_ste_l011_figures.py`: `figures/`. Clips (STANDARDS section 8): videos/guard_mark_edge_v_strike_straight.gif: guard_mark_edge v strike_straight, game 0, outcome hold at 2.5 s (0.05 MB, 3 s to make); videos/guard_field_v_strike_flank.gif: guard_field v strike_flank, game 0, outcome hold at 2.9 s (0.05 MB, 3 s to make); videos/guard_mirror_v_strike_low.gif: guard_mirror v strike_low, game 0, outcome hold at 3.1 s (0.06 MB, 3 s to make).

## Run notes added by the lead

- **Why 1.15 m** (owner, 21 Nov 2026): the owner asked for a tag that the drones can really make. 1.15 m is the
  safety filter's 1.10 m keep-out plus 0.05 m, so a tag means "touching the other drone's bubble", and the same rule can
  run in the simulator and on the drones.
- **Unchosen tags.** "Pushed together" is 0–10 % per tag 1.15 m cell of the screen (highest 225 of 2,378 tags, 0.095, mark-edge
  Guards v flanking Strikes) and 0 % for g* v s* (field Guards v straight Strikes); 1.0 % over the whole tag 1.15 m group
  (629 of 64,325). (The reference-replay control, T44's 1.6 m cells, runs higher: up to 27 % per cell.) "Filter active" is 92–100 % per 1.15 m cell (98.5 % over the group) because the filter brakes
  nearly every close approach; it is an upper bound. On the tag's tick, almost no tag is a filter push (pushed together 0–10 % per 1.15 m
  cell); filter effects on earlier ticks are not measured. The screen ran before QC fix 6
  ("pushed together" also needs the filter's own flag on one drone of the pair); QC found 0 of 10,871 pushed tags lacking
  the flag, so the shares stand.
- **Best cells.** g* = guard_field (645 holds) and s* = strike_straight (355 reaches): the same cells, and the same
  counts, as T44's tag 1.2 m. Only this best pair is known to match 1.2 m; the other cells were not compared.
  Clips: [docs/media/ste_l012b](../docs/media/ste_l012b/README.md).
- **Ledger date.** This writer stamps the time the record was written (17:19), after the runs of T51 and T52 (15:52 and
  15:58), which take the time of their first launch; the screen itself launched at 15:31.
- **Commit.** The results name `0d2438b6` (`1b747209` after the branch was rebased on development) with "working tree not
  clean", while code.json records an empty tracked diff (sha256 e3b0…, the empty string) and no later change; the flag is
  set by any `git status --porcelain` entry in the folder, untracked files included, so likely untracked files; not
  looked into.
- **Suspend.** Not suspended: one launch, 717 s effective against a 718 s wall-clock span. GPU-hours 0.200, charged to
  L0.12 (lead ruling Q2).

- Edited after the first write (same session, before any merge; no number changed; again after QC: the unchosen-tag
  sentence limited to the tag's tick, the filter-active range per cell): scopes, the lead's reading and the owner's pending answer stated plainly.

## Confounds stated before the run

- zone_2p4: not screened here; the zone 2.4 m game file is used only by the reach_fires control (tag off)
- arena_7p5: not screened here
- height_offset_cell: not screened here (no strike_start_dz_m group: the loaded starts are T44's as they were)
