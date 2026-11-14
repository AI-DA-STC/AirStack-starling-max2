# S0 Measure Throughput Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Record environment steps per second against number of games for both tiers, with and without obstacles and sensing, and write a compute budget for S2–S4 from those numbers.

**Architecture:** A pure-PyTorch package (`source/svg_training`) holds the world shapes, sensing and a minimal tier 1 game-less environment; it imports nothing from Isaac. One standalone Isaac Lab script holds the tier 2 measurement, with every Isaac call in `compat/isaaclab_232.py`. Both write the same `results.jsonl` rows; one script turns rows plus `gates.toml` into a record and a ledger row.

**Tech Stack:** Python 3.11, torch 2.7.0+cu128, pytest 9, Isaac Lab 2.3.2 on Isaac Sim 5.1 (conda `env_isaaclab`), TOML configs (`tomllib`).

**Spec:** [../DESIGN.md](../DESIGN.md) §4, §7, §8 (row S0); rules in [../../STANDARDS.md](../../STANDARDS.md).

**Status:** built and run; see [records/2026-11-15_s0_laptop_record.md](../../records/2026-11-15_s0_laptop_record.md) (T1) and [../S0_RESULTS.md](../S0_RESULTS.md). Written and approved (gates, decision rules, subagent-driven execution) 14 November 2026.

## Global Constraints

- Write only inside `~/AirStack-starling-max2/svg_training/`. Never edit `~/IsaacLab`, `AirStack/`, `tools/`, `isaac_sim/`, `localisation/`.
- No git writes of any kind (no add, commit, stash). The lead handles git on the owner's say-so. Where a task says "checkpoint", run the tests and report; do not commit.
- No YAML, `Dockerfile`, `docker-compose*` or `launch/` paths. Configs are TOML or Python.
- No `pip install`, no new dependency. Python is `~/miniconda3/envs/env_isaaclab/bin/python` (call it `$PY`). Tests find the package through `pythonpath = ["source"]` in `pyproject.toml`; scripts set `PYTHONPATH=source`.
- Everything that runs per step is a batched tensor operation: no Python loop over games, no `.cpu()`, no NumPy in the step (STANDARDS §6.1). Loops over a fixed small count (ray-march iterations, delay slots) are fine.
- `core/`, `worlds/`, `models/`, `envs/tier1*` and `bench/` import nothing from `isaaclab`, `isaacsim`, `omni` or `pxr`.
- GPU jobs: headless only; before starting, `docker ps` shows no AirStack simulator container and `nvidia-smi` is recorded. If a simulator is up, stop.
- Units in names (`_m`, `_mps`, `_s`); shapes in docstrings. `N` = games, `M` = drones per game, `R` = rays.
- Throughput is reported as environment steps per second (games × policy steps per second) together with games, drones per game, tier and GPU (STANDARDS §8); drone-steps per second is reported beside it.
- S0 numbers come from stand-ins and say so in the record: the tier 1 drone uses a placeholder lag and delay (STANDARDS §5 values, not a fit), the tier 2 airframe is Isaac Lab's ARL Robot 1, and **neither tier runs the safety filter** (its port is S1).
- Wording: "observed in the training simulator"; Strike team, Guard team, contact tag.

## Review Focus

