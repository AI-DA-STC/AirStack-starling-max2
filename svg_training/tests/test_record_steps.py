"""record_steps.sh + virtual_stick.py (S1 Task 5): plan, refusals, --dry-run order, bag-removal guard, and full NON-dry
sessions against a fake simulator.

Never starts the AirStack simulator. Dry tests use --dry-run, --print-plan or --check-bag-path. Non-dry tests put a fake
`docker` (a mapped container filesystem and process table, see FAKE below), `nvidia-smi`, `pgrep` and `ss` first on PATH,
point SVG_TEST_SIM at the same fake acting as tools/sim.sh, and HOME, SVG_TEST_RUNS and SVG_TEST_HOST_BAGS at temporary
folders: nothing outside tmp_path is written. The bags folder holds an old svg_20261112_094546 like the real one.
The stick's session runs against a fake rclpy (FakeWorld below)."""
import json
import os
import pathlib
import re
import signal
import stat
import subprocess
import sys
import threading
import time
import tomllib
import types

import pytest
from _proc import child_python

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "record_steps.sh"
STICK = ROOT / "scripts" / "virtual_stick.py"
CONFIG = ROOT / "configs" / "s1.toml"
NAME = "2099-01-01_s1_pytest"
STEPS = tomllib.loads(CONFIG.read_text())["steps"]
GAP_S = 2.0
GPU_FREE = "3905, /usr/libexec/gnome-remote-desktop-daemon"
OLD_S = 1_794_500_000          # 2026-11-12, before any test run
BAGS_C = "/root/AirStack/robot/ros_ws/bags"
R = "airstack-robot-desktop-1"


def bags_dir(tmp_path, extra=()):
    """A bags folder like the real one: svg_20261112_094546 and hover_step_20261029_074525 (old), plus extra (name, mtime)."""
    d = tmp_path / "bags"
    for name, mtime in (("svg_20261112_094546", OLD_S), ("hover_step_20261029_074525", OLD_S), *extra):
        (d / name).mkdir(parents=True)
        (d / name / "metadata.yaml").write_text("x")
        for q in (d / name / "metadata.yaml", d / name):
            os.utime(q, (mtime, mtime))
    return d


