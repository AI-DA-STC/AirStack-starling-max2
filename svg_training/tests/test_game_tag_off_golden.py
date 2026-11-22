"""STE task L0.9: with the study's tag switched off, the game plays exactly as before the tag existed.

The record (``tests/data/game_tag_off_golden.json``) was made from the commit BEFORE L0.9 (dec9d276, branch ste-l0.8).
It holds fingerprints (sha256 of each tensor's dtype, shape and bytes, stacked over 100 steps) of ten short runs of
``SvgGame``: partner and contact presets, pure rules and the Starling layer with the fitted drone, 3v3, 2v2 and 5v3, two
seeds each, drop-outs on, games of 40 ticks and a ``reset(seed)`` half-way, so every run crosses many auto-resets. Every
output is fingerprinted: positions, velocity, yaw, alive, step counts, the critic state, outcome, done, end step, both
rewards, every observation tensor and every info key.

Two tests use it (fix round 1 of L0.9, QC items I1 and I2):

- ``test_tag_off_game_bit_identical``: no ``[tag]`` table (the default) plays as dec9d276.
- ``test_tag_off_but_present_is_the_same_game``: a game file whose ``[tag]`` table is present with ``mode = "off"`` and
  other values (radius 0.5 m, Guard survives 0.5) plays the same game: the switch off means nothing else is read.

Measured 21 Nov 2026 on the laptop (Intel Core Ultra 9 275HX), from dec9d276: whole-number and yes/no outputs are the
same under PyTorch CPU capabilities AVX2 (native) and NO AVX (``ATEN_CPU_CAPABILITY=default``); decimal outputs
(positions, velocity, observations, ...) differ in the last bits. So whole-number fingerprints are one record for every
CPU, decimal ones one record per capability (AVX2, NO AVX). On a CPU whose capability has no record (the home RTX 5090
is believed to report AVX512), the check does not skip: it re-runs itself in a subprocess under
``ATEN_CPU_CAPABILITY=avx2`` and checks the AVX2 record there (``--check``). ``test_the_check_runs_under_another_
capability`` exercises that subprocess path under NO AVX on every machine.

Record (only from a commit whose game is known good, here dec9d276), one capability per call; the archive is read-only
on the repository and goes outside it:

    rm -rf /tmp/l09_old && mkdir -p /tmp/l09_old
    git -C ~/AirStack-starling-max2 archive dec9d276 svg_training/source svg_training/configs svg_training/params \\
        | tar -x -C /tmp/l09_old
    cd svg_training && PYTHONPATH=/tmp/l09_old/svg_training/source python tests/test_game_tag_off_golden.py --write-golden
    ATEN_CPU_CAPABILITY=default PYTHONPATH=/tmp/l09_old/svg_training/source \\
        python tests/test_game_tag_off_golden.py --write-golden
    rm -rf /tmp/l09_old

(``--write-golden`` adds this capability and refuses if the whole-number fingerprints disagree with the record; the
first call with the record file absent starts it.) This file imports only names that existed before L0.9
(``SvgGame``, ``load_game_cfg``, ``CONFIGS``), so the same code records from the old tree and checks the new one. CPU,
float32, scripted commands from a fixed generator.
"""
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import tempfile

import torch

ROOT = pathlib.Path(__file__).resolve().parents[1]
if "--write-golden" not in sys.argv:          # the writer takes the source tree from PYTHONPATH (the old commit)
    sys.path.insert(0, str(ROOT / "source"))
from svg_training.core.game import SvgGame  # noqa: E402
from svg_training.core.game_config import CONFIGS, load_game_cfg  # noqa: E402

GOLDEN = ROOT / "tests" / "data" / "game_tag_off_golden.json"
STEPS = 100
RESET_AT = 50                                  # reset(seed + 100) after this step: the reseed path is covered too
# name: (preset, Starling layer on, Guard drones, Strike drones, games)
RUNS = {"partner_pure": ("partner", False, 3, 3, 6), "contact_pure": ("contact", False, 3, 3, 6),
        "partner_starling": ("partner", True, 2, 2, 4), "contact_starling": ("contact", True, 2, 2, 4),
        "partner_pure_5v3": ("partner", False, 5, 3, 6)}
SEEDS = (0, 5)
# a [tag] table that is present but off, with values that would change the game if they were read (QC I1)
OFF_PRESENT = '\n[tag]\nmode = "off"\nradius_m = 0.5\nguard_survives_tag_prob = 0.5\n'
FALLBACK_CAPABILITY = "avx2"                   # ATEN_CPU_CAPABILITY value for a CPU whose own capability has no record