1. **GPU timing without synchronisation** reports queue time, not compute time. Expected: every timed section ends with `torch.cuda.synchronize()` when on CUDA. Test in Task 6.
2. **Out-of-memory at a large sweep point** must not end the sweep. Expected: that point gets a row with `status = "oom"` and the sweep continues. Test in Task 6.
3. **Games that reset every step** (drones spawned inside a structure or in contact) make throughput meaningless. Expected: spawns are clear of structures and of each other; the reset fraction per step is recorded and, in the open world with zero commands, is 0. Test in Task 5.
4. **Degenerate geometry**: a ray starting inside a structure, a line-of-sight test from a drone to itself, a point outside the distance field. Expected: finite outputs, no NaN; range 0 inside a structure; a drone sees itself; outside the field counts as free space. Tests in Tasks 3 and 4.
5. **Tier 2 asset not reachable** (the ARL Robot 1 USD is fetched from NVIDIA's asset server on first use). Expected: a clear error naming the path and exit code 2, never a silent substitute. Check in Task 7.

---

## File Structure

```
svg_training/
  pyproject.toml                      pytest config only (pythonpath, testpaths)
  .gitignore                          runs/, __pycache__/, *.egg-info/
  configs/s0_benchmark.toml           the sweep: every case both scripts run
  source/svg_training/
    __init__.py
    worlds/shapes.py                  analytic signed distance: boxes, vertical cylinders
    worlds/field.py                   DistanceField: one grid on the GPU, trilinear look-up
    worlds/sensing.py                 World, range rays, line of sight
    models/placeholder.py             delay + first-order lag velocity response (stand-in)
    envs/tier1_bench.py               minimal tier 1 environment: step, contact, touch, reset
    bench/timing.py                   measure(), result rows, out-of-memory handling
    bench/record.py                   results + gates -> record text, ledger row
    compat/isaaclab_232.py            every Isaac Lab call for tier 2
  scripts/benchmark_tier1.py          runs the tier 1 cases of the sweep
  scripts/benchmark_tier2.py          runs ONE tier 2 case per process
  scripts/run_s0.sh                   pre-flight, then both benchmarks, then the record
  scripts/make_record.py              CLI around bench/record.py
  tests/                              one test file per module above (no Isaac needed)
  records/LEDGER.md  records/_template_record.md
  runs/                               git-ignored
```

---

### Task 1: Skeleton, gates and record scaffolding

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `source/svg_training/__init__.py` (and empty `__init__.py` in `worlds/`, `models/`, `envs/`, `bench/`, `compat/`), `configs/s0_benchmark.toml`, `records/LEDGER.md`, `records/_template_record.md`, `tests/test_skeleton.py`

**Interfaces:**
- Produces: `configs/s0_benchmark.toml` with tables `[gates]`, `[decisions]`, `[timing]`, `[[tier1]]`, `[[tier2]]` (below); importable package `svg_training`.

- [x] **Step 1: Write the failing test** `tests/test_skeleton.py`

```python
import tomllib, pathlib, importlib
ROOT = pathlib.Path(__file__).resolve().parents[1]

def test_package_imports_without_isaac():
    import sys
    importlib.import_module("svg_training")
    assert not any(m.split(".")[0] in {"isaaclab", "isaacsim", "omni", "pxr"} for m in sys.modules)

def test_sweep_config_is_complete():
    cfg = tomllib.loads((ROOT / "configs/s0_benchmark.toml").read_text())
    assert cfg["gates"] == {"tests_pass": True, "sweep_complete": True, "repeat_spread_max": 0.10, "nan_count_max": 0}
    assert cfg["timing"] == {"warmup_steps": 50, "timed_steps": 200, "repeats": 2}
    assert len(cfg["tier1"]) == 13 and len(cfg["tier2"]) == 8
    for case in cfg["tier1"]:
        assert set(case) == {"name", "guards", "strikes", "world", "n_obstacles", "n_rays", "line_of_sight", "num_games"}

def test_no_yaml_or_launch_paths():
    bad = [p for p in ROOT.rglob("*") if "runs" not in p.parts and (p.suffix in {".yaml", ".yml"} or p.name.startswith(("Dockerfile", "docker-compose")) or p.name == "launch")]
    assert bad == []
```

- [x] **Step 2: Run** `$PY -m pytest tests/test_skeleton.py -q` — expected: FAIL (no package, no config).

- [x] **Step 3: Create the files.** `pyproject.toml` holds only `[tool.pytest.ini_options]` with `pythonpath = ["source"]`, `testpaths = ["tests"]`. `configs/s0_benchmark.toml`:

```toml
# Written 14 November 2026, before any run. Never edited after the first result exists (STANDARDS §7.1).
[gates]            # S0 is a measurement: the gates check that the measurement is sound.
tests_pass = true
sweep_complete = true        # every case below has a row with status "ok" or "oom"
repeat_spread_max = 0.10     # |a-b| / mean of the two repeats of a case
nan_count_max = 0

[decisions]        # PROPOSED rules read off the numbers; not pass/fail.
budget_drone_steps = 2.0e9   # samples a published game with a few columns needed (RESEARCH §10)
tier1_bulk_min_drone_steps_per_s = 50000    # case t1_5v3_full: below this, bulk training needs the workstation
tier2_train_min_drone_steps_per_s = 20000   # best tier 2 case: below this, tier 2 is cross-check only

[timing]
warmup_steps = 50
timed_steps = 200
repeats = 2
```

followed by 13 `[[tier1]]` cases and 8 `[[tier2]]` cases:

| Tier 1 case `name` | guards | strikes | world | n_obstacles | n_rays | line_of_sight | num_games |
|---|---|---|---|---|---|---|---|
| `t1_1v1_open` | 1 | 1 | open | 0 | 0 | false | [256, 1024, 4096, 16384, 65536] |
| `t1_2v1_open` | 2 | 1 | open | 0 | 0 | false | same list |
| `t1_5v3_open` | 5 | 3 | open | 0 | 0 | false | same list |
| `t1_5v3_prim10` | 5 | 3 | primitives | 10 | 0 | false | same list |
| `t1_5v3_prim50` | 5 | 3 | primitives | 50 | 0 | false | same list |
| `t1_5v3_prim10_rays32` | 5 | 3 | primitives | 10 | 32 | false | same list |
| `t1_5v3_prim10_rays64` | 5 | 3 | primitives | 10 | 64 | false | same list |
| `t1_5v3_prim10_los` | 5 | 3 | primitives | 10 | 0 | true | same list |
| `t1_5v3_prim50_full` | 5 | 3 | primitives | 50 | 32 | true | same list |
| `t1_5v3_field` | 5 | 3 | field | 0 | 0 | false | same list |
| `t1_5v3_field_rays32` | 5 | 3 | field | 0 | 32 | false | same list |
| `t1_5v3_full` | 5 | 3 | field | 10 | 32 | true | same list |
| `t1_2v1_full` | 2 | 1 | field | 10 | 32 | true | same list |

Tier 2 cases, keys `name`, `drones_per_game`, `num_games`, `physics_dt_s = 0.005`, `substeps = 10`: `t2_k2` (2 drones; [64, 256, 1024, 4096]), `t2_k3` (3; same), `t2_k8` (8; [64, 256, 1024, 2048]), plus the same three at `physics_dt_s = 0.01`, `substeps = 5` (`t2_k2_100hz`, `t2_k3_100hz`, `t2_k8_100hz`), plus `t2_k8_250hz` (`0.004`, `12`; [64, 256, 1024]) and `t2_k1` (1 drone; [64, 256, 1024, 4096]). Each `num_games` entry is one process.

`records/LEDGER.md`: a title, one line "Training ledger; separate from the flight ledger `docs/record/LEDGER.md`", and an empty table `| # | Date | Simulator | Run | What | Result | Record |`. `records/_template_record.md`: first line `Simulator: <training simulator, tier N>`, then the STANDARDS §8 fields as headings.

- [x] **Step 4: Run** `$PY -m pytest tests/test_skeleton.py -q` — expected: 3 passed.
- [x] **Step 5: Checkpoint.** Report the test output. The lead takes `[gates]` and `[decisions]` to the owner for approval before Task 9.

---

### Task 2: Analytic shapes

**Files:** Create `source/svg_training/worlds/shapes.py`; Test `tests/test_shapes.py`

**Interfaces:**
- Produces:
  - `sdf_boxes(points_m: Tensor[N, P, 3], centre_m: Tensor[N, B, 3], half_m: Tensor[N, B, 3]) -> Tensor[N, P]` — signed distance to the nearest axis-aligned box; `+inf` when `B == 0`.
  - `sdf_cylinders(points_m: Tensor[N, P, 3], base_m: Tensor[N, C, 3], radius_m: Tensor[N, C], height_m: Tensor[N, C]) -> Tensor[N, P]` — vertical cylinders standing on `base_m`; `+inf` when `C == 0`.

- [x] **Step 1: Write the failing tests**

```python
import torch
from svg_training.worlds.shapes import sdf_boxes, sdf_cylinders

def test_box_distances():
    c = torch.zeros(1, 1, 3); h = torch.tensor([[[1.0, 1.0, 1.0]]])
    p = torch.tensor([[[3.0, 0, 0], [0, 0, 0], [1.0, 0, 0], [2.0, 2.0, 0]]])
    d = sdf_boxes(p, c, h)
    assert torch.allclose(d, torch.tensor([[2.0, -1.0, 0.0, 2 ** 0.5]]), atol=1e-6)

def test_cylinder_distances():
    base = torch.zeros(1, 1, 3); r = torch.tensor([[0.5]]); hgt = torch.tensor([[2.0]])
    p = torch.tensor([[[1.5, 0, 1.0], [0, 0, 1.0], [0, 0, 3.0]]])
    assert torch.allclose(sdf_cylinders(p, base, r, hgt), torch.tensor([[1.0, -0.5, 1.0]]), atol=1e-6)

def test_no_shapes_is_free_space_and_batched():
    p = torch.rand(7, 5, 3)
    assert torch.isinf(sdf_boxes(p, torch.zeros(7, 0, 3), torch.zeros(7, 0, 3))).all()
    assert sdf_boxes(p, torch.zeros(7, 4, 3), torch.ones(7, 4, 3)).shape == (7, 5)
```

- [x] **Step 2: Run** `$PY -m pytest tests/test_shapes.py -q` — expected: FAIL (module missing).
- [x] **Step 3: Implement** both functions with the standard exact box and capped-cylinder distance formulas, broadcasting `points[:, :, None, :]` against shapes `[:, None, :, :]`, then `min` over shapes.
- [x] **Step 4: Run** the tests — expected: 3 passed.

---

### Task 3: Distance field

**Files:** Create `source/svg_training/worlds/field.py`; Test `tests/test_field.py`

**Interfaces:**
- Produces:
  - `class DistanceField` with attributes `grid: Tensor[X, Y, Z]`, `origin_m: Tensor[3]` (world position of voxel `[0,0,0]` centre), `voxel_m: float`; method `sample(points_m: Tensor[..., 3]) -> Tensor[...]` (trilinear, same dtype as `points_m`); points outside the grid return the nearest border value.
  - `synthetic_field(size_m: tuple[float, float, float] = (80.0, 80.0, 20.0), voxel_m: float = 0.2, n_boxes: int = 60, seed: int = 0, device="cpu", dtype=torch.float16) -> DistanceField` — a grid the size of the construction-site 40 m crop, filled from random boxes with `sdf_boxes`, centred on the origin in x and y, floor at z = 0. Built in chunks so that it fits in 2 GB while building.

- [x] **Step 1: Write the failing tests**

```python
import torch
from svg_training.worlds.field import DistanceField, synthetic_field

def _ramp():
    g = torch.arange(4.0)[:, None, None].expand(4, 3, 2).contiguous()   # value = x index
    return DistanceField(g, origin_m=torch.zeros(3), voxel_m=0.5)

def test_sample_at_voxel_centres_and_between():
    f = _ramp()
    pts = torch.tensor([[0.0, 0, 0], [0.5, 0.5, 0.5], [0.25, 0, 0], [1.5, 1.0, 0.5]])
    assert torch.allclose(f.sample(pts), torch.tensor([0.0, 1.0, 0.5, 3.0]), atol=1e-5)

def test_outside_returns_border_value_and_is_finite():
    f = _ramp()
    out = f.sample(torch.tensor([[-10.0, 0, 0], [99.0, 0, 0]]))
    assert torch.allclose(out, torch.tensor([0.0, 3.0])) and torch.isfinite(out).all()

def test_any_leading_shape():
    assert _ramp().sample(torch.zeros(5, 8, 32, 3)).shape == (5, 8, 32)

def test_synthetic_field_size():
    f = synthetic_field(size_m=(8.0, 8.0, 4.0), voxel_m=0.2, n_boxes=5)
    assert tuple(f.grid.shape) == (40, 40, 20) and f.grid.dtype == torch.float16
    assert (f.grid < 0).any() and (f.grid > 0).any()
```

- [x] **Step 2: Run** — expected: FAIL.
- [x] **Step 3: Implement.** `sample` uses `torch.nn.functional.grid_sample(mode="bilinear", padding_mode="border", align_corners=True)` on the grid viewed as `[1, 1, Z, Y, X]`; mind that `grid_sample` takes coordinates in `(x, y, z)` order mapped to the last three dimensions reversed. The grid is cast to float32 once at construction if the device lacks float16 `grid_sample`; record which in `self.sample_dtype`.
- [x] **Step 4: Run** — expected: 4 passed.

---

### Task 4: World, range rays and line of sight

**Files:** Create `source/svg_training/worlds/sensing.py`; Test `tests/test_sensing.py`

**Interfaces:**
- Consumes: Task 2 `sdf_boxes`, `sdf_cylinders`; Task 3 `DistanceField`.
- Produces:
  - `@dataclass class World`: `field: DistanceField | None`, `box_centre_m: Tensor[N, B, 3]`, `box_half_m: Tensor[N, B, 3]`, `cyl_base_m: Tensor[N, C, 3]`, `cyl_radius_m: Tensor[N, C]`, `cyl_height_m: Tensor[N, C]`; method `sdf(points_m: Tensor[N, P, 3]) -> Tensor[N, P]` = minimum of the field and the per-game shapes (`+inf` if there is neither).
  - `ray_directions(n_rays: int) -> Tensor[R, 3]` — `n_rays - 2` unit vectors on a horizontal ring, then straight up, then straight down; `n_rays == 0` returns shape `(0, 3)`.
  - `cast_rays(world: World, origin_m: Tensor[N, M, 3], dirs: Tensor[R, 3], max_range_m: float = 10.0, n_steps: int = 24) -> Tensor[N, M, R]` — sphere tracing with a fixed step count; 0 where the origin is inside a structure; capped at `max_range_m`.
  - `line_of_sight(world: World, pos_m: Tensor[N, M, 3], n_steps: int = 24) -> Tensor[N, M, M]` (bool) — True where the segment between two drones is clear; the diagonal is True.

- [x] **Step 1: Write the failing tests**

```python
import torch
from svg_training.worlds.sensing import World, ray_directions, cast_rays, line_of_sight

def _wall(n=2):   # a 0.4 m thick wall across x = 3, per game
    z = torch.zeros
    return World(None, torch.tensor([[[3.0, 0, 1.0]]]).expand(n, 1, 3), torch.tensor([[[0.2, 5.0, 5.0]]]).expand(n, 1, 3),
                 z(n, 0, 3), z(n, 0), z(n, 0))

def test_ray_directions():
    d = ray_directions(34)
    assert d.shape == (34, 3) and torch.allclose(d.norm(dim=-1), torch.ones(34))
    assert torch.allclose(d[-2], torch.tensor([0.0, 0, 1])) and torch.allclose(d[-1], torch.tensor([0.0, 0, -1]))
    assert ray_directions(0).shape == (0, 3)

def test_ray_hits_wall_at_known_range():
    o = torch.tensor([[[0.0, 0, 1.0]]]).expand(2, 1, 3)
    r = cast_rays(_wall(), o, torch.tensor([[1.0, 0, 0], [-1.0, 0, 0]]), max_range_m=10.0)
    assert r.shape == (2, 1, 2)
    assert torch.allclose(r[..., 0], torch.full((2, 1), 2.8), atol=0.02) and torch.allclose(r[..., 1], torch.full((2, 1), 10.0))

def test_ray_from_inside_structure_is_zero_and_finite():
    r = cast_rays(_wall(), torch.tensor([[[3.0, 0, 1.0]]]).expand(2, 1, 3), ray_directions(6))
    assert torch.isfinite(r).all() and (r == 0).all()

def test_line_of_sight_blocked_and_clear():
    p = torch.tensor([[[0.0, 0, 1.0], [6.0, 0, 1.0], [0.0, 2.0, 1.0]]]).expand(2, 3, 3)
    los = line_of_sight(_wall(), p)
    assert los.shape == (2, 3, 3) and los.dtype == torch.bool
    assert not los[0, 0, 1] and not los[0, 1, 0] and los[0, 0, 2] and los[0].diagonal().all()

def test_empty_world_sees_everything():
    z = torch.zeros
    w = World(None, z(1, 0, 3), z(1, 0, 3), z(1, 0, 3), z(1, 0), z(1, 0))
    assert line_of_sight(w, torch.rand(1, 4, 3)).all()
    assert (cast_rays(w, torch.rand(1, 4, 3), ray_directions(8), max_range_m=5.0) == 5.0).all()
```

- [x] **Step 2: Run** — expected: FAIL.
- [x] **Step 3: Implement.** `cast_rays`: travelled distance `t` starts at 0; each of `n_steps` iterations adds `clamp(sdf(origin + t·dir), min=0)`; rays whose distance drops below 0.01 m stop advancing. `line_of_sight`: same march along each of the `M·M` segments, clear when the march reaches the far end; force the diagonal True; build only the upper triangle if that is cheaper and mirror it.
- [x] **Step 4: Run** — expected: 5 passed.

---

### Task 5: Placeholder response model and the tier 1 benchmark environment

**Files:** Create `source/svg_training/models/placeholder.py`, `source/svg_training/envs/tier1_bench.py`; Test `tests/test_tier1_bench.py`

**Interfaces:**
- Consumes: Task 3 `synthetic_field`; Task 4 `World`, `ray_directions`, `cast_rays`, `line_of_sight`.
- Produces:
  - `class PlaceholderResponse(n_games, n_drones, dt_s=0.05, delay_s=0.15, lag_s=0.55, speed_cap_mps=4.0, device=...)` with `step(cmd_mps: Tensor[N, M, 3]) -> Tensor[N, M, 3]` (the velocity after a whole-step delay and a first-order lag) and `reset(mask: Tensor[N, M] bool)`. Values are STANDARDS §5 "response to a bare velocity command", marked placeholder; the fitted model replaces this class in S1.
  - `@dataclass class Tier1BenchCfg`: `num_games, guards, strikes, world ("open" | "primitives" | "field"), n_obstacles, n_rays, line_of_sight, dt_s=0.05, contact_m=0.50, body_radius_m=0.248, arena_half_m=(20.0, 20.0), height_m=(0.5, 8.0), seed=0, device="cuda"`.
  - `class Tier1BenchEnv(cfg)` with `M = guards + strikes`; `step(action: Tensor[N, M, 4]) -> dict` whose keys are `"pos_m" [N, M, 3]`, `"vel_mps" [N, M, 3]`, `"ranges_m" [N, M, R]`, `"visible" [N, M, M] bool`, `"tagged" [N, M] bool` (a Guard drone and a Strike drone closer than `contact_m`), `"touched" [N, M] bool` (distance to a structure below `body_radius_m`, or outside the arena box), `"reset_fraction"` (scalar tensor); attribute `world: World`. Tagged and touched drones are respawned in the same step at a random clear position (batched rejection: draw 8 candidates per drone, take the first that is clear of structures by 1 m and more than 1 m from every drone already placed in that game; if none, keep the last candidate and count it in `"bad_spawns"`).

- [x] **Step 1: Write the failing tests**

```python
import torch
from svg_training.models.placeholder import PlaceholderResponse
from svg_training.envs.tier1_bench import Tier1BenchCfg, Tier1BenchEnv

def test_delay_then_lag():
    m = PlaceholderResponse(1, 1, dt_s=0.05, delay_s=0.15, lag_s=0.55, speed_cap_mps=4.0, device="cpu")
    cmd = torch.tensor([[[1.0, 0, 0]]])
    v = [m.step(cmd)[0, 0, 0].item() for _ in range(40)]
    assert v[0] == v[1] == v[2] == 0.0 and v[3] > 0.0            # 0.15 s = 3 steps of pure delay
    assert abs(v[3 + 11] - 0.632) < 0.05                          # one lag time constant (0.55 s = 11 steps) later
    assert v[-1] < 1.0 and all(b >= a for a, b in zip(v, v[1:]))

def test_speed_cap():
    m = PlaceholderResponse(1, 1, speed_cap_mps=1.0, device="cpu")
    for _ in range(400): v = m.step(torch.tensor([[[30.0, 40.0, 0]]]))
    assert v.norm(dim=-1).max() <= 1.0 + 1e-4

def _env(**kw):
    base = dict(num_games=64, guards=2, strikes=1, world="open", n_obstacles=0, n_rays=0, line_of_sight=False, device="cpu")
    return Tier1BenchEnv(Tier1BenchCfg(**{**base, **kw}))

def test_shapes_and_finite():
    e = _env(world="primitives", n_obstacles=10, n_rays=32, line_of_sight=True)
    o = e.step(torch.zeros(64, 3, 4))
    assert o["pos_m"].shape == (64, 3, 3) and o["ranges_m"].shape == (64, 3, 32) and o["visible"].shape == (64, 3, 3)
    assert all(torch.isfinite(o[k]).all() for k in ("pos_m", "vel_mps", "ranges_m"))

def test_contact_tag_at_half_metre_between_teams_only():
    e = _env(num_games=2)
    e.pos_m[:] = torch.tensor([[0.0, 0, 2], [5.0, 0, 2], [0.49, 0, 2]])     # guard, guard, strike
    assert e.step(torch.zeros(2, 3, 4))["tagged"].tolist() == [[True, False, True]] * 2
    e.pos_m[:] = torch.tensor([[0.0, 0, 2], [0.0, 0.3, 2], [0.51, 0, 2]])   # guards 0.3 m apart; strike 0.51 m and 0.59 m away: no tag
    assert not e.step(torch.zeros(2, 3, 4))["tagged"].any()

def test_no_resets_when_hovering_in_open_world():
    e = _env(num_games=256)
    fr = [e.step(torch.zeros(256, 3, 4))["reset_fraction"].item() for _ in range(20)]
    assert max(fr[1:]) == 0.0

def test_spawns_clear_of_structures():
    e = _env(num_games=256, world="primitives", n_obstacles=50)
    assert (e.world.sdf(e.pos_m) > 0.248).all()

def test_seed_reproducible():
    a, b = _env(seed=3), _env(seed=3)
    act = torch.rand(64, 3, 4)
    assert torch.equal(a.step(act)["pos_m"], b.step(act)["pos_m"])
```

- [x] **Step 2: Run** — expected: FAIL.
- [x] **Step 3: Implement.** Action scaling: `action[..., :3].clamp(-1, 1) × cap`, Strike drones at `speed_cap_mps`, Guard drones at `speed_cap_mps / 1.5` (STANDARDS §4); the fourth channel (yaw rate) is accepted and ignored in S0. Position integrates the model's velocity. `world = "primitives"`: per game, `n_obstacles` split evenly between boxes (half-sizes 0.5–3 m) and cylinders (radius 0.2–1 m, height 2–8 m) placed uniformly in the arena. `world = "field"`: one shared `synthetic_field()` plus `n_obstacles` per-game shapes. Use one `torch.Generator` seeded from `cfg.seed` for every random draw.
- [x] **Step 4: Run** `$PY -m pytest tests/test_tier1_bench.py -q` — expected: 7 passed.

---

### Task 6: Timing harness and the tier 1 benchmark script

**Files:** Create `source/svg_training/bench/timing.py`, `scripts/benchmark_tier1.py`; Test `tests/test_timing.py`

**Interfaces:**
- Consumes: Task 1 config; Task 5 `Tier1BenchCfg`, `Tier1BenchEnv`.
- Produces:
  - `measure(step_fn: Callable[[], dict | None], warmup_steps: int, timed_steps: int, device: str) -> dict` with keys `steps_per_s`, `nan_count`, `mean_reset_fraction`, `peak_mem_mb` (0 on CPU). Calls `torch.cuda.synchronize()` before starting and before stopping the clock when `device` starts with `"cuda"`; resets and reads `torch.cuda.max_memory_allocated`.
  - `run_case(make_env: Callable[[], Any], step_of: Callable[[Any], Callable], case: dict, num_games: int, timing: dict, device: str) -> list[dict]` — one row per repeat; on `torch.OutOfMemoryError` returns one row with `status = "oom"` and frees the cache.
  - Row keys (both tiers): `tier, case, num_games, drones_per_game, repeat, status, env_steps_per_s, drone_steps_per_s, peak_mem_mb, nan_count, mean_reset_fraction, device, gpu_name, commit, date`.
  - CLI: `PYTHONPATH=source $PY scripts/benchmark_tier1.py --config configs/s0_benchmark.toml --out runs/<run>/results.jsonl [--device cuda] [--only <case>] [--max-games <n>]` (appends rows).

- [x] **Step 1: Write the failing tests**

```python
import json, subprocess, sys, pathlib, torch
from svg_training.bench import timing
ROOT = pathlib.Path(__file__).resolve().parents[1]

def test_measure_counts_steps_and_nans():
    calls = []
    def step():
        calls.append(1); return {"pos_m": torch.tensor([float("nan")]), "reset_fraction": torch.tensor(0.25)}
    r = timing.measure(step, warmup_steps=3, timed_steps=10, device="cpu")
    assert len(calls) == 13 and r["steps_per_s"] > 0 and r["nan_count"] == 10 and abs(r["mean_reset_fraction"] - 0.25) < 1e-6

def test_measure_synchronises_on_cuda(monkeypatch):
    n = []
    monkeypatch.setattr(torch.cuda, "synchronize", lambda *a, **k: n.append(1))
    monkeypatch.setattr(torch.cuda, "reset_peak_memory_stats", lambda *a, **k: None)
    monkeypatch.setattr(torch.cuda, "max_memory_allocated", lambda *a, **k: 0)
    timing.measure(lambda: None, warmup_steps=1, timed_steps=2, device="cuda")
    assert len(n) >= 2

def test_out_of_memory_becomes_a_row():
    def boom(): raise torch.OutOfMemoryError("x")
    rows = timing.run_case(boom, lambda e: (lambda: None), {"name": "c", "guards": 1, "strikes": 1}, 64,
                           {"warmup_steps": 1, "timed_steps": 1, "repeats": 2}, "cpu")
    assert len(rows) == 1 and rows[0]["status"] == "oom" and rows[0]["num_games"] == 64

def test_cli_smoke(tmp_path):
    out = tmp_path / "r.jsonl"
    subprocess.run([sys.executable, "scripts/benchmark_tier1.py", "--config", "configs/s0_benchmark.toml", "--out", str(out),
                    "--device", "cpu", "--only", "t1_2v1_open", "--max-games", "256"], cwd=ROOT, check=True,
                   env={"PYTHONPATH": "source", "PATH": "/usr/bin:/bin"})
    rows = [json.loads(l) for l in out.read_text().splitlines()]
    assert len(rows) == 2 and {r["status"] for r in rows} == {"ok"} and rows[0]["drones_per_game"] == 3
    assert rows[0]["drone_steps_per_s"] == rows[0]["env_steps_per_s"] * 3
```

- [x] **Step 2: Run** — expected: FAIL.
- [x] **Step 3: Implement.** `env_steps_per_s = steps_per_s × num_games`. The tier 1 step function draws `torch.rand` actions on the device inside the timed section (the policy's stand-in). `commit` comes from `git -C <repo> rev-parse --short HEAD` (read-only), `gpu_name` from `torch.cuda.get_device_name`.
- [x] **Step 4: Run** `$PY -m pytest tests/test_timing.py -q` — expected: 4 passed. Then the whole suite: `$PY -m pytest -q` — expected: 26 passed.

---

### Task 7: Tier 2 benchmark (Isaac Lab)

**Files:** Create `source/svg_training/compat/isaaclab_232.py`, `scripts/benchmark_tier2.py`; Test `tests/test_tier2_args.py`

**Interfaces:**
- Consumes: Task 6 `timing.measure` and the row keys.
- Produces:
  - `compat/isaaclab_232.py`: `build_scene(sim, num_games: int, drones_per_game: int, spacing_m: float = 12.0) -> tuple[InteractiveScene, list[Multirotor]]` and `step_scene(sim, scene, drones, thrust_n: list[Tensor[N, 4]], substeps: int) -> None`. This file is the only one that imports `isaaclab*`; importing it without Isaac running raises ImportError and nothing else imports it at module level.
  - `scripts/benchmark_tier2.py --case <name> --num-games <n> --config ... --out ...` runs **one** sweep point and appends its rows; exit code 2 with a one-line reason if the asset cannot be loaded.
  - `parse_case(cfg: dict, name: str, num_games: int) -> dict` in the script (pure, testable without Isaac): raises `KeyError` for an unknown case and `ValueError` when `num_games` is not listed for it.

- [x] **Step 1: Write the failing test** (`tests/test_tier2_args.py`): load `scripts/benchmark_tier2.py` with `importlib.util` (the script must not start Isaac at import; the launcher lives under `if __name__ == "__main__":`), then

```python
def test_parse_case(mod, cfg):
    c = mod.parse_case(cfg, "t2_k8", 1024)
    assert c["drones_per_game"] == 8 and c["physics_dt_s"] == 0.005 and c["substeps"] == 10
    with pytest.raises(KeyError): mod.parse_case(cfg, "nope", 64)
    with pytest.raises(ValueError): mod.parse_case(cfg, "t2_k8", 4096)

def test_only_compat_imports_isaac():
    src = pathlib.Path("source/svg_training")
    offenders = [p for p in src.rglob("*.py") if "compat" not in p.parts and re.search(r"^\s*(from|import) (isaaclab|isaacsim|omni|pxr)", p.read_text(), re.M)]
    assert offenders == []
```

- [x] **Step 2: Run** — expected: FAIL.
- [x] **Step 3: Implement.** Before writing, read the local sources and follow them, not memory: `~/IsaacLab/scripts/benchmarks/benchmark_non_rl.py` (launcher pattern: `AppLauncher.add_app_launcher_args`, `AppLauncher(args)`, imports of `isaaclab` only after it), `~/IsaacLab/source/isaaclab_assets/isaaclab_assets/robots/arl_robot_1.py` (`ARL_ROBOT_1_CFG`, a `MultirotorCfg`), `~/IsaacLab/source/isaaclab_contrib/isaaclab_contrib/assets/multirotor/multirotor.py` (`set_thrust_target(target: Tensor[num_envs, num_thrusters])`, `write_data_to_sim`), and `~/IsaacLab/source/isaaclab_tasks/isaaclab_tasks/direct/shadow_hand_over/` (two assets per environment). The scene: a ground plane, and per game `drones_per_game` copies of `ARL_ROBOT_1_CFG.replace(prim_path="{ENV_REGEX_NS}/Drone_<k>")` spawned 1.5 m apart at 2 m height, `replicate_physics=True`, collision filtering left on. One 20 Hz step = set a random thrust near hover on every drone (`hover ± 10 %`, hover = mass × 9.81 / 4 read from the asset's data), then `substeps` physics steps; drones lower than 0.3 m or further than 5 m from their spawn are put back in one batched root-state write. The step function returns `{"pos_m": ..., "reset_fraction": ...}` so `timing.measure` counts NaNs and resets. The asset is NVIDIA's ARL Robot 1, a stand-in for the Starling: the row carries `"airframe": "arl_robot_1"`.
- [x] **Step 4: Run** `$PY -m pytest tests/test_tier2_args.py -q` — expected: 2 passed.
- [x] **Step 5: Smoke run** (GPU; do the pre-flight of the `train-run` skill first: `docker ps` shows no AirStack simulator, record `nvidia-smi`):

```bash
cd ~/AirStack-starling-max2/svg_training && conda run -n env_isaaclab --no-capture-output \
  env PYTHONPATH=source ~/IsaacLab/isaaclab.sh -p scripts/benchmark_tier2.py --headless \
  --case t2_k2 --num-games 64 --config configs/s0_benchmark.toml --out runs/smoke/results.jsonl
```

Expected: exit code 0 and 2 rows with `status "ok"`, `nan_count 0`, `mean_reset_fraction` below 0.05. If the asset download fails: exit code 2, report it, stop (Review Focus 5). Smoke rows are not results; `runs/smoke/` is deleted afterwards.

---

### Task 8: Record and ledger from results and gates

**Files:** Create `source/svg_training/bench/record.py`, `scripts/make_record.py`; Test `tests/test_record.py`

**Interfaces:**
- Consumes: Task 1 config (`[gates]`, `[decisions]`, the case lists); Task 6 row keys.
- Produces:
  - `evaluate(rows: list[dict], cfg: dict, tests_passed: bool) -> dict` with `gates: {name: {"limit", "observed", "pass"}}`, `decisions: {...}`, `missing: list[(case, num_games)]`, `overall: "PASS" | "FAIL"`.
  - `render_record(rows, cfg, verdict, meta: dict) -> str` — first line `Simulator: training simulator, tiers 1 and 2 (stand-in drone models, no safety filter)`; then purpose, commit, config path, model parameter set (`placeholder`), seeds, machine, the throughput tables (one row per case and number of games: mean of the repeats), the gates with PASS or FAIL, the decision rules with their inputs, and a budget line: `budget_drone_steps ÷ drone_steps_per_s` of case `t1_5v3_full` at its best `num_games`, in GPU-hours.
  - `ledger_row(n: int, meta, verdict) -> str`.
  - CLI: `scripts/make_record.py --results runs/<run>/results.jsonl --config configs/s0_benchmark.toml --tests-passed {yes,no} --name <date>_s0_<machine>` writes `records/<name>_record.md` and appends `T<n>` to `records/LEDGER.md`; refuses to overwrite an existing record.

- [x] **Step 1: Write the failing tests** with a fixture of synthetic rows built from the config (every case, two repeats, `env_steps_per_s = 1000 × num_games`):

```python
def test_complete_sweep_passes(rows, cfg):
    v = record.evaluate(rows, cfg, tests_passed=True)
    assert v["overall"] == "PASS" and v["missing"] == [] and all(g["pass"] for g in v["gates"].values())

def test_missing_point_fails(rows, cfg):
    v = record.evaluate([r for r in rows if not (r["case"] == "t1_5v3_full" and r["num_games"] == 4096)], cfg, True)
    assert v["overall"] == "FAIL" and ("t1_5v3_full", 4096) in v["missing"] and not v["gates"]["sweep_complete"]["pass"]

def test_oom_row_counts_as_present(rows, cfg): ...        # replace one point by a single status "oom" row -> still PASS
def test_repeat_spread_and_nan_fail(rows, cfg): ...       # one repeat 30 % apart -> repeat_spread_max FAIL; nan_count 1 -> FAIL
def test_tests_failed_fails(rows, cfg): ...               # tests_passed=False -> FAIL

def test_record_text(rows, cfg):
    txt = record.render_record(rows, cfg, record.evaluate(rows, cfg, True), {"machine": "laptop", "gpu": "RTX 5070 Ti", "commit": "abc1234", "date": "2026-11-15"})
    assert txt.splitlines()[0].startswith("Simulator: training simulator")
    assert "observed in the training simulator" in txt and "validated" not in txt
    for word in ("stand-in", "no safety filter", "GPU-hours", "PASS", "t1_5v3_full", "RTX 5070 Ti"): assert word in txt
```

- [x] **Step 2: Run** — expected: FAIL.
- [x] **Step 3: Implement.** A FAIL is written as FAIL; nothing in this module edits the config.
- [x] **Step 4: Run** `$PY -m pytest -q` — expected: all tests pass (34).

---

### Task 9: Run S0 on the laptop, record it, review it

**Files:** Create `scripts/run_s0.sh`, `runs/<date>_s0_laptop/` (git-ignored), `records/<date>_s0_laptop_record.md`; Modify `records/LEDGER.md`, `docs/claude/HANDOFF.md` (§4, §5)

**Interfaces:**
- Consumes: everything above.

- [x] **Step 1: Confirm the gates are approved.** The lead has the owner's approval of `[gates]` and `[decisions]` in `configs/s0_benchmark.toml` in the conversation. If not, stop here.
- [x] **Step 2: Write `scripts/run_s0.sh <name>`** (`set -euo pipefail`): (1) refuse to run if `docker ps --format '{{.Names}}'` lists an AirStack or Isaac container; (2) save `nvidia-smi` and `git rev-parse --short HEAD` into `runs/<name>/preflight.txt`; (3) copy the config to `runs/<name>/s0_benchmark.toml` and check it is byte-identical to the approved file's hash recorded in `preflight.txt`; (4) run the test suite and remember the result; (5) tier 1 sweep; (6) tier 2 sweep, one process per `(case, num_games)`, continuing after a non-zero exit and appending a row with `status "crash"` for that point; (7) `make_record.py`. An interrupt (Ctrl-C) writes `records/<name>_ABORTED_record.md` with what ran.
- [x] **Step 3: Run it** from a local terminal or over Ethernet (starting Isaac Sim over the remote desktop has crashed this laptop's WiFi firmware): `bash scripts/run_s0.sh $(date +%F)_s0_laptop`. Run it in the background and watch `results.jsonl` grow.
- [x] **Step 4: Read the record.** Check by eye: the open-world cases are the fastest; throughput per game falls as games rise once the GPU is saturated; reset fractions are small; no NaN. Anything odd goes to the `train-debug` skill, not into the record as a result.
- [x] **Step 5: Gatekeeper.** Dispatch `train-gatekeeper` on the record, the gates and the ledger. Every item PASS, or fix and re-check.
- [x] **Step 6: Update `docs/claude/HANDOFF.md`** §4 (what was observed, with the record's path) and §5 (remove "Compute budget", add what the decision rules say). State plainly: stand-in models, no safety filter, laptop only.
- [ ] **Step 7: Workstation.** When the owner gives access to a training workstation, repeat Steps 2–5 there with `<date>_s0_<machine>`; same config, new record, new ledger row.

---

## What S0 does not answer

- The safety filter's cost per step (its port is S1; the S1 plan repeats cases `t1_5v3_open` and `t1_5v3_full` with the filter on).
- Tier 2 with the Starling airframe, a PX4-style cascade, or the shared construction-site mesh (S4).
- Training speed with a policy network and learning updates in the loop (S2).
