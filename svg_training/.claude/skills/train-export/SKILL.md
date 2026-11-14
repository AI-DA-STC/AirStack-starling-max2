---
name: train-export
description: Use when handing a trained policy to AirStack. Only for a checkpoint that passed stages 3 and 4. Covers the policy file, interface.toml, a reload check and the record, then stops at the folder boundary.
---

# Export a policy

Do these in order. The export script (`scripts/`) is planned for build step S5.

## 1. Confirm the checkpoint qualifies
- A record exists showing PASS on the evaluation gates (stage 3) and on the tier 2 cross-check (stage 4).
- `train-gatekeeper` has read that record and returned no FAIL.
If either is missing, stop. Use `train-evaluate`.

## 2. Export the policy file
Write the policy to `runs/<date>_<name>/export/`. The policy runs once per drone on that drone's own
observation (STANDARDS §3 rule 2).

## 3. Write `interface.toml`
Required fields (STANDARDS §3 rule 1):
| Field | Content |
|---|---|
| interface version | the version the policy was trained against |
| observation layout and order | every entry, with units and frame |
| action scaling | `[-1, 1]` per axis to m/s and rad/s; the speed cap used |
| rate | commands a second (20 for version 0) |
| frames | world ENU |
| game config | name and file |
| drone-model parameter set | name and source log |
| git commit | of this folder's code |
| seed | the training seed |

A policy without a complete file is not handed over.

## 4. Reload and reproduce
```bash
cd ~/AirStack-starling-max2
~/IsaacLab/isaaclab.sh -p svg_training/scripts/export.py --headless   # planned; from build step S5
```
Load the exported files in a fresh process, feed the recorded observations, and check the outputs match
the recorded ones within a stated tolerance. Quote the output.

## 5. Write the record
`records/<date>_<name>_record.md` and a ledger row, as in `train-run` step 5. Name the training
simulator in the first line and say "observed in the training simulator".

## 6. Stop
Placing the files, or a ROS 2 policy node, in the AirStack tree is outside this folder and needs the
owner's approval in the conversation. Tell the owner the export is ready and what the next step needs.
Real flights follow `docs/PREFLIGHT.md` and `docs/RUNBOOK.md` of the repository; nothing here
authorises one.
