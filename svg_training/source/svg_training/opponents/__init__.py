"""Opponent strategies. Scripted opponents read only the observation (see scripted.py); make_strategy also loads a
stand-in run folder (learned.py, imported only then)."""
from .scripted import REGISTRY, make_strategy

__all__ = ["REGISTRY", "make_strategy"]
