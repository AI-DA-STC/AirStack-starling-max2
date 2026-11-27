INTERNAL · plan for moving route 3 to the 1.15 m tag before the LS1 build (owner R51, 27 Nov 2026): what is reused, what is redone, the marks written before any run, the cost and the owner's decisions · links: [LS1_REDESIGN.md](LS1_REDESIGN.md) (the network design and its section 4 marks), [LS1_REDESIGN_PILOT_RESULTS.md](LS1_REDESIGN_PILOT_RESULTS.md) (the 1.6 m pilots), [DISCUSSION R51](../DISCUSSION_2026-11-19_20.md), [README.md](README.md)

# Route 3 at the 1.15 m tag: the switch plan (27 Nov 2026)

Training simulator, tier 1, CPU only until the build; 0 GPU-hours in this plan. Nothing here is flown.

## 0. In plain words

The owner moved route 3 to the 1.15 m tag (the bubble-touch tag: the safety filter keeps opposite drones 1.10 m apart,
plus 0.05 m) before the LS1 build (R51). The 11 scripts do not read the tag distance, so the scripts, their code and
the network design stay. What changes is the game: who gets tagged, so which games a copy error flips. The copy limits
(R48) were set from the 1.6 m calibration, and the stored script games were played at 1.6 m; both are redone at 1.15 m.
The best scripts change too: at 1.15 m the best Guard script is guard_field (645 holds of 1,000 against
strike_straight), not guard_mark_edge, and parked Guards collapse against high and low Strikes (31 and 16 holds).
Last night's pilot networks are replayed at 1.15 m with no refit; decisions 2 and 8 wait for that replay.

## 1. Reused, unchanged

| Item | Why it carries over |
|---|---|
| Game file `configs/ste_l011/tag_1p15.toml` (`b2e09683…`) | equals `base.toml` except the tag radius (`tests/test_ste_l012b.py`) |
| T44's 1,000 starts (seed 110000, `5aeba7ab…`) | drawn from the arena, ring and seed only |
| Reference games of the 30 fixed cells at 1.15 m: T50's `configs/ste_l012b/screen_reference.npz` (`49014000…`, variant `tag_1p15`) | already played on T44's starts; g* = guard_field, s* = strike_straight (T50 record). Played on the GPU: step C checks it replays exactly on the CPU (as T44 did in T90); if not, the 30 cells are re-played on the CPU (minutes) |
| `configs/ste_ls1/cells.toml`, `opponents/scripted.py` | depend on the player lists and seeds only |
| The pilot networks (`runs/2026-11-27_ste_ls1r_pilots_scratch/nets/`) and the network design | R51: replayed with no refit |

## 2. Redone at 1.15 m, in order

