"""Auto-growing square grid (pure logic, stdlib only, no ROS). Sim only.

The first finite position sets the centre, snapped to the cell size. The centre never moves afterwards.
When a position comes within `margin * half` of an edge, `half` doubles until it fits (up to `max_half_m`).
Whenever the grid would hold more than `max_lines_per_side` cells per side, the cell size doubles.
The grid never shrinks. A position beyond the cap clamps there and does not throw.
"""
from __future__ import annotations

import math


class GrowingGrid:
    def __init__(self, start_half_m: float = 10.0, cell_m: float = 1.0, margin: float = 0.25,
                 max_lines_per_side: int = 80, max_half_m: float = 1600.0):
        self.half = float(start_half_m)
        self.cell = float(cell_m)
        self.margin = float(margin)
        self.max_lines = int(max_lines_per_side)
        self.max_half = float(max_half_m)
        self.cx = None
        self.cy = None
        self._fit_cell()

    def _fit_cell(self) -> None:
        while 2.0 * self.half / self.cell > self.max_lines:
            self.cell *= 2.0

    def update(self, x: float, y: float) -> bool:
        """Feed one position. True when the grid changed (first centre, bigger half or bigger cell)."""
        try:
            x, y = float(x), float(y)
        except (TypeError, ValueError):
            return False
        if not (math.isfinite(x) and math.isfinite(y)):
            return False
        if self.cx is None:
            self.cx = round(x / self.cell) * self.cell
            self.cy = round(y / self.cell) * self.cell
            return True
        far = max(abs(x - self.cx), abs(y - self.cy))
        old = (self.half, self.cell)
        while far > (1.0 - self.margin) * self.half and self.half < self.max_half:
            self.half = min(self.half * 2.0, self.max_half)
        self._fit_cell()
        return (self.half, self.cell) != old

    def lines(self) -> list:
        """Every grid line as ((x1, y1), (x2, y2)); empty before the first position. z is the caller's."""
        if self.cx is None:
            return []
        n = int(math.floor(self.half / self.cell + 1e-9))
        x0, x1 = self.cx - self.half, self.cx + self.half
        y0, y1 = self.cy - self.half, self.cy + self.half
        out = []
        for k in range(-n, n + 1):
            out.append(((self.cx + k * self.cell, y0), (self.cx + k * self.cell, y1)))
            out.append(((x0, self.cy + k * self.cell), (x1, self.cy + k * self.cell)))
        return out
