# svg_training — training pipeline for the Strike vs Guard game

Trains drone-team strategies (Guard team, Strike team) by playing thousands of games at once on one GPU,
so that a trained policy can then fly through AirStack on Starling 2 Max drones. A top-level component of
this repository, like `localisation/`; it does not change CMU's `AirStack/` tree.

**Status (14 November 2026):** design approved; build step S0 (throughput benchmark) built and reviewed;
nothing has been trained yet. Where it stands: [docs/claude/HANDOFF.md](docs/claude/HANDOFF.md) §0.

| Read | For |
|---|---|
| [docs/DESIGN.md](docs/DESIGN.md) | what the pipeline is, the two tiers, the build steps S0–S5 |
| [docs/pipeline/training-pipeline.pptx](docs/pipeline/training-pipeline.pptx) | the diagrams |
| [STANDARDS.md](STANDARDS.md) | the rules: policy interface, game, drone models, gates, records |
| [docker/README.md](docker/README.md) | running it in a container with Isaac Lab |
| [docs/RESEARCH.md](docs/RESEARCH.md) | the evidence, with sources |
| [CLAUDE.md](CLAUDE.md) | working on it with Claude (agents and skills in `.claude/`) |

## Run it

```bash
docker/build.sh                                  # once: NVIDIA's Isaac Lab 2.3.2 image + a few launchers
docker/run.sh '$SVG_PY -m pytest -q'             # the tests, inside the container
docker/run.sh                                    # a shell inside the container
```

The throughput benchmark is started by `scripts/run_s0.sh` (see its header and HANDOFF §0). Results go to
`runs/` (not in git); records and the training ledger to `records/`. Every number here was observed in the
training simulator; none is a flight result.
