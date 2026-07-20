# AirStack — Starling Max 2 lab snapshot (code folder)

**What this folder is:** a frozen, working copy of CMU AirStack, taken 2026-07-20 from branch
`daniel/diffaero_ground_control` (commit `f544c743`) of
[castacks/AirStack](https://github.com/castacks/AirStack), **with our two local bug fixes
already applied** (camera-info init race in PegasusSimulator; swarm_commander logging crash —
patch files and explanations in [`../patches/`](../patches/), one level up in this repo).

**Why it exists:** insurance. `daniel/diffaero_ground_control` is a personal branch on CMU's
repo — it could be rebased, changed, or deleted at any time. This snapshot is the exact code
our Milestone 1 sim rehearsal succeeded on, so the lab can always rebuild a known-good setup.

**Differences from a normal AirStack clone:**

- Git submodules (PegasusSimulator, macvo, vdb_mapping, …) are included as **plain folders**
  — no `git submodule update` needed, and no `.gitmodules` file. Fully self-contained.
- Our two bug fixes are already in the code — do **NOT** re-apply the patches from
  [`../patches/`](../patches/) on top of this snapshot.
- Two machine-specific config files are excluded (credentials / per-machine config) and must
  be copied from an existing lab machine or created from their `*_TEMPLATE` neighbours:
  `simulation/isaac-sim/docker/omni_pass.env` and
  `simulation/isaac-sim/docker/user.config.json`.

**How to use it:** follow "Setting up AirStack on a NEW machine" in the
[repo README](../README.md) one level up and pick **Option B** — it copies this folder out to
`~/AirStack-diffaero` and continues from there (the submodule and patch steps don't apply to
this snapshot).
