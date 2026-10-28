# tools/tests/test_hover_step_plot.py
import json, pathlib, shutil, sys, tempfile, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import hover_step_plot as P
import hover_step_analysis as A
FX = pathlib.Path(__file__).resolve().parent / "fixtures" / "run1"

class Plot(unittest.TestCase):
    def test_panel_order_handles_n_steps(self):
        ev = [{"name": n} for n in ["takeoff_lateral_x", "takeoff", "step_x_1", "step_x_2", "step_z_1", "landing"]]
        self.assertEqual([n for n, _ in P.panel_order(ev)], ["takeoff", "step_x_1", "step_x_2", "step_z_1", "landing"])

    def test_panel_order_sorts_by_step_index_not_lexically(self):
        ev = [{"name": n} for n in ["step_x_10", "step_z_2", "step_x_2", "landing", "takeoff", "step_z_1", "step_x_1"]]
        self.assertEqual([n for n, _ in P.panel_order(ev)],
                         ["takeoff", "step_x_1", "step_x_2", "step_x_10", "step_z_1", "step_z_2", "landing"])

    def test_renders_png_from_fixture(self):
        with tempfile.TemporaryDirectory() as d:
            out = pathlib.Path(d)
            for f in ("drone_1_odom.csv", "drone_1_cmd.csv", "drone_1_state.csv", "px4_arm_times.txt"): shutil.copy(FX / f, out / f)
            odom, cmd, state = A.load_xyz_csv(out / "drone_1_odom.csv"), A.load_xyz_csv(out / "drone_1_cmd.csv"), A.load_state_csv(out / "drone_1_state.csv")
            (out / "bag_analysis.json").write_text(json.dumps(A.analyse(odom, cmd, state, px4_arm_times=A.load_px4_arm_times(out / "px4_arm_times.txt"))))
            P.main([str(out)])
            self.assertGreater((out / "step_response.png").stat().st_size, 20_000)
