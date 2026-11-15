"""Small shared helpers for the drone models (no model of its own).

`lag_alpha` lived in `response.py` (the AirStack-simulator route) until the S1 final review (15 November 2026).
It moved here so the training model (`fitted.py`, `px4_trajectory.py`) no longer depends on that route's file.
`response.py` imports it from here, so its behaviour is unchanged."""
from __future__ import annotations

import math


def lag_alpha(dt_s: float, tau_s: float) -> float:
    """Exact zero-order-hold gain of a first-order lag over one step: 1 - exp(-dt/tau); 1 when tau = 0."""
    if tau_s <= 0.0:
        return 1.0
    return -math.expm1(-dt_s / tau_s)
