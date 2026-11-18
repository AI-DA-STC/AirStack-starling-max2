"""The PROVISIONAL bundle ``nus_provisional/`` and its installer (owner decision 6, 18 Nov 2026).

The bundle holds the lab's converted weights, local settings files and recordings, byte-identical, with a sha256 list. The code never
reads it directly: ``scripts/nus_install_provisional.sh`` copies it into the git-ignored ``configs/local/`` and ``runs/nus_port/``.
The installs here go into temporary folders only (``--dest``), never into this checkout."""
import hashlib
import shutil
import subprocess

import pytest

from _nus_markers import ROOT
from svg_training.nus import deploy as deploy_mod, hangar as hangar_mod, method_cfg, rules as rules_mod

BUNDLE = ROOT / "nus_provisional"
SCRIPT = ROOT / "scripts" / "nus_install_provisional.sh"
OK, REFUSED, BAD_ARGUMENT = 0, 1, 2


def _sums(folder):
    return {rel: digest for digest, rel in (line.split(maxsplit=1) for line in (folder / "SHA256SUMS").read_text().splitlines())}


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _install(*args, script=SCRIPT):
    return subprocess.run(["bash", str(script), *args], capture_output=True, text=True)


def test_bundle_matches_its_sha256_list_and_lists_every_file():
    sums = _sums(BUNDLE)
    files = {str(p.relative_to(BUNDLE)) for p in BUNDLE.rglob("*") if p.is_file()} - {"SHA256SUMS", "README.md"}
    assert files == set(sums)
    assert all(_sha(BUNDLE / rel) == digest for rel, digest in sums.items())


def test_bundle_is_labelled_provisional_and_holds_no_source_code():
    text = (BUNDLE / "README.md").read_text()
    assert text.startswith("# PROVISIONAL") and "NUS will retrain" in text and "8 generations" in text
    assert not [p for p in BUNDLE.rglob("*") if p.suffix in (".py", ".yaml", ".yml", ".sh", ".ipynb")]


def test_bundle_is_tracked_and_the_local_folders_stay_ignored():
    r = subprocess.run(["git", "check-ignore", "-q", "nus_provisional/configs/nus_rules.toml"], cwd=ROOT)
    if r.returncode not in (OK, REFUSED):
        pytest.skip("git not available")
    for rel in _sums(BUNDLE):
        assert subprocess.run(["git", "check-ignore", "-q", f"nus_provisional/{rel}"], cwd=ROOT).returncode == REFUSED, rel
    for path in ("configs/local/nus_rules.toml", "runs/nus_port/weights/x/actor.msgpack"):
        assert subprocess.run(["git", "check-ignore", "-q", path], cwd=ROOT).returncode == OK, path


def test_code_reads_only_the_local_folders():
    """No code path reads the bundle: the loaders keep configs/local/ and runs/nus_port/ (the mechanism of STANDARDS section 2)."""
    code = sorted((ROOT / "source").rglob("*.py")) + sorted((ROOT / "scripts").glob("*.py"))
    assert not [p.name for p in code if "nus_provisional" in p.read_text()]


def test_install_into_a_fresh_folder_then_the_loaders_read_it(tmp_path):
    dest = tmp_path / "svg"
    dest.mkdir()
    dry = _install("--dry-run", "--dest", str(dest))
    assert dry.returncode == OK, dry.stderr
    assert not (dest / "configs").exists() and not (dest / "runs").exists()
    r = _install("--dest", str(dest))
    assert r.returncode == OK, r.stderr
    local, runs = dest / "configs" / "local", dest / "runs" / "nus_port"
    for rel, digest in _sums(BUNDLE).items():
        top, rest = rel.split("/", 1)
        assert _sha((local if top == "configs" else runs) / rest) == digest
    deploy = deploy_mod.load_deploy(local / "nus_deploy.toml")
    deploy_ref = deploy_mod.load_deploy(local / "nus_deploy_ref.toml")
    rules_mod.load_rules(local / "nus_rules.toml")
    hangar_mod.load_hangar(local / "nus_hangar.toml")
    method_cfg.load_method(local / "nus_method.toml")
    for d in (deploy, deploy_ref):
        for name in (d.guard_weights, d.strike_weights):
            assert (runs / "weights" / name / "actor.msgpack").is_file()
    again = _install("--dest", str(dest))
    assert again.returncode == OK and "0 file(s) copied" in again.stdout


def test_a_different_local_file_is_refused_unless_forced(tmp_path):
    dest = tmp_path / "svg"
    (dest / "configs" / "local").mkdir(parents=True)
    mine = dest / "configs" / "local" / "nus_hangar.toml"
    mine.write_text("# my own hangar file\n")
    r = _install("--dest", str(dest))
    assert r.returncode == REFUSED and "nus_hangar.toml" in r.stderr
    assert mine.read_text() == "# my own hangar file\n" and not (dest / "runs").exists()      # nothing copied
    assert _install("--force", "--dest", str(dest)).returncode == OK
    assert _sha(mine) == _sums(BUNDLE)["configs/nus_hangar.toml"]


def test_a_damaged_bundle_is_refused(tmp_path):
    """A copy of the installer beside a small made-up bundle: a changed file, or a file missing from the list, refuses."""
    root = tmp_path / "copy"
    (root / "scripts").mkdir(parents=True)
    shutil.copy2(SCRIPT, root / "scripts" / SCRIPT.name)
    (root / "nus_provisional" / "configs").mkdir(parents=True)
    item = root / "nus_provisional" / "configs" / "a.toml"
    item.write_text("a = 1\n")
    (root / "nus_provisional" / "SHA256SUMS").write_text(f"{_sha(item)}  configs/a.toml\n")
    script = root / "scripts" / SCRIPT.name
    assert _install("--dry-run", script=script).returncode == OK
    (root / "nus_provisional" / "configs" / "b.toml").write_text("b = 1\n")
    assert _install(script=script).returncode == REFUSED
    (root / "nus_provisional" / "configs" / "b.toml").unlink()
    item.write_text("a = 2\n")
    r = _install(script=script)
    assert r.returncode == REFUSED and "SHA256SUMS" in r.stderr
    assert not (root / "configs" / "local").exists()
    assert _install("--no-such-option", script=script).returncode == BAD_ARGUMENT
