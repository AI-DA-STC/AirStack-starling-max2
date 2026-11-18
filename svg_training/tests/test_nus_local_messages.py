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