# ------------------------------------------------------------------------------------------------- fake simulator
FAKE = r'''
import json, os, re, shutil, signal, subprocess, sys
FD = os.environ["FAKE_DIR"]
HOST_BAGS = os.environ["SVG_TEST_HOST_BAGS"]
BAGS_C = "/root/AirStack/robot/ros_ws/bags"
R, I = "airstack-robot-desktop-1", "isaac-sim"
SC = json.load(open(os.path.join(FD, "scenario.json")))
STATE_F = os.path.join(FD, "state.json")


def load():
    if os.path.exists(STATE_F):
        return json.load(open(STATE_F))
    return {"procs": {R: [], I: []}, "fired": [], "stick_polls": 0, "topic_lists": 0}


def save(st):
    json.dump(st, open(STATE_F, "w"))


def log(line):
    with open(os.path.join(FD, "calls.log"), "a") as f:
        f.write(line + "\n")


def cmap(c, p):
    if c == R and (p == BAGS_C or p.startswith(BAGS_C + "/")):
        return HOST_BAGS + p[len(BAGS_C):]
    return os.path.join(FD, "c_" + c) + p


def main_pid():
    pid, best = os.getppid(), None
    while pid > 1:
        try:
            argv = open(f"/proc/{pid}/cmdline", "rb").read().split(b"\0")
            ppid = int(open(f"/proc/{pid}/stat").read().rsplit(")", 1)[1].split()[1])
        except OSError:
            break
        # only the script under test: argv = [.../bash, .../scripts/record_steps.sh, <name>] (never a shell whose
        # command TEXT merely mentions the script)
        if len(argv) >= 3 and argv[0].endswith(b"bash") and argv[1].endswith(b"/scripts/record_steps.sh"):
            best = pid
        pid = ppid
    return best


def maybe_kill(line):
    st = load()
    for i, k in enumerate(SC.get("kill", [])):
        if i not in st["fired"] and re.search(k["on"], line):
            st["fired"].append(i)
            save(st)
            p = main_pid()
            if p:
                os.kill(p, getattr(signal, "SIG" + k.get("sig", "TERM")))


def en_us_sorted(names):
    out = subprocess.run(["sort"], input="\n".join(names) + "\n", capture_output=True, text=True,
                         env=dict(os.environ, LC_ALL="en_US.UTF-8")).stdout
    return [n for n in out.splitlines() if n]


def truncate(d):
    for root, _, files in os.walk(d):
        for f in files:
            if f.endswith(".mcap"):
                with open(os.path.join(root, f), "r+") as h:
                    h.truncate(10)


def resolve(spec):
    if ":" in spec and not spec.startswith("/"):
        c, p = spec.split(":", 1)
        return cmap(c, p)
    return spec


def cp(src, dst):
    s, d = resolve(src), resolve(dst)
    if not os.path.exists(s):
        return 1
    if os.path.isdir(d) or dst.endswith("/"):
        d = os.path.join(d, os.path.basename(s.rstrip("/")))
    os.makedirs(os.path.dirname(d), exist_ok=True)
    if os.path.isdir(s):
        shutil.copytree(s, d, dirs_exist_ok=True)
        if SC.get("truncate_docker_cp"):
            truncate(d)
    else:
        shutil.copy(s, d)
    return 0


def shell(st, c, sh):
    if "ros2 launch svg_ground_control" in sh:
        prefix = re.search(r"bag_prefix:=(\S+)", sh).group(1)
        logp = cmap(c, re.search(r"> (\S+commander\.log)", sh).group(1))
        lines = ["[swarm_commander-1] [INFO] [1.0] [swarm_commander]: SwarmCommander up | scenario=hover | drones=1"]
        if not SC.get("no_bag"):
            bag = f"{prefix}_20991231_235959"
            b = os.path.join(HOST_BAGS, bag)
            os.makedirs(b)
            open(os.path.join(b, "metadata.yaml"), "w").write("rosbag2_bagfile_information: {}\n")
            open(os.path.join(b, f"{bag}_0.mcap"), "w").write("m" * 1000)
            lines.append(f"[bag_recorder-2] [INFO] [1.0] [bag_recorder]: recording all topics to {BAGS_C}/{bag}\x1b[0m")
        os.makedirs(os.path.dirname(logp), exist_ok=True)
        open(logp, "w").write("\n".join(lines) + "\n")
        st["procs"][c].append("/usr/bin/python3 /opt/ros/jazzy/bin/ros2 launch svg_ground_control ground_control.launch.py "
                              f"config:=x scenario:=hover record_bag:=true bag_prefix:={prefix}")
        save(st)
        return 0
    if "virtual_stick.py --config" in sh:
        d = re.search(r"python3 (\S+)/virtual_stick\.py", sh).group(1)
        rc = SC.get("stick_rc", 0)
        os.makedirs(cmap(c, d), exist_ok=True)
        pre = "[0.4] pre-takeoff: drone_1 state=IDLE z=0.07 m (odometry age 0.02 s); one commander: publishing from now on"
        if SC.get("stick_no_takeoff"):
            lines = []
        elif SC.get("stick_pre_takeoff_only"):          # the takeoff request is in flight / unanswered
            lines = [pre]
        else:
            lines = [pre, "[0.5] takeoff: success=True message='takeoff: drone_1'",
                     "[1.0] step 1/36 onset axis=x sign=+1 speed=0.50 z=1.20"]
        if rc == 67 and SC.get("stick_real_drone"):
            lines.append("[1.5] !! REFUSED: REAL DRONE MAY BE PRESENT: x — NOTHING SENT (NO PUBLISH, NO SERVICE CALL); exit 67")
        elif rc == 67:
            lines.append("[1.5] !! SECOND COMMANDER OR FOREIGN STATUS ON THE DOMAIN: x — NOTHING SENT (NO ZEROS, NO LAND); exit 67")
        lines += ["[2.0] steps reached: 36/36", f"[2.1] virtual_stick: exit {rc}"]
        open(cmap(c, d + "/stick.log"), "w").write("\n".join(lines) + "\n")
        if SC.get("foreign_commander"):
            st["procs"][c].append("/usr/bin/python3 /opt/ros/jazzy/bin/ros2 launch svg_ground_control "
                                  "ground_control.launch.py config:=/tmp/svg_real/teleop_real_drone_2.yaml use_mocap:=true")
        open(cmap(c, d + "/steps_flown.json"), "w").write("{}")
        st["procs"][c].append(f"python3 {d}/virtual_stick.py --config {d}/s1.toml --drone drone_1")
        st["stick_polls"] = SC.get("stick_polls", 2)
        save(st)
        return 0
    if sh.startswith(": > "):
        p = cmap(c, sh[4:].strip())
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "w").close()
        return 0
    if "mavros/state" in sh:
        armed = SC.get("armed") or (SC.get("armed_until_land") and not st.get("land_called"))
        print("armed: " + ("true" if armed else "false"))
        return 0
    if "ros2 topic list" in sh:
        st["topic_lists"] += 1
        save(st)
        real = st["topic_lists"] in SC.get("real_topics_on_call", [])
        mocap = st["topic_lists"] in SC.get("mocap_pub_on_call", [])
        if "topic list -v" in sh:                     # the verbose form: publishers and subscribers apart
            print("Published topics:")
            print(" * /svg/commander_status [std_msgs/msg/String] 1 publisher")
            if SC.get("sim_topics", True):            # the simulator's own MAVROS and our mocap_bridge relay
                print(" * /drone_1/interface/mavros/local_position/pose [geometry_msgs/msg/PoseStamped] 1 publisher")
                print(" * /drone_1/fmu/in/vehicle_visual_odometry [px4_msgs/msg/VehicleOdometry] 1 publisher")
            if real:
                print(" * /drone_1/fmu/out/vehicle_status [px4_msgs/msg/VehicleStatus] 1 publisher")
            if mocap:
                print(" * /drone_1/pose [geometry_msgs/msg/PoseStamped] 1 publisher")
            print("")
            print("Subscribed topics:")
            if SC.get("sim_topics", True):            # our mocap_bridge listens for a mocap pose that never comes
                print(" * /drone_1/pose [geometry_msgs/msg/PoseStamped] 1 subscriber")
                print(" * /drone_1/fmu/out/vehicle_status [px4_msgs/msg/VehicleStatus] 1 subscriber")
            return 0
        print("/svg/commander_status")
        if SC.get("sim_topics", True):
            print("/drone_1/interface/mavros/local_position/pose\n/drone_1/fmu/in/vehicle_visual_odometry\n/drone_1/pose")
        if real:
            print("/fmu/out/vehicle_status")
        return 0
    if "ros2 topic info" in sh:
        ours = any("bag_prefix:=" in p for p in st["procs"][R])
        n = int(ours) + SC.get("status_pubs_after_stop", 0)
        print(f"Type: std_msgs/msg/String\nPublisher count: {n}\nSubscription count: 0")
        return 0
    if "ros2 service call" in sh:
        if "/land" in sh:
            st["land_called"] = True
            save(st)
        print("response: std_srvs.srv.Trigger_Response(success=True, message='landing: drone_1')")
        return 0
    if "ls -d" in sh and "| tail -1" in sh:
        if SC.get("pick"):
            print(SC["pick"])
            return 0
        names = en_us_sorted([n for n in os.listdir(HOST_BAGS) if n.startswith("svg_")])
        if names:
            print(BAGS_C + "/" + names[-1])
        return 0
    if "for f in /tmp/tmp*/log" in sh:
        p = "/tmp/tmpab12/log/2099-12-31/23_59_59.ulg"
        os.makedirs(os.path.dirname(cmap(c, p)), exist_ok=True)
        open(cmap(c, p), "w").write("ulog")
        print(p)
        return 0
    return 0


def docker(argv):
    line = "docker " + " ".join(argv)
    log(line)
    maybe_kill(line)
    st = load()
    if argv[0] == "ps":
        print("isaac-sim\nairstack-robot-desktop-1")
        return 0
    if argv[0] == "cp":
        return cp(argv[1], argv[2])
    a = argv[1:]
    while a[0].startswith("-"):
        a = a[1:]
    c, cmd = a[0], a[1:]
    st["procs"].setdefault(c, [])
    prog = cmd[0]
    if prog == "true":
        return 0
    if prog == "pgrep":
        return 1
    if prog == "ps":
        print("STAT ARGS")
        for p in st["procs"][c]:
            print("S " + p)
        if any("virtual_stick.py" in p for p in st["procs"][c]):
            st["stick_polls"] -= 1
            if st["stick_polls"] <= 0:
                st["procs"][c] = [p for p in st["procs"][c] if "virtual_stick.py" not in p]
            save(st)
        return 0
    if prog == "pkill":
        pat = cmd[-1]
        before = st["procs"][c]
        st["procs"][c] = [p for p in before if not re.search(pat, p)]
        save(st)
        return 0 if len(st["procs"][c]) < len(before) else 1
    if prog == "mkdir":
        p = cmap(c, cmd[-1])
        if SC.get("sentinel_mkdir_fail") and p.endswith("_00000000_000000"):
            return 1
        os.makedirs(p, exist_ok=True)
        return 0
    if prog == "test":
        f = {"-e": os.path.exists, "-d": os.path.isdir, "-f": os.path.isfile}[cmd[1]]
        return 0 if f(cmap(c, cmd[2])) else 1
    if prog == "rm":
        shutil.rmtree(cmap(c, cmd[-1]), ignore_errors=True)
        return 0
    if prog == "rmdir":
        try:
            os.rmdir(cmap(c, cmd[-1]))
            return 0
        except OSError:
            return 1
    if prog == "ls":
        return subprocess.run(["ls", "-1A", cmap(c, cmd[-1])]).returncode
    if prog == "grep":
        return subprocess.run(["grep"] + cmd[1:-1] + [cmap(c, cmd[-1])]).returncode
    if prog == "python3":
        print("2")
        return 0
    if prog == "bash":
        return shell(st, c, cmd[-1])
    return 0


def sim(argv):
    line = "sim " + " ".join(argv)
    log(line)
    maybe_kill(line)
    st = load()
    if argv[0] == "up":
        mode = SC.get("up", "ok")
        if mode == "precheck":
            print("[t] FAIL (precheck): a real-drone/mocap bridge is running on the laptop")
            return 1
        if mode == "precheck_port":
            print("[t] FAIL (precheck): port 8765 already in use (stray foxglove_bridge)")
            return 1
        st["procs"][I] = ["/isaac-sim/kit/python/bin/python3 /isaac-sim/AirStack/svg_multi_drone_single_domain.py",
                          "/isaac-sim/PX4-Autopilot/build/px4_sitl_default/bin/px4 -i 1"]
        save(st)
        if mode == "fail":
            print("[t] FAIL (isaac): Isaac not ready")
            return 1
        print("[t] interfaces: 3 drones with odometry")
        return 0
    if argv[0] == "down":
        mode = SC.get("down", "ok")
        if mode == "fail":
            print("[t] ulog guard: copy FAILED — Isaac NOT stopped")
            return 1
        st["procs"][R] = [p for p in st["procs"][R] if "ground_control.launch.py" not in p]
        names = en_us_sorted([n for n in os.listdir(HOST_BAGS) if n.startswith("svg_")])
        stack = os.path.join(os.environ["HOME"], "flight_logs/sim/_stack")
        if names and mode != "no_copy":
            b = names[-1]
            os.makedirs(stack, exist_ok=True)
            shutil.copytree(os.path.join(HOST_BAGS, b), os.path.join(stack, b), dirs_exist_ok=True)
            if SC.get("truncate_stack"):
                truncate(os.path.join(stack, b))
            if SC.get("hook_ok") and os.path.isfile(os.path.join(HOST_BAGS, b, "metadata.yaml")):
                shutil.rmtree(os.path.join(HOST_BAGS, b))
        if SC.get("down_moves_other"):
            shutil.rmtree(os.path.join(HOST_BAGS, "svg_20261112_094546"))
        if mode != "stays_up":
            st["procs"][I] = []
        save(st)
        print("[t] down: stack stopped, containers left up")
        return 0
    return 2


tool = os.path.basename(sys.argv[0])
sys.exit(docker(sys.argv[1:]) if tool == "docker" else sim(sys.argv[1:]))
'''


def fake_bin(tmp_path, gpu_lines=GPU_FREE, docker_ps=""):
    """A PATH directory with fake docker / nvidia-smi / pgrep / ss (dry tests); docker calls are appended to docker.log."""
    b = tmp_path / "bin"
    b.mkdir(parents=True)
    log = tmp_path / "docker.log"
    tools = {
        "docker": f'#!/bin/bash\necho "$*" >> "{log}"\n[ "$1" = ps ] && printf "%s" "{docker_ps}"\nexit 0\n',
        "nvidia-smi": f'#!/bin/bash\nprintf "%s\\n" "{gpu_lines}"\n',
        "pgrep": "#!/bin/bash\nexit 1\n",
        "ss": "#!/bin/bash\nexit 0\n",
    }
    for name, body in tools.items():
        p = b / name
        p.write_text(body)
        p.chmod(p.stat().st_mode | stat.S_IXUSR)
    return b, log


