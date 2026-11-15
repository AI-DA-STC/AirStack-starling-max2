"""Opponent strategies. Scripted opponents read only the observation (see scripted.py)."""
from .scripted import REGISTRY, make_strategy

__all__ = ["REGISTRY", "make_strategy"]
