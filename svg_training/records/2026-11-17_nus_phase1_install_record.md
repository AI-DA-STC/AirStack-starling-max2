Simulator: none (NUS's own test suite, CPU only). Not a flight result.

# 2026-11-17 NUS port, Phase 1: NUS's code installed as the reference (INFO, after the fact)

**INFO record, written 18 November 2026 from the logs and notes listed below; no ledger number at the time of the run.**
It records what ran on 17 November 2026. Nothing here was re-run to write it.

| Item | Value |
|---|---|
| Purpose | Phase 1 of the NUS port: install NUS's code unchanged in its own environment and run NUS's own tests, so that later phases compare against a working reference |
| Gate at the time | PROPOSED in the private port plan: "NUS's test suite: 0 failed". Not frozen in `configs/`; reported here as INFO |
| Date, machine | 2026-11-17, install log closed 18:29:55 (+08:00); the lab's RTX 5090 workstation; CPU only (`--skip-gpu-check`, `JAX_PLATFORMS=cpu`) |
| NUS code | branch `area-denial-continuous-space-self-play`, commit `2d2b904`, clean working tree; a clone outside every git repository of the lab |
| Command | `unset PYTHONPATH; scripts/workstation/setup_nus_jax.sh --skip-gpu-check <NUS clone>` (dry run read first) |
| Environment | conda `nus_jax`: Python 3.12, jax 0.10.2, flax 0.12.8 (the CUDA 13 build of JAX installed, the GPU not used) |
| Log | `~/svg_setup_logs/setup_nus_jax.log` on the workstation (not in git); script exit 5 = "installed, but some partner tests failed" |

## Result

| Check | Result |
|---|---|
| NUS's tests, CPU | **65 passed, 1 failed**, 42.8 s |
| The failure | `tests/test_jax_config.py:18` expects the Guard team's safety distance of an earlier NUS specification; NUS's config (`ma_skills/config/environment/area_denial_self_play.yaml:24`) has used another value since commit `7509c36`. NUS confirmed the test is out of date (17 November 2026). Not caused by the install |

## Verdict

INFO. Against the proposed gate the count is 1 failed, from a test NUS confirmed is out of date; the owner accepted that
cause on 17 November 2026 and the port went on. This grades our install, not NUS's code.

## Limits

- Not compared with an earlier reference install on the lab's laptop.
- At run time the environment also sees the user's `~/.local` packages unless `PYTHONNOUSERSITE=1` is set;
  `scripts/workstation/run_nus_job.sh` sets it for every later job.
- No training, no logging service, no GPU use. No videos: nothing was trained.

## Ledger

Row `T35` in `records/LEDGER.md` (INFO, after the fact).