def run(tmp_path, *args, bags=None, **kw):
    b, log = fake_bin(tmp_path, **kw)
    env = dict(os.environ, PATH=f"{b}{os.pathsep}{os.environ['PATH']}", SVG_HOST_PY=child_python(),
               SVG_TEST_HOST_BAGS=str(bags if bags is not None else bags_dir(tmp_path)), HOME=str(tmp_path / "home"))
    r = subprocess.run(["bash", str(SCRIPT), *args], capture_output=True, text=True, cwd=ROOT, env=env, timeout=60)
    return r, (log.read_text() if log.exists() else "")


class Session:
    """One NON-dry record_steps.sh run against the fake simulator."""

    def __init__(self, tmp_path, scenario=None, name="run1", extra_bags=(), lock_pid=None):
        self.tmp, self.name = tmp_path, name
        self.fd = tmp_path / "fake"
        self.fd.mkdir()
        (self.fd / "scenario.json").write_text(json.dumps(scenario or {}))
        self.bags = bags_dir(tmp_path, extra_bags)
        self.home = tmp_path / "home"
        self.stack = self.home / "flight_logs" / "sim" / "_stack"
        self.lock = self.home / "flight_logs" / "sim" / ".sim_test.lock"
        if lock_pid is not None:
            self.lock.parent.mkdir(parents=True)
            self.lock.write_text(f"{lock_pid}\n")
        self.runs = tmp_path / "runs"
        self.runs.mkdir()
        self.out = self.runs / name
        b = tmp_path / "bin"
        b.mkdir()
        for tool in ("docker", "fakesim"):
            p = b / tool
            p.write_text(f"#!{sys.executable}\n" + FAKE)
            p.chmod(0o755)
        for tool, body in (("nvidia-smi", f'#!/bin/bash\necho "{GPU_FREE}"\n'), ("pgrep", "#!/bin/bash\nexit 1\n"),
                           ("ss", "#!/bin/bash\nexit 0\n")):
            (b / tool).write_text(body)
            (b / tool).chmod(0o755)
        env = dict(os.environ, PATH=f"{b}{os.pathsep}{os.environ['PATH']}", SVG_HOST_PY=child_python(),
                   SVG_TEST_HOST_BAGS=str(self.bags), SVG_TEST_SIM=str(b / "fakesim"), SVG_TEST_RUNS=str(self.runs),
                   SVG_TEST_POLL_S="0.05", HOME=str(self.home), FAKE_DIR=str(self.fd))
        self.r = subprocess.run(["bash", str(SCRIPT), name], capture_output=True, text=True, cwd=ROOT, env=env,
                                timeout=180)
        self.calls = (self.fd / "calls.log").read_text().splitlines() if (self.fd / "calls.log").exists() else []
        self.bag = f"svg_s1_{name}_20991231_235959"
        self.sentinel = f"svg_s1_{name}_00000000_000000"

    def text(self, f):
        p = self.out / f
        return p.read_text() if p.exists() else ""

    def idx(self, pattern):
        """Index of the first call matching pattern, or -1."""
        return next((i for i, c in enumerate(self.calls) if re.search(pattern, c)), -1)

    def has(self, pattern):
        return self.idx(pattern) >= 0

    def why(self):
        return self.r.stdout[-4000:] + self.r.stderr[-2000:]


