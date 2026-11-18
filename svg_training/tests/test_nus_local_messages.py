"""A missing local file says what to make first (docs panel C8, owner 18 Nov 2026): the deploy file comes BEFORE the conversion
(nus_make_local_deploy.py only records the weights-folder names), so nus_convert_checkpoint.py's error names it as the first step."""
import pytest

from svg_training.nus import deploy as deploy_mod


def test_missing_deploy_file_names_the_order(tmp_path):
    with pytest.raises(FileNotFoundError) as ex:
        deploy_mod.load_deploy(tmp_path / "nus_deploy.toml")
    text = str(ex.value)
    assert "scripts/nus_make_local_deploy.py" in text and "before" in text and "nus_convert_checkpoint.py" in text
    assert "weights-folder names" in text


def test_missing_local_files_point_at_the_provisional_installer(tmp_path):
    """Decision 6 (18 Nov 2026): the lab's own files are in the repository, labelled PROVISIONAL; every missing-file error names the
    one command that installs them."""
    from svg_training.nus import hangar as hangar_mod, method_cfg, rules as rules_mod
    for load in (deploy_mod.load_deploy, rules_mod.load_rules, hangar_mod.load_hangar, method_cfg.load_method):
        with pytest.raises(FileNotFoundError, match="scripts/nus_install_provisional.sh"):
            load(tmp_path / "absent.toml")