def _cfg(preset: str, starling: bool, tag_table: str = ""):
    """configs/s2_game.toml (plus ``tag_table`` appended, when given), no local file, with short games (40 ticks), half
    the games given a drop-out, and for the contact preset a Guard that survives a tag in about half the games (both
    random streams are then in use). With the Starling layer the filter keeps drones 1.10 m apart, so the contact
    distance is raised to 1.3 m there for tags to happen; 20 filter sweeps keep the test fast."""
    if tag_table:
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "game.toml"
            path.write_text((CONFIGS / "s2_game.toml").read_text() + tag_table)
            cfg, _ = load_game_cfg(path, use_local=False)
    else:
        cfg, _ = load_game_cfg(use_local=False)
    changes = {"preset": preset, "dropout_fraction": 0.5, "rules.game_steps": 40,
               "contact.guard_survives_tag_prob": 0.5}
    if starling:
        changes.update({"starling.enabled": True, "starling.filter_iterations": 20, "contact.contact_m": 1.3})
    return cfg.replace(**changes)


def _actions(game: SvgGame, gen: torch.Generator) -> dict[str, torch.Tensor]:
    """Strike drones head for the zone centre, Guard drones for the nearest live Strike drone; noise from ``gen``."""
    g = game.guards
    pos = game.pos_m
    to_zone = torch.cat((game.arenas.zone_centre_m[:, None, :] - pos[:, g:, :2],
                         torch.zeros_like(pos[:, g:, :1])), dim=-1)                         # [N, S, 3]
    rel = pos[:, None, g:, :] - pos[:, :g, None, :]                                        # [N, G, S, 3]
    dist = rel.norm(dim=-1).masked_fill(~game.alive[:, None, g:], float("inf"))
    nearest = dist.argmin(dim=2)                                                           # [N, G]
    to_strike = torch.gather(rel, 2, nearest[:, :, None, None].expand(-1, -1, 1, 3))[:, :, 0]
    heading = torch.cat((to_strike, to_zone), dim=1)
    heading = heading / heading.norm(dim=-1, keepdim=True).clamp(min=1e-6)
    noise = torch.rand(*heading.shape, generator=gen) * 2.0 - 1.0
    a = torch.cat((heading + 0.6 * noise, torch.rand(*heading.shape[:2], 1, generator=gen) * 2.0 - 1.0), dim=-1)
    a = a.clamp(-1.0, 1.0)
    return {"guard": a[:, :g], "strike": a[:, g:]}


def _outputs(game: SvgGame, out) -> dict[str, torch.Tensor]:
    """Every output of one step: the game's state after it, the step's result, every observation and info tensor."""
    values = {"pos_m": game.pos_m, "vel_mps": game.vel_mps, "yaw": game.yaw, "alive": game.alive,
              "steps": game.steps, "state": game.state(), "outcome": out.outcome, "done": out.done,
              "end_step": out.end_step}
    values.update({f"reward_{k}": v for k, v in out.reward.items()})
    values.update({f"obs_{k}": v for k, v in out.obs.items()})
    values.update({f"info_{k}": v for k, v in out.info.items()})
    return values


def golden_run(name: str, seed: int, tag_table: str = "") -> dict[str, torch.Tensor]:
    """STEPS steps of one run; every output stacked over steps [T, ...]."""
    preset, starling, guards, strikes, games = RUNS[name]
    game = SvgGame(_cfg(preset, starling, tag_table), games, guards, strikes, device="cpu", seed=seed)
    gen = torch.Generator().manual_seed(1000 + seed)
    log: dict[str, list[torch.Tensor]] = {}
    for t in range(STEPS):
        for k, v in _outputs(game, game.step(_actions(game, gen))).items():
            log.setdefault(k, []).append(v.clone())
        if t == RESET_AT:
            game.reset(seed=seed + 100)
    return {k: torch.stack(v) for k, v in log.items()}


def fingerprint(t: torch.Tensor) -> str:
    """sha256 of a CPU tensor's dtype, shape and bytes."""
    h = hashlib.sha256(f"{t.dtype}{tuple(t.shape)}".encode())
    h.update(t.contiguous().numpy().tobytes())
    return h.hexdigest()


def fingerprints(tag_table: str = "") -> tuple[dict, dict]:
    """(whole, decimal): {run: {output: fingerprint}}; decimal = floating-point outputs, whole = the rest."""
    whole: dict[str, dict[str, str]] = {}
    decimal: dict[str, dict[str, str]] = {}
    for name in RUNS:
        for seed in SEEDS:
            run, now = f"{name}/{seed}", golden_run(name, seed, tag_table)
            # the run must exercise what it guards: games end (auto-reset), drones leave, the contact preset tags
            assert (now["end_step"] > 0).sum() >= 2 * now["end_step"].shape[1], f"{run}: too few games ended"
            assert (~now["info_final_alive"]).any(), f"{run}: no drone ever left"
            if name.startswith("contact"):
                assert now["info_tagged"].any(), f"{run}: no tag happened, the contact path is not checked"
            whole[run] = {k: fingerprint(v) for k, v in now.items() if not v.is_floating_point()}
            decimal[run] = {k: fingerprint(v) for k, v in now.items() if v.is_floating_point()}
    return whole, decimal