def plan_lines():
    r = subprocess.run([child_python(), str(STICK), "--config", str(CONFIG), "--print-plan"],
                       capture_output=True, text=True, cwd=ROOT, timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr
    return r.stdout.splitlines()


def expected_steps():
    """Plan order: repeat, speed, axis, sign (each + step is followed by its - twin on the same axis)."""
    return [(rep + 1, sp, ax, sg) for rep in range(STEPS["repeats"]) for sp in STEPS["speeds_mps"]
            for ax in STEPS["axes"] for sg in STEPS["signs"]]


def assert_nothing_created():
    assert not (ROOT / "runs" / NAME).exists()


# --------------------------------------------------------------------------------------------- plan, dry-run, guard
def test_syntax():
    assert subprocess.run(["bash", "-n", str(SCRIPT)]).returncode == 0


def test_help_shows_detached_form():
    r = subprocess.run(["bash", str(SCRIPT), "--help"], capture_output=True, text=True, cwd=ROOT, timeout=60)
    assert r.returncode == 0
    assert "setsid nohup bash scripts/record_steps.sh <name> > runs/<name>.out 2>&1 &" in r.stdout
    assert "trap '' PIPE" in SCRIPT.read_text()


def test_stick_importable_without_ros():
    r = subprocess.run([child_python(), "-c", "import sys; sys.path.insert(0, 'scripts'); import virtual_stick; "
                        "assert 'rclpy' not in sys.modules"], capture_output=True, text=True, cwd=ROOT, timeout=60)
    assert r.returncode == 0, r.stderr


def test_print_plan_matches_config():
    lines = plan_lines()
    steps = [ln for ln in lines if ln.startswith("step ")]
    exp = expected_steps()
    assert len(steps) == len(exp) == 36
    pat = re.compile(r"^step +(\d+)/36 repeat (\d) axis ([xyz]) sign ([+-]1) speed ([0-9.]+) m/s "
                     r"zero ([0-9.]+) s then hold ([0-9.]+) s onset +([0-9.]+) s end +([0-9.]+) s")
    t = 0.0
    for k, (ln, (rep, sp, ax, sg)) in enumerate(zip(steps, exp), start=1):
        m = pat.match(ln)
        assert m, ln
        assert int(m[1]) == k and int(m[2]) == rep and m[3] == ax and int(m[4]) == sg
        assert float(m[5]) == sp and float(m[6]) == GAP_S and float(m[7]) == STEPS["hold_s"]
        t += GAP_S
        assert abs(float(m[8]) - t) < 1e-9
        t += STEPS["hold_s"]
        assert abs(float(m[9]) - t) < 1e-9
    total = [ln for ln in lines if ln.startswith("plan: ")]
    assert len(total) == 1 and f"total {t + GAP_S:.1f} s" in total[0]


def test_plan_pairs_cancel():
    """Every + step is followed by the same step with sign -: a -z step never runs before its +z twin."""
    exp = expected_steps()
    for a, b in zip(exp[0::2], exp[1::2]):
        assert a[:3] == b[:3] and a[3] == 1 and b[3] == -1


def test_plan_json(tmp_path):
    out = tmp_path / "steps.json"
    r = subprocess.run([child_python(), str(STICK), "--config", str(CONFIG), "--plan-json", str(out)],
                       capture_output=True, text=True, cwd=ROOT, timeout=60)
    assert r.returncode == 0, r.stderr
    j = json.loads(out.read_text())
    assert len(j["steps"]) == 36 and j["zero_gap_s"] == GAP_S and j["hold_s"] == STEPS["hold_s"]
    s = j["steps"][4]
    assert s["axis"] == "z" and s["sign"] == 1 and s["velocity_enu_mps"] == [0.0, 0.0, 0.5]
    assert s["onset_s"] == 5 * GAP_S + 4 * STEPS["hold_s"]


def test_dry_run_prints_every_command_in_order(tmp_path):
    r, docker_log = run(tmp_path, "--dry-run", NAME)
    assert r.returncode == 0, r.stdout + r.stderr
    dry = [ln[5:] for ln in r.stdout.splitlines() if ln.startswith("DRY: ")]
    stack = re.escape(str(tmp_path / "home" / "flight_logs" / "sim" / "_stack"))
    sent = f"{BAGS_C}/svg_s1_{NAME}_00000000_000000"
    markers = [
        r"take .*\.sim_test\.lock",
        r"virtual_stick\.py --config .*s1\.toml --plan-json .*runs/%s/steps\.json" % NAME,
        r"write .*runs/%s/preflight\.txt .*svg_20261112_094546" % NAME,
        r"tools/sim\.sh up --headless$",
        r"compare ls -1A .* with docker exec %s ls -1A %s" % (R, BAGS_C),
        r"ground_control\.launch\.py config:=.*/teleop_single_ours\.yaml scenario:=hover record_bag:=true "
        r"bag_prefix:=svg_s1_%s" % NAME,
        r"wait .*SwarmCommander up \| scenario=hover",
        r"wait .*recording all topics to",
        r"\(real-drone check\)",
        r"docker cp .*scripts/virtual_stick\.py %s:" % R,
        r"docker cp .*configs/s1\.toml %s:" % R,
        r"docker exec -d %s bash -ic .*virtual_stick\.py --config" % R,
        r"wait .*virtual_stick",
        r"wait .*armed: false",
        r"docker exec %s pkill -INT -f bag_prefix:=svg_s1_%s\( \|\$\)$" % (R, NAME),
        r"docker cp isaac-sim:.*\.ulg .*runs/%s/drone_1_sysid2_" % NAME,
        r"\(other-commander check\)",
        r"docker exec %s mkdir -p %s$" % (R, re.escape(sent)),
        r"docker exec %s bash -c 'ls -d %s/svg_\* 2>/dev/null \| tail -1'" % (R, BAGS_C),
        r"tools/sim\.sh down$",
        r"verify down: exit 0, and no 'isaac-sim' process svg_multi_drone_single_domain\.py or px4",
        r"cp -a %s/svg_s1_%s_\S+ .*runs/%s/" % (stack, NAME, NAME),
        r"docker exec %s rm -rf %s/svg_s1_%s_" % (R, BAGS_C, NAME),
        r"docker exec %s rmdir %s$" % (R, re.escape(sent)),
        r"check every entry of runs/%s/preflight\.txt is still in" % NAME,
        r"write .*runs/%s/outside_writes\.txt" % NAME,
    ]
    pos = []
    for m in markers:
        hits = [i for i, ln in enumerate(dry) if re.search(m, ln)]
        assert hits, f"no dry-run line matches {m!r}:\n" + "\n".join(dry)
        pos.append(hits[-1] if m == r"\(real-drone check\)" and pos and pos[-1] > hits[0] else hits[0])
    assert pos == sorted(pos), list(zip(markers, pos))
    assert len([ln for ln in dry if "(real-drone check)" in ln]) == 2      # before the stick and before down
    assert "36 steps" in r.stdout
    down = pos[markers.index(r"tools/sim\.sh down$")]
    assert not any(re.search(r"docker cp %s:%s" % (R, BAGS_C), ln) for ln in dry[:down])
    assert not any(re.search(r"pkill .*-f ground_control\.launch\.py", ln) for ln in dry)
    assert_nothing_created()
    for call in docker_log.splitlines():   # read-only docker calls only: ps and pgrep inside a container
        assert call.startswith("ps") or " pgrep " in f" {call} ", call


def test_refuses_busy_gpu(tmp_path):
    for proc in ("/isaac-sim/kit/python/bin/python3", "kit", "/home/u/miniconda3/envs/env_isaaclab/bin/python"):
        r, docker_log = run(tmp_path / proc.replace("/", "_"), "--dry-run", NAME, gpu_lines=f"{GPU_FREE}\n4242, {proc}")
        assert r.returncode == 65, r.stdout + r.stderr
        assert "GPU busy" in r.stderr and "4242" in r.stderr
        assert "DRY: " not in r.stdout
        assert docker_log == ""
    assert_nothing_created()


def test_gnome_remote_desktop_is_not_busy(tmp_path):
    r, _ = run(tmp_path, "--dry-run", NAME)
    assert r.returncode == 0, r.stderr
    assert "GPU busy" not in r.stderr


def test_refuses_existing_run_folder(tmp_path):
    d = ROOT / "runs" / NAME
    d.mkdir()
    try:
        r, docker_log = run(tmp_path, "--dry-run", NAME)
        assert r.returncode == 65 and "already exists" in r.stderr
        assert "DRY: " not in r.stdout and docker_log == ""
        assert list(d.iterdir()) == []
    finally:
        d.rmdir()


def test_refuses_running_simulator(tmp_path):
    """Isaac container up: the fake docker answers every pgrep with success, so the launcher looks alive."""
    b, log = fake_bin(tmp_path, docker_ps="isaac-sim\nairstack-robot-desktop-1\n")
    env = dict(os.environ, PATH=f"{b}{os.pathsep}{os.environ['PATH']}", SVG_HOST_PY=child_python(),
               SVG_TEST_HOST_BAGS=str(bags_dir(tmp_path)), HOME=str(tmp_path / "home"))
    r = subprocess.run(["bash", str(SCRIPT), "--dry-run", NAME], capture_output=True, text=True, cwd=ROOT, env=env,
                       timeout=60)
    assert r.returncode == 65 and "simulator is already running" in r.stderr, r.stdout + r.stderr
    assert_nothing_created()


def test_usage():
    for args in ([], ["--dry-run"], ["bad name"], ["../x"], ["--frobnicate", NAME]):
        r = subprocess.run(["bash", str(SCRIPT), *args], capture_output=True, text=True, cwd=ROOT, timeout=60)
        assert r.returncode == 64, (args, r.stdout + r.stderr)
    assert_nothing_created()


def test_bag_removal_guard():
    def check(path):
        return subprocess.run(["bash", str(SCRIPT), "--check-bag-path", NAME, path], capture_output=True, text=True,
                              cwd=ROOT, timeout=60)

    for ok in (f"{BAGS_C}/svg_s1_{NAME}_20991231_235959", f"{BAGS_C}/svg_s1_{NAME}_20991231_235959_2"):
        r = check(ok)
        assert r.returncode == 0, (ok, r.stderr)
    for bad in (BAGS_C, f"{BAGS_C}/", f"{BAGS_C}/svg_20261112_094546", f"{BAGS_C}/hover_step_20261029_074525",
                f"{BAGS_C}/svg_s1_{NAME}_*", f"{BAGS_C}/svg_s1_{NAME}_20991231_235959/..",
                f"{BAGS_C}/svg_s1_{NAME}_20991231_235959/../svg_20261112_094546", f"{BAGS_C}/svg_s1_other_20991231_235959",
                f"/root/AirStack/robot/ros_ws/svg_s1_{NAME}_20991231_235959", f"{BAGS_C}/svg_s1_{NAME}_",
                f"{BAGS_C}/svg_s1_{NAME}_20991231_235959 /", "/", ""):
        r = check(bad)
        assert r.returncode == 2 and "refused" in r.stderr, (bad, r.stdout + r.stderr)


def test_refuses_bag_newer_than_start(tmp_path):
    """Someone is recording: an svg_* bag in the bags folder changed after the script started -> 66, nothing created."""
    future = time.time() + 3600
    bags = bags_dir(tmp_path, extra=(("svg_20991231_235959", future),))
    r, docker_log = run(tmp_path, "--dry-run", NAME, bags=bags)
    assert r.returncode == 66, r.stdout + r.stderr
    assert "svg_20991231_235959" in r.stderr and "recording" in r.stderr
    assert "DRY: " not in r.stdout and not any(" mkdir " in f" {c} " or " rm " in f" {c} " for c in docker_log.splitlines())
    assert_nothing_created()


def test_refuses_file_inside_bag_newer_than_start(tmp_path):
    bags = bags_dir(tmp_path)
    f = bags / "svg_20261112_094546" / "rec_0.mcap"
    f.write_text("x")
    t = time.time() + 3600
    os.utime(f, (t, t))
    r, _ = run(tmp_path, "--dry-run", NAME, bags=bags)
    assert r.returncode == 66 and "svg_20261112_094546" in r.stderr, r.stdout + r.stderr
    assert_nothing_created()


def test_refuses_bag_that_down_would_pick(tmp_path):
    """An old svg_* bag whose name sorts after ours: tools/sim.sh down (last name of ls) would take it -> 66."""
    bags = bags_dir(tmp_path, extra=(("svg_zz_20261101_000000", OLD_S),))
    r, _ = run(tmp_path, "--dry-run", NAME, bags=bags)
    assert r.returncode == 66 and "svg_zz_20261101_000000" in r.stderr and "would pick" in r.stderr, r.stdout + r.stderr
    assert_nothing_created()


def test_refuses_en_us_only_collation_case(tmp_path):
    """svg_s1_run10_* vs this run's svg_s1_run1_*: C puts it first ('0' < '_'), en_US.UTF-8 (underscores ignored at
    the first level, the robot image's LANG) puts it after — so `down` there would pick it -> 66."""
    bags = bags_dir(tmp_path, extra=(("svg_s1_run10_20261101_000000", OLD_S),))
    r, _ = run(tmp_path, "--dry-run", "run1", bags=bags)
    assert r.returncode == 66, r.stdout + r.stderr
    assert "svg_s1_run10_20261101_000000(en_US.UTF-8)" in r.stderr
    assert "svg_s1_run10_20261101_000000(C)" not in r.stderr
    assert not (ROOT / "runs" / "run1").exists()


def test_old_bags_allowed_missing_folder_refused(tmp_path):
    r, _ = run(tmp_path / "a", "--dry-run", NAME, bags=bags_dir(tmp_path / "a"))
    assert r.returncode == 0, r.stdout + r.stderr
    r, _ = run(tmp_path / "b", "--dry-run", NAME, bags=tmp_path / "missing")
    assert r.returncode == 66 and "does not exist" in r.stderr, r.stdout + r.stderr
    assert_nothing_created()


# ---------------------------------------------------------------------------------- NON-dry sessions (fake simulator)
def assert_clean_down(s):
    """down ran once, after the sentinel and the pick check; the sentinel is gone; the old bags are in place."""
    assert s.has(r"^sim down$")
    assert s.idx(rf"docker exec {R} mkdir -p {BAGS_C}/{s.sentinel}$") < s.idx(r"^sim down$")
    assert s.idx(r"bash -c ls -d .*svg_\* .*tail -1") < s.idx(r"^sim down$")
    assert not (s.bags / s.sentinel).exists() and not (s.stack / s.sentinel).exists()
    assert (s.bags / "svg_20261112_094546").is_dir() and (s.bags / "hover_step_20261029_074525").is_dir()
    assert not s.lock.exists()
    assert not s.has(r"pkill -INT -f ground_control\.launch\.py") and not s.has(r"sim down --force")


def test_session_complete(tmp_path):
    s = Session(tmp_path)
    assert s.r.returncode == 0, s.why()
    assert_clean_down(s)
    assert (s.out / s.bag / "metadata.yaml").is_file() and (s.out / s.bag / f"{s.bag}_0.mcap").stat().st_size == 1000
    assert not (s.bags / s.bag).exists()                         # the original removed (down's hook failed)
    assert s.idx(rf"docker exec {R} rm -rf {BAGS_C}/{s.bag}$") > s.idx(r"^sim down$")
    assert s.idx(r"pkill -INT -f bag_prefix:=svg_s1_run1\( \|\$\)$") < s.idx(r"^sim down$")
    assert (s.out / "drone_1_sysid2_23_59_59.ulg").is_file() and (s.out / "preflight.txt").is_file()
    assert "svg_20261112_094546" in s.text("preflight.txt")
    ow = s.text("outside_writes.txt")
    assert "all still in place" in ow and ".sim_test.lock" in ow and "STILL UP" not in ow
    assert not (s.out / "ABORTED.txt").exists()


def test_down_deleted_the_original(tmp_path):
    s = Session(tmp_path, {"hook_ok": True})
    assert s.r.returncode == 0, s.why()
    assert "already removed by tools/sim.sh down" in s.text("session.log")
    assert not s.has(rf"rm -rf {BAGS_C}/{s.bag}") and (s.out / s.bag / "metadata.yaml").is_file()
    assert_clean_down(s)


def test_collect_without_stack_copy(tmp_path):
    s = Session(tmp_path, {"down": "no_copy"})
    assert s.r.returncode == 0, s.why()
    assert s.idx(rf"docker cp {R}:{BAGS_C}/{s.bag} ") > s.idx(r"^sim down$")
    assert (s.out / s.bag / f"{s.bag}_0.mcap").stat().st_size == 1000 and not (s.bags / s.bag).exists()
    assert_clean_down(s)


def test_truncated_stack_copy_falls_back_to_container(tmp_path):
    s = Session(tmp_path, {"truncate_stack": True})
    assert s.r.returncode == 0, s.why()
    assert "does not match" in s.text("session.log") and s.has(rf"docker cp {R}:{BAGS_C}/{s.bag} ")
    assert (s.out / s.bag / f"{s.bag}_0.mcap").stat().st_size == 1000 and not (s.bags / s.bag).exists()


def test_size_check_gates_removal(tmp_path):
    s = Session(tmp_path, {"truncate_stack": True, "truncate_docker_cp": True})
    assert s.r.returncode == 1, s.why()
    assert (s.bags / s.bag / f"{s.bag}_0.mcap").stat().st_size == 1000          # original kept
    assert not s.has(rf"rm -rf {BAGS_C}/{s.bag}")
    assert "LEFT at" in s.text("session.log") and (s.out / "ABORTED.txt").is_file()
    assert not s.lock.exists()


@pytest.mark.parametrize("mode", ["fail", "stays_up"])
def test_down_failure_leaves_everything(tmp_path, mode):
    s = Session(tmp_path, {"down": mode})
    assert s.r.returncode == 5, s.why()
    assert (s.bags / s.bag / "metadata.yaml").is_file() and (s.bags / s.sentinel).is_dir()
    assert not s.has(r"rm -rf /root") and not s.has(r" rmdir ")
    for f in ("session.log", "ABORTED.txt", "outside_writes.txt"):
        assert "SIMULATOR STILL UP" in s.text(f), f
    assert not s.lock.exists() and not s.has(r"sim down --force")


def test_pick_check_blocks_down(tmp_path):
    s = Session(tmp_path, {"pick": f"{BAGS_C}/svg_20261112_094546"})
    assert s.r.returncode == 5, s.why()
    assert not s.has(r"^sim down") and "WOULD PICK '/root/AirStack/robot/ros_ws/bags/svg_20261112_094546'" in s.text("session.log")
    assert "SIMULATOR STILL UP" in s.text("ABORTED.txt") and (s.bags / s.bag).is_dir()


def test_sentinel_failure_blocks_down(tmp_path):
    s = Session(tmp_path, {"sentinel_mkdir_fail": True})
    assert s.r.returncode == 5, s.why()
    assert not s.has(r"^sim down") and "SENTINEL" in s.text("session.log")


@pytest.mark.parametrize("mode,capitals", [("precheck", True), ("precheck_port", False)])
def test_up_precheck_refusal_runs_no_down(tmp_path, mode, capitals):
    s = Session(tmp_path, {"up": mode})
    assert s.r.returncode == 65, s.why()
    assert not s.has(r"^sim down")
    assert ("REAL-DRONE/MOCAP SIGNAL FOUND BY tools/sim.sh up" in s.r.stdout) is capitals
    assert (s.out / "REFUSED.txt").is_file() and not s.lock.exists()


def test_up_failure_brings_the_simulator_down(tmp_path):
    s = Session(tmp_path, {"up": "fail"})
    assert s.r.returncode == 1, s.why()
    assert_clean_down(s)
    assert "stage=1" in s.text("ABORTED.txt") and not s.has("ros2 service call")


@pytest.mark.parametrize("on,sig,stage,landed,extra", [
    (r"^sim up", "TERM", 1, False, {}),
    (r"ros2 launch svg_ground_control", "TERM", 2, False, {}),           # nothing flew: no zeros, no land
    (r"virtual_stick\.py --config", "HUP", 3, True, {}),
    (r"virtual_stick\.py --config", "TERM", 3, False, {"stick_no_takeoff": True}),
    (r"mavros/state", "INT", 3, True, {}),
])
def test_trap_at_each_stage(tmp_path, on, sig, stage, landed, extra):
    s = Session(tmp_path, {"kill": [{"on": on, "sig": sig}], "stick_polls": 50, **extra})
    assert s.r.returncode == 3, s.why()
    assert f"stage={stage}" in s.text("ABORTED.txt") and f"signal {sig}" in s.text("ABORTED.txt")
    assert_clean_down(s)
    land = s.idx(r"ros2 service call /swarm_commander/land")
    assert (land >= 0) is landed and s.has(r"ros2 topic pub") is landed
    if not landed and stage >= 2:
        assert "no takeoff request by this run's stick and drone_1 not armed: no zeros and no land sent" in s.text("session.log")
    if stage >= 2:
        assert land < s.idx(r"^sim down$") < s.idx(rf"docker exec {R} rm -rf {BAGS_C}/{s.bag}$")
        assert (s.out / s.bag / "metadata.yaml").is_file() and not (s.bags / s.bag).exists()
        assert s.idx(r"pkill -INT -f bag_prefix:=svg_s1_run1\( \|\$\)$") < s.idx(r"^sim down$")


def test_signal_during_collect_is_ignored(tmp_path):
    s = Session(tmp_path, {"kill": [{"on": rf"docker exec {R} rm -rf {BAGS_C}/svg_s1_", "sig": "TERM"}]})
    assert s.r.returncode == 0, s.why()
    assert not (s.out / "ABORTED.txt").exists() and (s.out / s.bag / "metadata.yaml").is_file()
    assert_clean_down(s)


def test_moved_preexisting_bag_in_capitals(tmp_path):
    s = Session(tmp_path, {"down_moves_other": True})
    assert s.r.returncode == 0, s.why()
    assert "PRE-EXISTING BAG(S) NO LONGER IN" in s.r.stdout
    assert "svg_20261112_094546   PRE-EXISTING ENTRY NO LONGER IN PLACE" in s.text("outside_writes.txt")


def test_sim_own_topics_are_not_a_real_drone_signal(tmp_path):
    """L1.4 first run, 24 Nov 2026: the simulator's MAVROS pose, our mocap_bridge's /fmu/in relay and its unanswered
    /drone_N/pose subscription (a subscriber only) are not a real drone: the session completes."""
    s = Session(tmp_path, {"sim_topics": True})
    assert s.r.returncode == 0, s.why()
    assert "REAL-DRONE/MOCAP SIGNAL" not in s.text("session.log")


@pytest.mark.parametrize("call,flew", [(1, False), (2, True)])
def test_mocap_publisher_on_pose_is_a_real_drone_signal(tmp_path, call, flew):
    """A mocap bridge publishing /drone_N/pose (another machine on the domain) still stops the session, no down."""
    s = Session(tmp_path, {"mocap_pub_on_call": [call]})
    assert s.r.returncode == 67, s.why()
    assert not s.has(r"^sim down") and "REAL-DRONE/MOCAP SIGNAL" in s.text("session.log")
    assert "/drone_1/pose" in s.text("session.log")
    assert s.has(r"virtual_stick\.py --config") is flew


@pytest.mark.parametrize("call,flew", [(1, False), (2, True)])
def test_real_drone_signal_stops_without_down(tmp_path, call, flew):
    s = Session(tmp_path, {"real_topics_on_call": [call]})
    assert s.r.returncode == 67, s.why()
    assert not s.has(r"^sim down") and "REAL-DRONE/MOCAP SIGNAL" in s.text("session.log")
    assert s.has(r"virtual_stick\.py --config") is flew
    assert s.has(r"pkill -INT -f bag_prefix:=svg_s1_run1\( \|\$\)$") and not s.has(r"pkill -INT -f ground_control\.launch\.py")
    assert "SIMULATOR STILL UP" in s.text("ABORTED.txt") and not s.lock.exists()


def test_held_lock_refuses(tmp_path):
    s = Session(tmp_path, lock_pid=os.getpid())
    assert s.r.returncode == 65 and "lock" in s.r.stderr, s.why()
    assert s.calls == [] or all(c.startswith("docker ps") or " pgrep " in c for c in s.calls)
    assert not s.out.exists() and s.lock.read_text().strip() == str(os.getpid())


# ------------------------------------------------------------------------------------------ the stick, fake rclpy
class FakeWorld:
    """A one-drone commander + odometry, driven by the stick's own publisher and service calls."""

    def __init__(self, hover_z=1.2, k=1.0, status_pubs=1, extra_subs=(), idle=True, mode="sim", topics=()):
        self.lock = threading.Lock()
        self.mode, self.topics = mode, list(topics)    # the drone's status `mode` (None = field absent); graph topics
        self.checks, self.pub_times = [], []
        self.z, self.vz, self.k, self.hover_z = 0.07, 0.0, k, hover_z
        self.state = "IDLE" if idle else "ARMING"
        self.mission, self.t_event, self.pid = False, None, 42
        self.status_pubs, self.extra_subs = status_pubs, list(extra_subs)
        self.status_on, self.never_active, self.commander_subscribed = True, False, True
        self.calls, self.published, self.subs, self.timers = [], [], {}, []
        self.on_moving, self.moving_fired = None, False
        self.on_takeoff, self.takeoff_no_answer = None, False

    def service(self, name):
        with self.lock:
            self.calls.append(name)
            if name == "takeoff" and self.state == "IDLE":
                self.state, self.t_event = "ASCEND", time.monotonic()
                hook = self.on_takeoff
            else:
                hook = None
        if hook:
            hook(self)
        with self.lock:
            if name == "takeoff" and self.state == "ASCEND":
                return True, "takeoff: drone_1"
            if name == "start":
                if self.state != "ACTIVE":
                    return False, "not all drones holding yet: drone_1"
                self.mission = True
                return True, 'scenario "hover" running'
            if name == "land" and self.state in ("ASCEND", "ACTIVE"):
                self.state, self.mission, self.t_event = "LANDING", False, time.monotonic()
                return True, "landing: drone_1"
            return False, "no"

    def publish(self, msg):
        v = msg.twist.linear
        with self.lock:
            self.pub_times.append(time.monotonic())
            self.published.append((v.x, v.y, v.z))
            self.vz = v.z
            fire = (v.x or v.y or v.z) and not self.moving_fired and self.on_moving
            if fire:
                self.moving_fired = True
        if fire:
            self.on_moving(self)

    def tick(self, dt):
        with self.lock:
            now = time.monotonic()
            if self.state == "ASCEND" and not self.never_active and now - self.t_event > 0.1:
                self.state, self.z = "ACTIVE", self.hover_z
            elif self.state == "LANDING" and now - self.t_event > 0.1:
                self.state, self.z = "IDLE", 0.07
            elif self.state == "ACTIVE" and self.mission:
                self.z += self.vz * dt * self.k
            status = None
            if self.status_on:
                d = {"name": "drone_1", "state": self.state, "odom_fresh": True}
                if self.mode is not None:
                    d["mode"] = self.mode
                status = json.dumps({"pid": self.pid, "node": "/swarm_commander", "scenario": "hover",
                                     "mission_active": self.mission, "tuning": {"teleop_max_speed_mps": 2.0},
                                     "drones": [d]})
            z = self.z
        for cb in self.subs.get("/drone_1/odometry_conversion/odometry", []):
            cb(types.SimpleNamespace(pose=types.SimpleNamespace(pose=types.SimpleNamespace(
                position=types.SimpleNamespace(z=z)))))
        if status is not None:
            for cb in self.subs.get("/svg/commander_status", []):
                cb(types.SimpleNamespace(data=status))


def fake_ros(world):
    """sys.modules entries for rclpy, geometry_msgs, nav_msgs, std_msgs, std_srvs backed by world."""
    ns = types.SimpleNamespace
    info = lambda n: ns(node_name=n, node_namespace="/")  # noqa: E731

    class Twist:
        def __init__(self):
            self.header = ns(stamp=None, frame_id="")
            self.twist = ns(linear=ns(x=0.0, y=0.0, z=0.0), angular=ns(x=0.0, y=0.0, z=0.0))

    class Future:
        def __init__(self, res):
            self._r = res

        def done(self):
            return True

        def result(self):
            return self._r

    class Client:
        def __init__(self, name):
            self.name = name.rsplit("/", 1)[-1]

        def wait_for_service(self, timeout_sec=None):
            return True

        def call_async(self, _req):
            ok, msg = world.service(self.name)
            if self.name == "takeoff" and world.takeoff_no_answer:
                return ns(done=lambda: False, result=lambda: None)      # accepted, but the answer never comes
            return Future(ns(success=ok, message=msg))

    class Node:
        def get_name(self):
            return "svg_s1_virtual_stick"

        def create_publisher(self, _t, _topic, _q):
            return ns(publish=world.publish, get_subscription_count=lambda: 1)

        def create_subscription(self, _t, topic, cb, _q):
            world.subs.setdefault(topic, []).append(cb)

        def create_timer(self, period, cb):
            world.timers.append([period, cb, 0.0])

        def create_client(self, _t, name):
            return Client(name)

        def destroy_client(self, _c):
            pass

        def destroy_node(self):
            pass

        def get_clock(self):
            return ns(now=lambda: ns(to_msg=lambda: None))

        def count_publishers(self, topic):
            world.checks.append(time.monotonic())
            return world.status_pubs if topic == "/svg/commander_status" else 1

        def get_subscriptions_info_by_topic(self, _topic):
            mine = [info("swarm_commander")] if world.commander_subscribed else []
            return mine + [info("rosbag2_recorder")] + [info(n) for n in world.extra_subs]

        def get_publishers_info_by_topic(self, _topic):
            return [info("svg_s1_virtual_stick")]

        def get_topic_names_and_types(self):
            base = ["/svg/commander_status", "/svg/drone_1/teleop_command", "/drone_1/odometry_conversion/odometry"]
            return [(t, ["x/msg/X"]) for t in base + world.topics]

    class Executor:
        def __init__(self):
            self.stop = False

        def add_node(self, _n):
            pass

        def spin(self):
            last = time.monotonic()
            while not self.stop:
                now = time.monotonic()
                for t in world.timers:
                    if now >= t[2]:
                        t[1]()
                        t[2] = now + t[0]
                world.tick(now - last)
                last = now
                time.sleep(0.005)

        def shutdown(self):
            self.stop = True

    rclpy = types.ModuleType("rclpy")
    rclpy.init = lambda **_k: None
    rclpy.create_node = lambda _n: Node()
    rclpy.try_shutdown = lambda: None
    rclpy.shutdown = lambda: None
    mods = {"rclpy": rclpy,
            "rclpy.executors": types.ModuleType("rclpy.executors"),
            "rclpy.qos": types.ModuleType("rclpy.qos"),
            "rclpy.signals": types.ModuleType("rclpy.signals"),
            "geometry_msgs": types.ModuleType("geometry_msgs"), "geometry_msgs.msg": types.ModuleType("geometry_msgs.msg"),
            "nav_msgs": types.ModuleType("nav_msgs"), "nav_msgs.msg": types.ModuleType("nav_msgs.msg"),
            "std_msgs": types.ModuleType("std_msgs"), "std_msgs.msg": types.ModuleType("std_msgs.msg"),
            "std_srvs": types.ModuleType("std_srvs"), "std_srvs.srv": types.ModuleType("std_srvs.srv")}
    mods["rclpy.executors"].SingleThreadedExecutor = Executor
    mods["rclpy.qos"].qos_profile_sensor_data = None
    mods["rclpy.signals"].SignalHandlerOptions = ns(NO="no")
    mods["geometry_msgs.msg"].TwistStamped = Twist
    mods["nav_msgs.msg"].Odometry = object
    mods["std_msgs.msg"].String = object
    mods["std_srvs.srv"].Trigger = ns(Request=lambda: None)
    return mods


@pytest.fixture
def stick(monkeypatch, tmp_path):
    """(run, vs): run(world, steps=None) runs the stick's session on a 2-step z plan (0.5 m/s, hold 0.3 s, gap 0.1 s)."""
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    import virtual_stick as vs
    for k, v in dict(STATUS_WAIT_S=1.0, SUB_WAIT_S=1.0, HOLD_WAIT_S=1.0, START_EVERY_S=0.05, LAND_WAIT_S=1.0, CALL_TIMEOUT_S=0.3,
                     ODOM_STALE_S=0.3, STATUS_STALE_S=0.3).items():
        monkeypatch.setattr(vs, k, v)

    def run(world, steps=None):
        for name, mod in fake_ros(world).items():
            monkeypatch.setitem(sys.modules, name, mod)
        plan = vs.build_plan(steps or {"speeds_mps": [0.5], "axes": ["z"], "hold_s": 0.3, "signs": [1, -1],
                                       "repeats": 1}, gap_s=0.1)
        flown = tmp_path / "flown.json"
        old = signal.getsignal(signal.SIGTERM)
        rc = vs.run_session(plan, "drone_1", str(flown))
        assert signal.getsignal(signal.SIGTERM) is old                 # handlers restored
        return rc, (json.loads(flown.read_text()) if flown.exists() else None)

    return run, vs


def test_stick_session_complete_zeros_and_lands(stick, capsys):
    run, _ = stick
    w = FakeWorld()
    rc, flown = run(w)
    assert rc == 0, capsys.readouterr().out
    assert w.checks and w.pub_times and min(w.pub_times) > min(w.checks)   # nothing published before the check
    assert w.calls[0] == "takeoff" and "start" in w.calls and w.calls[-1] == "land"
    assert any(p[2] > 0 for p in w.published) and any(p[2] < 0 for p in w.published)
    assert w.published[-1] == (0.0, 0.0, 0.0) and flown["reached"] == 2
    assert "landed: drone_1 IDLE" in capsys.readouterr().out


def test_stick_stop_lands(stick, capsys):
    run, _ = stick
    w = FakeWorld()
    w.on_moving = lambda _w: os.kill(os.getpid(), signal.SIGTERM)
    rc, _ = run(w)
    out = capsys.readouterr().out
    assert rc == 3 and "stopped by SIGTERM" in out, out
    assert w.calls[-1] == "land" and w.published[-1] == (0.0, 0.0, 0.0)


def test_stick_floor_skip(stick, capsys):
    """Hover at 0.9 m and +z does not climb (k=0): the -z step's predicted bottom 0.9 - 0.5 * 0.3 * 1.4 = 0.69 m
    < 0.5 + 0.3 m, so it is skipped and no descending command is ever sent."""
    run, _ = stick
    w = FakeWorld(hover_z=0.9, k=0.0)
    rc, flown = run(w)
    out = capsys.readouterr().out
    assert rc == 0 and "FLOOR GUARD: step 2 not flown" in out, out
    assert flown["steps"][1]["skipped"] and not any(p[2] < 0 for p in w.published)


def test_stick_floor_cut(stick, monkeypatch, capsys):
    run, vs = stick
    monkeypatch.setattr(vs, "FLOOR_PREDICT_SCALE", 0.0)       # never skip: exercise the in-step cut
    w = FakeWorld(hover_z=0.85, k=1.0)                         # +z to ~1.0; -z cut once z - 0.5 * 0.8 < 0.5
    rc, flown = run(w)
    out = capsys.readouterr().out
    assert rc == 0 and "FLOOR GUARD: step 2 cut" in out, out
    assert flown["steps"][1]["cut"] and not flown["steps"][1]["skipped"]


def test_stick_refuses_two_commanders(stick, capsys):
    """A second commander before takeoff: nothing published (zeros included), no service call, exit 67."""
    run, _ = stick
    for w, why in ((FakeWorld(status_pubs=2), "2 publishers"), (FakeWorld(extra_subs=["swarm_commander"]), "subscribers")):
        rc, _ = run(w)
        out = capsys.readouterr().out
        assert rc == 67 and "refused" in out and why in out and "NOTHING SENT" in out, out
        assert w.calls == [] and w.published == []


def test_stick_publishes_nothing_before_the_check(stick, capsys):
    """Refusals before the one-commander check passed (never IDLE, no commander subscribed) publish nothing."""
    run, _ = stick
    w = FakeWorld(idle=False)
    rc, _ = run(w)
    assert rc == 1 and w.published == [] and w.calls == [], capsys.readouterr().out
    w = FakeWorld()
    w.commander_subscribed = False
    rc, _ = run(w)
    out = capsys.readouterr().out
    assert rc == 1 and "not subscribed" in out and w.published == [] and w.calls == [], out


def test_stick_foreign_status_no_land(stick, capsys):
    """Foreign status mid-flight: no land (it reaches every commander), no zeros after detection, exit 67."""
    run, _ = stick
    w = FakeWorld()
    w.on_moving = lambda ww: setattr(ww, "pid", 99)
    rc, _ = run(w)
    out = capsys.readouterr().out
    assert rc == 67 and "second process" in out and "NO ZEROS, NO LAND" in out, out
    assert "land" not in w.calls and "takeoff" in w.calls


def test_stick_stale_status_lands(stick, capsys):
    run, _ = stick
    w = FakeWorld()
    w.on_moving = lambda ww: setattr(ww, "status_on", False)
    rc, _ = run(w)
    out = capsys.readouterr().out
    assert rc == 4 and "commander status stale" in out, out
    assert w.calls[-1] == "land" and w.published[-1] == (0.0, 0.0, 0.0)


def test_stick_timeouts(stick, capsys):
    run, _ = stick
    w = FakeWorld(idle=False)                   # never IDLE: refused, nothing flown
    rc, _ = run(w)
    assert rc == 1 and w.calls == [] and "never showed drone_1 IDLE" in capsys.readouterr().out
    w = FakeWorld()
    w.never_active = True                       # takeoff accepted, never ACTIVE: flight error, land
    rc, _ = run(w)
    out = capsys.readouterr().out
    assert rc == 4 and "not ACTIVE" in out and w.calls == ["takeoff", "land"], out


def test_floor_rules():
    sys.path.insert(0, str(ROOT / "scripts"))
    import virtual_stick as vs
    assert vs.floor_skip(1.0, -0.5, 3.0)
    assert vs.floor_skip(2.8, -0.5, 3.0) and not vs.floor_skip(3.0, -0.5, 3.0)   # 3.0 - 2.1 = 0.9 >= 0.8
    assert not vs.floor_skip(0.1, 0.5, 3.0)                                       # climbing steps never skipped
    assert vs.floor_cut(0.89, -0.5) and not vs.floor_cut(0.91, -0.5)              # 0.5 * (0.7 + 0.1) = 0.4
    assert vs.floor_cut(2.65, -2.0) and not vs.floor_cut(2.75, -2.0)              # 2.0 * (0.7 + 0.4) = 2.2
    assert not vs.floor_cut(0.1, 0.5)                                              # climbing steps never cut


def test_stage_failure_without_takeoff_sends_no_land(tmp_path):
    """The stick refused before takeoff (exit 1): the host dies at stage 3 but sends no zeros and no land."""
    s = Session(tmp_path, {"stick_rc": 1, "stick_no_takeoff": True})
    assert s.r.returncode == 1, s.why()
    assert not s.has(r"ros2 service call") and not s.has(r"ros2 topic pub")
    assert "no takeoff request by this run's stick" in s.text("session.log")
    assert_clean_down(s)


def test_stick_second_commander_leaves_up(tmp_path):
    """Stick exit 67: nothing sent, our commander stopped by its prefix, no down, exit 67 in capitals."""
    s = Session(tmp_path, {"stick_rc": 67})
    assert s.r.returncode == 67, s.why()
    assert not s.has(r"^sim down") and not s.has(r"ros2 service call") and not s.has(r"ros2 topic pub")
    assert s.has(r"pkill -INT -f bag_prefix:=svg_s1_run1\( \|\$\)$")
    assert "SECOND COMMANDER" in s.text("session.log") and "SIMULATOR STILL UP" in s.text("ABORTED.txt")
    assert (s.bags / s.bag).is_dir() and not s.lock.exists()


@pytest.mark.parametrize("scenario,what", [({"foreign_commander": True}, "teleop_real_drone_2.yaml"),
                                           ({"status_pubs_after_stop": 1}, "publishers: 1")])
def test_other_commander_blocks_down(tmp_path, scenario, what):
    """I2: after ours is stopped, another commander process in the robot container, or any /svg/commander_status
    publisher on the domain -> no down (it would SIGINT that commander), exit 67."""
    s = Session(tmp_path, scenario)
    assert s.r.returncode == 67, s.why()
    assert not s.has(r"^sim down") and "OTHER COMMANDER PRESENT" in s.text("session.log") and what in s.text("session.log")
    assert not s.has(rf"mkdir -p {BAGS_C}/{s.sentinel}")       # checked before the sentinel
    assert "SIMULATOR STILL UP" in s.text("outside_writes.txt") and (s.bags / s.bag).is_dir()


# ------------------------------------------------------------------------- round 4: may-be-airborne from the request on
def test_stick_takeoff_timeout_lands(stick, capsys):
    """The takeoff request is accepted but its answer never comes: the stick still lands (exit 4)."""
    run, _ = stick
    w = FakeWorld()
    w.takeoff_no_answer = True
    rc, _ = run(w)
    out = capsys.readouterr().out
    assert rc == 4 and "takeoff: success=False message='no answer'" in out, out
    assert w.calls == ["takeoff", "land"] and "landed: drone_1 IDLE" in out
    assert out.index("pre-takeoff:") < out.index("takeoff: success")


def test_stick_kill_during_takeoff_lands(stick, capsys):
    run, _ = stick
    w = FakeWorld()
    w.on_takeoff = lambda _w: os.kill(os.getpid(), signal.SIGTERM)
    rc, _ = run(w)
    out = capsys.readouterr().out
    assert rc == 3 and "stopped by SIGTERM" in out, out
    assert w.calls == ["takeoff", "land"]


def test_stick_second_commander_after_pre_takeoff_no_land(stick, capsys):
    """A second commander appears with the takeoff request: precedence -> nothing sent, not even land; exit 67."""
    run, _ = stick
    w = FakeWorld()
    w.on_takeoff = lambda ww: setattr(ww, "status_pubs", 2)
    rc, _ = run(w)
    out = capsys.readouterr().out
    assert rc == 67 and "NO ZEROS, NO LAND" in out, out
    assert "land" not in w.calls and "takeoff" in w.calls


def test_abort_lands_after_pre_takeoff_only(tmp_path):
    """Killed while the takeoff request is in flight (only `pre-takeoff:` in stick.log): the host lands."""
    s = Session(tmp_path, {"stick_pre_takeoff_only": True, "stick_polls": 50,
                           "kill": [{"on": r"virtual_stick\.py --config", "sig": "TERM"}]})
    assert s.r.returncode == 3, s.why()
    assert s.has(r"ros2 service call /swarm_commander/land") and s.has(r"ros2 topic pub")
    assert s.idx(r"ros2 service call /swarm_commander/land") < s.idx(r"^sim down$")
    assert_clean_down(s)


def test_takeoff_timeout_host_lands(tmp_path):
    """The stick's takeoff call timed out (exit 4, only `pre-takeoff:`): the host's failure path lands too."""
    s = Session(tmp_path, {"stick_pre_takeoff_only": True, "stick_rc": 4})
    assert s.r.returncode == 1, s.why()
    assert s.has(r"ros2 service call /swarm_commander/land")
    assert_clean_down(s)


def test_abort_lands_when_armed(tmp_path):
    """No stick line at all, but MAVROS says drone_1 is armed: the host lands, then waits for the disarm."""
    s = Session(tmp_path, {"stick_no_takeoff": True, "armed_until_land": True, "stick_polls": 50,
                           "kill": [{"on": r"virtual_stick\.py --config", "sig": "TERM"}]})
    assert s.r.returncode == 3, s.why()
    assert s.has(r"ros2 service call /swarm_commander/land") and "disarmed" in s.text("session.log")
    assert_clean_down(s)


def test_abort_second_commander_after_pre_takeoff_no_land(tmp_path):
    """stick.log has `pre-takeoff:` AND a SECOND COMMANDER line: precedence 1 -> nothing sent, exit 67, no down."""
    s = Session(tmp_path, {"stick_rc": 67, "stick_polls": 50,
                           "kill": [{"on": r"virtual_stick\.py --config", "sig": "TERM"}]})
    assert s.r.returncode == 67, s.why()
    assert "pre-takeoff:" in s.text("stick.log")
    assert not s.has(r"ros2 service call") and not s.has(r"ros2 topic pub") and not s.has(r"^sim down")
    assert "MAY STILL BE IN THE AIR" in s.text("ABORTED.txt")


def test_abort_with_two_status_publishers_sends_nothing(tmp_path):
    """`pre-takeoff:` but another commander also publishes status: precedence 2 -> nothing sent; then 67 before down."""
    s = Session(tmp_path, {"stick_pre_takeoff_only": True, "status_pubs_after_stop": 1, "stick_polls": 50,
                           "kill": [{"on": r"virtual_stick\.py --config", "sig": "TERM"}]})
    assert s.r.returncode == 67, s.why()
    assert not s.has(r"ros2 service call") and not s.has(r"ros2 topic pub") and not s.has(r"^sim down")
    assert "not our one commander" in s.text("session.log") and "OTHER COMMANDER PRESENT" in s.text("session.log")


# ------------------------------------------------------------------- round 5 (R4-m1): re-check before the abort land
def test_stick_takeoff_timeout_with_second_commander_no_land(stick, capsys):
    """The takeoff request is accepted but unanswered, and a second commander appears meanwhile (not yet seen by
    health()): the re-check before the abort land finds it -> nothing sent, no land, exit 67."""
    run, _ = stick
    w = FakeWorld()
    w.takeoff_no_answer = True
    w.on_takeoff = lambda ww: setattr(ww, "status_pubs", 2)
    rc, _ = run(w)
    out = capsys.readouterr().out
    assert rc == 67 and "re-check before the abort land" in out and "NO ZEROS, NO LAND" in out, out
    assert w.calls == ["takeoff"]


def test_stick_takeoff_timeout_unreadable_count_no_land(stick, capsys):
    """Same, but the commander count cannot be read: fail closed -> nothing sent, exit 67."""
    run, _ = stick
    w = FakeWorld()
    w.takeoff_no_answer = True

    def broken(ww):
        ww.status_pubs = None                       # count_publishers then returns None: the comparison raises

    w.on_takeoff = broken
    rc, _ = run(w)
    out = capsys.readouterr().out
    assert rc == 67 and "commander count unreadable" in out, out
    assert w.calls == ["takeoff"]


# ------------------------------------------------- final review I1: the stick refuses unless the drone is simulated
REAL_DRONE = "REAL DRONE MAY BE PRESENT"


@pytest.mark.parametrize("world_kw,why", [
    (dict(mode="real"), "mode 'real'"),
    (dict(mode=None), "mode None"),
    (dict(topics=["/fmu/out/vehicle_status"]), "/fmu/out/vehicle_status"),
    (dict(topics=["/drone_2/fmu/in/vehicle_visual_odometry"]), "/drone_2/fmu/in/vehicle_visual_odometry"),
])
def test_stick_refuses_real_drone(stick, capsys, world_kw, why):
    """Status mode not "sim" (or absent), or any /fmu/ topic on the domain: exit 67, capitals, NOTHING published and
    NO service call (not even land)."""
    run, _ = stick
    w = FakeWorld(**world_kw)
    rc, flown = run(w)
    out = capsys.readouterr().out
    assert rc == 67 and REAL_DRONE in out and why in out, out
    assert w.published == [] and w.calls == []
    assert flown["reached"] == 0


def test_stick_refuses_unreadable_status(stick, capsys):
    """No commander status ever read: the mode cannot be checked -> refusal, exit 67, nothing sent."""
    run, _ = stick
    w = FakeWorld()
    w.status_on = False
    rc, _ = run(w)
    out = capsys.readouterr().out
    assert rc == 67 and REAL_DRONE in out and "no readable" in out, out
    assert w.published == [] and w.calls == []


def test_stick_sim_check_passes_then_flies(stick, capsys):
    """Mode "sim" and no /fmu/ topic: the check is logged, then the session flies as before."""
    run, _ = stick
    w = FakeWorld(topics=["/drone_1/interface/mavros/state"])
    rc, _ = run(w)
    out = capsys.readouterr().out
    assert rc == 0 and "simulator check: drone_1 mode sim, no /fmu/ topic" in out, out
    assert out.index("simulator check:") < out.index("pre-takeoff:")


def test_host_names_the_real_drone_refusal(tmp_path):
    """Stick exit 67 because it saw a real drone: the host leaves everything up and says so, not 'second commander'."""
    s = Session(tmp_path, {"stick_rc": 67, "stick_real_drone": True, "stick_no_takeoff": True})
    assert s.r.returncode == 67, s.why()
    assert not s.has(r"^sim down") and not s.has(r"ros2 service call") and not s.has(r"ros2 topic pub")
    assert "REAL DRONE MAY BE PRESENT" in s.text("session.log") and "SECOND COMMANDER" not in s.text("session.log")
