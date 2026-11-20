"""STE task L0.9: with the study's tag switched off, the game plays exactly as before the tag existed.

``test_tag_off_game_bit_identical`` plays eight short runs of ``SvgGame`` (partner and contact presets; pure rules and the
Starling layer with the fitted drone; two seeds each; drop-outs on; games of 40 ticks, so every run crosses many
auto-resets) and compares every step's positions, alive masks, outcomes, end steps, rewards, tags and closest 3-D
opposite distance with fingerprints (sha256 of each tensor's bytes, stacked over 100 steps) recorded from the commit
BEFORE L0.9 (dec9d276, branch ste-l0.8). The game here reads no ``[tag]`` setting, so it plays with the tag off (the
default).

Measured 21 Nov 2026 on the laptop (Intel Core Ultra 9 275HX), from dec9d276: the yes/no and whole-number outputs
(alive, outcome, end step, tags) and the rewards (win and loss only: shaping weight 0) are the same with PyTorch's CPU
capability AVX2 (native) and NO AVX (``ATEN_CPU_CAPABILITY=default``); the positions and distances differ in the last
bits from step 4 on. So, as in TEST-F2
(``tests/test_train_standin.py``): the whole-number fingerprints are checked on every machine, the decimal ones per CPU
capability, and a capability without a record skips that part and says so (a skip is not a pass). Record a capability
only from a commit whose game is known good (here dec9d276), with that commit's source on the path:

    git -C .. archive dec9d276 svg_training/source svg_training/configs svg_training/params | tar -x -C /tmp/old
    cd svg_training && PYTHONPATH=/tmp/old/svg_training/source python tests/test_game_tag_off_golden.py --write-golden

(``--write-golden`` adds this machine's capability and refuses if the whole-number fingerprints disagree with the record.)
This file imports only names that existed before L0.9 (``SvgGame``, ``load_game_cfg``), so the same code records from the
old tree and checks the new one. CPU, float32, scripted commands from a fixed generator.
"""
import hashlib
import json
import pathlib
import sys

import pytest
import torch

ROOT = pathlib.Path(__file__).resolve().parents[1]
if "--write-golden" not in sys.argv:          # the writer takes the source tree from PYTHONPATH (the old commit)
    sys.path.insert(0, str(ROOT / "source"))
from svg_training.core.game import SvgGame  # noqa: E402
from svg_training.core.game_config import load_game_cfg  # noqa: E402

GOLDEN = ROOT / "tests" / "data" / "game_tag_off_golden.json"
STEPS = 100
# name: (preset, Starling layer on, Guard drones, Strike drones, games)
RUNS = {"partner_pure": ("partner", False, 3, 3, 6), "contact_pure": ("contact", False, 3, 3, 6),
        "partner_starling": ("partner", True, 2, 2, 4), "contact_starling": ("contact", True, 2, 2, 4)}
SEEDS = (0, 5)
KEYS = ("pos_m", "alive", "outcome", "end_step", "reward_guard", "reward_strike", "tagged", "final_alive",
        "closest_cross_3d_m")
WHOLE = ("alive", "outcome", "end_step", "reward_guard", "reward_strike", "tagged", "final_alive")   # every CPU
DECIMAL = ("pos_m", "closest_cross_3d_m")                                                             # per CPU capability


def _cfg(preset: str, starling: bool):
    """configs/s2_game.toml, no local file, with short games (40 ticks), half the games given a drop-out, and for the
    contact preset a Guard that survives a tag in about half the games (both random streams are then in use). With the
    Starling layer the filter keeps drones 1.10 m apart, so the contact distance is raised to 1.3 m there for tags to
    happen; 20 filter sweeps keep the test fast."""
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


def golden_run(name: str, seed: int) -> dict[str, torch.Tensor]:
    """STEPS steps of one run; every key of KEYS stacked over steps [T, ...]."""
    preset, starling, guards, strikes, games = RUNS[name]
    game = SvgGame(_cfg(preset, starling), games, guards, strikes, device="cpu", seed=seed)
    gen = torch.Generator().manual_seed(1000 + seed)
    log: dict[str, list[torch.Tensor]] = {k: [] for k in KEYS}
    for _ in range(STEPS):
        out = game.step(_actions(game, gen))
        values = (game.pos_m, game.alive, out.outcome, out.end_step, out.reward["guard"], out.reward["strike"],
                  out.info["tagged"], out.info["final_alive"], out.info["closest_cross_3d_m"])
        for k, v in zip(KEYS, values):
            log[k].append(v.clone())
    return {k: torch.stack(v) for k, v in log.items()}


def fingerprint(t: torch.Tensor) -> str:
    """sha256 of a CPU tensor's dtype, shape and bytes."""
    h = hashlib.sha256(f"{t.dtype}{tuple(t.shape)}".encode())
    h.update(t.contiguous().numpy().tobytes())
    return h.hexdigest()


def all_runs() -> dict[str, dict[str, torch.Tensor]]:
    return {f"{name}/{seed}": golden_run(name, seed) for name in RUNS for seed in SEEDS}


def test_tag_off_game_bit_identical():
    record = json.loads(GOLDEN.read_text())
    runs = all_runs()
    assert set(record["whole"]) == set(runs)
    for run, now in runs.items():
        # the run must exercise what it guards: games end (auto-reset), drones drop out, the contact preset tags
        assert (now["end_step"] > 0).sum() >= 2 * now["end_step"].shape[1], f"{run}: too few games ended"
        assert (~now["final_alive"]).any(), f"{run}: no drone ever left"
        if run.startswith("contact"):
            assert now["tagged"].any(), f"{run}: no tag happened, the contact path is not checked"
        for k in WHOLE:
            assert fingerprint(now[k]) == record["whole"][run][k], f"{run}: {k} differs from the pre-L0.9 record"
    cap = torch.backends.cpu.get_cpu_capability()
    if cap not in record["decimal"]:
        pytest.skip(f"whole-number outputs match; positions recorded for CPU capabilities {sorted(record['decimal'])}, "
                    f"this CPU reports {cap}: record it (module docstring) (not a pass)")
    for run, now in runs.items():
        for k in DECIMAL:
            assert fingerprint(now[k]) == record["decimal"][cap][run][k], \
                f"{run}: {k} differs from the pre-L0.9 record for capability {cap}"


if __name__ == "__main__" and "--write-golden" in sys.argv:
    runs = all_runs()
    whole = {run: {k: fingerprint(v[k]) for k in WHOLE} for run, v in runs.items()}
    decimal = {run: {k: fingerprint(v[k]) for k in DECIMAL} for run, v in runs.items()}
    record = json.loads(GOLDEN.read_text()) if GOLDEN.exists() else {"whole": whole, "decimal": {}}
    if record["whole"] != whole:
        sys.exit("refused: the whole-number outputs differ from the record; record only from a known-good commit")
    cap = torch.backends.cpu.get_cpu_capability()
    record["decimal"][cap] = decimal
    record["_how"] = ("tests/test_game_tag_off_golden.py --write-golden from dec9d276 (pre-L0.9), CPU, one capability per "
                      "call; see the module docstring")
    GOLDEN.parent.mkdir(parents=True, exist_ok=True)
    GOLDEN.write_text(json.dumps(record, indent=1, sort_keys=True) + "\n")
    print(f"wrote {GOLDEN} for capability {cap}")
