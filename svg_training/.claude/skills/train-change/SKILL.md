---
name: train-change
description: Use for any edit to code, a config or a document inside svg_training. Covers plan, boundary check, test first, edit, tests, wording, definition of done, hand-off notes and proof that nothing else changed.
---

# Change code, config or documents

Do these in order.

## 1. Plan in two lines
What changes, and how you will know it worked. If the change is more than a few files, write the plan
down and have `train-gatekeeper` read it before you build.

## 2. Confirm the paths are inside the folder
Every path you will write starts with `~/AirStack-starling-max2/svg_training/`. If one does not, stop
(see the list at the end). No `*.yaml`, `*.yml`, `Dockerfile`, `docker-compose*` or `launch/` path
(STANDARDS §9 rule 2): configs are Python or TOML.

## 3. Test first
Write the failing test, run it, watch it fail. `core/` and the tier 1 model are tested without
launching Isaac. Run the whole suite on the host and, for anything the container runs, inside it too
(`docker/run.sh '$SVG_PY -m pytest -q -W error -p no:cacheprovider'`).
```bash
cd ~/AirStack-starling-max2
python -m pytest svg_training/tests -q
```
Anything that needs Isaac Lab uses conda env `env_isaaclab`, headless, with `nvidia-smi` checked first.

## 4. Edit
Smallest change that makes the test pass. Batched tensors only in anything that runs in training
(STANDARDS §6.1). Isaac-specific calls go in `source/svg_training/compat/`.

## 5. Run the tests and quote the output
Same command as step 3. If no tests exist for this change yet, say "no tests exist" rather than "pass".

## 6. Check wording and labels
- Programme wording and "observed in the training simulator" (STANDARDS §2).
- Every new value has a status label: FIXED, MEASURED, PROPOSED or OPEN, with its source.
- The simulator is named wherever a result appears.

## 7. Definition of done (STANDARDS §11)
Walk the checklist: inside the folder; tests quoted; numbers traceable; labels; wording; run records
if a run happened; HANDOFF updated.

## 8. Update HANDOFF
`docs/claude/HANDOFF.md` §4 (what changed) and §5 (what is still open). Change the "Last updated" line.
If the change finishes, starts or reshapes a Linear issue, offer the owner an instruction file in
`docs/linear/updates/` (process and rules: `docs/linear/README.md`).

## 9. Prove nothing else changed
```bash
git -C ~/AirStack-starling-max2 status -sb
```
Only `svg_training/` entries from you may appear (plus `docs/record/CHANGES.md` for a `docker/` change).
Commit finished, tested work with explicit paths (CLAUDE.md rule 2); never push, never `git add -A`.

## Stop and ask the owner
- Any file outside `svg_training/`, including `~/IsaacLab` and the website repository.
- A change to the interface version (STANDARDS §3 rule 3).
- A new dependency.
- A GPU driver or Isaac Sim / Isaac Lab version change.
- Anything that would change a drone parameter, an AirStack config or the sim airframe.
