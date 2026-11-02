"""Shared test helpers: a tiny PNG decoder (for filter type 0 RGB, which is all we write)."""

import struct
import zlib
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def decode_png(data: bytes):
    """Return (width, height, rows) and verify signature, chunk CRCs and layout."""
    assert data[:8] == b"\x89PNG\r\n\x1a\n", "bad signature"
    pos, chunks = 8, []
    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos:pos + 4])
        kind = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + length]
        (crc,) = struct.unpack(">I", data[pos + 8 + length:pos + 12 + length])
        assert zlib.crc32(kind + body) & 0xFFFFFFFF == crc, f"bad CRC in {kind!r}"
        chunks.append((kind, body))
        pos += 12 + length
    assert chunks[0][0] == b"IHDR" and chunks[-1][0] == b"IEND"
    w, h, depth, ctype, _, _, _ = struct.unpack(">IIBBBBB", chunks[0][1])
    assert (depth, ctype) == (8, 2), "expected 8-bit RGB"
    raw = zlib.decompress(b"".join(b for k, b in chunks if k == b"IDAT"))
    stride = w * 3 + 1
    assert len(raw) == stride * h
    rows = []
    for y in range(h):
        line = raw[y * stride:(y + 1) * stride]
        assert line[0] == 0, "unexpected filter type"
        rows.append(line[1:])
    return w, h, rows
