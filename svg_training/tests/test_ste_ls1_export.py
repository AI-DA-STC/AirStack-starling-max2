"""Route 3 (stage LS1), merge M3: the export of a team and of the skill network (``ste/export.py``,
``scripts/ste_l6_export.py``; plan ste_learning/drafts/LS1_TASK_PLAN.md section 4, tasks LS1-M3-T1 to LS1-M3-T4).

LS1-M3-T1, the export's variant is no longer fixed to "base": ``golden_observations``, ``_dispatch``,
``export_policy``, ``_interface`` and ``ste_l6_export.team_outputs`` take a trailing keyword ``variant`` (default
"base"). Without it the export is the same bytes as before (ONNX files and ``interface.toml``); with another variant
the golden observations, the dispatch and ``interface.toml`` use that variant's game and its ``train_seed`` of the
side, and ``interface.toml`` names the variant (``variant = "<name>"``, written only for a variant other than base,
OP-24). A variant the gate file does not hold is refused before anything is written; the export command takes the
run's own variant from ``results.json`` (default "base") and refuses (exit 2) one its gate file copy does not hold.

CPU only; needs onnxruntime (the file skips itself without it, as tests/test_ste_l3_export.py does)."""
import json
import sys
import tomllib
from pathlib import Path

import pytest
import torch

pytest.importorskip("onnxruntime")

import _ste_ls1  # noqa: E402
import test_ste_l3_export as tx  # noqa: E402
from _ste_tools import SCRIPTS  # noqa: E402
from svg_training.ste import exploit, export  # noqa: E402
from test_ste_l3_pool import POOL, SMOKE, TWO_LEVEL  # noqa: E402

sys.path.insert(0, str(SCRIPTS))
import ste_l6_export as cli  # noqa: E402

OTHER = "tag_1p2"                  # a second variant of configs/ste_l012/smoke_gates.toml (its own game and seeds)
SIDE = "strike"


@pytest.fixture(scope="module")
def two_level(tmp_path_factory):
    """(gates file, gates, saved): the smoke gate file with the pool and the two-level skills route, and a tiny
    learner's ``saved()`` on it (trained on base: the variant does not change the checkpoint's shape)."""
    path = tmp_path_factory.mktemp("ls1_export_gates") / "gates.toml"
    path.write_text(SMOKE.read_text() + POOL + TWO_LEVEL)
    gates = exploit.load_gates(path)
    return path, gates, _ste_ls1.tiny_learner_saved(gates, SIDE)


@pytest.fixture
def asked_variants(monkeypatch):
    """Every game name ``exploit.variant_cfg`` is asked for from now on (the export's call sites included)."""
    asked = []
    real = exploit.variant_cfg

    def recording(gates, variant, *args, **kwargs):
        asked.append(variant)
        return real(gates, variant, *args, **kwargs)
    monkeypatch.setattr(exploit, "variant_cfg", recording)
    return asked


@pytest.mark.parametrize(("route", "side"), [("velocity", "guard"), ("skills", "strike")], ids=["velocity", "skills"])
def test_export_without_variant_equals_variant_base_bit_for_bit(route, side, tmp_path):
    gates, learner = tx.tiny_learner(route, side)
    saved = learner.saved()
    obs = export.golden_observations(gates, side, games=4, seed=5)
    assert torch.equal(obs, export.golden_observations(gates, side, games=4, seed=5, variant="base"))
    plain = export.export_policy(saved, gates, side, tmp_path / "plain", obs)
    named = export.export_policy(saved, gates, side, tmp_path / "named", obs, variant="base")
    text = (plain / "interface.toml").read_text()
    assert text == (named / "interface.toml").read_text()
    meta = tomllib.loads(text)
    assert "variant" not in meta and meta["seed"] == int(gates.variants["base"]["train_seed"][side])
    for f in meta["files"]:
        assert (plain / f["file"]).read_bytes() == (named / f["file"]).read_bytes(), f["file"]


