Simulator: training simulator — our batched PyTorch replica of the partner's 2-D area-denial game, against recordings of the partner's own JAX environment (CPU). Not a flight result.

# NUS port, Phase 2: replica parity gate (run of record)

| Item | Value |
|---|---|
| Purpose | Show that our replica (`source/svg_training/nus/replica.py`) reproduces the partner's game step by step before the partner's policy is converted onto it (Phase 3) |
| Date, machine | 2026-11-17T23:27:13+08:00, home RTX 5090 workstation (CPU run), conda `env_isaaclab` (replica) and `nus_jax` (recordings) |
| Code | branch `nus-port-phase2` at `1e6499e0` plus this run's uncommitted gate files (`configs/nus_port.toml`, the two gate cases added to `tests/test_nus_replica.py`) — committed with this record |
| Partner code | NUS `area-denial-continuous-space-self-play` @ `2d2b904` (private clone on the 5090) |
| Gates | `configs/nus_port.toml` `[gates.phase2_replica_parity]`, written before the run (owner approval 17 Nov 2026) |
| Rules | git-ignored `configs/local/nus_rules.toml` (sha256 `dd22cc28ce2042f3…`, 3 v 3) and `nus_rules_5v3.toml` (`3d002f1f50566b43…`, 5 v 3); no partner value is written here |
| Recordings | `runs/nus_port/fixtures/gate_3v3.npz` (sha256 `b43dc8a0f077e9ea…`, seed 2026) and `gate_5v3.npz` (`84dc274f4bc650ba…`, seed 2027), 100 episodes each, recorded by `scripts/nus_record_fixtures.py` from the partner's environment (random and rule-exercising scripted actions) |
| Command | `cd svg_training; unset PYTHONPATH; PYTHONPATH=source ~/miniconda3/envs/env_isaaclab/bin/python -m pytest -q -s tests/test_nus_replica.py -k gate` (output: `runs/nus_port/gate_phase2_pytest.txt`) |

## Results

| Gate | Limit | gate_3v3 | gate_5v3 | Result |
|---|---|---|---|---|
| episodes | 100 | 100 | 100 | PASS |
| max position error per step (units) | ≤ 1.0e-4 | 3.8e-6 | 5.7e-6 | PASS |
| previous-position error | ≤ 1.0e-4 | 0 | 0 | PASS |
| reached flag and step counter equal at every step | equal | equal | equal | PASS |
| steps with each rule active (push / team cap / total cap / Guard boundary / reached flip) | ≥ 1 each | 8984 / 19303 / 2495 / 5289 / 36 | 9140 / 19573 / 1956 / 6534 / 31 | PASS |
| observation error (test's extra check; direction only where the vector is longer than 0.1 units) | ≤ 1.0e-4 | 5.7e-6 (direction 1.9e-5) | 7.6e-6 (direction 3.5e-5) | PASS |

**Gate result: PASS.**

Information, not gated: open-loop drift (the replica's own state from the recorded start, recorded actions only) stays
within 1e-4 units over the whole episode in 43/100 (3 v 3) and 44/100 (5 v 3) episodes, and the first reached step
matches in 91/100 and 87/100. Divergence comes from sustained near-hard contact between teams, where the partner's
very small smoothing amplifies float32 rounding; the per-step match rules out a rule difference.

## Limits

- Parity is with the partner's 2-D game only. Nothing here says how the partner's policy behaves on Starling-like
  drones (Phase 4) or in flight.
- Random starts are drawn by different random number generators (JAX vs PyTorch); starts are checked statistically by
  the unit tests, not episode by episode.
- The partner value scans in `tests/test_partner_privacy.py` skip on the 5090 (no private reference files): rerun on
  the laptop before merging.

## Ledger

Row `W1` in `records/LEDGER.md` (a workstation number; the laptop gives it the next T number when it merges,
WORKSTATION_SETUP §4).
