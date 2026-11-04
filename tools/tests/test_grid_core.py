# tools/tests/test_grid_core.py — the auto-growing Foxglove grid, pure logic (sim only)
import math, pathlib, sys, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "teleop" / "foxglove"))
from grid_core import GrowingGrid  # noqa: E402


def extent(g):
    """(xs, ys) of the line coordinates, vertical lines have constant x."""
    ls = g.lines()
    xs = sorted({a[0] for a, b in ls if a[0] == b[0]})
    ys = sorted({a[1] for a, b in ls if a[1] == b[1]})
    return xs, ys


class Growth(unittest.TestCase):
    def test_defaults(self):
        g = GrowingGrid()
        self.assertEqual((g.half, g.cell), (10.0, 1.0))
        self.assertEqual(g.lines(), [])                       # nothing before the first position

    def test_first_position_sets_centre_snapped_to_cell(self):
        g = GrowingGrid()
        self.assertTrue(g.update(103.4, -57.6))
        self.assertEqual((g.cx, g.cy), (103.0, -58.0))

    def test_first_position_far_from_origin_keeps_start_size(self):
        g = GrowingGrid()
        g.update(5000.0, -3000.0)
        self.assertEqual(g.half, 10.0)

    def test_no_change_inside_the_margin(self):
        g = GrowingGrid()
        g.update(0, 0)
        for p in ((7.4, 0), (-7.4, 0), (0, 7.4), (0, -7.4), (7.4, -7.4)):
            self.assertFalse(g.update(*p), p)
        self.assertEqual(g.half, 10.0)

    def test_grows_on_each_of_the_four_edges(self):
        for p in ((8, 0), (-8, 0), (0, 8), (0, -8)):
            g = GrowingGrid()
            g.update(0, 0)
            self.assertTrue(g.update(*p), p)
            self.assertEqual(g.half, 20.0, p)

    def test_doubles_until_it_fits(self):
        g = GrowingGrid()
        g.update(0, 0)
        g.update(100, 0)
        self.assertEqual(g.half, 160.0)
        self.assertLessEqual(100, 0.75 * g.half)

    def test_never_shrinks_and_centre_fixed(self):
        g = GrowingGrid()
        g.update(2, 3)
        g.update(50, 0)
        h, c = g.half, (g.cx, g.cy)
        self.assertFalse(g.update(0, 0))
        self.assertEqual((g.half, (g.cx, g.cy)), (h, c))
        self.assertFalse(g.update(1, 1))

    def test_non_finite_ignored(self):
        g = GrowingGrid()
        for p in ((float("nan"), 0), (0, float("inf")), (float("-inf"), 1)):
            self.assertFalse(g.update(*p))
        self.assertEqual(g.lines(), [])                       # still no centre
        g.update(0, 0)
        self.assertFalse(g.update(float("nan"), 1e9))
        self.assertEqual(g.half, 10.0)

    def test_huge_jump_clamps_at_the_cap(self):
        g = GrowingGrid()
        g.update(0, 0)
        self.assertTrue(g.update(1e12, -1e12))
        self.assertEqual(g.half, 1600.0)
        self.assertFalse(g.update(1e12, 1e12))
        self.assertLessEqual(len(g.lines()), 2 * 81)

    def test_cells_per_side_never_exceed_the_limit(self):
        g = GrowingGrid()
        g.update(0, 0)
        for x in [2 ** k for k in range(1, 14)]:
            g.update(float(x), 0.0)
            self.assertLessEqual(2 * g.half / g.cell, 80, x)
            xs, ys = extent(g)
            self.assertLessEqual(len(xs), 81)
            self.assertLessEqual(len(ys), 81)

    def test_cell_doubles_and_lines_stay_aligned_to_the_centre(self):
        g = GrowingGrid()
        g.update(13.2, -4.6)                                  # centre (13, -5)
        g.update(13.2 + 300, -4.6)
        self.assertGreater(g.cell, 1.0)
        xs, ys = extent(g)
        for x in xs:
            self.assertEqual((x - g.cx) % g.cell, 0.0)
        for y in ys:
            self.assertEqual((y - g.cy) % g.cell, 0.0)
        self.assertIn(g.cx, xs)
        self.assertIn(g.cy, ys)

    def test_lines_cover_the_full_square(self):
        g = GrowingGrid()
        g.update(0, 0)
        ls = g.lines()
        self.assertEqual(len(ls), 2 * 21)
        allx = [p[0] for l in ls for p in l]
        ally = [p[1] for l in ls for p in l]
        self.assertEqual((min(allx), max(allx)), (-10.0, 10.0))
        self.assertEqual((min(ally), max(ally)), (-10.0, 10.0))
        for a, b in ls:
            self.assertTrue(a[0] == b[0] or a[1] == b[1])


if __name__ == "__main__":
    unittest.main()
