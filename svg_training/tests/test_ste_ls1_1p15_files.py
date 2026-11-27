"""Route 3 at the 1.15 m tag (owner R51, 27 Nov 2026; plan ste_learning/drafts/LS1_1P15_SWITCH.md, step A): the four
1.15 m files under configs/ste_ls1/ equal their 1.6 m twins except the named keys, and every pin they carry holds.

* ``skills_gates_1p15.toml`` = ``configs/ste_l3/skills_gates.toml`` but [reference] (T50's), [games] (tag_1p15 only),
  [variants] base (game and reference_variant tag_1p15, g* guard_field) and [run0] (no skills_reach_min).
* ``calibration_1p15.toml``, ``calibration_topup_1p15.toml`` = their 1.6 m files but [source] skills_gates and its sha.
* ``distil_gates_1p15.toml`` = ``distil_gates.toml`` but [source] (skills gates, game file and their shas), the Strike
  near-miss opponent (guard_field), the owner's keys (FILL_ until the owner rules the 1.15 m limits) and nothing else.
* The 1.6 m twins are unchanged (their own shas), so the 1.6 m record stays readable."""
import copy
import hashlib
import tomllib

import pytest

from svg_training.ste import distil, exploit

ROOT = exploit.ROOT
LS1 = ROOT / "configs" / "ste_ls1"
GAME_1P15 = ("configs/ste_l011/tag_1p15.toml", "b2e09683f7088964a7d1ca15dfc9c98d1e04c15e96b14196d6971afb75f27580")
T50_REF = ("configs/ste_l012b/screen_reference.npz", "49014000d07e8b52ae579deb325dad53d98c5020f533026dfbff778f306b2296")
T50_GATES_SHA = "881375f054a78ae33c7fd330e271a4e3b27a0a1cf3d58eca4b893cdca8ce2479"
TWINS_1P6 = {"configs/ste_l3/skills_gates.toml": "e16e77298833ca1a74b8154a175f88fe5b71f87c9559e565994db1a881060f5e",
             "configs/ste_ls1/distil_gates.toml": "5cce1245052f2e9ef87d6a3c83d2301f1161100ed818224b932b0248735ee6bb",
             "configs/ste_ls1/calibration.toml": "b628fa0af36390ddf2830f08923f97c3f93d232663b1591155590a70af367d76",
             "configs/ste_ls1/calibration_topup.toml": "0c3668db1460d5bd9bc7df307ec55f09977c706d291a0da084352d4771584b55"}


def sha(rel: str) -> str:
    return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()


def toml(rel: str) -> dict:
    return tomllib.loads((ROOT / rel).read_text())


@pytest.mark.parametrize("rel", sorted(TWINS_1P6))
def test_the_1p6_twins_are_unchanged(rel):
    assert sha(rel) == TWINS_1P6[rel]


def test_the_pinned_game_and_reference_hold():
    assert sha(GAME_1P15[0]) == GAME_1P15[1]
    assert sha(T50_REF[0]) == T50_REF[1]
    assert sha("configs/ste_l012b/screen_gates.toml") == T50_GATES_SHA


def test_the_skills_gate_file_differs_only_in_the_named_keys():
    old, new = toml("configs/ste_l3/skills_gates.toml"), toml("configs/ste_ls1/skills_gates_1p15.toml")
    assert new["reference"] == {"file": T50_REF[0], "sha256": T50_REF[1],
                                "start_sha256": old["reference"]["start_sha256"], "t44_gates_sha256": T50_GATES_SHA,
                                "t44_record": "records/2026-11-21_ste_l012b_screen_record.md",
                                "t44_run": "2026-11-21_ste_l012b_screen"}
    assert new["games"] == {"tag_1p15": {"file": GAME_1P15[0], "sha256": GAME_1P15[1]}}
    want = dict(old["variants"]["base"], game="tag_1p15", reference_variant="tag_1p15", g_star="guard_field",
                role="route 3 at the 1.15 m tag (R51)")
    assert new["variants"] == {"base": want}
    run0 = dict(old["run0"]); run0.pop("skills_reach_min")
    assert new["run0"] == run0
    rest = lambda d: {k: v for k, v in d.items() if k not in ("reference", "games", "variants", "run0")}  # noqa: E731
    assert rest(new) == rest(old)
    gates = exploit.load_gates(ROOT / "configs/ste_ls1/skills_gates_1p15.toml")
    assert exploit.ref_variant(gates, "base") == "tag_1p15"
    assert exploit.load_reference(ROOT / T50_REF[0]).start_sha256 == old["reference"]["start_sha256"]


@pytest.mark.parametrize("name", ["calibration", "calibration_topup"])
def test_the_calibration_files_differ_only_in_the_skills_gates_pin(name):
    old, new = toml(f"configs/ste_ls1/{name}.toml"), toml(f"configs/ste_ls1/{name}_1p15.toml")
    assert new["source"]["skills_gates"] == "configs/ste_ls1/skills_gates_1p15.toml"
    assert new["source"]["skills_gates_sha256"] == sha("configs/ste_ls1/skills_gates_1p15.toml")
    o, n = copy.deepcopy(old), copy.deepcopy(new)
    for d in (o, n):
        del d["source"]["skills_gates"], d["source"]["skills_gates_sha256"]
    assert n == o


def test_the_distil_gate_file_differs_only_in_the_named_keys():
    old, new = toml("configs/ste_ls1/distil_gates.toml"), toml("configs/ste_ls1/distil_gates_1p15.toml")
    src = new["source"]
    assert (src["skills_gates"], src["skills_gates_sha256"]) == ("configs/ste_ls1/skills_gates_1p15.toml",
                                                                 sha("configs/ste_ls1/skills_gates_1p15.toml"))
    assert (src["game_file"], src["game_sha256"]) == GAME_1P15
    assert {c["opponent"] for c in new["read"]["near_miss_cells"]["strike"]} == {"guard_field"}
    assert [c["codes"] for c in new["read"]["near_miss_cells"]["strike"]] == [c["codes"] for c in old["read"]["near_miss_cells"]["strike"]]
    assert new["read"]["near_miss_cells"]["guard"] == old["read"]["near_miss_cells"]["guard"]
    g = distil.load_distil_gates(ROOT / "configs/ste_ls1/distil_gates_1p15.toml")
    unfilled = set(distil.unfilled_limits(g))
    assert len(unfilled) == 16 and "limits.end_time_max_ticks" not in unfilled
    o, n = copy.deepcopy(old), copy.deepcopy(new)
    for d in (o, n):
        for k in ("skills_gates", "skills_gates_sha256", "game_file", "game_sha256"):
            del d["source"][k]
        del d["read"]["near_miss_cells"]["strike"]
        for sec in ("limits", "controls"):
            for k in list(d[sec]):
                if not isinstance(d[sec][k], dict) and k != "end_time_max_ticks":
                    del d[sec][k]
        for k in list(d["controls"]["near_miss"]):
            if not isinstance(d["controls"]["near_miss"][k], dict):
                del d["controls"]["near_miss"][k]
        del d["controls"]["near_miss"]["switch"]
    assert n == o
    for k, v in new["controls"]["near_miss"]["switch"].items():
        assert v == "FILL_R51", k
