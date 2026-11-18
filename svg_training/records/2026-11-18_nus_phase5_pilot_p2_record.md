Simulator: training simulator, tier 1 (the hangar game of Phase 4 row 5: the all-pairs safety filter, the commander copy, delay and lag of the EXPLORATORY fitted drone model, drones free in height with the start-height jitter). Not a flight result.

# 2026-11-18 NUS port, Phase 5 pilot P2 (W13, W14): ABORTED by the lead (pilot, not gated, INFO record)

**Pilot, not gated, INFO record. Both attempts ABORTED by the lead; no training happened.** P2 (plan section 7: Guard
learners against the scripted Strike players, warm-started from P1's final networks) was stopped on purpose by the lead
(18 Nov 2026, Ctrl-C), because P1's learner held 0 of 1,000 games against S20 where the parked Guard holds about 43 %:
a warm start from P1 is uninformative (see `records/2026-11-18_nus_phase5_pilot_p1_record.md`). The lead's decision: no
pilot is relaunched until the learner set-up is diagnosed.

| Item | Value |
|---|---|
| Plan | `docs/plans/2026-11-18-nus-phase5-retraining.md` section 7, P2: `configs/nus_phase5.toml [pilot_p2]` (Strike team in equal game blocks: S20, ApfStrike, strike_straight, strike_flank), 32,768 games, hard cap 1.5 GPU-h including evaluations |
| Code | branch `nus-phase5`, commit `c74cb5b2` (code unchanged; only record files uncommitted) |
| Command | `scripts/train_standin.py --game nus_hangar --settings pilot_p2 --seed 101 --warm-start runs/nus_port/phase5/pilots/2026-11-18_nus_phase5_pilot_p1 --runs-dir runs/nus_port/phase5/pilots --device cuda` |
| Machine | home RTX 5090 workstation; GPU otherwise idle before each start (`scripts/isaac_preflight.sh --approved-headless` exit 0: `preflight_p2.txt`, `preflight_p2_run2.txt`) |
| Seeds | training 101, evaluation 1101 |

## The two attempts

| Ledger | Run folder | Start | Stop | Where it stopped | GPU hours |
|---|---|---|---|---|---|
| W13 | `2026-11-18_nus_phase5_pilot_p2` | 18:07:23 | 18:10:31 | in the start evaluation (after the 897 s evaluation estimate); stopped by the lead (Ctrl-C) | 0.052 |
| W14 | `2026-11-18_nus_phase5_pilot_p2_run2` | 18:11:11 | 18:12:49 | in the start evaluation (after the 801 s evaluation estimate); stopped by the lead | 0.027 |

The implementer read the first stop as an outside interrupt of unknown cause and relaunched once in its own process
session (run 2); the lead then stopped run 2 as well and asked that no pilot be relaunched.

- Last good step: none. Neither attempt reached a training update or finished an evaluation: no `curve.json`, no
  `agent.pt`, no videos. Each folder holds `interface.toml` (written before training) and the TensorBoard settings text
  (5090 only, git-ignored; folders kept, not deleted).
- The pilot's crash path wrote one line per attempt to `runs/nus_port/phase5/pilots/gpu_hours.log` ("CRASHED:
  KeyboardInterrupt"; the lines stay as written). The pilots' ledger stands at 1.540 of 6.0 GPU-h.
- Videos: none (no evaluation finished).

## Output

`runs/nus_port/phase5/pilots/2026-11-18_nus_phase5_pilot_p2{,_run2}/` and the logs
`runs/nus_port/phase5/pilots/2026-11-18_nus_phase5_pilot_p2{,_run2}.log` (5090 only). Ledger rows T27 and T28 (run on the home RTX 5090 as workstation rows W13 and W14 and renumbered at the merge into `main`).