def test_a_second_variant_exports_with_its_own_seed_and_game(two_level, asked_variants, tmp_path):
    _, gates, saved = two_level
    base_cfg, other_cfg = exploit.variant_cfg(gates, "base"), exploit.variant_cfg(gates, OTHER)
    asked_variants.clear()
    obs = export.golden_observations(gates, SIDE, games=4, variant=OTHER)
    folder = export.export_policy(saved, gates, SIDE, tmp_path / "e", obs, variant=OTHER)
    assert asked_variants and set(asked_variants) == {OTHER}, asked_variants       # no call site left on base
    meta = tomllib.loads((folder / "interface.toml").read_text())
    game = gates.games[gates.variants[OTHER]["game"]]
    seed = int(gates.variants[OTHER]["train_seed"][SIDE])
    assert meta["variant"] == OTHER
    assert meta["seed"] == seed != int(gates.variants["base"]["train_seed"][SIDE])
    assert meta["game_file"] == str(game.file) and meta["game_sha256"] == game.sha256
    assert meta["game_sha256"] != gates.games[gates.variants["base"]["game"]].sha256
    assert meta["tag_radius_m"] == float(other_cfg.tag.radius_m) != float(base_cfg.tag.radius_m)
    assert meta["gates_sha256"] == gates.sha256 and meta["policy_schema"] == export.SCHEMAS["skills"]
    r = tx.reload_in_a_fresh_process(folder)        # the reload plays the skills on the exported (variant's) game
    assert r.returncode == 0, r.stderr[-2000:]
    assert json.loads(r.stdout.strip().splitlines()[-1])["ok"]


def test_an_unknown_variant_is_refused(two_level, tmp_path):
    _, gates, saved = two_level
    unknown = "base_typo"
    with pytest.raises(ValueError, match="not in the gate file"):
        export.golden_observations(gates, SIDE, games=2, variant=unknown)
    with pytest.raises(ValueError, match="not in the gate file"):
        export._dispatch(gates, SIDE, 2, variant=unknown)
    obs = export.golden_observations(gates, SIDE, games=2)
    with pytest.raises(ValueError, match="not in the gate file"):
        export.export_policy(saved, gates, SIDE, tmp_path / "never", obs, variant=unknown)
    assert not (tmp_path / "never").exists()                                     # refused before anything is written
    game_key = next(iter(gates.games))           # a [games] key that is not a variant name is refused too
    if game_key not in gates.variants:
        with pytest.raises(ValueError, match="not in the gate file"):
            export.golden_observations(gates, SIDE, games=2, variant=game_key)
    with pytest.raises(ValueError, match="not in the gate file"):
        cli.team_outputs(saved, gates, SIDE, obs, variant=unknown)


def _run_folder(where, gates_file, gates, saved, **res) -> Path:
    """A finished run folder as scripts/ste_exploit_l012.py leaves it, for the export command: the gate file copy,
    its pin, ``results.json`` (complete, the side, the gate sha, plus ``res``) and ``agent_final.pt``."""
    where.mkdir(parents=True)
    (where / cli.GATES_COPY).write_text(gates_file.read_text())
    (where / cli.PINNED_SHA).write_text(gates.sha256 + "\n")
    (where / cli.RESULTS).write_text(json.dumps({"complete": True, "side": SIDE, "gates_sha256": gates.sha256, **res}))
    torch.save(saved, where / cli.AGENT)
    return where


def test_the_export_command_takes_the_runs_variant(two_level, asked_variants, tmp_path):
    gates_file, gates, saved = two_level
    run = _run_folder(tmp_path / "run_other", gates_file, gates, saved, variant=OTHER)
    asked_variants.clear()
    assert cli.main(["--run-dir", str(run), "--out", str(tmp_path / "out_other"), "--games", "2"]) == 0
    assert asked_variants and set(asked_variants) == {OTHER}, asked_variants
    meta = tomllib.loads((tmp_path / "out_other" / "interface.toml").read_text())
    assert meta["variant"] == OTHER and meta["seed"] == int(gates.variants[OTHER]["train_seed"][SIDE])
    assert meta["game_sha256"] == gates.games[gates.variants[OTHER]["game"]].sha256
    controls = json.loads((tmp_path / "out_other" / "controls.json").read_text())
    assert controls["ctl_team_equals_export"]["status"] == cli.PASS

    plain = _run_folder(tmp_path / "run_plain", gates_file, gates, saved)        # no "variant" key: base
    assert cli.main(["--run-dir", str(plain), "--out", str(tmp_path / "out_plain"), "--games", "2"]) == 0
    meta = tomllib.loads((tmp_path / "out_plain" / "interface.toml").read_text())
    assert "variant" not in meta and meta["seed"] == int(gates.variants["base"]["train_seed"][SIDE])

    bad = _run_folder(tmp_path / "run_bad", gates_file, gates, saved, variant="base_typo")
    assert cli.main(["--run-dir", str(bad), "--out", str(tmp_path / "out_bad"), "--games", "2"]) == 2
    assert not (tmp_path / "out_bad" / "interface.toml").exists()
