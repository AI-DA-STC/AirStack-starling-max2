"""The marker scans search error text and captured output for the made-up architecture numbers (tests/_nus_markers.py). That text
names folders the test harness chose: pytest numbers its temp folder, and on the run whose number equals a marker the scan found the
folder's name (tests/test_nus_actor.py and tests/test_nus_phase3_privacy.py failed on those runs). ``mask_paths`` takes exactly those
folders out of the text before the scan. Both halves are pinned here: the folder's name is no longer a hit; a marker value anywhere
else in the text still is."""
import re

import pytest

from _nus_markers import MARKER_ARCH, PATH_MASK, mask_paths

HIDDEN = MARKER_ARCH["hidden_dim"]
SEARCHED = (HIDDEN, HIDDEN + 2, HIDDEN // 2)   # the width, the width test_nus_actor.py changes it to, the derived half width


def found(value: int, text: str) -> tuple[bool, bool]:
    """(the substring search of test_nus_actor.py, the whole-number search of test_nus_phase3_privacy.py)."""
    return str(value) in text, bool(re.search(rf"\b{value}\b", text))


@pytest.mark.parametrize("value", SEARCHED)
def test_a_temp_folder_named_with_the_marker_digits_is_not_a_hit(tmp_path, value):
    base = tmp_path / f"pytest-{value}"                     # pytest's own name for its numbered temp folder
    folder = base / "test_name_0" / "widths"
    folder.mkdir(parents=True)
    for text in (f"{folder}: the parameters do not match the config's actor architecture",   # the loader's message
                 f"wrote {folder / 'nus_deploy.toml'}\nkeys: a, b\n"):                        # the deploy script's first line
        assert found(value, text) == (True, True)           # unmasked, the folder's name alone is a hit: the old failure
        assert found(value, mask_paths(text, base)) == (False, False)
        assert found(value, mask_paths(text, folder, base)) == (False, False)   # nested folders, in either order
        assert found(value, mask_paths(text, base, folder)) == (False, False)


@pytest.mark.parametrize("value", SEARCHED)
def test_a_marker_value_outside_the_masked_folder_is_still_a_hit(tmp_path, value):
    base = tmp_path / f"pytest-{value}"
    folder = base / "widths"
    folder.mkdir(parents=True)
    leaks = (f"{folder}: width {value} does not match",       # in the message
             f"{folder}: width {value}",                      # at the end of the text
             f"{value} {folder}",                             # at the start
             f"width={value}{folder}",                        # written right before the path
             f"{folder}{value}",                              # written right after it
             f"{folder}/{value}/config.json",                 # a folder below the masked one, named by the code under test
             f"{tmp_path / f'other-{value}'}: no such folder",   # a path nobody asked to mask
             f"{folder}: {folder.name} {value} {folder}")     # between two masked paths
    for text in leaks:
        assert found(value, mask_paths(text, base, folder)) == (True, True), text
    assert str(value) in mask_paths(f"{folder}/weights_{value}.npz", base, folder)   # a file name: the substring search finds it


def test_the_mask_cannot_hide_or_make_a_number(tmp_path):
    assert not any(c.isdigit() for c in PATH_MASK)
    assert re.fullmatch(r"\W(.*\W)?", PATH_MASK)             # not a word character at either end, so \b still holds beside it
    assert mask_paths(f"{tmp_path}", tmp_path) == PATH_MASK
    assert mask_paths("no path here", tmp_path) == "no path here" and mask_paths("unchanged") == "unchanged"
    assert mask_paths(f"{tmp_path}", tmp_path.parent / ".." / tmp_path.parent.name / tmp_path.name) == PATH_MASK   # resolved form


@pytest.mark.parametrize("not_a_folder", [str(HIDDEN), f"pytest-{HIDDEN}", ".", ""])
def test_only_an_absolute_path_can_be_masked(not_a_folder):
    with pytest.raises(ValueError, match="absolute"):       # otherwise the mask could be handed the marker itself
        mask_paths(f"width {HIDDEN}", not_a_folder)