def differences(tag_table: str = "") -> tuple[str, list[str]]:
    """(capability checked, every difference from the record). Raises KeyError if this capability has no record."""
    record = json.loads(GOLDEN.read_text())
    cap = torch.backends.cpu.get_cpu_capability()
    expected_decimal = record["decimal"][cap]
    whole, decimal = fingerprints(tag_table)
    found = []
    for kind, now, old in (("whole-number", whole, record["whole"]), (f"decimal ({cap})", decimal, expected_decimal)):
        if set(now) != set(old):
            found.append(f"{kind}: runs {sorted(now)} against the record's {sorted(old)}")
            continue
        for run in now:
            if set(now[run]) != set(old[run]):
                found.append(f"{run}: outputs {sorted(set(now[run]) ^ set(old[run]))} are not in both")
            found += [f"{run}: {k} ({kind}) differs from the pre-L0.9 record" for k in now[run]
                      if k in old[run] and now[run][k] != old[run][k]]
    return cap, found


def check(tag_table: str = "") -> None:
    """Assert this game equals the record; on a CPU capability without a decimal record, re-run under
    ATEN_CPU_CAPABILITY=avx2 in a subprocess (never a skip)."""
    record = json.loads(GOLDEN.read_text())
    cap = torch.backends.cpu.get_cpu_capability()
    if cap in record["decimal"]:
        cap, found = differences(tag_table)
        assert not found, "\n".join(found)
        return
    assert os.environ.get("ATEN_CPU_CAPABILITY") != FALLBACK_CAPABILITY, (
        f"capability {cap} under ATEN_CPU_CAPABILITY={FALLBACK_CAPABILITY} has no record (recorded: "
        f"{sorted(record['decimal'])})")
    run_check_subprocess(FALLBACK_CAPABILITY, off_present=bool(tag_table), expect=None)


def run_check_subprocess(capability: str, off_present: bool, expect: str | None) -> None:
    """``--check`` in a fresh Python with ATEN_CPU_CAPABILITY=capability; asserts it passed (and, if given, that it
    checked the record of capability ``expect``)."""
    env = {**os.environ, "ATEN_CPU_CAPABILITY": capability, "PYTHONPATH": str(ROOT / "source"),
           "CUDA_VISIBLE_DEVICES": ""}
    args = [sys.executable, "-B", str(pathlib.Path(__file__)), "--check"] + (["--off-present"] if off_present else [])
    run = subprocess.run(args, env=env, capture_output=True, text=True, cwd=ROOT)
    assert run.returncode == 0, f"--check under ATEN_CPU_CAPABILITY={capability} failed:\n{run.stdout}\n{run.stderr}"
    if expect is not None:
        assert f"checked capability {expect}" in run.stdout, run.stdout


def test_tag_off_game_bit_identical():
    check()


def test_tag_off_but_present_is_the_same_game():
    """QC I1: ``[tag]`` present with ``mode = "off"`` and values that would change the game if read (radius 0.5 m,
    Guard survives 0.5): the same game as dec9d276, every output, bit for bit."""
    check(OFF_PRESENT)


def test_the_check_runs_under_another_capability():
    """The subprocess path of ``check`` (used on a CPU without its own record), run here under NO AVX: it reports the
    capability it checked and passes against that record."""
    run_check_subprocess("default", off_present=False, expect="NO AVX")


if __name__ == "__main__" and "--check" in sys.argv:
    capability, problems = differences(OFF_PRESENT if "--off-present" in sys.argv else "")
    if problems:
        sys.exit(f"capability {capability}:\n" + "\n".join(problems))
    print(f"checked capability {capability}: equal to the pre-L0.9 record")

if __name__ == "__main__" and "--write-golden" in sys.argv:
    whole_now, decimal_now = fingerprints()
    saved = json.loads(GOLDEN.read_text()) if GOLDEN.exists() else {"whole": whole_now, "decimal": {}}
    if saved["whole"] != whole_now:
        sys.exit("refused: the whole-number outputs differ from the record; record only from a known-good commit")
    saved["decimal"][torch.backends.cpu.get_cpu_capability()] = decimal_now
    saved["_how"] = ("tests/test_game_tag_off_golden.py --write-golden from dec9d276 (pre-L0.9), CPU, one capability "
                     "per call; see the module docstring")
    GOLDEN.parent.mkdir(parents=True, exist_ok=True)
    GOLDEN.write_text(json.dumps(saved, indent=1, sort_keys=True) + "\n")
    print(f"wrote {GOLDEN} for capability {torch.backends.cpu.get_cpu_capability()}")
