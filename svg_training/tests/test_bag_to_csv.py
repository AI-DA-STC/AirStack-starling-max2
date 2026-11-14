"""bag_to_csv: pure row conversion, output-folder refusal, manifest and missing-topic handling. No ROS: fake messages."""
import csv
import hashlib
import json
import pathlib
import subprocess
import sys
from types import SimpleNamespace as NS

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import bag_to_csv as b  # noqa: E402


def twist(vx, vy, vz, wz):
    return NS(twist=NS(linear=NS(x=vx, y=vy, z=vz), angular=NS(x=0.0, y=0.0, z=wz)))


def odom():
    return NS(pose=NS(pose=NS(position=NS(x=1.0, y=2.0, z=3.0), orientation=NS(x=0.1, y=0.2, z=0.3, w=0.9))),
              twist=NS(twist=NS(linear=NS(x=4.0, y=5.0, z=6.0))))


def test_twist_row():
    assert b.twist_row(twist(0.5, -1.0, 0.25, 0.1), 1762110824.123456789) == (1762110824.123456789, 0.5, -1.0, 0.25, 0.1)


def test_odom_row_order_is_wxyz():
    assert b.odom_row(odom(), 10.5) == (10.5, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 0.9, 0.1, 0.2, 0.3)


def test_status_row():
    assert b.status_row(NS(data="a,b"), 2.0) == (2.0, "a,b")


def read(path):
    with open(path, newline="") as f:
        return list(csv.reader(f))


def fake_reader(topics_present):
    def reader(bag, wanted):
        yield "/svg/drone_1/teleop_command", twist(1, 2, 3, 4), 100.25
        yield "/svg/drone_1/teleop_command", twist(1, 2, 3, 5), 100.30
        yield "/drone_1/odometry_conversion/odometry", odom(), 100.26
        yield "/svg/commander_status", NS(data="hello, world"), 100.27
        yield "/unrelated", NS(), 100.28
    return reader


def test_main_writes_files_and_manifest(tmp_path):
    out = tmp_path / "out"
    assert b.main(["bagdir", str(out)], reader=fake_reader(None)) == 0
    rows = read(out / "teleop_command.csv")
    assert rows[0] == ["t_wall_s", "vx", "vy", "vz", "yaw_rate"]
    assert rows[1] == ["100.25", "1", "2", "3", "4"]
    assert len(rows) == 3
    assert not (out / "velocity_command.csv").exists()  # absent topic: no file
    o = read(out / "odometry.csv")
    assert o[0] == "t_wall_s,x,y,z,vx,vy,vz,qw,qx,qy,qz".split(",")
    assert read(out / "commander_status.csv")[1][1] == "hello, world"
    m = json.loads((out / "manifest.json").read_text())
    assert m["rows"] == {"teleop_command": 2, "odometry": 1, "commander_status": 1, "velocity_command": 0}
    assert m["bag"] == "bagdir"
    b.main(["bagdir", str(tmp_path / "o2"), "--bag-label", "/host/bag"], reader=fake_reader(None))
    assert json.loads((tmp_path / "o2" / "manifest.json").read_text())["bag"] == "/host/bag"
    assert m["script_sha256"] == hashlib.sha256((ROOT / "scripts" / "bag_to_csv.py").read_bytes()).hexdigest()


def test_absent_topic_is_a_note_not_an_error(tmp_path, capsys):
    assert b.main(["bagdir", str(tmp_path / "o")], reader=fake_reader(None)) == 0
    assert "velocity_command" in capsys.readouterr().out


def test_refuses_nonempty_output(tmp_path):
    (tmp_path / "x").write_text("keep")
    assert b.main(["bagdir", str(tmp_path)], reader=fake_reader(None)) == 1
    assert [p.name for p in tmp_path.iterdir()] == ["x"]


def test_accepts_empty_existing_output(tmp_path):
    assert b.main(["bagdir", str(tmp_path)], reader=fake_reader(None)) == 0


def test_topic_options_and_drone(tmp_path):
    seen = {}

    def reader(bag, wanted):
        seen.update(wanted)
        return iter(())
    b.main(["bagdir", str(tmp_path / "o"), "--drone", "drone_7"], reader=reader)
    assert "/drone_7/interface/velocity_command" in seen and "/svg/drone_7/teleop_command" in seen
    assert "/drone_7/odometry_conversion/odometry" in seen


def test_shell_script_syntax():
    assert subprocess.run(["bash", "-n", str(ROOT / "scripts" / "extract_bag.sh")]).returncode == 0
