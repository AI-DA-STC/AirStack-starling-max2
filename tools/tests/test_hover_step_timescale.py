# tools/tests/test_hover_step_timescale.py
import pathlib, sys, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import hover_step_timescale as T

class Transitions(unittest.TestCase):
    def test_first_arm_then_disarm(self):
        ts = [i * 1_000_000 for i in range(10)]
        st = [1, 1, 2, 2, 2, 1, 1, 2, 1, 1]
        self.assertEqual(T.arming_transitions(ts, st), (2.0, 5.0))
    def test_never_armed(self):
        self.assertEqual(T.arming_transitions([0, 1_000_000], [1, 1]), (None, None))
    def test_format_line(self):
        self.assertEqual(T.format_line(293.840613, 394.710525, "/tmp/x/07_39_26.ulg", 3),
                         "arm_s=293.840613 disarm_s=394.710525 interval_s=100.869912 source=07_39_26.ulg sysid=3")
