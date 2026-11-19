INTERNAL · the rules of STE's learning track. **They add to [../STANDARDS.md](../STANDARDS.md), which still applies in
full.** Where they seem to conflict, the parent wins until the owner rules; a ruling is then written into the parent
(FIXED rows change only there).

# STANDARDS: STE learning track

## 1. Sources of truth, in order

1. The owner's latest word in the conversation, then written into [DISCUSSION](DISCUSSION_2026-11-19_20.md) (append-only).
2. [../STANDARDS.md](../STANDARDS.md) (programme rules, FIXED rows, gates, records, code, git).
3. [PLAN.md](PLAN.md), then the reference pages (ARCHITECTURE, WORK_BREAKDOWN, VALIDATION_QC, AUTOMATION,
   DOCS_AND_STATUS, CODING_PRACTICES). PLAN wins over the reference pages.

A decision is DECIDED only when the owner said so; a lead call is labelled LEAD CALL; everything else is PROPOSED or
OPEN. Never upgrade a label without the owner.

## 2. Pending rulings and how work proceeds before them

| Item | Until the owner rules |
|---|---|
| P1 tag radius 1.6 m (overturns parent §4 "main game has no tag", "no tag radius") | built behind a setting, off by default; INFO runs only; no run of record depends on it; ruled at gate G0 with L0's numbers |
| P2 filter option B (only the Guard swerves in Guard–Strike pairs) | the same; ruled at the L2 gate, when it is built and measured |
| D4 the AirStack approach | no AirStack change plan is acted on; specs only |
| P7 drone loss in the flight rules | drone loss is trained (it costs nothing in flight) but not claimed as a flight capability |
| P8 do attackers run the filter? | the robustness suite reports both cases |
| P9 team sizes (programme 2v1 and 5v3, NUS 3v3, demo 1v1) | L0 studies all four; no learner is sized until gate G0 |
| P10 environments (parent FIXED: realistic 3-D, construction-site world first) | open arena as the first build step only; not claimed as meeting the rule |
| P11 what the real demo must show | L0 reports scripted 1v1 baselines; no demo is promised |
| P12 zone radius against tag radius; what a tag costs (D2 revisit) | both ends are measured in L0 (`guard_survives_tag_prob` 0 and 1); ruled at G0 |

## 3. Rules that bind every task

1. **Off means identical.** Every new behaviour (delay/noise, drag, option B, tag, landing obstacles, drone loss) sits
   behind a TOML setting whose default reproduces today's output bit for bit. The equality test is written first.
2. **One change per gate.** A new behaviour is checked on its own against the previous state as control before the next
   is added.
3. **Gates before runs.** A gate file is written and hashed before the run and never edited after (parent §7).
   Positive controls must PASS and negative controls must FAIL before any result is read.
4. **Write only inside `svg_training/`.** AirStack, `~/IsaacLab`, NUS's clones are read-only. Running `tools/sim.sh`
   for velocity-step logs is the one approved exception, only in an owner-free window (P5).
5. **Vectorised.** No per-game Python loops in anything that runs during training (parent §6).
6. **Videos in every run**, recorded inside the run, with the Starling's own look in Isaac Lab clips (D9); every result
   shown in docs has a GIF that plays on GitHub.
7. **A training result is not a flight result.** "Observed in the training simulator"; never "validated".
8. **Privacy.** NUS's source code is never committed. Names of NUS individuals, private messages and the owner's private
   remarks are never written in this folder; they live in `~/ma_skills-self-play/_notes/` on the 5090.
9. **Git.** Worktrees from `main`; explicit-path staging; ff-only merges; never push, `git add -A`, `--no-verify` or
   `git stash`; the Co-Authored-By trailer on commits.

## 4. Names and labels

- Tasks: ID + plain name, always (`L2.1 Filter option B in the training copy`). Phases L0–L9; gate G0 = the owner's
  ruling at the end of L0; workstreams DOC-n, VID-n, AS-n (AirStack change plans).
- Test levels: T-U unit, T-I integration, T-Ii Isaac-marked, T-X tier cross-checks, T-S AirStack simulator, T-R real.
- Simulators by name: *STE game engine (tier 1)*, *Isaac Lab (tier 2)*, *AirStack simulator*, *real Starlings*.
- Status words: PLANNED, RUNNING, PAUSED, BLOCKED (on whom), DONE with verdict PASS / FAIL / INCONCLUSIVE / INFO /
  ABORTED.
- Terms defined in [DOCS_AND_STATUS](DOCS_AND_STATUS.md) §1.4 before first use in any reader page.

## 5. Roles

| Agent | May write | Never |
|---|---|---|
| lead (main session) | everything in `svg_training/`, commits, merges to local `main` | push; act on a human gate alone |
| `ste-orchestrator` | `status/state.json`, `status/RESUME.md`, launches per AUTOMATION §2.2 | spawn agents, schedule wake-ups, retry a gate verdict |
| `ste-software-engineer` | code and tests in its worktree | commit to `main`, move a gate, edit outside `svg_training/` |
| `ste-test-qc-engineer` | gate drafts, scores, QC reports | build what it scores, edit a gate after a run |
| `ste-technical-writer` | `status/*`, doc sections the lead names | invent numbers, push, pause or start jobs |
| `ste-architect` | nothing (read-only reviews) | — |
