# tools/tests/test_auto_grid_scripts.py — slam_up.sh / slam_down.sh start and stop the auto grid (sim only, source level)
import pathlib, re, unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
UP = (ROOT / "localisation/scripts/slam_up.sh").read_text()
DOWN = (ROOT / "localisation/scripts/slam_down.sh").read_text()
BEGIN, END = "# --- auto grid", "# --- end auto grid"


def block():
    return UP[UP.index(BEGIN):UP.index(END)]


class SlamUp(unittest.TestCase):
    def test_block_is_after_the_bridge_and_before_the_detach_exit(self):
        self.assertLess(UP.index("foxglove_bridge_isaac.sh"), UP.index(BEGIN))
        self.assertLess(UP.index(END), UP.index('[ "${1:-}" = "--detach" ]') if '[ "${1:-}" = "--detach" ]' in UP
                        else UP.index('[ "${1:-}" = --detach ]'))

    def test_odom_copy_runs_from_the_mount_with_its_log(self):
        b = block()
        self.assertIn("/teleop-foxglove/auto_grid.py --source odom --drone drone_1", b)
        self.assertIn("results/auto_grid.log", b)
        self.assertIn("test -f /teleop-foxglove/auto_grid.py", b)
        self.assertIn("exd ", b)

    def test_odom_copy_does_not_set_the_bridge_profile(self):
        self.assertNotIn("FASTRTPS_DEFAULT_PROFILES_FILE", block())
        self.assertNotIn("fastdds_bridge", block())

    def test_status_copy_goes_into_the_robot_container(self):
        b = block()
        self.assertIn("airstack-robot-desktop-1", b)
        self.assertIn("/tmp/svg_grid", b)
        self.assertEqual(b.count("docker cp"), 2)
        self.assertIn("auto_grid.py", b); self.assertIn("grid_core.py", b)
        self.assertIn("docker exec -d", b)
        self.assertIn("bash -ic", b)
        self.assertIn("--source status", b)
        self.assertIn("auto_grid.log", b)
        self.assertIn("already running", b)
        self.assertIn("WARNING", b)

    def test_no_path_in_the_block_can_exit_non_zero(self):
        b = block()
        self.assertNotRegex(b, r"\bexit\b")
        self.assertNotRegex(b, r"\breturn\b")
        depth = 0
        for raw in b.splitlines():
            line = raw.strip()
            if re.match(r"^(if|elif)\b", line):
                depth += 1
                continue
            if line == "fi":
                depth -= 1
                continue
            if depth == 0 and re.match(r"^(docker|ex|exd)\b", line):
                self.assertRegex(line, r"\|\| ", "unguarded under set -e: " + line)

    def test_ctrl_c_path_goes_through_slam_down(self):
        self.assertIn("./scripts/slam_down.sh", UP[UP.index("trap "):])


class SlamDown(unittest.TestCase):
    def test_stops_the_status_copy_in_the_robot_container_tolerantly(self):
        self.assertRegex(DOWN, r"docker exec airstack-robot-desktop-1 pkill[^\n]*svg_grid/auto_grid[^\n]*\|\| true")

    def test_status_copy_is_stopped_before_the_exploration_container_check(self):
        self.assertLess(DOWN.index("svg_grid/auto_grid"), DOWN.index("not running"))


if __name__ == "__main__":
    unittest.main()
