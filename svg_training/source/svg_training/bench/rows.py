"""Result-row constants and the resume helper for the throughput benchmark. Standard library only (no torch)."""
import hashlib
import json
import pathlib

ROW_KEYS = ("tier", "case", "num_games", "drones_per_game", "repeat", "status", "env_steps_per_s",
            "drone_steps_per_s", "peak_mem_mb", "nan_count", "mean_reset_fraction", "device", "gpu_name",
            "commit", "code_sha", "date")


def existing_points(path) -> set:
    """(case, num_games) points that already have at least one row in a JSON-lines file (empty set if no file).

    Raises ValueError naming the line number if a line is not a valid JSON row.
    """
    path = pathlib.Path(path)
    points = set()
    if not path.exists():
        return points
    for n, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            points.add((row["case"], int(row["num_games"])))
        except (ValueError, KeyError, TypeError):
            raise ValueError(f"{path}: line {n} is not a valid result row") from None
    return points


_CODE_DIRS = ("source", "scripts", "configs")


def code_sha(root=None) -> str:
    """First 12 hex of a sha256 over the sorted relative paths and contents of every file under source/, scripts/
    and configs/ of `root` (default: the svg_training folder), skipping __pycache__. Standard library only.

    The parent repository's HEAD does not contain this folder while it is untracked, so this is the provenance
    that identifies the code a row was measured with.
    """
    root = pathlib.Path(root) if root is not None else pathlib.Path(__file__).resolve().parents[3]
    files = []
    for d in _CODE_DIRS:
        base = root / d
        if base.is_dir():
            files += [p for p in base.rglob("*") if p.is_file() and "__pycache__" not in p.parts]
    h = hashlib.sha256()
    for p in sorted(files, key=lambda q: q.relative_to(root).as_posix()):
        h.update(p.relative_to(root).as_posix().encode() + b"\0")
        h.update(p.read_bytes() + b"\0")
    return h.hexdigest()[:12]
