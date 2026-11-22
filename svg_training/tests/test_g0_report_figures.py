"""The G0 report's game diagram reads its lengths from the game files, and those lengths are the report's."""
import sys
import tomllib

from _ste_tools import ROOT, SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import make_g0_report_figures as fig  # noqa: E402

BASE = ROOT / "configs" / "ste_l011" / "base.toml"
TAG_1P15 = ROOT / "configs" / "ste_l011" / "tag_1p15.toml"


def test_the_diagram_values_equal_the_game_files():
    b = tomllib.loads(BASE.read_text())
    t = tomllib.loads(TAG_1P15.read_text())
    v = fig.game_values(BASE, TAG_1P15)
    side = b["arena"]["bands_m"]["lab"][0]
    assert v["side_m"] == side
    assert v["keep_in_m"] == side / 2 - b["arena"]["wall_margin_m"]
    assert v["zone_m"] == b["arena"]["zone_radius_frac"][0] * side
    assert v["guard_disc_m"] == b["starts"]["guard_disc_m"]
    assert v["strike_ring_m"] == b["starts"]["strike_ring_m"]
    params = tomllib.loads((ROOT / b["starling_layer"]["params"]).read_text())
    assert v["filter_m"] == 2 * params["filter"]["safety_radius_m"]          # per-drone radius, both drones
    assert v["tag_wide_m"] == b["tag"]["radius_m"] and v["tag_close_m"] == t["tag"]["radius_m"]


def test_the_game_files_still_hold_the_values_the_report_states():
    """The report (ste_learning/G0_REPORT.md section 1) quotes these numbers; a changed game file fails here."""
    v = fig.game_values(BASE, TAG_1P15)
    expected = {"side_m": 6.5, "keep_in_m": 3.0, "zone_m": 1.6, "guard_disc_m": 0.8, "strike_ring_m": 2.75,
                "filter_m": 1.1, "tag_wide_m": 1.6, "tag_close_m": 1.15, "start_height_m": 1.2}
    for key, value in expected.items():
        assert abs(v[key] - value) < 1e-9, key
    assert v["height_band_m"] == (0.5, 1.8)


def test_main_writes_the_png(tmp_path):
    out = tmp_path / "g0" / "game_diagram.png"
    assert fig.main(["--out", str(out)]) == 0
    assert out.stat().st_size > 10_000
