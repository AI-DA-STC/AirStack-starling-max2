"""Decode flat ROS 2 messages (CDR, little endian) from their own `.msg` schema text.

Only messages made of primitives and fixed-size arrays of primitives are supported (the PX4 messages the S2 bag
check reads are of this kind). Strings, unbounded or bounded sequences, nested message types and big-endian CDR
raise NotImplementedError. Constants in the schema text are skipped.

CDR layout: a 4-byte encapsulation header (bytes 0-1: 0x00 0x01 = little endian), then the fields in order, each
primitive aligned to its own size counted from the end of that header.
"""
from __future__ import annotations

import re
import struct
from dataclasses import dataclass

_PRIM = {"bool": "?", "byte": "B", "char": "b", "int8": "b", "uint8": "B", "int16": "h", "uint16": "H",
         "int32": "i", "uint32": "I", "int64": "q", "uint64": "Q", "float32": "f", "float64": "d"}


@dataclass(frozen=True)
class CdrLayout:
    """fields: name -> (struct char, count (1 = scalar, kept as a float), byte offset after the 4-byte header)."""
    fields: dict[str, tuple[str, int, int, bool]]
    size: int


def compile_ros2msg(text: str) -> CdrLayout:
    fields: dict[str, tuple[str, int, int, bool]] = {}
    off = 0
    for raw in text.splitlines():
        if raw.startswith("====") or raw.startswith("MSG:"):
            raise NotImplementedError("nested message types are not supported")
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        m = re.match(r"^(\S+)\s+(\S+)(.*)$", line)
        if not m:
            raise NotImplementedError(f"cannot parse schema line {raw!r}")
        typ, name, rest = m.groups()
        if "=" in name or rest.strip().startswith("="):
            continue                                            # a constant
        count, array = 1, False
        am = re.match(r"^([A-Za-z0-9_]+)\[(\d*)\]$", typ)
        if am:
            typ = am.group(1)
            if am.group(2) == "":
                raise NotImplementedError(f"unbounded array in {raw!r}")
            count, array = int(am.group(2)), True
        elif "[" in typ or "<=" in typ:
            raise NotImplementedError(f"bounded sequence in {raw!r}")
        if typ not in _PRIM:
            raise NotImplementedError(f"type {typ!r} is not a flat primitive")
        c = _PRIM[typ]
        w = struct.calcsize("<" + c)
        off = (off + w - 1) // w * w
        fields[name] = (c, count, off, array)
        off += w * count
    return CdrLayout(fields, off)


def decode(layout: CdrLayout, data: bytes, fields: tuple[str, ...]) -> dict[str, float | tuple[float, ...]]:
    """The named fields of one message: a float for a scalar, a tuple of floats for an array."""
    if len(data) < 4:
        raise ValueError("message shorter than the CDR header")
    if data[0] != 0 or data[1] != 1:
        raise NotImplementedError(f"only plain little-endian CDR (header 00 01) is supported, got {data[:2].hex()}")
    out: dict[str, float | tuple[float, ...]] = {}
    for name in fields:
        c, count, off, array = layout.fields[name]
        vals = struct.unpack_from("<" + c * count, data, 4 + off)
        out[name] = tuple(float(v) for v in vals) if array else float(vals[0])
    return out
