RECORD · SIM + DESK — research project; L4 is hand-carried real hardware (no flight). Nothing here flies. Codes, titles and "Done when" are Linear's, verbatim (Linear writes "Localisation"; repo prose writes "localization").

# HTX-R3 Multi-Drone Localisation (VO + UWB)

Question (Linear): Without mocap, which approach keeps drones positioned correctly relative to one another? · Where: literature, simulation, then real drones · [Linear project](https://linear.app/nearlab/project/htx-r3-multi-drone-localisation-vo-uwb-b4a877b2fd7c) · Linear snapshot: 2026-10-26 · Evidence: [LEDGER](../record/LEDGER.md) · Sim runs: [localisation/README.md](../../localisation/README.md)

### L0 · Literature review — DESK
**Purpose:** before building anything, find out what the field has already tried for multi-drone positioning without mocap. The review of 13 methods set the direction: each drone's own visual odometry plus UWB alignment as the baseline.
Linear (snapshot 2026-10-26): target 2026-10-22 · 100 % · no ledger row (deliverable, not a test)

| Issue | Title (Linear, verbatim) | Result | Evidence |
|---|---|---|---|
| NEAR-842 | Literature review with validation evidence | — | `localisation/reports/Multi drone localisation methods review.md` (13 methods; notes in `localisation/research_notes/`) |

### L1 · Team review pack — DESK
**Purpose:** the team and HTX need one readable pack of the evidence so far (literature, flat-world versus site cuVSLAM result, effort, open questions) to decide the direction.
Linear (snapshot 2026-10-26): 0 % · last ledger row feeding it: #16 (2026-10-22)

**Done when** (Linear's target, verbatim; a target, not a result): the review includes the literature table, flat-world versus construction-site cuVSLAM result, effort log, recommendation and open questions.

| Issue | Title (Linear, verbatim) | Result | Evidence |
|---|---|---|---|
| NEAR-843 | Results table: what was tested, what it showed | — | inputs: [#15, #16](../record/LEDGER.md); [HTX-R1.md](HTX-R1.md) S3/S4 table |
| NEAR-844 | Recommendation and open questions | — | — |
| NEAR-845 | Update the effort log | — | `localisation/results/effort_log.md` |
| NEAR-846 | Slides for the review | — | — |

### L2 · Three-drone dataset and UWB emulator — SIM ONLY (Isaac)
**Purpose:** a method can only be compared on data. This records three-drone flights with true positions and emulates UWB distances with realistic errors, so L3 has something to test against.
Linear (snapshot 2026-10-26): 0 % · no ledger row yet

**Done when** (Linear's target, verbatim; a target, not a result): cameras run on all three drones; hover, formation, crossing and a 10–15 min figure-8 are recorded with true positions; the emulator includes realistic noise, bias and blocked-line errors from the papers.

| Issue | Title (Linear, verbatim) | Result | Evidence |
|---|---|---|---|
| NEAR-847 | Cameras on all three sim drones, added one at a time with a GPU check | — | — |
| NEAR-848 | Record hover, formation, crossing and long figure-8 with true positions | — | — |
| NEAR-849 | UWB distance emulator between drones (noise, bias, blocked-line errors) | — | — |
| NEAR-850 | Drift injector to test many drones without many cameras | — | — |
| NEAR-851 | Run one public multi-drone dataset (MILUV) for a real-data result | — | — |

### L3 · Own visual odometry + UWB alignment — SIM ONLY (Isaac)
**Purpose:** the chosen baseline needs numbers: how well drones keep a shared frame from their own visual odometry plus UWB ranges, how fast it converges, and whether one or two tags per drone are needed.
Linear (snapshot 2026-10-26): 0 % · no ledger row yet

**Done when** (Linear's target, verbatim; a target, not a result): pairwise relative-position error over time, heading error and convergence time are measured; one versus two UWB tags per drone are compared.

| Issue | Title (Linear, verbatim) | Result | Evidence |
|---|---|---|---|
| NEAR-852 | Aligner: continuous frame alignment from positions and UWB distances | — | — |
| NEAR-853 | Measure pair error, heading error and convergence time | — | — |
| NEAR-854 | Compare one vs two UWB tags per drone | — | — |

### L4 · First real-hardware number — REAL HARDWARE, hand-carried (no flight)
**Purpose:** sim numbers are not enough for a hardware decision. One hand-carried run of the chosen camera, scored against mocap, gives the first real number.
Linear (snapshot 2026-10-26): 0 % · no ledger row yet

**Done when** (Linear's target, verbatim; a target, not a result): its trajectory is scored against Motive/mocap.

| Issue | Title (Linear, verbatim) | Result | Evidence |
|---|---|---|---|
| NEAR-855 | Hand-carry the chosen camera under mocap with cuVSLAM on the laptop | — | — |
| NEAR-856 | Score cuVSLAM against Motive | — | — |

### L5 · Scale to 10 sim drones — SIM ONLY (Isaac)
**Purpose:** the method must work for the swarm size the demo needs. Ten simulated drones show the error and the radio bandwidth cost.
Linear (snapshot 2026-10-26): 0 % · no ledger row yet

**Done when** (Linear's target, verbatim; a target, not a result): alignment runs on 10 simulated drones; error and UWB/WiFi bandwidth are measured.

| Issue | Title (Linear, verbatim) | Result | Evidence |
|---|---|---|---|
| NEAR-857 | Run the aligner on 10 sim drones | — | — |
| NEAR-858 | Measure error and UWB/WiFi bandwidth | — | — |
