"""Test helper: write a tiny MCAP file (uncompressed, or one chunk marked with another compression) for the reader.

Not a general writer: schemas, channels and messages only, grouped in chunks; no index, no summary, no CRCs.
"""
from __future__ import annotations

import struct
from pathlib import Path

MAGIC = b"\x89MCAP0\r\n"


def _s(text: str) -> bytes:
    raw = text.encode()
    return struct.pack("<I", len(raw)) + raw


def _rec(op: int, body: bytes) -> bytes:
    return bytes([op]) + struct.pack("<Q", len(body)) + body


def schema_rec(sid: int, name: str, text: str) -> bytes:
    return _rec(0x03, struct.pack("<H", sid) + _s(name) + _s("ros2msg") + struct.pack("<I", len(text.encode()))
                + text.encode())


def channel_rec(cid: int, sid: int, topic: str) -> bytes:
    return _rec(0x04, struct.pack("<HH", cid, sid) + _s(topic) + _s("cdr") + struct.pack("<I", 0))


def message_rec(cid: int, seq: int, log_ns: int, data: bytes) -> bytes:
    return _rec(0x05, struct.pack("<HIQQ", cid, seq, log_ns, log_ns) + data)


def chunk_rec(records: bytes, compression: str = "") -> bytes:
    return _rec(0x06, struct.pack("<QQQI", 0, 0, len(records), 0) + _s(compression)
                + struct.pack("<Q", len(records)) + records)


def write_mcap(path: str | Path, schemas: dict[int, tuple[str, str]], channels: dict[int, tuple[int, str]],
               messages: list[tuple[int, int, bytes]], per_chunk: int = 25, compression: str = "") -> Path:
    """schemas {id: (name, text)}, channels {id: (schema id, topic)}, messages [(channel id, log ns, data)].

    Schemas and channels go at the top level; the messages are split into chunks of per_chunk records."""
    out = bytearray(MAGIC)
    out += _rec(0x01, _s("") + _s("test"))                              # Header
    for sid, (name, text) in schemas.items():
        out += schema_rec(sid, name, text)
    for cid, (sid, topic) in channels.items():
        out += channel_rec(cid, sid, topic)
    for i in range(0, len(messages), per_chunk):
        body = b"".join(message_rec(c, i + k, t, d) for k, (c, t, d) in enumerate(messages[i:i + per_chunk]))
        out += chunk_rec(body, compression)
    out += _rec(0x02, struct.pack("<QQI", 0, 0, 0)) + MAGIC             # Footer
    Path(path).write_bytes(bytes(out))
    return Path(path)


def cdr_header() -> bytes:
    return bytes([0, 1, 0, 0])
