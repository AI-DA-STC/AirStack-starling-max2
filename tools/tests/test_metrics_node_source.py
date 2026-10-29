# tools/tests/test_metrics_node_source.py
import ast, pathlib, py_compile, unittest
LIVE = pathlib.Path(__file__).resolve().parents[1] / "live"
class NodeSource(unittest.TestCase):
    def test_compiles(self):
        for f in ("metrics_node.py", "bag_recompute.py"): py_compile.compile(str(LIVE / f), doraise=True)
    def test_node_uses_metrics_core_and_the_spec_topics(self):
        src = (LIVE / "metrics_node.py").read_text()
        for needle in ("import metrics_core", "/svg/test/", "Float64", "Int32", "offset_sanity", "REFUSED", "metrics_node: ready", "--publish-hz", "header.stamp"):
            self.assertIn(needle, src, needle)
    def test_recompute_never_refetches_params(self):
        src = (LIVE / "bag_recompute.py").read_text()
        self.assertIn("--meta-from", src); self.assertNotIn("ros2 param", src); self.assertIn("rosbag2_py", src)
    def test_no_top_level_ros_import_in_core(self):
        tree = ast.parse((LIVE / "metrics_core.py").read_text())
        names = {n.names[0].name.split(".")[0] for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom)) for _ in [0]} | {n.module.split(".")[0] for n in tree.body if isinstance(n, ast.ImportFrom) and n.module}
        self.assertFalse(names & {"rclpy", "rosbag2_py", "std_msgs", "nav_msgs"}, names)
