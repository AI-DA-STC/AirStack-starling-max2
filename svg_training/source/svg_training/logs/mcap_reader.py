"""Minimal read-only MCAP reader (pure Python, no package needed).

Reads uncompressed MCAP files such as the ROS 2 rosbags in ~/flight_logs. Handles the Schema (0x03), Channel (0x04),
Message (0x05) and Chunk (0x06) records; every other record is skipped by its length. A chunk with a compression
other than "" raises ValueError (the 12 November bag is uncompressed). The file is memory-mapped read-only.

Layout (https://mcap.dev/spec): magic b"\\x89MCAP0\\r\\n", then records of opcode u8 + length u64 (little endian) +
body. A chunk body holds records of the same form.
"""
from __future__ import annotations

import mmap
import struct
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

MAGIC = b"\x89MCAP0\r\n"
OP_SCHEMA, OP_CHANNEL, OP_MESSAGE, OP_CHUNK = 0x03, 0x04, 0x05, 0x06


@dataclass(frozen=True)
class McapMessage:
    topic: str
    log_time_ns: int
    publish_time_ns: int
    data: bytes


@contextmanager
def _open(path: str | Path):
    with open(path, "rb") as fh:
        mm = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
        try:
            if mm[:8] != MAGIC:
                raise ValueError(f"{path}: not an MCAP file (bad magic)")
            yield mm
        finally:
            mm.close()


def _records(buf, start: int, end: int) -> Iterator[tuple[int, int, int]]:
    """(opcode, body start, body end) for each record in buf[start:end]."""
    pos = start
    while pos + 9 <= end:
        op = buf[pos]
        length = struct.unpack_from("<Q", buf, pos + 1)[0]
        body = pos + 9
        if body + length > end:
            raise ValueError("truncated MCAP record")
        yield op, body, body + length
        pos = body + length
        if op == 0x02:                       # Footer: the closing magic follows
            return


def _string(buf, pos: int) -> tuple[str, int]:
    n = struct.unpack_from("<I", buf, pos)[0]
    return bytes(buf[pos + 4:pos + 4 + n]).decode("utf-8"), pos + 4 + n


def _walk(buf) -> Iterator[tuple[int, object, int, int]]:
    """Every Schema, Channel and Message record, chunks opened: (opcode, buffer, body start, body end)."""
    for op, b0, b1 in _records(buf, 8, len(buf)):
        if op == OP_CHUNK:
            # Chunk: message_start_time u64, message_end_time u64, uncompressed_size u64, uncompressed_crc u32,
            # compression string, records_length u64, records.
            pos = b0 + 8 + 8 + 8 + 4
            compression, pos = _string(buf, pos)
            if compression != "":
                raise ValueError(f"compressed MCAP chunk ({compression!r}) is not supported")
            rec_len = struct.unpack_from("<Q", buf, pos)[0]
            pos += 8
            for op2, c0, c1 in _records(buf, pos, pos + rec_len):
                if op2 in (OP_SCHEMA, OP_CHANNEL, OP_MESSAGE):
                    yield op2, buf, c0, c1
        elif op in (OP_SCHEMA, OP_CHANNEL, OP_MESSAGE):
            yield op, buf, b0, b1


def _scan(path) -> tuple[dict, dict]:
    schemas: dict[int, tuple[str, str]] = {}
    channels: dict[int, tuple[str, int]] = {}
    with _open(path) as buf:
        for op, b, b0, _b1 in _walk(buf):
            if op == OP_SCHEMA:
                sid = struct.unpack_from("<H", b, b0)[0]
                name, p = _string(b, b0 + 2)
                _enc, p = _string(b, p)
                n = struct.unpack_from("<I", b, p)[0]
                schemas[sid] = (name, bytes(b[p + 4:p + 4 + n]).decode("utf-8", "replace"))
            elif op == OP_CHANNEL:
                cid, sid = struct.unpack_from("<HH", b, b0)
                topic, _p = _string(b, b0 + 4)
                channels[cid] = (topic, sid)
    return schemas, channels


def list_topics(path: str | Path) -> dict[str, tuple[str, str]]:
    """topic -> (schema name, ros2msg schema text)."""
    schemas, channels = _scan(path)
    return {topic: schemas.get(sid, ("", "")) for topic, sid in channels.values()}


def iter_messages(path: str | Path, topics: set[str]) -> Iterator[McapMessage]:
    """Messages on the named topics, in file order (log time order for a normal recording)."""
    wanted: dict[int, str] = {}
    with _open(path) as buf:
        for op, b, b0, b1 in _walk(buf):
            if op == OP_CHANNEL:
                cid, _sid = struct.unpack_from("<HH", b, b0)
                topic, _p = _string(b, b0 + 4)
                if topic in topics:
                    wanted[cid] = topic
            elif op == OP_MESSAGE:
                cid, _seq, log_t, pub_t = struct.unpack_from("<HIQQ", b, b0)
                if cid in wanted:
                    yield McapMessage(wanted[cid], log_t, pub_t, bytes(b[b0 + 22:b1]))
