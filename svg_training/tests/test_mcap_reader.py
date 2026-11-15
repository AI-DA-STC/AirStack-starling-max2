"""The pure-Python MCAP reader and the CDR decoder, on a tiny synthetic file (never the 592 MB bag)."""
import struct

import pytest

from _mcap_writer import cdr_header, write_mcap
from svg_training.logs.cdr import compile_ros2msg, decode
from svg_training.logs.mcap_reader import iter_messages, list_topics

SCHEMAS = {1: ("pkg/msg/A", "uint8 n\n"), 2: ("pkg/msg/B", "float32 x\n")}
CHANNELS = {1: (1, "/a"), 2: (2, "/b")}


def _messages():
    out = []
    for k in range(50):
        out.append((1 if k % 2 == 0 else 2, 1_000 + 10 * k, bytes([k])))
    return out


def test_reader_round_trip(tmp_path):
    p = write_mcap(tmp_path / "x.mcap", SCHEMAS, CHANNELS, _messages(), per_chunk=25)     # 2 chunks
    msgs = list(iter_messages(p, {"/a"}))
    expected = [1_000 + 10 * k for k in range(50) if k % 2 == 0]
    assert [m.log_time_ns for m in msgs] == expected
    assert all(m.topic == "/a" for m in msgs)
    assert [m.data[0] for m in msgs] == [k for k in range(50) if k % 2 == 0]
    assert list_topics(p) == {"/a": ("pkg/msg/A", "uint8 n\n"), "/b": ("pkg/msg/B", "float32 x\n")}


def test_reader_refuses_compressed_chunk(tmp_path):
    p = write_mcap(tmp_path / "z.mcap", SCHEMAS, CHANNELS, _messages(), compression="zstd")
    with pytest.raises(ValueError, match="compress"):
        list(iter_messages(p, {"/a"}))


def test_reader_refuses_non_mcap(tmp_path):
    (tmp_path / "bad.mcap").write_bytes(b"not an mcap file at all")
    with pytest.raises(ValueError):
        list_topics(tmp_path / "bad.mcap")


def test_cdr_alignment():
    text = ("uint64 timestamp\nbool ok\nfloat32[3] v   # three\nuint8 FOO = 4\nuint8 n\nfloat32 last\n")
    lay = compile_ros2msg(text)
    # after the header: u64 at 0, bool at 8, float32[3] aligned to 12, uint8 at 24, float32 aligned to 28
    body = struct.pack("<Q", 7) + struct.pack("<?", True) + b"\0\0\0" + struct.pack("<3f", 1.5, -2.25, 0.125) \
        + struct.pack("<B", 9) + b"\0\0\0" + struct.pack("<f", 3.5)
    got = decode(lay, cdr_header() + body, ("timestamp", "ok", "v", "n", "last"))
    assert got == {"timestamp": 7.0, "ok": 1.0, "v": (1.5, -2.25, 0.125), "n": 9.0, "last": 3.5}


def test_cdr_unsupported_type_raises():
    for text in ("string name\n", "float32[] xs\n", "float32[<=3] xs\n", "geometry_msgs/Point p\n"):
        with pytest.raises(NotImplementedError):
            compile_ros2msg(text)
