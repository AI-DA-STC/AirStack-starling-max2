INTERNAL · the lab's AI-assistant hand-over notes. Not needed to read or run anything here: start at [../../README.md](../../README.md).

# Claude handoff: svg_training (vectorised training pipeline)

> **How to use this file.** Read it at the start of a session, after [../../CLAUDE.md](../../CLAUDE.md).
> §4 is the current state, §5 is what is waiting on people. Update both before you stop.
> Last updated: 20 November 2026 ~12:30, on the home RTX 5090 (the owner approved phase L0 of the STE learning track: note at the top of §0; laptop takeover note below it), worktree `~/AirStack-starling-max2-naming`, branch `docs-naming` (owner-approved naming and story pass on the public docs; committed, not pushed, not merged). Before: 19 November 2026, ~00:30, on the home RTX 5090, release worktree `~/AirStack-starling-max2-release`, branch `nus-release` (plain-laptop CPU route: code fixes C1–C9 and the PROVISIONAL bundle `nus_provisional/`, owner decision 6; committed, not pushed). Before: 18 November 2026, ~15:15, on the home RTX 5090, NUS-port worktree `~/AirStack-starling-max2-nus-port`, branch `phase6-pass2` (Phase 6 pass 2B: **Phase 4 complete**, its results written into every doc, every NUS-port clip published, the hangar size restored, the Phase 5 plan described; uncommitted, the lead commits). Before: ~06:45, on the home RTX 5090, integration worktree `main-5090` (Phase 6 pass 1: public NUS docs, privacy rails rewritten to the owner's decision, Claude files touched up; Phase 4 rows 4–6 running). Before: ~05:30 (Phase 4: T17 PASS, rungs 1 to 3 scored, rungs 4 to 6 not run). Before: ~01:00 (Phase 3 T16 PASS). Before: 17 November 2026, ~22:30, on the home RTX 5090 (evening summary in §0). Before: ~07:00 (morning summary in §0). Before: ~05:30 (S2b Tasks 1–8 done (T13 FAIL, over/under passing), 9 Isaac seeds running, 10 docs being written, 8b deferred; see §0 S2b line). Before: ~03:00. Earlier: 16 November morning (**S2 CLOSED**: final whole-stage review done on Opus, one fix wave 4d0d409, wording c218cbb; owner ruled A and B; S2b plan approved and ready to start).

## 0. Resume here (for a new session or another Claude account)

Everything needed is in this folder; nothing depends on the previous chat. Claude's user memory (`~/.claude/…`) and
the private NUS workspace (`~/ma_skills-self-play/`, 5090 only) do **not** travel with git: if this file and a memory
note disagree, this file wins.

### STE LEARNING TRACK: PHASE L0 APPROVED, 20 November 2026 — read this first for anything after the NUS port

The owner set a new direction on 19–20 Nov: **STE trains its own Guard and Strike policies, in parallel with NUS**
(the NUS route is paused, lead call D8). Everything is in [`ste_learning/`](../../ste_learning/README.md): the README (what is
being built, the plan, phase L0 step by step, four flowcharts), `PLAN.md` (version 2, after an independent soundness
review), `DISCUSSION_2026-11-19_20.md` (every question, decision D1–D9 and open item P1–P12), the track's STANDARDS,
reference pages and five agents (`ste-*`, copied into `.claude/agents/`).

- **State:** **phase L0 (game definition and feasibility, cap 19 GPU-h) APPROVED by the owner, 20 Nov 2026** (L0 only:
  no later phase, no PROPOSED value); task status in `ste_learning/status/STATUS_LATEST.md`. L0 ends at gate G0, where the owner rules on the tag and zone, what a tag costs, team sizes, where to
  train, environments, the demo and the L1–L9 budget.
- **Links (owner, 20 Nov 2026):** the root `README.md` ("I want to…" row and one sentence in its `svg_training/` row) and
  the training `README.md` §7 now point at `ste_learning/README.md`. The root `CLAUDE.md` row for this folder still says
  "Phase 5 planned": not approved for change, proposed to the owner.
- **Status files:** `ste_learning/status/STATUS_LATEST.md` (overwritten) and `LOG.md` (append-only), first written 20 Nov.
- **Heartbeat:** the owner did not answer the heartbeat question; the standing rule holds (full status every 30 min).
- **Why L0 exists:** the review found that the proposed rules (1.6 m proximity tag, 1-for-1) may let head-count decide
  the game, that the zone radius equals the tag radius, that the programme's sizes are 2v1 and 5v3 (not 3v3), and that
  tier 2 has never trained anything (PLAN §2, F1–F10).
- **5.1 scored: FAIL** (T43), route (b) stopped; the NUS route is paused (lead call D8). G19 v P3S in NUS's JAX game and
  the same-start videos are done (T42).
- **Owner's standing asks:** the advisor is consulted at every key point; status every 30 min in the owner's format;
  quality first.
- **Private notes (5090 only):** `~/ma_skills-self-play/_notes/DISCUSSION_2026-11-19_20_FULL_PRIVATE.md`.

### LAPTOP TAKEOVER, 19 November 2026 ~11:30 — read this first if the 5090 is out of reach (for the laptop session)

The owner is moving to the office and may lose remote access to the home RTX 5090. Everything below is what a laptop
session needs; Claude's user memory on the 5090 does **not** travel, so the owner's working preferences are written
here too.

**What is on `main` (pushed by the owner):** every Phase 5 result so far, the code fixes and the PROVISIONAL bundle
(`nus_provisional/`, install with `scripts/nus_install_provisional.sh`), the docs restructure and naming pass (front
page story, What we found, Run it yourself, Train a Guard, video gallery) and this note. The stage 5.2 code (S1–S5,
CPU-tested, not yet run on a GPU) is on `main` too (full CPU suite 1,114 passed, 0 failed, 19 Nov ~11:25), once the owner
has pushed it. On the laptop: `git pull`, then `svg_training/README.md` and this file.

**What exists only on the 5090 (not reachable from the laptop):**

| Item | Where | State at ~11:30 |
|---|---|---|
| 5.1 Method match (STE port of NUS's training method), 3 seeds | worktree `~/AirStack-starling-max2-nus-method` (branch `nus-phase5-method`), `runs/nus_port/phase5/s51/` | DONE 19 Nov 21:06, scored 22:10: **FAIL** (T43; b and c fail on seed 3001 only, d passes). Plan: route (b) stops; 5.2 not started; owner's call |
| Docs pass 3 (videos viewable in every page: a GIF per clip, folded video list, GIFs beside every result, a "Watch the clips" line appended to records; new front-page section 3 "The game: NUS 2-D game vs STE drone set-up"; root README training rows; old pointer pages deleted with links updated; a list of other possibly stale pages for the owner) | worktree `~/AirStack-starling-max2-naming` (branch `docs-naming`) | a writer agent was working; NOT on main. If lost, redo from the brief in the owner's 19 Nov ~11:00 messages (summarised in this bullet) |
| Private files: NUS's code, `~/ma_skills-self-play/` (port plan, notes, docs-panel proposal and drafts, resume notes), `configs/local/` with the lab's NUS values, `runs/` | 5090 | the laptop can install the PROVISIONAL bundle instead of `configs/local/`; NUS's code only from NUS |

**Pilot results so far (on main):** 5.P1b "STE Guard policy" holds the zone against S20 in **829 of 1,000** games in
Test 5 conditions (T41; parked Guard 429). R0, N0, C0 PASS (T29, T30, T33): the 5.1 test is calibrated.

**Waiting on the owner:**
1. Route decision (5.1 FAILED, T43; the plan stops route (b)): promote the STE Guard policy route (more seeds, more
   Strike behaviours, self-play, Isaac Lab check, then an AirStack hand-over plan with CMU) and shelve 5.1b/5.1c/5.2
   unless NUS asks? (lead's recommendation: yes).
2. Review of docs pass 3 (branch `docs-naming`) before it goes to main; decide on the stale-page list it produces.
3. Send NUS the cover note (questions on the front page, section "Next steps and open questions").

**The owner's working preferences (from Claude memory on the 5090; follow them on the laptop):**
- Status updates every ~30 min and on events, always three tables: Phases (Phase | Status | Math library |
  Simulator | What), the current phase task by task (ID | Plain name | Status | Simulator | Result / ETA), and any
  other workstream (ID | Plain name | Status); then Next and Waiting on you. While `main` has unpushed commits, add a
  bold "Ready to push" line; drop it after the owner pushes.
- Task IDs, always "ID + plain name": 5.0 Plan · 5.R0 Reference rebuild · 5.C0 Fairness check: NUS vs NUS · 5.N0
  Fairness check: untrained · 5.1 Method match · 5.1b/5.1c Cheaper method variants · 5.2 Train on our drones · 5.3
  Isaac Lab check · 5.P0 Pilot: speed test · 5.P1 Pilot: Guard learner, first try · 5.P1b Pilot: Guard learner, fixed ·
  5.P2 Pilot: Guard vs mixed Strikes · 5.P3 Pilot: self-play. Side work: DOC, VID, FLT.
- The owner delegates technical training calls to the lead (decide, record why, report); still ask for AirStack or
  flight changes, external messages, pushes and anything published. Propose before large doc changes; the owner
  reviews before `main`.
- Run GPU jobs side by side when the GPU has room (`scripts/isaac_preflight.sh --approved-headless
  --allow-siblings`), but give short pilots the GPU alone (a starved run says nothing); the owner pauses jobs to use
  the PC with `scripts/gpu_pause.sh` (nus-method worktree's copy; pause-aware caps).
- Videos are recorded inside every run (never a separate re-record), and every result shown in a doc gets a GIF that
  plays on GitHub (MP4 links do not play inline).
- Public docs: neutral report tone (NUS by name, not "you"); every label is NUS's own term or defined where first
  used; NUS's policies were trained **by STE with NUS's code** (NUS gave no checkpoints).
- Never push, never `git add -A`; the owner pushes from GitHub Desktop.
### Videos, the game section and pointer pages deleted, 19 November 2026 ~12:00 — branch `docs-naming` (for the lead and the owner)

Owner-approved (19 Nov ~11:00) follow-up on the same branch; numbers and evidence unchanged.

- **GIF previews**: 261 new GIFs beside the MP4s of `docs/media/nus/` (15.9 MB; 380 px, 5–6 frames/s, 48–64 colours,
  at most 14.2 s with the last frame held; 19 re-made at 5 frames/s and 48 colours, 4 of them at 320 px;
  `isaac/g19_vs_s20_strike_win_2.gif` 224 kB is the one over 150 kB). `docs/media/nus/README.md` regenerated: every clip as a 240 px preview linking its MP4, captions
  "Guard vs Strike · played in … · outcome", one `<details>` block per section with stable anchors (`#nus-2-d-game`,
  `#copy-of-nus-2-d-game`, `#tests-1-6`, `#test-1` … `#test-6` incl. `#test-2-1`, `#test-2-2`, `#test-3a`, `#test-5a`,
  `#isaac-lab-clips`, `#ste-guard-policy`, `#how-they-were-made`). `docs/media/README.md` the same for S2/S2b.
- **Reader pages**: previews beside every result with a clip (WHAT_WE_FOUND §2, §3; day by day §4–§8, §12;
  TRAIN_A_GUARD §5–§6; RUN_IT_YOURSELF A, D2, E, F).
- **Records**: 11 records gained one final line "Watch the clips: …" (additive only; the owner's one exception).
- **Front page**: new §3 "The game: NUS 2-D game vs STE drone set-up" (table + one preview per column; the term lines
  moved there from the tests section); sections renumbered 1–8 (Watch it unnumbered). GLOSSARY: NUS 2-D game, hangar
  set-up, STE drone set-up.
- **Root**: README "I want to…" svg_training rows replaced with the owner's text; root CLAUDE.md row link now
  `WHAT_WE_DID_DAY_BY_DAY.md` (link target only).
- **Deleted** (`git rm`): HOW_IT_WORKS, NUS_PORT, NUS_RESULTS, TRY_IT, PLUG_IN, NUS_PHASE4_RESULTS, WHAT_WE_DID. Plain-text
  old names stay in dated history (plans, this file's log, Linear comment copies, two records' "NUS_PORT §3" and
  "NUS_PORT Figure 1"). The deletions landed in the commit titled for the root CLAUDE.md fix (a staging slip; content
  correct).
- Checks: every relative link, image (Markdown and HTML) and anchor in `svg_training/**/*.md`, README.md and
  CLAUDE.md resolves (scripted, 1,723 links); every `<details>` block well-formed and every MP4 shown with its own
  preview (scripted); `tools/docs_check/check_docs.sh` 0 FAIL (13 PASS, 7 WARN, 1 SKIP); full CPU suite 1,077 passed,
  47 skipped, 0 failed (10 min 14 s, `env_isaaclab`). GitHub rendering itself was not viewed (no browser here).

### Naming and story pass, 19 November 2026 ~11:00 — branch `docs-naming` (for the lead and the owner)

Owner-approved (19 Nov) pass on the public docs; facts, numbers and evidence links unchanged; records not re-worded.

- **Renames** (`git mv`, one-line pointer page left at each old name so records, plans, Linear copies and the root
  README/CLAUDE.md keep working): `NUS_RESULTS` → `WHAT_WE_FOUND`, `NUS_PORT` → `WHAT_WE_DID_DAY_BY_DAY`, `TRY_IT` →
  `RUN_IT_YOURSELF`, `PLUG_IN` → `PLUG_IN_YOUR_CODE` (`tests/test_adapters.py` follows), `HOW_IT_WORKS` → `THE_GAME`.
  New `docs/TRAIN_A_GUARD.md`: the pilot P1b run 4 recipe (T41) with a CPU check run on 19 Nov (1 min 45 s, exit 0).
- **Story**: front page in seven sections (overview + policies table; porting NUS's code; testing NUS's policies on STE
  drones; why performance drops; training in STE conditions; next steps and the five questions; run it yourself),
  gallery after section 5.
- **Names**: "STE" defined once per page; "defender (Guard team)", "attacker (Strike team)" at first mention; Tests 1–6
  (sub-tests 2.1, 2.2, 3a, 5a) replace ladder rows on reader pages, "Test N = ladder row N in the records" in GLOSSARY
  and WHAT_WE_FOUND; Copy of NUS 2-D game (PyTorch), STE game engine, STE drone model, Isaac Lab physics drones, STE
  port of NUS's training method (PyTorch), STE Guard policy; G19/S20/P3G/P3S said to be trained by STE using NUS's
  code. Tone neutral (no "you"/"your"): CLAUDE.md's reader-page rule and STANDARDS §2's "the partner" row updated to match.
- Checks: every relative link and anchor in `svg_training/**/*.md` resolves (scripted); `tools/docs_check/check_docs.sh`
  0 FAIL (13 PASS, 7 WARN, 1 SKIP); full CPU suite 1,077 passed, 47 skipped, 0 failed (10 min 22 s, `env_isaaclab`).

### Plain-laptop route and the PROVISIONAL bundle, 19 November 2026 ~00:30 — branch `nus-release` (for the lead and the docs writer)

Owner decisions of 18 Nov ~23:15 (docs panel `~/ma_skills-self-play/_notes/docs_panel/PROPOSAL.md`, 5090 only). Done, test
first, one commit each, on `nus-release` (not pushed):

- **C1–C3** `score.py` and `train_standin.py`: `--device auto` (default; CUDA if PyTorch sees one, else the CPU with a note);
  `train_standin.py --smoke` (the pipe test in seconds, `train_result.json` `smoke: true`). Module `svg_training/devices.py`.
- **C4** `pyproject.toml` lists the real dependencies (torch, numpy<2, scipy, msgpack, matplotlib, imageio, imageio-ffmpeg,
  opencv-python-headless, pyyaml, skrl 2.x, gymnasium, tensorboard; extra `test` = pytest) and installs with
  `pip install -e .[test]`; `tests/test_dependencies.py` fails on any unlisted import (Isaac, ROS 2, NUS's JAX named apart).
- **C5** `test_run_s0.py` passes off the lab machines (SVG_PY stub); the unstubbed host-default test skips there.
- **C6** the numpy-2 line in `test_fit_response.py`'s fixture. **C7** `make_nus_phase4_figures.py` refuses (exit 2) when
  a row is missing. **C8** the missing-`nus_deploy.toml` error says "before nus_convert_checkpoint.py". **C9**
  `setup_nus_jax.sh --cpu`.
- **Decision 6**: `nus_provisional/` (44 MB, 38 files, sha256 list) holds the lab's local settings files, the converted
  weights G19, S20, P3G, P3S, the Phase 4 starts, T16's reference data and the recordings of NUS's game, byte-identical,
  labelled PROVISIONAL (NUS will retrain). `scripts/nus_install_provisional.sh` copies it into the git-ignored
  `configs/local/` and `runs/nus_port/`. Privacy tests exempt that folder only; STANDARDS §2 and §8 say so (dated).
  STANDARDS §2 also allows NUS's own terms once per page in a translation line.
- Fresh-clone check found one more: a plain venv from `pyproject.toml` gets torch 2.15.0+cpu and skrl 2.1.2, and the
  default-path bit-level fingerprint test (recorded with torch 2.7.0, skrl 2.1.0) failed; with torch 2.7.0 + skrl 2.1.0
  in a CPU venv it passes, so the test now skips on other versions and names both. Pin or float the versions in
  `pyproject.toml`: the lead's call (floating today).
- Verified: this worktree with the bundle installed, env_isaaclab, CPU only: 1074 passed, 47 skipped, 0 failed (11 min);
  10 NUS tests that skipped before now run and pass. A fresh clone of `nus-release` (`1fd05474`), plain CPU venv with
  only `pip install -e .[test]`, bundle installed, empty HOME, `OMP_NUM_THREADS=4`: 1069 passed, 52 skipped, 0 failed
  in 10 min 21 s, `git status` clean (commands: `~/ma_skills-self-play/_notes/docs_drafts/VERIFIED_CPU_COMMANDS.md`,
  5090 only). Same clone, CPU: `nus_phase4.py --w2-replay` equals T16 exactly (46 and 1,000 of 1,000); ladder row 1 in
  full (97 s) equals the lab's GPU row in 7 of 12 pairs and differs by 1–3 of 1,000 games in 5 (each inside the record's
  Wilson interval; identical with torch 2.7.0, so not the torch version; CPU v GPU or the earlier settings file of rows
  1–3, not separated).

### Phase 4 complete and Phase 6 pass 2, 18 November 2026 ~15:15 — NUS port (for the owner, the lead and the laptop session)

Observed in the training simulator only; nothing flown. **Phase 4 is complete.** Rows 4, 5a, 5 and 6 ran in one background
chain, 05:52 to 13:54 (T22 row 4, T23 rows 5a and 5, T24 row 6; all INFO, exit 0; records
`records/2026-11-18_nus_phase4_rung{4_2,5,6}_record.md`). What they show:

| Row | Change | G19 v S20 Strike reach (of 1,000) | Reading (likely causes, not tested) |
|---|---|---|---|
| 3 | drone response, filter off | 43 | (before) |
| 4 | the all-pairs safety filter | 740 | both drones give way, so push-based blocking fails; both trained Guards concede every game to NUS's scripted Strike; the parked Guard team now holds 444 |
| 5a | free height, no jitter (control) | 740 | equals row 4 in all 12 × 1,000 games |
| 5 | free height, ±1 mm start jitter | 983 | Strike drones pass over or under (as S2b T13): G19 v S20 horizontal closest approach median 1.09 → 0.93 m, 3-D stays 1.09 m |
| 6 | Isaac Lab physics drone | 979 | agrees with tier 1; parked v S20 571 → 524 (247 games differ); 0 upsets |

A parked (zero-speed) Guard team holds 429–476 of 1,000 against S20 on rows 4–6, more than either trained Guard: the
filter works as a wall. The records' "Contact" column (853 of 1,000 on rows 4–6, whatever the Strike policy) counts
any pair under 0.50 m, team-mates included: NUS's start layout already gives 853 such starts (checked on `starts.npz`);
it is not evidence of a flight hazard (Guard–Strike 3-D closest approach: medians 1.05–1.14 m; one scripted-v-scripted game at 0.48 m; NUS-policy pairs ≥ 0.57 m). Isaac Lab camera clips: six, by `scripts/nus_isaac_clips.py` (commit `e595bfd3`).

**Phase 6 pass 2 (this session; docs only, no code or test edited).** Owner, 18 Nov ~14:10: "just put all clips on the
github … no need to keep it private": the hangar size is public (supersedes Phase 4 answer 6 and pass 1's hold-back).
- Filled every pass-2 placeholder: NUS_PORT (at a glance, §3 arena 7.5 m and the usable flying box, §8 table
  rows 4–6 and "What rows 4–6 show" with the Contact explanation, Figure 2 caption, §9 videos with key clips, §10 flight
  meaning, §11, §12 renamed "Next steps: the Phase 5 plan"), NUS_PHASE4_RESULTS, PLUG_IN, HOW_IT_WORKS, README,
  CLAUDE.md, root `CLAUDE.md` svg_training row, `docs/media/README.md` (a pointer).
- **All clips published:** 263 new files, 16.8 MB, in `docs/media/nus/{phase3,w3,phase4/row_*,isaac}/` (260 MP4
  re-encoded H.264 CRF 30, at most 800 px, same frame rate and frame count, checked; 3 Isaac Lab GIF previews).
  Index, one line per clip with game, outcome and size: [../media/nus/README.md](../media/nus/README.md). The
  top-down titles round the 7.5 m arena to "8 m x 8 m" (`viz/replay.py:148`, `:.0f`); the README says so.
- **Phase 5 plan** (owner delegated to the lead ~12:20; own-training pilots ~12:30): route (b) with a 2-D method match
  first, 3-D with the filter, hangar geometry, interface v0.1 plus height, gates before runs, a message to NUS, and
  own-training pilots not of record. Described as the plan in NUS_PORT §12; nothing started.

- STANDARDS §8 video bullet: one dated sentence added for the owner's ~14:10 decision (all NUS-port clips, re-encoded
  small, may be committed; it said "a small chosen set").

**Waiting on the lead:** review and commit (`git add` the four new media folders by path; 263 files); the Phase 5 plan
document and the NUS message (D-P5-5, D-P5-6); the stale comments, the private CLAUDE.md rule and the stale STANDARDS
fence row listed in §5.

### Phase 6 pass 1, 18 November 2026 ~06:45 — public NUS docs (for the owner, the lead and the laptop session)

Observed in the training simulator only; nothing flown. Done in the integration worktree `~/AirStack-starling-max2-integrate`
(branch `main-5090` = GitHub `main` + `docs-5090-setup` + `nus-port-phase2`), uncommitted; the lead reviews, commits, renumbers
W rows and merges. **Owner's decisions applied (18 November 2026):** NUS agreed that their code details, game settings and our
results on their code may be published (STANDARDS §2 rewritten, dated; NUS's source code and confidential report quotes stay
out); the contact-tag track may be described publicly (STANDARDS §2); root `README.md` and root `CLAUDE.md` svg_training rows
updated (status and pointers only).

- **New:** [../WHAT_WE_DID_DAY_BY_DAY.md](../WHAT_WE_DID_DAY_BY_DAY.md) (NUS's three branches, Phases 0–6 with library and simulator, Run 0, hangar
  geometry, self-play matrices and settling, T15–T17, Phase 4 rows 1–3, what it means for flight, Phase 5 options, the
  contact-tag track); Figure 1 `docs/figures/nus_selfplay_matrix.png` by the new `scripts/make_nus_selfplay_figures.py`
  (reads the 5090's matrix file); 13 clips in `docs/media/nus/` (1.25 MB, captions in its README).
- **Pass-2 placeholders** in NUS_PORT, NUS_PHASE4_RESULTS, media/nus README and PLUG_IN: all filled in pass 2 (above).
- **Setup and run docs:** GETTING_STARTED (NUS JAX env section, `msgpack` step, preflight 1024 MiB and both machines'
  approval), TRAINING (new "NUS jobs": `setup_nus_jax.sh`, `run_nus_job.sh` with unique `hydra.run.dir` and
  `save_eval_gif=True`, self-play videos with `eval.py`, the Phase 2–4 scripts in order), WORKSTATION_SETUP (§2c decided,
  §3 rewritten), PLUG_IN, HOW_IT_WORKS, GLOSSARY (terms; Versions: `nus_jax`, `msgpack`, layout `nus_area_denial_v1`).
- **Privacy tests rewritten, not dropped:** `tests/test_partner_privacy.py` now (1) fails on tracked NUS source (path
  rule always; file and long-line block scan when a NUS clone is present, `SVG_NUS_CLONE` or the 5090 default) and (2)
  scans code, configs and scripts only for local values (documents may state them). `tests/test_workstation_scripts.py`:
  the word and value scans cover the scripts only, not the page. `tests/test_nus_phase4.py`: the committed-text check
  (D8) is retired with a dated comment. G1–G4 (the `configs/local/` mechanism) unchanged.
- **Claude files:** CLAUDE.md (status table, machine-by-machine Environment, "5090 only" table), all six skills and six
  agents, AGENTS_AND_SKILLS, this file. `FROM_5090_2026-11-17.md` retired into §4 and §5 below (removed from the working tree).

**Waiting on the lead:** review; `git add -f` for the `.claude/` files; stage the removal of `docs/claude/FROM_5090_2026-11-17.md`
(deleted from the working tree; its content is in §4 and §5); renumber the W rows to the next T numbers (T15 onward on
today's ledger) in LEDGER and the records that cite them; merge. On the laptop after the pull: install `msgpack` if missing
(GETTING_STARTED step 5) and run `tests/test_partner_privacy.py` and `tests/test_workstation_scripts.py`, whose value scans
need the laptop's private reference files (they skip on the 5090). **Waiting on the owner:** confirm publishing the hangar's
hangar arena side (answered ~14:10: publish, see pass 2 above); choose Phase 5's route after Phase 4 (delegated to the lead ~12:20); push `main`.
**Gap:** Phase 1, Phase 2a, Run 0 and the self-play evaluation have no record or ledger row (their numbers are INFO, from the
5090's private notes); write records for them if they should count.

### Phase 4 summary, 18 November 2026 ~05:30 — NUS port, transfer ladder (for the lead, the owner and the laptop session)

Observed in the training simulator; nothing flown; no partner or hangar value here. Built and ran the plan `docs/plans/2026-11-18-nus-phase4-transfer-ladder.md` v2 with
the owner's seven answers (hold in rung 2, no row 3h). **T17 PASS** (archive pair G19/S20 through the frozen Phase 3 gates, both arms). Ledger **T17 PASS, T18 to T20 INFO,
T21 ABORTED**; records `records/2026-11-18_nus_phase4_*_record.md`; summary page `docs/NUS_PHASE4_RESULTS.md`. Rungs 1 to 3 scored (rows 1, 2.1, 2.2, 2, 3a, 3; the split of
rung 2 fired). **Rungs 4, 5, 6 NOT run:** each is estimated at 4 to 5 h (limit 2 h); rung 4 was started and stopped, rows 5a, 5 and 6 never started; the lead or owner chooses
(background run with `--accept-long`, core block only, or a filter-setting change). **Reading rule 2 fired on row 2.1** (float32 noise floor; diagnosed in the rung 2 record): the
implementer continued; the lead confirms or rewords the rule. Core change: one hook, `SvgGame._draw_starts` (owner-approved), its test is `tests/test_game_draw_starts.py`.
**Files** (all uncommitted, the lead commits; the core hook, its test and this HANDOFF line as one separate commit): `source/svg_training/core/game.py`, `tests/test_game_draw_starts.py`;
new `source/svg_training/nus/{hangar,hangar_game,players,ladder}.py`, `configs/{nus_hangar.template,nus_hangar_game,nus_phase4}.toml`, `scripts/{nus_phase4,nus_phase4_w3,make_nus_phase4_figures}.py`,
`tests/{test_nus_phase4.py,_nus_phase4_fixture.py}`; changed `nus/{outputs,outcome,strategy}.py`, `scripts/{nus_jax_common,nus_export_reference,nus_make_local_deploy}.py`,
`tests/{test_nus_phase3_privacy,test_nus_rules_privacy}.py`, `docs/PLUG_IN_YOUR_CODE.md`, `records/LEDGER.md`; new records and `docs/figures/nus_phase4_ladder.png`.
**Waiting on the lead:** commit; `train-gatekeeper` read of the records; laptop privacy scans before merge (the partner value scans skip on the 5090; every diff and commit message by eye for short partner numbers). **How the privacy check was done:** `check_payload` on every committed text and an in-memory scan of every new or changed non-ignored file for the protected set in decimal and integer forms catch EQUALITY (and relative 1e-6 near-equality) with local values only, not ratios or common divisors; two ratio leaks were found by reading and removed (the per-sample smoothness column, which differs from the per-tick one by the hold length; reach times of replica and jump rows, which are multiples of the step length, now whole seconds) and run times are kept out of the records (throughput x run time shows the game length).

### Phase 3 summary, 18 November 2026 — NUS port, converted policy (for the owner and the laptop session)

Observed in the training simulator (2-D replica); nothing flown; no partner value here (they stay in `configs/local/` and `runs/`).
Built Tasks 1–9 of `docs/plans/2026-11-18-nus-phase3-converted-policy.md`: privacy guard rails widened (literal scan over `tests/test_nus_*.py`;
`write_record` refuses any rules, deploy or architecture number), `nus/deploy.py` (git-ignored `configs/local/nus_deploy.toml`, template committed), both
scripted controllers ported (`nus/apf.py`), msgpack weight loader and bfloat16-faithful actor (`nus/actor.py`), reference export, wrapper
`svg_training.nus.strategy:NusPolicy`, outcome machinery and JAX action worker, interface draft. Gates on the first hangar checkpoints: (a) action error
0.0074 (Guard) / 0.0105 (Strike), limit 0.02; (b) converted Strike reach rate inside the JAX arm's Wilson 95 % interval for both teams (Guard 46 v 48 of 1,000;
Strike 1,000 v 1,000); wrapper test passes. Ledger `T16` (PASS); record `records/2026-11-18_nus_phase3_conversion_record.md` (see the note below if it is missing).
Videos: `runs/nus_port/videos/`. **Interface layout id `nus_area_denial_v1` (STANDARDS §3 rule 3 entry):** observation = partner layout rebuilt from our
71-number observation (own, team-mates cyclic, opponents; position / previous sample / last displacement blocks; zone radius; reached flag), action = deterministic mean, held for the hold length, vertical and yaw zero, prior weight 0; keys in `configs/nus_interface.template.toml`.
`msgpack` added to `pyproject.toml` (new `[project]` table); container image and its `CHANGES.md` line not done.
**Waiting on the lead:** commit; laptop privacy scans before merge; owner reads T16 before Phase 4.

### Evening summary, 17 November 2026 — home RTX 5090 session (for the owner and the laptop session)

All observed in the training simulator or on the desktop; nothing flown. Partner numbers are NOT in this file: they
live only on the 5090 in `~/ma_skills-self-play/` (private port plan, notes `_notes/`) and in the
git-ignored `configs/local/` and `runs/`.

**Done:**
- 5090 host env `env_isaaclab` built (setup script exits 1 on a fresh install; hand fixes in
  [../GETTING_STARTED.md](../GETTING_STARTED.md) step 5, on branch `docs-5090-setup` with its note
  `docs/claude/FROM_5090_2026-11-17.md`). Full suite there: 798 passed, 11 skipped.
- NUS code (three branches) cloned on the 5090 only; owner: NUS's code may live on the workstation,
  so TRAINING.md's "must not leave the laptop" needs updating. NUS confirms the continuous-space branch is the one.
- **Two tracks (owner, 17 Nov):** (1) area denial = the NUS port, contact-free, filter on every pair (matches the
  programme design review's Scenarios A/B); (2) contact tag = a separate one-on-one track,
  [../plans/2026-11-17-contact-tag-track.md](../plans/2026-11-17-contact-tag-track.md) (DRAFT, nothing started).
- NUS answers: their units are scaled to the arena (scale is ours; owner adopted a PROPOSED scale fitted to the
  8 m hangar, value in `configs/local/`); a policy works only on the config it was trained on (train NUS policies on
  the deployment geometry); fixed team size for the whole game (no drone dropping out).
- Phase 1: conda `nus_jax` built; NUS's own tests 65 passed, 1 failed (their stale test vs their config; NUS
  confirmed harmless). Phase 2a: NUS benchmark and two short 3 v 3 fixed-opponent runs (one per team), both teams
  win every evaluation game against NUS's scripted opponents; not runs of record; videos saved with NUS's outputs.
- **Phase 2 part A (this branch, `nus-port-phase2`):** privacy checks G1–G4 (`configs/nus_rules.template.toml`,
  `source/svg_training/nus/rules.py`, `outputs.py`, `tests/test_nus_rules_privacy.py`; marker test), a batched
  PyTorch replica of NUS's 2-D game (`source/svg_training/nus/replica.py`), fixture recorder
  (`scripts/nus_record_fixtures.py`), tests (`tests/test_nus_replica.py`). Per-step parity with NUS's code on 3 v 3,
  5 v 3 and fixed starts: max position error < 1e-5 units, flags and steps identical, every rule exercised. Full
  suite 820 passed, 11 skipped. Development check only: no record or ledger row.
- **New standard:** every training run saves videos (STANDARDS §8; `train-run` skill).
- Claude setup copied to `~/ma_skills-self-play/.claude/` (agents, skills, superpowers) with its own `CLAUDE.md`;
  kept current by the process in §6.

**Later the same night (to ~23:55):** hangar geometry decided from three reviews and a CPU balance probe (values
private on the 5090); Phase 2 gate of record **T15 PASS** (`records/2026-11-17_nus_phase2_parity_record.md`, gates in
`configs/nus_port.toml`); NUS self-play go/no-go on the hangar geometry running detached (3 seeds × 8 generations,
done ≈ 02:00); Phase 3 plan v2 committed (owner approved `msgpack` and layout id `nus_area_denial_v1`), its build
may be unfinished and uncommitted in this worktree. **Resume note (private, on the 5090):**
`~/ma_skills-self-play/_notes/RESUME_2026-11-17_night.md`.

**Waiting on the owner:**
1. ~~Zone radius and arena~~ decided (lead, from three reviews; owner asked agents to decide).
2. Phase 1: 65 of NUS's 66 tests pass (the failure is a test NUS confirmed is out of date); approve the PROPOSED gate numbers in the private port plan.
3. Go for a full NUS self-play run on the 5090 (a few hours) on the chosen hangar geometry.
4. ~~5090 Isaac preflight~~ owner chose (18 Nov) to raise the GPU limit: `isaac_preflight.sh` now allows up to 1024 MiB per foreign process (the 5090's remote-desktop daemon holds 546-589 MiB; a NUS JAX job, ~1.7 GB, still blocks). The WiFi rule (exit 10) is unchanged; the owner extended his 16 Nov headless-on-WiFi approval to the 5090 (18 Nov, "wifi: yes"), so headless launches here use `--approved-headless`. `run_nus_job.sh` uses the same 1024 MiB limit (owner, 18 Nov), so NUS jobs no longer need `--allow-shared-gpu`. Branch `docs-5090-setup` still says "500 MiB" in WORKSTATION_SETUP §2c and GETTING_STARTED step 7: update when merging.
5. **Container route is incomplete (found 17 Nov on the 5090, first container suite run since T1):** image
   `svg-training:isaaclab-2.3.2` built; `docker/run.sh '$SVG_PY -m pytest -q'` gives 704 passed, 29 failed, 13 errors
   (host: 820 passed). Causes: skrl 1.4.3 in the image (stand-in trainer tests need 2.x; 27 + 2 adapter tests);
   `svg_ground_control` not importable because only `svg_training/` is mounted (`docker/run.sh:32`; 7 filter tests);
   bare `python` subprocesses without torch/toml (3). Not 5090-specific. Fix on the laptop: (a) skip host-only tests
   in the container, or (b) skrl 2.x in the image + AirStack read-only mount (docker change: CHANGES.md entry).
   GETTING_STARTED's "two skipped tests in the container are normal" is out of date.
6. Merge `docs-5090-setup` and `nus-port-phase2` on the laptop; run `test_partner_privacy.py` there (its value scan
   skips on the 5090) and read the diff for short partner numbers.

### Morning summary, 17 November 2026 (for the owner)

**Done overnight (all observed in the training simulator; nothing flown):** S2b Tasks 1–9 built and reviewed, Task 10
results page [../S2B_RESULTS.md](../S2B_RESULTS.md) (linked from the root README). Ledger: T13 scripted games on both
backends **FAIL** (Strike drones pass over/under Guards on the physics drone; your option (a)); T14 stand-in on Isaac
drones **FAIL** (seeds 1–2 hold 0 % v straight Strike, 7–13 % v flank; seed 3 queued for the 5090, §5a). 5090 port kit
(`scripts/workstation/`, [../WORKSTATION_SETUP.md](../WORKSTATION_SETUP.md)) and the private bundle `~/svg_workstation_bundle/`. Five live screenshots of the Isaac Sim window (four worlds + the stand-in
trainer running) in [../media/README.md](../media/README.md); new opt-in `--windowed` launch option (headless stays default; WiFi survived).

**Waiting on you, most important first:**

1. **Push `main`** from GitHub Desktop before you port (the 5090 clones from GitHub; ~310 commits ahead, ~45 MB of clips and figures).
2. **The stand-in does not learn on the physics drone.** Pick the next step: (a) a tier-1 control run to find the cause, (b) a different learner or a curriculum, (c) Guards with a height-covering reward. Lead suggests (a) first, on the 5090.
3. **Confirm `[standin_v2]`** (initial log std −1.6, frozen noise on reward-free axes, 100 M game-steps per seed): taken as approved from "Issac drone runs, if possible"; you have not confirmed the table itself.
4. **T13 hold-rate gate**: FAIL by design after option (a). Re-scope that gate for later stages, or keep it as a standing record of the 2-D/3-D gap?
5. **Undiagnosed**: in 4 random-Guard cells the physics drones come 0.12–0.23 m closer than tier 1; stand-in and scripted Guards reach ~0.95 m in 3-D (under the 1.10 m keep-out). Diagnose next session?
6. **NUS**: their JAX reference results are in `~/nus_jax_reference/` (Guard best 0.999, Strike 1.000 against scripted opponents; full self-play needs the 5090). The agent's REPORT.md write was refused — say "save it" if you want it written. Slack draft in the chat.
7. **5090 settings (PROPOSED)**: JAX memory fraction 0.60; a larger S0 config for 32 GB needs your approval (STANDARDS §7).
8. **Deferred by the lead**: Task 8b (registered Isaac Lab task) and the S2b final review (gatekeeper, drone dynamics, Isaac Lab engineer) — next session. (The two small trainer fixes M7/M8 are done, 0d10ffb.)

**Where it stands.** S0 and S1 are closed. **S2 is CLOSED (16 November): every task reviewed, the final
whole-stage review done (no Critical), its single fix wave applied and re-reviewed** (review notes: `runs/sdd/s2/`). Nothing has been trained. S2's results, with figures:
[../S2_RESULTS.md](../S2_RESULTS.md); the partner guide: [../PLUG_IN_YOUR_CODE.md](../PLUG_IN_YOUR_CODE.md). The short version:

| Run | Result | Meaning |
|---|---|---|
| T5, drone model against the 12 Nov bag | FAIL | worst leg 0.120 m/s (gate 0.10; leg 3 is not a push), 63 % time off by 0.690 s (gate 0.10; mostly the held-setpoint method); model not refitted |
| T6, scripted reference | INFO, no gates | pure-rule half stands; Starling closeness spoilt by the wall bug (fixed in 17197a7) |
| T7, faster filter | ABORTED | stopped by hand for the wall fix |
| T8, faster filter | PASS (owner's 4-decimal ruling on `max_abs_dv_mps`) | 1,000 sweeps + `check_every` 8: 121,118 game-steps/s timed window (gate 100,000); whole game 90,121 INFO; staggered restarts NOT measured. Now in `configs/s2_game.toml` |
| T9, scripted reference on the fixed layer | INFO, no gates | the reference for later strategies. Pure half identical to T6. Crowded 5 v 3 near walls still reaches 0.75–0.80 m in 3-D: a LIMIT faithful to CMU's commander (filter wall-blind, fence after the filter), not a bug |

Design §7 done conditions: (1) game-rule tests PASS; (2) scoring tool on fixed scenarios PASS; (3) filter PASS (T8);
(4) stand-in trainer MOVED to S2b by the owner (16 November), not run; (5) partner guide DONE in part (the guide
exists and runs; the design's worked example uses the stand-in, so it comes in S2b, lead's ruling). Interface change 16 November: observation 69 → 71 numbers (zone centre at 69–70; central state 59 → 61); policy interface version 0 → 0.1 (`INTERFACE_VERSION`).

S1 in one line: T2 filter copy FAIL (accepted by the owner), T3 simulator fit FAIL (two clocks), real-log fit
exploratory, T4 INFO; details in [../S1_RESULTS.md](../S1_RESULTS.md).

Tests (Task 11, 16 November, laptop host, conda `env_isaaclab`, `PYTHONPATH=source`): `531 passed, 2 warnings in 398.78s` (full suite after the Task 11 document edits; the 2 warnings are matplotlib tight-layout notices from `scripts/make_s2_figures.py`). The partner leak test ran but checks nothing on this laptop: the local file has no number distinctive enough to scan (see §5).

1. `cd ~/AirStack-starling-max2/svg_training && claude`, then say: **"Run the train-start skill, read
   docs/claude/HANDOFF.md §0, and tell me what is waiting on me."**
2. **Next, in order.**
   - **S2 final review: DONE** (16 November): Opus (Fable was out of quota), no Critical; fix wave 4d0d409 (setting guard, honest leak test, committed wall probe `scripts/probe_wall_limit.py`, interface version 0.1, caveats, clip on the fixed walls); A/B wording c218cbb.
   - **Owner ruled, 16 November** (S2b plan, a7e4c2f): (A) the S2b games gate is now `closest_cross_3d_gap_max_m = 0.10`
     (Isaac Lab drones' 3-D closest approach at most 0.10 m below tier 1's on paired games without a start miss),
     replacing `physics_closest_cross_min_m = 1.0`, which failed by construction; (B) the training filter stays faithful
     to CMU's.
   - **S2b STARTED 16 Nov ~06:45** (build ledger `runs/sdd/s2b/progress.md`, briefs beside it): Tasks 1–2 DONE (20021af, 2d000bf, 7873811), Task 3 PX4 cascade done (a669df8, eea2d2e: + ModalAI 15 Hz yaw filter, + PX4 allocator saturation feedback), Task 4 physics backend done (f4ff5fb, 1a94f87), Task 5 done (Isaac Lab adapter; ledger T10 FAIL, accepted). **Night 16 Nov:** Task 9 stand-in trainer committed (dfc2211) + fix round 1 (7eb8241: Tanh-bounded policy; non-finite actions counted, refused by score.py, abort exit 3), re-review 5/5 ✅, five small findings queued as fix round 2; GPU pilot (pure, seed 1, not of record) running. Task 6 Isaac Lab video committed ad6a9ef (7 scripted clips + 3 stills in `docs/media/s2b_*`, 41 MB; four clips cut at 40 s with no result), task review running. **Night 16→17 Nov, later:** Task 6 complete (fix round 9832c51: two sidecars now say working tree unknown). Task 7 complete (413c713, 4eb6e55): ledger **T11 step tests FAIL** (real-log t63 worst 0.377 s, Isaac drone 0.05–0.13 s quicker than the real drone; tier 1 far slower than both — REAL tier-1 behaviour: fitted 1.72 m/s² acceleration cap eats the commander's 0.1 s feed-forward pulse, t63 ~0.9 s; owner's call), **T12 throughput INFO** (4,096 games: 2v1 162,510, 5v3 262,190 drone-steps/s; all > 20,000). Task 9 diagnosis (nine pilots, none of record, `runs/sdd/s2b/task-9-report.md`): cause of no learning = initial exploration noise (std 1.0 on a ±1 action box); init log std −1.6 + frozen noise on reward-free axes learns, but seed 1 ends 0.22 and seed 2 0.13 v straight → stand-in gate likely FAIL. Proposed `[standin_v2]` (100 M/seed) waits for the OWNER: (a) approve and run, accept a likely FAIL as the pipe-test result (lead recommends); (b) new learner/curriculum; (c) gate change. Diag-only flags 9471b61, 9964ac7. **Task 8 DONE (c4d722d, 17 Nov ~05:25): ledger T13 FAIL** — 36 of 60 cells over the 0.10 hold gap, every one with Guards holding less on the physics drone (worst 95.1 % → 0.3 %): Strike drones pass over or under Guards (43–64 % of physics games, 0 of 48,000 tier-1 games); tier 1 itself drops 97.5 % → 0 % held when the Strike starts 1 mm higher, so tier 1's scripted holds rest on exact equal heights. 4 random-Guard cells over the 0.10 m closest-approach gap (physics 0.12–0.23 m closer at the minimum; undiagnosed). 0 upsets, 0 NaN. Owner kept vertical passing (option a). Review: 2 Important fixed in round 1 (600464d: fail-closed upset/NaN gates; 1 mm diagnosis committed as `scripts/diag_vertical_pass.py` + `docs/notes/2026-11-17_s2b_vertical_pass_note.md`), re-review ✅ — Task 8 COMPLETE. **Task 10:** `docs/S2B_RESULTS.md` committed ee2a59f + newcomer fix round dee4cb8; root README links it (8d32cf0); stand-in section waits for the Isaac seeds. Isaac stand-in seed 3 goes to the 5090 (lead's ruling 05:52). **17 Nov ~01:30 (owner):** NUS MARMOT Lab's JAX training code shared (`~/ma_skills-area-denial-continuous-space-self-play`, partner-confidential, never committed); owner chose to run it unchanged tonight as the reference (`~/nus_jax_reference/`, conda env `nus_jax`, W&B off); later our PyTorch copy of their method must match it on 2-D rules before training on Starling/Isaac drones. Home RTX 5090 PC (Ubuntu 24.04) = future training workstation: checklist [../WORKSTATION_SETUP.md](../WORKSTATION_SETUP.md). **Port kit (17 Nov, owner porting next day):** `scripts/workstation/` (check_machine, setup_isaaclab_host with pinned `env_isaaclab_requirements.txt`, setup_nus_jax, run_nus_job, sync_results; all `--dry-run`, UNTESTED ON THE 5090), `tests/test_workstation_scripts.py` (29 pass), page rewritten; PRIVATE bundle `~/svg_workstation_bundle/` (99 MB, outside git: NUS code, tonight's two NUS checkpoints, reference logs, log103 flight log, NOTES.md with commands + sha256). Open for the 5090 evening: the remaining S2b Isaac stand-in seeds and their exact command go here once the laptop's overnight seeds finish (WORKSTATION_SETUP §2 step 4 points here); memory fraction 0.60 and an S0 config for 32 GB are PROPOSED, owner approves. Still to do: Task 10 docs (`docs/S2B_RESULTS.md`, being written 17 Nov from 05:30; then the root README row gets its link), Task 8b registered Isaac task DEFERRED to the next session / 5090 (lead's ruling), windowed screenshots last, S2b final review. OWNER DECIDED (16 Nov, before sleeping): accept T10's FAIL; use SIM-ONLY yaw-rate gains 0.25/0.2/0 (AirStack sim precedent CHG-0024; translation identical); construction-site world bought by the owner from CGTrader — rendered clips may be committed (never the asset files). Running S2b Tasks 6–10 overnight; Isaac spike done (bcad43e). Isaac launches: HEADLESS only, approved on the WiFi laptop by the owner (16 Nov, "yes dont worry about wifi"); windowed launches allowed too ("u can allow window launches"); default stays headless for runs of record. An early headless Isaac spike runs alongside Task 2.
   - **S2b** ([../plans/2026-11-16-s2b-isaac-lab-environment.md](../plans/2026-11-16-s2b-isaac-lab-environment.md)),
     approved with the owner's 7 answers (in the plan): the S2 game on rigid-body Starlings in Isaac Lab with PX4's
     cascade and the real gains; compare with tier 1; throughput; stand-in trainer on both backends (unchanged
     `[standin_gates]`); Isaac Lab MP4s; TensorBoard for every training run. Isaac headless only (WiFi-firmware crash risk).
   - **Before any training-time claim:** an INFO speed run with staggered game restarts (T8 did not measure it).
   - **Real flight with planned pushes (owner flies; PENDING; NEAR-962).** It gives the drone model its run of record;
     what to record: [../S1_RESULTS.md](../S1_RESULTS.md#what-the-owner-needs-to-do-next) (proposals only, authorises
     no flight). Then gates BEFORE the fit, the fit, a record, a ledger row and a named parameter file under `params/`.
3. **Owner's decisions so far** (all also in the plans):
   - 15 Nov night: NUS's strategy is the MAIN use; NEAR Lab's own strategies are a research SIDE QUEST; arena sizes
     vary; approach A; main game = **partner rules preset** with the Starling layer scored on top; contact tags only
     in the side quest; NUS's numbers only in the **git-ignored** `configs/local/` (the programme report is
     confidential; this repo may be public); speeds Strike 0.5, Guard 0.33 m/s. Fix the sim commander's wall clock in
     an AirStack session (note `~/Downloads/note-for-airstack-sim-clock-fix.md`); CMU need not be told about the
     position-setpoint gap; emergency push-apart differences accepted; owner labels `08_34_27.ulg`; no sim step session.
   - 15 Nov late night: "just execute the rest" = S2 plan and gates approved (`configs/s2.toml`), build it.
   - 16 Nov: `max_abs_dv_mps` gate compared at its 4 written decimals ("4 decimals. yes."); S2b approved, the S2
     stand-in trainer moves into S2b; replay media wanted (done, `docs/media/`) plus an Isaac Lab MP4 (S2b);
     TensorBoard for every training run (S2b plan); no Linear cycles or dates on pipeline issues; the project's Linear
     snapshot lives in `svg_training/docs/linear/`.
   - **Still to ask NUS (owner; NEAR-970):** metres per unit, seconds per step, which NUS project is the strategy to
     host, its inputs/outputs and software, code access; whether to tell NUS and UPenn about this pipeline.
   - Linear: project P-NEAR-31, S2 issues NEAR-963 game core, NEAR-964 bag check, NEAR-965 faster filter, NEAR-966
     scoring + opponents, NEAR-967 plug-in guide, NEAR-968 stand-in (now S2b), NEAR-969 S2 results page
     ([snapshot](../linear/snapshots/2026-11-16-project-plan-linear.md)); the snapshot's states predate Tasks 6–11.
4. Rules while building: write only inside `svg_training/`; commit finished, tested steps with explicit
   paths, never push (builder agents make no git writes; the lead commits); no `pip install`; Python is
   `~/miniconda3/envs/env_isaaclab/bin/python`; tests with `python -m pytest -q` from this folder.
   Owner rules of 15 November: every results page shows generated figures or a flowchart; plain language for
   a reader new to the topic; no change to flight or simulator code (STANDARDS §11).
5. Model use the owner prefers: the lead plans and reviews, cheaper models build. He expects usage
   limits to run out quickly, so **update the tables below after every task**, before starting the next.
6. A copy of this file is kept at `~/Downloads/claude-handoff-svg-training.md`; refresh it with
   `cp docs/claude/HANDOFF.md ~/Downloads/claude-handoff-svg-training.md` after each update.

**S2 progress** (plan: [../plans/2026-11-15-s2-game-and-plug-in.md](../plans/2026-11-15-s2-game-and-plug-in.md); build ledger `runs/sdd/s2/progress.md`, git-ignored, with every ruling and finding)

| Task | What | State |
|---|---|---|
| 1 | Configs, gates, git-ignored local partner file, leak test | done (`fc1a2bd`) |
| 2 | Game core: arenas, starts, motion, walls, zone, time-out, drop-outs, observations | done (`96894cc`..`fc19712`); 5 v 3 lab start miss ~1/3 = geometry, flagged and counted |
| 3 | Pair rules: push-apart (partner) and contact tags (side quest) | done (`3a174d1`) |
| 4 | Starling layer | done (`12ffaf7`..`04a5223`); exploratory-model limits: head-on 1.050 m, t63 0.6–0.9 s, ~9 s slow mode |
| 5 | Strategy contract and scripted opponents | done (`bf49b31`..`771f206`) |
| 6 | Match loop, metrics, scoring tool, scripted reference T6 (INFO) | done (`91746a6`..`27deb4f`); wall bug found in review, 3-D closest approach added |
| 7 | Faster filter: 7a accuracy (`df8a591`), 7b speed: T7 ABORTED, T8 PASS, wall fix | done (`17197a7`..`673536f`); `check_every` 8 in the game config (`f6702ca`) |
| 8 | Drone-model check on the 12 Nov bag, T5 FAIL | done (`f6f0a39`..`59e8ec4`) |
| — | Scripted reference re-run on the fixed layer, T9 (INFO) | done (`0467628`, `002a65b`); crowded-5 v 3 wall limit diagnosed |
| 9 | skrl and Gymnasium adapters, partner guide `docs/PLUG_IN_YOUR_CODE.md`; observation 69 → 71 | done (`c9faff3`..`911b3ae`) |
| 10 | Stand-in trainer | MOVED to S2b (owner, 16 November) |
| — | Replay clips (`docs/media/`) | done (`bcae60b`); the Starling clip predates the wall fix |
| 11 | Documents (S2_RESULTS, WHAT_WE_DID §7, GLOSSARY, README, CLAUDE.md, DESIGN §8 note, STANDARDS §4 sources, this file) | DONE (aedb076; final review fix wave 4d0d409, c218cbb) |

**S1 progress** (plan: [../plans/2026-11-15-s1-drone-model-and-safety-filter.md](../plans/2026-11-15-s1-drone-model-and-safety-filter.md); build ledger `runs/sdd/s1/progress.md`)

| Task | What | State |
|---|---|---|
| 1 | Config and approved gates (`configs/s1.toml`) | done (`92d30ac`) |
| 2 | Bag to CSV inside CMU's robot image | done (`cf239d0`) |
| 3 | Response model and fitting (NumPy reference) | done (`c4f77d0`) |
| 4 | Fit v0 on the existing teleop session | DONE, reviewed: run of record **T3 = FAIL** on 3 of 4 gates (`records/2026-11-15_s1_fit_v0_record.md`, figures in `docs/figures/s1_t3_*`). Main finding: on every 0.5 m/s push the sim drone peaks at ~85 % of the command, sags to 50–65 % while the command is still held, then drifts backwards ~25 % after release; no lag model can do that. CAUSE FOUND ([../notes/s1_two_clocks_cause.md](../notes/s1_two_clocks_cause.md), replay matches to 0.019 m/s): in the SIM the commander advances its teleop reference on the wall clock while PX4 runs 1.9× faster, so the drone outruns it (sim-only; real drone σ = 1). Recommendation for Task 6: copy the commander's teleop law in code with the time scale σ as a parameter, and fit only PX4's lag (setpoint → velocity; a first-order fit gives held-out RMS 0.036–0.047 m/s). Owner to confirm; running the commander on sim time inside AirStack is his call. Sim time scale this session 1.907 (ulog) |
| 5 | Designed step session in the AirStack simulator (Isaac starts once) | SCRIPTS DONE and committed after 5 fix rounds and a safety re-review (`runs/sdd/s1/task-5-rereview.md`: safe with the owner present, no open Critical/Important). 270 tests pass; dry run creates nothing. **Real session NOT RUN, held for the owner.** Conditions: launch detached (`setsid nohup bash scripts/record_steps.sh <name> > runs/<name>.out 2>&1 &`, about 7–11 min), and the owner confirms no real drone, mocap bridge or second ground station is on DDS domain 1. Expected (worked out with the old time scale 1.33; the measured one is 1.73–1.97, so more descents may be skipped or cut): 35 of 36 steps fly (one 2.0 m/s descent skipped by the floor guard), peak about 16.5 m in the sim. Since the final review the stick itself refuses (exit 67) unless the commander reports every drone in mode `sim` and no `/fmu/` topic is on the domain. Any other commander seen → exit 67, no `land`, no `down` |
| 6 | Fit v1 on the designed steps | REPLACED: the drone model's run of record comes from planned pushes at the next REAL flight (list in `records/2026-11-15_s1_real_px4_exploratory.md`); the sim step session is optional |
| 7 | Batched safety filter with team mask, parity run | built; run of record **T2 = FAIL** on 2 of 4 gates (`records/2026-11-15_s1_filter_parity_record.md`). DONE: reviewed (task review + re-review clean after one fix: a NaN in one team leaked into the other team; T2 numbers unchanged bit for bit); 28 tests pass; figures in the record. **Owner, 15 Nov: "if 1998/2000 checks passed its ok"** = T2 stays FAIL in the ledger, gates unchanged, and S1 goes on with this filter. The owner accepted T2 on 15 November ('if 1998/2000 checks passed its ok'); that figure is the emergency-agreement count. Re-confirmation on the counts above was asked the same day; **the owner confirmed (15 November, night: "yes ok")**. Background (corrected after the gatekeeper check, `runs/sdd/s1/gatekeeper-s1.md`): of the 1,779 scenes where CMU did not push apart, 13 are over the 0.02 m/s limit (3 over 0.1 m/s; the worst 2, 1.67 and 1.04 m/s, are where our copy pushed apart) and 109 over the 2e-3 residual limit (CMU's own filter is over it in 94); the speed failures are scenes where CMU needs its slow one-pair-at-a-time phase, and CMU's own answer stops up to 0.10 m/s short of the exact one. Options: re-define the two gates against the exact answer, add that slow phase (a pair loop), or accept FAIL. Also: 1,000 sweeps cost 582 ms per step for 4,096 games, about 7,000 game-steps/s (Task 7 estimate; T4 later measured 10,027 open / 7,938 full sensing), far too slow to train; Task 8 must measure a lower sweep count |
| 8 | Tier 1 with the fitted model and the filter | DONE, reviewed clean after 1 fix round. Real-drone chain in tier 1 (commander copy + exploratory PX4 response + team filter at the commander's CBF point; per-team speed cap, Guard = Strike ÷ 1.5). Run T4 = INFO (`records/2026-11-15_s1_tier1_fitted_filter_record.md`): 4,096 games, open/full sensing: filter off 2.27 M / 38.3 k game-steps/s; 1,000 sweeps 10.0 k / 7.9 k; 200 sweeps 48.4 k / 21.3 k. Finding (HYPOTHESIS for the real drone, owner told): the commander's CBF filters only the teleop velocity, the position setpoint up to 0.2 m ahead is not filtered, so teammates flown head-on reach 1.083 m (keep-out 1.10 m) in the copy |
| 9 | Hand-over | DONE: [../S1_RESULTS.md](../S1_RESULTS.md) written (10 figures, route flowchart, run table, the owner's next steps); STANDARDS §5 rows and rules 3 and 8, new rule 10 (training model from real flight logs); WHAT_WE_DID §6–7, GLOSSARY, README, CLAUDE.md status; report `runs/sdd/s1/task-9-report.md` (local); tests `316 passed` at hand-over, `325 passed` after the final-review fixes. Gatekeeper reading of the S1 records done; its must-fixes applied |

**Owner, 15 Nov afternoon ("ok i will follow all ur reccomendations"):** (1) Task 6 = copy the commander's teleop law in code (time scale σ as a parameter, 1 for the real drone) + fit only PX4's lag; fit it from the sim first (label "simulator drone"), then from REAL flight logs, which is what training should use, plus small randomisation. The real-log fit is a NEW step outside the approved plan; first a read-only survey of ~/flight_logs/2026-11-1x ([../notes/s1_real_logs_survey.md](../notes/s1_real_logs_survey.md)). (2) Owner says no drone is up. The sim step session is still held: at 15:xx the laptop was on WiFi only (Ethernet down, 10.10.100.x, remote desktop active), which is the Isaac-start WiFi-crash setup; launch once on Ethernet or with the owner at the machine. SURVEY RESULT ([../notes/s1_real_logs_survey.md](../notes/s1_real_logs_survey.md)): the real drone gets position + velocity setpoints (px4_interface TRAJECTORY mode, CMU comment ~0.1 s lag), the sim gets velocity only through MAVROS (~0.7 s): a sim-fitted model would make training think the drone is sluggish. Real ulogs: setpoint 5 Hz, position 10 Hz, ≤0.5 m/s, no stick topic. Exploratory real fit on log103 (#36) DONE and committed (`records/2026-11-15_s1_real_px4_exploratory.md`, no gates, reviewed clean after one fix round): commander → px4_interface TRAJECTORY mode → PX4 1.14 `v_ff + 0.95·(p_sp − p)`; real σ = 1.01. After choosing the family on training legs only, held-out RMS 0.058 m/s, the SAME as the baseline 'drone flies the setpoint speed ~0.15 s later' (no delay: 0.095). So at ≤0.5 m/s the real drone ≈ setpoint delayed ~0.1–0.15 s; the model misses the overshoot (held-out peaks up to 1.31×) and the slow drift after release (−0.14×). Also found: MPC_XY_VEL_MAX is 3.0 m/s on both drones (docs/CONFIG.md said 20; fixed on the owner's request in AirStack commit 680cd1f); tilt limit 30° drone_1, 45° drone_2. Recommendation: sim step session deprioritised (it measures the wrong chain); the run of record for the drone model should come from designed steps at the next real flight with full-rate logging. (3) The commander's wall-clock bug is SIM-ONLY (the real drone runs in real time); fixing AirStack is the owner's call, not done here.

**S0 progress** (plan: [../plans/2026-11-14-s0-measure-throughput.md](../plans/2026-11-14-s0-measure-throughput.md))

| Task | What | State | Evidence |
|---|---|---|---|
| 1 | Skeleton, gates, record scaffolding | done | 3 tests pass; reviewed. Approved config sha256: [../GETTING_STARTED.md](../GETTING_STARTED.md#approved-sha256) (approved 15 November; replaced `959dc710…` of 14 November) |
| 2 | Analytic shapes | done | reviewed; maths checked independently. Known limit parked for S3: the 24-step ray march is conservative beside surfaces (`runs/sdd/progress.md`) |
| 3 | Distance field | done | reviewed; maths checked independently. Known limit parked for S3: the 24-step ray march is conservative beside surfaces (`runs/sdd/progress.md`) |
| 4 | World, range rays, line of sight | done | reviewed; maths checked independently. Known limit parked for S3: the 24-step ray march is conservative beside surfaces (`runs/sdd/progress.md`) |
| 5 | Placeholder response model, tier 1 benchmark environment | done | reviewed twice; 23 tests pass for Tasks 1–5. Review caught and fixed: Guard drones could reach Strike speed on diagonals (now capped at speed ÷ 1.5 in norm, with a test) |
| 6 | Timing harness, tier 1 benchmark script | done | reviewed (timing logic verified: no hidden sync, clock bounded by synchronises); one fix round (re-runs skip finished points instead of duplicating rows). Whole suite: 64 tests pass |
| 7 | Tier 2 benchmark (Isaac Lab) | done; FIRST RUN 15 Nov | smoke point in the container: 64 games × 2 drones, ~1,800–2,300 game-steps/s, 0 NaN, 2.5 % resets per step, repeats within 1 %. Found and fixed: `simulation_app.close()` spun forever after the rows were written; the script now always leaves with `os._exit` (commit `08107eb`) |
| 8 | Record and ledger from results and gates | done | 30 tests pass; reviewed with an attack list, two fix rounds. Reviews closed three ways the record could have shown a false PASS (NaN rate, missing NaN count, negative or duplicated rows). `make_record.py` needs `--seeds` |
| 9 | Run S0 on the laptop, record, gatekeeper | done: T1 = FAIL on one gate | `records/2026-11-15_s0_laptop_record.md`, ledger T1 (commit `1b50419`). Only `sweep_complete` failed: tier 2 point `t2_k1` at 64 games lost to an Isaac Sim start-up segfault (Kit telemetry thread, before project code). Gatekeeper: every number recomputes exactly from `results.jsonl`; record faults to fix in code for the next run: commit shown as `unknown` (no `.git` in the container) and stale "untracked" text; no status labels (MEASURED / PROPOSED) in the record; ledger date in container UTC. Owner decides: accept T1 and go to S1, or re-run S0 after the fixes |
| — | Owner's decision on T1 (15 Nov) | (the owner followed the recommendations) | T1 stands as FAIL as written; its numbers are used. Next, in order: (1) record fixes + automatic retry of an Isaac start-up crash (building); (2) the S1 plan for the owner's approval (research running); (3) documentation written with the technical-writer agent. The next S0 (on the workstation) should come out PASS |
| — | Owner, 15 Nov ("yup ok") | S1 plan approved with its gates; root README links the folder | S1 runs subagent-driven from `docs/plans/2026-11-15-s1-drone-model-and-safety-filter.md`; a training guide (headless and with the Isaac Sim window) is being written for when training exists (S2) |
| — | Owner, 15 Nov, before signing off for the night | "show it by showing generated graphs … (flowchart etc) to visualize the data" | Standing rule: every results or evidence page shows at least one figure generated by a committed script from the run's own data (and a flowchart where a process is explained). Apply to S0_RESULTS now and to every S1 record. He checks tomorrow |
| — | Owner, 15 Nov, same evening | "ensure that none of the real drone code or sim code in airstack is affected"; "provide explanation in non AI-ish terms … assume reader is new to this" | Verified by git: no commit of this work touches `AirStack/`, `tools/`, `patches/`, `mocap/`, `localisation/` or the drone parameters; now a definition-of-done check (STANDARDS §11). Plain-language rule added to STANDARDS §2; a plain-language pass and a new page `docs/WHAT_WE_DID.md` are being written. Applies to chat replies too |

Build bookkeeping (rulings, briefs, reports, snapshots) is in `runs/sdd/`; its ledger is `runs/sdd/progress.md`. `runs/` is git-ignored: these exist on this laptop only, so committed pages must not cite them (notes they need are copied to `docs/notes/`).
S0 was built before the folder was tracked: each task was reviewed from a file diff against a snapshot (`bash runs/sdd/tools.sh`).
Tasks 2–4 are built and reviewed together. No Isaac Sim launch before the lead checks `docker ps` and
that the owner is at the machine or on Ethernet.

What the final review found that matters to the owner: (1) a cold laptop GPU made two repeats differ by 22 % at the smallest sweep point, so warm-up becomes at least 50 steps AND 2 s (gates and config untouched); (2) one distance routine in the tier 1 stand-in dominated open-arena timing (being replaced, with a before/after measurement); (3) rows carry a hash of the code (`code_sha`), added while the folder was untracked; (4) `gnome-remote-desktop-daemon` holds 611 MiB of GPU compute memory on this laptop, a sign a remote-desktop session may be active.

**S0 results:** [../S0_RESULTS.md](../S0_RESULTS.md) (run of record T1; record
[../../records/2026-11-15_s0_laptop_record.md](../../records/2026-11-15_s0_laptop_record.md)). The tier 1 table of
14 November and its repeat-gate question are superseded: the owner approved the new config (timed window at least
200 steps and at least 2 s) on 15 November, and T1 passed the repeat gate.

**Packaging (14 November 2026, third round).** The folder is COMMITTED: `2daf942` on `main` (change-log
CHG-0068), mirror updated (one commit ahead of GitHub; the owner pushes after checking the repository is
private). It is a top-level component of the repository. `docker/build.sh` builds `svg-training:isaaclab-2.3.2` on NVIDIA's `nvcr.io/nvidia/isaac-lab:2.3.2`
(26 GB download, once) and adds pytest plus two launchers, `svg-python` and `svg-isaaclab`, that keep exit codes
(Isaac Sim's own `python.sh` turns every failure into exit 1). Tests: T1's test count is in
[../S0_RESULTS.md](../S0_RESULTS.md#the-fail). `scripts/run_s0.sh` works in both places
(`SVG_PY`, `SVG_ISAACLAB`, `SVG_IN_CONTAINER`). The partial run `runs/2026-11-14_s0_laptop/` (code hash
`e9a7b4407e58`) was not finished; T1 ran from the start as `2026-11-15_s0_laptop` (code hash `13bebe8bb138`).

State values: not started · building · built, in review · done (tests quoted) · blocked (why).

## 1. Summary

Jeremy (Robotics AI Engineer, NEAR Lab, ST Engineering) wants training for the Strike vs Guard game to
run in parallel on a GPU. On 14 November 2026 a first session read the flight stack and the programme
website, ran web research on drone training in Isaac Lab, proposed a pipeline, and the owner chose an
approach. This folder now holds the rules, the design, the research digest, the diagrams, and the
agents and skills for the work. Since then S0, S1 and S2 have been built and run (T1–T9), S2b built and run (T10–T14), and NUS's strategy ported (T15–T21, [WHAT_WE_DID_DAY_BY_DAY](../WHAT_WE_DID_DAY_BY_DAY.md)); **no strategy of ours has been trained** (NUS's policies were trained with NUS's code).

## 2. Read these first

| File | Why |
|---|---|
| [../../CLAUDE.md](../../CLAUDE.md) | hard rules, environment, how a session runs |
| [../../STANDARDS.md](../../STANDARDS.md) | interface, game specification, drone models, gates, records |
| [../DESIGN.md](../DESIGN.md) | seven stages, two tiers, four uses, build order |
| [../RESEARCH.md](../RESEARCH.md) | evidence with sources |
| [AGENTS_AND_SKILLS.md](AGENTS_AND_SKILLS.md) | which agent or skill to use for what |
| `~/Downloads/claude-handoff-vectorised-drone-training.md` | the earlier chat that started this (11 November 2026) |

## 3. Non-negotiables

1. Write only inside `svg_training/`. Ask the owner before anything outside it.
2. Never push. Commit finished, tested work with explicit paths (CLAUDE.md rule 2).
3. Drone numbers flow from the drone to the trainer, never back.
4. A simulator result is "observed in the training simulator", not "validated".
5. Gates before runs; never moved.
6. Programme wording: Strike team, Guard team, tag, reach the zone, drone team.

## 4. Current state

**State on 18 November 2026** (details in §0 and the results pages):

| Item | State |
|---|---|
| S2b | built through Task 8, not closed; T14 seed 3 queued for the 5090 (§5a); Task 8b and the S2b final review deferred |
| NUS port | Phases 1–4 done: T15, T16, T17 PASS; Phase 4 rows 1–3 (T18–T20) and 4, 5a, 5, 6 (T22–T24) INFO, the first row 4 attempt T21 ABORTED. The safety filter and 3-D undo NUS's push-based blocking (G19 v S20 43 → 740 → 983 of 1,000; Isaac Lab 979); a parked Guard team holds about half against S20. Phase 5 planned by the lead (route (b) and own-training pilots), not started; Phase 6 passes 1 and 2 done, every clip published ([WHAT_WE_DID_DAY_BY_DAY](../WHAT_WE_DID_DAY_BY_DAY.md)). The lab's NUS files are committed PROVISIONAL in `nus_provisional/` (decision 6, 19 Nov; installer `scripts/nus_install_provisional.sh`) |
| 5090 host env | `env_isaaclab` built with hand fixes (GETTING_STARTED step 5; the follow-ups in §5); NVIDIA's licence accepted (owner's choice) through the `EULA_ACCEPTED` file; `nus_jax` built; container image built, its suite not clean (§0, 17 Nov evening, item 5) |
| Preflight | 1024 MiB per foreign process in `isaac_preflight.sh` and `run_nus_job.sh`; `--approved-headless` approved on both machines (laptop 16 Nov, 5090 18 Nov) |

**Decided by the owner, 17–18 November 2026.**

| Decision | Choice |
|---|---|
| NUS's code on the workstation | allowed (owner, 17 Nov) |
| Two tracks | (1) area denial = the NUS port, contact-free, filter on every pair; (2) contact tag = a separate one-on-one track, DRAFT plan (17 Nov) |
| NUS port values | the hangar geometry decided by the lead from three reviews (owner asked agents to decide, 17 Nov); every PROPOSED gate approved before its run; Phase 1 FAIL accepted |
| Publication | NUS agreed: code details, settings and our results may be published; NUS's source code may not (18 Nov; STANDARDS §2) |
| Contact-tag track | may be described in public documents (18 Nov; STANDARDS §2) |
| GPU limit, WiFi | 1024 MiB per foreign process; headless over WiFi approved on the 5090 (18 Nov) |
| Phase 4 | all seven plan answers accepted (18 Nov ~05:00); core hook `SvgGame._draw_starts` approved |
| Root edits | root `README.md` and root `CLAUDE.md` svg_training rows (status and pointers only, 18 Nov) |
| Phase 5 (~12:20) | delegated to the lead (owner, 18 Nov): route (b), our PyTorch copy of NUS's method with a 2-D method match first; 3-D with the filter; hangar geometry kept; gates before any run ([WHAT_WE_DID_DAY_BY_DAY §12](../WHAT_WE_DID_DAY_BY_DAY.md#12-next-steps-the-phase-5-plan)) |
| Own training (~12:30) | "explore to see if we can train ourselves": time-boxed pilots, not of record, training our own Guard policy on tier 1 with the filter and 3-D |
| Clips and hangar size (~14:10) | "just put all clips on the github … no need to keep it private": every NUS-port clip published; the 7.5 m arena and the usable flying box may be stated (the motion-capture camera survey is still not needed in the docs) |

**How to talk to the owner.** Start from the high-level picture, then go deeper step by step. Use
standard professional terms. Prefer simple diagrams and tables, readable at page width. He is new to
this simulation and training stack. He dislikes walls of text. He asked to be consulted before
anything uncertain is executed, and told about anything that could affect other sessions' work.

**Decided by the owner, 14 November 2026.**

| Decision | Choice |
|---|---|
| What the pipeline is for | team strategy; hosting partner strategies; low-level flight control; camera-based behaviour ("future work, not a priority at the moment") |
| Build approach | C: two tiers sharing one game ([DESIGN §4](../DESIGN.md)) |
| Isaac Lab version | 2.3.2 now; 3.0 later on the RTX 5090 machine |
| Folder | `svg_training` in the live clone `~/AirStack-starling-max2` (he first wrote "IssacLab") |
| Packaging (third round, same day) | "the point is to add a training pipeline to airstack": the folder is committed as a top-level component of the repository, like `localisation/`, with a `docker/` image carrying Isaac Lab (option A); its agents and skills are committed too ("yes commit agents") |
| Models | Fable orchestrates; if it runs out, Opus at high effort |
| Fourth round (15 November) | repository may be public ("its just a training pipeline doesnt need to be private"); new S0 config approved (timed window at least 200 steps and at least 2 s); Isaac Lab launch approved ("ok do it"; he is remote with the laptop behind him); after a tag both drones leave by default |
| Design | approved ("yup looks good"), with the four answers below |
| Tag | physical contact between a Guard drone and a Strike drone; no tag radius. His words: "the end goal is to have physical interdiction between strike team and guard team drones" |
| Safety filter | only between drones of the same team |
| Environments | "different real-ish environments", the construction-site world as the example; he asked for research on more realistic ones and whether it affects training |
| Velocity-step logs | this pipeline may run `tools/sim.sh` |
| Training hardware | "eventually" an RTX 5090, RTX PRO 6000 or RTX 6000 Ada |

The priority order among the four uses (strategy, partners, flight control, cameras) is Claude's
reading of his answer, not his words; confirm it if it matters.

**The earlier handoff's three open questions, answered.**

| Question | Answer |
|---|---|
| What is being trained? | the four uses above |
| Which Isaac Sim and Isaac Lab? | Isaac Sim 5.1.0, Isaac Lab 2.3.2 + 25 commits → the 2.x cloning API (`clone_environments`, `GridCloner`) |
| Which AirStack simulation profile, how many drones? | Isaac Sim + Pegasus + PX4 v1.16.1, three drones by default, PX4 time about 1.3 times wall-clock |

**Session 1 (14 November 2026): what was done.**
- Read `~/AirStack-starling-max2` and the website repository; six agents (two repository readers, one
  local Isaac Lab inspector, three web researchers).
- Checked that a new top-level folder cannot break another session's commit: the pre-commit hook reads
  staged paths only and the docs checker does not scan it.
- Built the diagram deck (10 slides) and, after the owner's choices, wrote `CLAUDE.md`,
  `STANDARDS.md`, `docs/DESIGN.md`, `docs/RESEARCH.md`, this file, six agents and six skills.
- Nothing outside this folder was edited. Nothing was committed.

**Session 1, second round (same day): what the owner's answers changed.**
- Contact tags and a per-team safety filter are now FIXED in STANDARDS §4. Contact distance in tier 1
  is 0.50 m, measured from the drone's USD.
- Three more research tasks: the construction-site world on disk, sources of realistic environments,
  and how clutter and contact change training. Results are in RESEARCH §9–10 and DESIGN §7.
- A realistic environment does affect training: drones lose sight of each other, cost rises, one
  layout is not enough, and sensing becomes the speed limit. DESIGN §7 has the environment ladder.
- Published comparisons found velocity-commanded drones touch an agile drone far less often than
  thrust-and-body-rate ones. S2 measures this here; the fallback is a final-approach skill on tier 2.
- Build steps keep their names S0–S5 but now carry environments: S2 open arena, S3 random blocks and
  columns, S4 the construction-site world with the tier 2 cross-check.

**Calls Claude made in that round, for the owner to correct:** a drone that touches a structure
leaves the game and avoiding structures is learned (the flight stack has no obstacle avoidance);
the policy senses its surroundings through range rays; files baked from the construction-site asset
stay out of git; real flights of a contact policy should start with a virtual contact distance.

**Facts found that the design rests on** (sources in STANDARDS §3–5 and RESEARCH):
- A strategy sends velocity + yaw rate in the world frame, 20 times a second, into the ground
  controller; today's plug-in point is `/svg/{name}/teleop_command`.
- The safety filter is one centralised node, about 550 lines of Python, keep-out 1.10 m.
- Isaac Lab 2.3.2 offers a multirotor at motor-thrust level, multi-agent environments and skrl's
  IPPO and MAPPO; it has no velocity controller and no self-play. Both are ours to build.
- Isaac Lab 3.0 (20 October 2026) adds batched velocity controllers and a velocity-command
  navigation task, needs Isaac Sim 6.2 and a newer GPU driver.
- No published throughput existed for quadrotor teams in Isaac Lab; S0 has since measured ours ([../S0_RESULTS.md](../S0_RESULTS.md)).
- The repository holds no Strike vs Guard game code.

## 5. Open items

### 5-phase5-2. Branch `nus-phase5-2` (19 Nov 2026): what stage 5.2 still needs

- `train-gatekeeper` read of the S1–S5 code and of `[gates.phase5_tier1_training]` (PROPOSED), then the freeze. Items to read: the
  opt-in v0.2 interface; the critic's missing reached flag (`critic_reached_flag`); the reward choices (sticky flag per tick, inside share
  at the decision's end, horizontal distances); `configs/nus_phase5_tier1.toml` (training cap 72 GPU-h OPEN, the INFO pairing lists,
  clamp tolerance 0.01 m); whether training may use the CUDA-graph filter (the evaluation always uses row 5's path, which C-1 needs).
- 5.1 PASS, then 5.1b and 5.1c (variants run only after it); 5.2 uses the cheapest variant that PASSES. At P0's rates only 5.1c with the
  three seeds side by side fits 72 GPU-h (about 35 h, plan §8); three seeds in **one process** is not built; separate processes need
  `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` plus `--memory-fraction`, tested on the GPU first.
- Copy the Phase 4 `row_5/` and `row_6/` `scores.json` and `per_game.npz` (sha256 pinned in the gate table) into this worktree's
  `runs/nus_port/phase4/`; the evaluation refuses without them.
- The plan's S6–S9 and D1 (runs, evaluation, 5.3, docs) are not started.

### 5-naming. Branch `docs-naming` (19 Nov 2026): what is still open

- Merge to `main` (the lead) and the owner's read of the front page. The figure `docs/figures/nus_phase4_ladder.png` still
  says "row" on its axis (its caption maps row N = Test N); redrawing it needs all ten Phase 4 `scores.json` (5090 only).
- TRAIN_A_GUARD's GPU run and the Parked Guard re-score are not verified from a fresh clone.

### 5-release. Branch `nus-release` (19 Nov 2026): what is still open

- The docs restructure for NUS is applied on this branch (19 Nov): front door `README.md`, `docs/WHAT_WE_FOUND.md`,
  `docs/RUN_IT_YOURSELF.md` (the verified fresh-clone commands), `docs/README.md` (page map, labels, history), `records/README.md`,
  four after-the-fact INFO records (T35–T38; T34 unused: the P1b rerun takes the next free number when it ends), the agents and skills no longer call
  `configs/local/` and `runs/nus_port/` 5090-only. Not done: the S1/S2/S2b owner to-do sections stay on their pages
  (other pages link their anchors).
- Not in the bundle: `runs/nus_port/w3/reference/` (only `--cuda-parity` needs it), the 223 MB Phase 5 one-update exports
  (3 `test_nus_mappo` tests keep skipping), `configs/local/partner_rules.toml` (exists nowhere; 2 privacy scans skip).

### 5a. On the home RTX 5090: S2b stand-in seed 3 (ledger T14 is FAIL already; seed 3 completes the record)

**17 Nov 2026:** the 5090's host env is built (with hand fixes): setup in [../GETTING_STARTED.md](../GETTING_STARTED.md) (5090 column), record in [../WORKSTATION_SETUP.md](../WORKSTATION_SETUP.md) §2a. **18 Nov:** preflight decided (§2c: 1024 MiB, headless on WiFi approved); `--approved-headless` exits 0 when no other GPU job runs; the Phase 4 chain finished at 13:54 and the Isaac Lab clips at 14:33 (18 Nov), so the GPU is free unless a Phase 5 job has started.

Seeds 1–2 ran on the laptop (17 Nov, record `records/2026-11-17_s2b_standin_isaac_record.md`); both FAIL every gate
cell, so T14 is FAIL and seed 3 cannot change it, but it completes the record. From `svg_training/`, with
`export PYTHONPATH=source`, `P=~/miniconda3/envs/env_isaaclab/bin/python`, after `scripts/isaac_preflight.sh --approved-headless`,
inside `tmux`:

```bash
$P scripts/train_standin.py --headless --config configs/s2.toml --settings standin_v2 --seed 3 --name 2026-11-17_s2b_standin_isaac_seed3 --motion physics --eval-every-updates 80 > runs/2026-11-17_s2b_standin_isaac_seed3.log 2>&1
$P scripts/score.py --guard runs/2026-11-17_s2b_standin_isaac_seed3,random --strike strike_straight,strike_flank --sizes 2v1 --presets physics --batch-per-pair --games-per-band 1000 --seed 1003 --no-local --headless --out runs/2026-11-17_s2b_standin_isaac_seed3_score
$P scripts/score.py --guard guard_mark_edge --strike strike_straight,strike_flank --sizes 2v1 --presets physics --batch-per-pair --games-per-band 1000 --seed 1003 --no-local --headless --out runs/2026-11-17_s2b_standin_isaac_seed3_score_mark_edge
```

Bring the three folders back with `scripts/workstation/sync_results.sh` (one folder per call), then on the laptop
(where seeds 1–2 live; `runs/` is not in git) run:

```bash
G=runs/2026-11-17_s2b_standin_isaac
$P scripts/train_standin.py verdict --gates $G/gates.toml \
   --scores runs/2026-11-17_s2b_standin_isaac_seed1_score,runs/2026-11-17_s2b_standin_isaac_seed2_score,runs/2026-11-17_s2b_standin_isaac_seed3_score \
   --out $G/verdict_seeds_1_2_3
$P scripts/make_s2b_figures.py standin docs/figures/s2b_standin_isaac_curves.png runs/2026-11-17_s2b_standin_isaac_seed{1,2,3}
$P scripts/make_s2b_figures.py standin_bars docs/figures/s2b_standin_isaac_bars.png $G/verdict_seeds_1_2_3 \
   runs/2026-11-17_s2b_standin_isaac_seed{1,2,3}_score runs/2026-11-17_s2b_standin_isaac_seed{1,2,3}_score_mark_edge
```

Then amend the T14 record (it must name the
5090 and the commit seed 3 ran on). About 70 min training on a free laptop GPU; expect less on the 5090.

| Item | Who | Needed before |
|---|---|---|
| D1 reading of "one keep-out per team" (`push_rule = "block"`) against NUS's report; `shove` is the other switch | owner | a partner-rules result |
| Real-drone hazards, **HYPOTHESES, not flown, not fixed**: (1) CMU's commander runs the CBF (`swarm_commander.py` ~2140) before the keep-in fence (~2210), so a drone held at the fence may let another inside 1.10 m (T9 diagnosis, training copy); (2) the position setpoint is not filtered, teammates head-on 1.083 m in tier 1 (T4) | owner (tell CMU? test?) | the next multi-drone real flight near a fence |
| INFO speed run with staggered game restarts (T8 timed all games starting together) | Claude | any training-time claim |
| Phase 5, route (b) (decided by the lead, owner delegated, 18 Nov ~12:20): write the plan with its gates (method match in 2-D first, 3 seeds), have the gatekeeper read it, then build ([WHAT_WE_DID_DAY_BY_DAY §12](../WHAT_WE_DID_DAY_BY_DAY.md#12-next-steps-the-phase-5-plan)) | lead | before any Phase 5 run |
| Phase 5 own-training pilots (owner ~12:30): tier 1, hangar geometry, filter and 3-D, the stand-in trainer; Guard first against S20 and our scripted Strike, then self-play; not of record; videos on | lead | when the GPU is free of Phase 5 work |
| Message to NUS with the Phase 4 findings (the filter and 3-D break push-blocking), asking whether NUS retrains on their side in parallel | lead drafts, owner sends | soon |
| A flight-side height lock that removes over/under passing (an AirStack change, CHG entry) | owner + CMU | before a 3-D policy flies |
| Records and ledger rows for Phase 1, Phase 2a (benchmark, fixed-opponent runs), Run 0 and the self-play evaluation (today INFO from the 5090's private notes) | lead + owner | if they should count as runs |
| STANDARDS §4 row "Arena, lab scale" still says the keep-in fence is 4 × 4 × 4 m; `goal_two_ours.yaml:74-75` is ±3.25 m × 4 m (CHG-0072, owner 16 Nov). A flight-stack value: STANDARDS changes go through the owner | lead → owner | the next STANDARDS edit |
| Stale "kept local" wording after the owner's ~14:10 decision (the hangar size is public): `scripts/nus_isaac_clips.py:18` docstring and `configs/nus_hangar.template.toml` lines 1–3 (comments only; the `configs/local/` mechanism stays); `~/ma_skills-self-play/CLAUDE.md` rule 1 (5090 only: still lists the hangar size as never committed); the Phase 4 plan's answer 6 (historical, leave it or add a dated note). Not edited in pass 2 (a docs-only pass) | lead | the next code edit |
| `~/ma_skills-self-play/CLAUDE.md` rules 1 and 3 (5090 only) still say NUS values and videos never enter the repository: update them to STANDARDS §2 (18 Nov) | lead, on the 5090 | the next NUS session |
| Code and config comments still state the old rule ("never type/copy a partner value into a tracked file"): `configs/nus_{rules,deploy,hangar,interface}.template.toml` line 3; `scripts/nus_make_local_rules.py:63`, `scripts/nus_make_local_deploy.py:51` (the header they write into the local files); `scripts/nus_make_videos.py:10` (videos stay under `runs/`); `source/svg_training/nus/hangar.py:100`. True for code and configs (the mechanism), no longer for documents (STANDARDS §2, 18 Nov). Not edited in Phase 6 pass 1 because the Phase 4 chain runs this code | lead | the next code edit, after Phase 4 |
| Build the hand fixes into `setup_isaaclab_host.sh` (`flatdict` needs setuptools < 81; `isaaclab_rl` upgrades torch to CUDA 13 and leaves its libraries; unpinned drift), from the 5090's note of 17 Nov | owner decides | the next fresh install |
| Pin `warp-lang==1.14.0`, `tensordict==0.12.4`, `stable_baselines3==2.8.0`, `starlette==0.49.1`, `pandas==3.0.3` in `scripts/workstation/env_isaaclab_requirements.txt` | owner decides | the next fresh install |
| `tests/test_record_steps.py::test_refuses_existing_run_folder` needs `runs/` to exist (fresh clone: `FileNotFoundError`; docs say `mkdir -p runs`) | lead | — |
| The setup script could clear a ROS `PYTHONPATH` itself (`env -u PYTHONPATH`); its header still says `UNTESTED ON THE 5090` (the test `test_syntax_header_and_executable` requires that phrase: change both together) | lead | — |
| `msgpack` in the container image (and its `docs/record/CHANGES.md` line) | lead | the next image build |
| `docs/media/5v3_starling` clip and its README "known limit" line predate the wall fix (`bcae60b` < `17197a7`); regenerate or relabel | Claude | showing the clip outside the lab |
| A pair mask in CMU's safety filter, so that a contact tag can fly at all; and a flight safety case for deliberate contact | owner + CMU (outside this folder) | any flight of a contact policy |
| The zone's size and place in each world beyond S2 (S2 draws arena and zone sizes at random; partner zone ratio in the local file) | owner | S3 |
| What the real drone senses its surroundings with: a known map, or an on-board range sensor | owner | S3 |
| Control level for contact tags: stay at velocity, or add a final-approach skill at thrust and body rates | owner | side quest (S2 trained nothing with tags) |
| The real flight with planned pushes (NEAR-962; list: [../S1_RESULTS.md](../S1_RESULTS.md#what-the-owner-needs-to-do-next)); T5 shows the exploratory model rises too slowly | owner | the `real` parameter set's run of record |
| Metres per partner unit and seconds per step (NEAR-970): decided for the hangar, 0.40 m per unit and 0.60 s per step (NUS: the units are scaled to the arena; [WHAT_WE_DID_DAY_BY_DAY §3](../WHAT_WE_DID_DAY_BY_DAY.md#3-phase-0-answers-and-the-hangar-geometry)) | closed (lead, 17 Nov) | — |
| What a drone may observe about others (full state, or shared with delay and loss); S2 gives the full state behind the `obs_view` switch | owner + partners | S3 |
| How a drop-out is simulated | owner + partners | S4 |
| Written velocity contract with NUS and CMU (Linear NEAR-874, NEAR-875) | owner + NUS + CMU | use 2, S5 |
| Tell UPenn about this pipeline (NUS knows: Phases 0–4 ran on its code with its answers); UPenn already has an Isaac Lab environment | owner | early |
| Access to a training workstation (RTX 5090, RTX PRO 6000 or RTX 6000 Ada); its driver and Isaac versions (NEAR-959) | owner | S0 on that machine |
| Build and try the image on the training workstation (`docker/build.sh`, then `docker/run.sh`) | owner + Claude | S0 on that machine |
| A ROS 2 policy node inside the AirStack tree | owner (separate approval) | S5 |
| Rotor positions for tier 2: sim CAD or the drone's parameters | owner | S4 |
| Driver 595 with AirStack's Isaac Sim 5.1 | untested | any move to Isaac Lab 3.0 on a machine that also runs AirStack |

**Closed 16 November 2026:** licence of the construction-site asset. The owner bought it from CGTrader. Rendered
clips made from it may be committed; the asset files themselves never are.

**Not verified** (carry these as doubts, not facts): every published throughput estimate for Isaac Lab (S0 measured
ours: [../S0_RESULTS.md](../S0_RESULTS.md)); the
Isaac Lab 3.0 release details beyond what RESEARCH cites; the links in RESEARCH (collected by web
research agents; open one before quoting it outside the lab); the axis order of the inertia values;
the real drone's response above 0.5 m/s (S1 saw only up to 0.5 m/s, exploratory); the vertical response
(not fitted); whether the drone's PX4 build matches tag v1.14.0, which S1 read.

**Independent checks run in session 1.** A builder check of the design and a review by the agent that
wrote the agents and skills found five wrong statements (simulator speed cap, arena box, delay
figure, Isaac Lab velocity controller, one speed cap in the filter); all five are corrected in
STANDARDS and DESIGN. Their open questions are in the table above.

## 6. How to continue

**Keeping this file current (owner, 17 November 2026):** every session ends by updating §0 (a dated summary for the
owner and the next session, on whichever machine), §4, §5 and "Last updated", committed with the work on its branch;
the other machine merges it. NUS's settings and results may be written here since 18 November 2026 (STANDARDS §2);
NUS's source code and quotes from confidential programme reports may not. The NUS workspace on the 5090
(`~/ma_skills-self-play/`, private, 5090 only) keeps copies of this folder's agents, skills and STANDARDS, refreshed at
each session start by `sync_claude_setup.sh`; the laptop has none and needs none.

1. Run the `train-start` skill.
2. The design is approved. A change to it goes through the owner first.
3. S0, S1 and S2 are closed; S2b is built and waits on the owner's choices (§0 morning summary 17 Nov); the NUS port
   has finished Phase 4 and Phase 6 pass 2; next is the Phase 5 plan (route (b)) and the own-training pilots (§0, §5,
   [../WHAT_WE_DID_DAY_BY_DAY.md](../WHAT_WE_DID_DAY_BY_DAY.md#12-next-steps-the-phase-5-plan)).
   Build with `train-implementer`, test first, and have `train-gatekeeper` read each record.
4. One step at a time, S0 to S5. Each ends on a record and a ledger row.
5. For a design question, brief the adviser agents in parallel with the files, not your conclusion;
   reconcile; show the owner; then build.
6. Model split the owner prefers: the lead plans, orchestrates and reviews; other models execute.

## 7. Source material

| Source | Where |
|---|---|
| Flight stack, configs, records | this repository, read-only from here |
| Starling system identification | `isaac_sim/Starling 2 Max Sys ID Results - Slite.pdf` |
| Drone PX4 parameters | `starling_1_indoor_params.params` |
| Safety filter | `AirStack/robot/ros_ws/src/svg_ground_control/svg_ground_control/cbf_filter.py` |
| Ground controller | same package, `swarm_commander.py`, `trajectory.py`, `fence.py` |
| Programme, game, wording rules | `~/Documents/GitHub/Strike-Versus-Guard` (`content/programme/`, `STANDARDS.md`) |
| Programme reports | `~/Documents/GitHub/Strike-Versus-Guard-sources` — **confidential**: point to them, do not copy from them |
| Isaac Lab | `~/IsaacLab` (2.3.2), conda `env_isaaclab` |
| NUS's code (three branches), the private port plan, notes `_notes/`, probes `_probes/` (Run 0, self-play matrices, videos), NUS's outputs | `~/ma_skills-self-play/` — **5090 only**; on the laptop read [../WHAT_WE_DID_DAY_BY_DAY.md](../WHAT_WE_DID_DAY_BY_DAY.md) |
| NUS job logs and exact commands | `~/nus_jax_runs/*.log`, `*.cmd.txt` — **5090 only** |
| NUS local values, converted weights, Phase 4 rows | `configs/local/nus_*.toml`, `runs/nus_port/` in `~/AirStack-starling-max2-nus-port/svg_training/` — **5090 only** (git-ignored) |
| Linear plan snapshot | this project (P-NEAR-31): [svg_training/docs/linear/snapshots/2026-11-16-project-plan-linear.md](../linear/snapshots/2026-11-16-project-plan-linear.md) (folder layout: [../linear/README.md](../linear/README.md)); the flight-stack projects: `docs/linear/snapshots/2026-11-13-project-plan-linear.md` in this repository |