| Step | What | How | Cost (estimate) |
|---|---|---|---|
| C0 | CPU-exactness of T50's reference, before any file is hashed | scratch: replay T50's 30 fixed scripted cells on the CPU and compare outcome, end step, tags and Strike drones left game for game (`exploit.replay_ok`, as T90 did for T44); if not exact, re-play the 30 cells on the CPU and rebuild the reference (`scripts/ste_l012_reference.py`), and every later file pins the rebuilt one | minutes |
| A | Files and one code fix | new `configs/ste_ls1/skills_gates_1p15.toml` (copy of the skills gate file: game `tag_1p15`, reference T50 with its label and gate sha, g* guard_field; the variant keeps the name `base`, which the distil code expects, with `reference_variant = "tag_1p15"`); `calibration_1p15.toml`, `calibration_topup_1p15.toml`; `distil_gates_1p15.toml` with the owner's limits left FILL and `[source]` on the 1.15 m game; one fix in `scripts/ste_ls1_calibration.py`: only the reference lookup (`t44_of`) goes through `exploit.ref_variant`, the game config stays built from the `base` variant; test first; sibling tests for each new file | agent time 2 to 4 h with QC; full suite once at merge (code changed) |
| C | Stored script games at 1.15 m in T94's batch layout | scratch driver on `scripts/ste_ls1_equivalence.py` (`prepare`, `plan_batches`, `play_batch`) playing only the scripted stages (c1, c1m, r2) into `runs/2026-11-27_ste_ls12_1p15_scripts_{guard,strike}`. It reads a scratch copy of `distil_gates_1p15.toml` with R48's values filled in (so `prepare` reads 1,000 games a cell, not the smoke 24: asserted) and its network check bypassed. It also measures the natural share of games with a team-mate absent at 1.15 m (the build's `absent_min_share` 0.2 was set from 0.22 and 0.27 at 1.6 m) | about 0.5 CPU-h |
| B | 1.15 m skill screen | a table of every fixed and mixed cell, 1.6 m (T44, T94) against 1.15 m (T50, step C); the run 0 ceiling at 1.15 m (`scripts/ste_l3_run0_ceiling.py`, minutes) | under 0.2 CPU-h |
| D | Copy-limit calibration at 1.15 m (as T90, T91) | `scripts/ste_ls1_calibration.py` through `ste_job.py launch --task LS1.5 --gpu-h 0`, both teams side by side; the Strike side's top-up opponent is the new g* (guard_field) | about 5 to 6.5 CPU job-h, about 3 h wall clock |
| E | Pilot networks replayed at 1.15 m, every gated cell, no screen list (sealed, section 3) | scratch copy of the pilot harness pointed at the 1.15 m files and the step C games (the 1.6 m pins in `harness.py`, the T94 layout check, `stage2.py`'s screen from T94 and T90, `lsr.py`'s game file all repointed). Arms: Guard S1 at both seeds; Strike S2 at both seeds; Strike S1 at seed 1 only (its seed-2 networks for sacrifice and converge were never fitted, and R51 says no refit; as at 1.6 m); the script-oracle arm (0 changed games expected, as stage 0a) and the C4 analogue as controls; runs beside D | about 2.5 to 3.5 CPU-h |

Up to 4 jobs at 6 threads at once. Total about 8 to 11 CPU job-hours, 4 to 5 h wall clock after step A.

## 3. Marks, written before any run (not moved)

- **Step C0:** T50's 30 fixed cells replay exactly on the CPU, game for game. If not: rebuilt as above; reported.
- **Step C:** 1,000 games a cell read (asserted); the C1 rule holds on the 30 fixed cells against the step C0 reference.
- **Step D:** the calibration's own controls (identity arm equal to the reference, reference replay exact), as in T90.
  The calibration proposes no limits; the owner sets them from D alone, on a 1.15 m options page.
- **Step E is sealed until the owner has ruled the 1.15 m limits.** Its jobs write their per-cell results to files and
  print no verdict; neither the lead nor the owner reads them before the ruling, so the limits are set blind to E.
  After the ruling E is judged once, by LS1_REDESIGN.md 4.4 with the owner's 1.15 m limits (the per-cell changed-game
  limit, the intervals and the command limits as ruled; R48's values where the owner keeps them). **Headroom marks fixed
  now, not moved with the limits:** median at most 9 changed games a cell and at most 5 cells over 20. The worse of two
  seeds decides (Strike S1: seed 1 only, so S1 can fail the Strike team but not pass it at both seeds; S2 decides).
- **Controls in E:** the script-oracle arm changes 0 games in every cell; the C4 analogue (an unfitted network) misses
  at least 15 of the 30 fixed cells on each team. Either failing voids E's read.
- **How E is read: a transfer test.** The networks were fitted on 1.6 m rows: at 1.6 m an opposite pair closer than
  1.6 m was tagged at once, so the fit rows hold almost no states with opposite drones 1.15 to 1.6 m apart, which are
  common at 1.15 m (field's 1.1 m range, mark, mirror, sacrifice and converge as they commit). A PASS is strong evidence
  for the design at 1.15 m. **A FAIL is not a failure of the design**: the build refits on its own 1.15 m rows (R49);
  a FAIL is reported with its cells and goes to the build as a known risk, and decisions 2 and 8 are then read from
  the 1.15 m replay where it informs them. Reported beside each cell's changed games: its hold rate at 1.15 m and at
  1.6 m (lopsided cells, such as parked Guards holding 101 or 31 of 1,000, flip less and pull the median down), and D's
  noise 0.02 arm on the same cell (does the ruler still see changes at 1.15 m). **Dropped (27 Nov, before any E
  run):** command error reported separately for rows with an opposite drone between 1.15 and 1.6 m; the read's
  recorder bins error only by drones alive, and a distance bin needs a change in `source/` that scratch pilots do not
  make. The build's own row marks, on 1.15 m rows, cover those states.
- **Step B:** INFO, no mark.

## 4. What it asks of the owner

| # | Decision | When |
|---|---|---|
| 1 | The copy limits at 1.15 m (as R48), from step D alone, on a 1.15 m options page; E stays sealed until then | after D; **ruled R52 (27 Nov): 31, the rest as R48**; E judged: FAIL on both teams, controls PASS ([record](../../records/2026-11-27_ste_ls1_1p15_switch_record.md)) |
| 2, 8 | Decisions 2 (R3 for sacrifice and converge) and 8 (guard_field at R2), from step E. At 1.15 m guard_field is the best Guard script (g*), which raises the stakes of decision 8 | after E |
| 3 | Run 0 against the parked Guard at 1.15 m: the parked_centre Guard holds only 101 of 1,000 against strike_straight (534 at 1.6 m; reaches 899 against 466), so the run 0 check is close to trivial; keep it with a new mark, or replace it. Parked Guards also collapse against high and low (31, 16 holds), so the copy check sees less in their cells | after B |
| 4 | **The LS1.4 GPU cap, before the build.** R51 means route 2's comparison arm is redone at 1.15 m on the GPU (about 0.9 to 1.1 GPU-h, plus a 0.06 GPU-h recipe pilot), which puts LS1.4 near 5.3 GPU-h against its 4.0 cap (R43): raise the cap or rescope LS1.4 | before the build |
| later | Filter option B, screened at 1.15 m before LS1.4 (R51) | before LS1.4 |

## 5. Lead's calls (announced, not ruled; the advisor agreed)

- The variant inside the 1.15 m gate files keeps the name `base` (the distil code fixes it); the game it points at is
  `tag_1p15`. The 1.6 m files stay as they are, with their tests.
- The Strike side's near-miss opponent and top-up opponent: guard_field (the 1.15 m g*), in place of mark_edge.
- The pilot replays at 1.15 m use no screen list: every gated cell is played (the 1.6 m screen cells came from 1.6 m
  results).

Advisor read before any build: Fable 5.2 (agent, read-only), 27 Nov 2026: go with changes; all nine folded in above.
