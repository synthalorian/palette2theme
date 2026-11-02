"""Stdlib-only PNG output: a minimal writer, a tinted wallpaper and a swatch preview."""

from __future__ import annotations

import hashlib
import math
import random
import struct
import zlib
from pathlib import Path

from .color import Color


def _chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def encode_png(width: int, height: int, rows: list[bytes | bytearray], level: int = 9) -> bytes:
    """Encode 8-bit RGB rows (each width*3 bytes) as a PNG, filter type 0 on every row."""
    if width <= 0 or height <= 0:
        raise ValueError("PNG dimensions must be positive")
    if len(rows) != height or any(len(r) != width * 3 for r in rows):
        raise ValueError("row data does not match the PNG dimensions")
    raw = b"".join(b"\x00" + bytes(r) for r in rows)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", ihdr)
            + _chunk(b"IDAT", zlib.compress(raw, level)) + _chunk(b"IEND", b""))


def write_png(path: str | Path, width: int, height: int, rows: list[bytes | bytearray]) -> None:
    Path(path).write_bytes(encode_png(width, height, rows))


def _gauss(n: int, centre: float, sigma: float) -> list[float]:
    return [math.exp(-(((i + 0.5) / n - centre) / sigma) ** 2) for i in range(n)]


def render_wallpaper(width: int, height: int, top: Color, bottom: Color, glow: Color, glow2: Color,
                     dark: bool = True, seed: str = "") -> list[bytearray]:
    """A vertical gradient (top -> bottom) lit by two soft palette-coloured glows, with fine grain.

    Both glows are separable Gaussians, so each pixel is a couple of multiply-adds; the
    grain doubles as dithering against gradient banding. Output is deterministic for a seed."""
    rng = random.Random(hashlib.sha256(seed.encode()).digest())
    strength = 0.42 if dark else 0.22
    gx1, gy1 = _gauss(width, 0.74, 0.42), _gauss(height, 0.80, 0.38)
    gx2, gy2 = _gauss(width, 0.16, 0.30), _gauss(height, 0.12, 0.30)
    # Diagonal light streaks: a slow sine across x+y, very faint.
    streak = [0.5 + 0.5 * math.sin(i / max(width, height) * math.tau * 3.0) for i in range(width + height)]
    noise_pool = [rng.uniform(-3.5, 3.5) for _ in range(width + 4093)]
    clamp = bytes(min(255, max(0, v - 64)) for v in range(256 + 128))

    rows = []
    for y in range(height):
        base = top.mix(bottom, y / max(1, height - 1))
        a1, a2 = gy1[y] * strength, gy2[y] * strength * 0.55
        chans = []
        for ch in range(3):
            b = (base.r, base.g, base.b)[ch]
            d1 = (glow.r, glow.g, glow.b)[ch] - b
            d2 = (glow2.r, glow2.g, glow2.b)[ch] - b
            chans.append((b, d1 * a1, d2 * a2, d1 * 0.035))
        off = rng.randrange(4093)
        row = bytearray(width * 3)
        for ch, (b, k1, k2, ks) in enumerate(chans):
            row[ch::3] = bytes(clamp[int(b + k1 * g1 + k2 * g2 + ks * s + n + 64.5)]
                               for g1, g2, s, n in zip(gx1, gx2, streak[y:y + width], noise_pool[off:off + width]))
        rows.append(row)
    return rows


def fill_rect(rows: list[bytearray], x0: int, y0: int, x1: int, y1: int, color: Color) -> None:
    px = bytes((color.r, color.g, color.b))
    for y in range(max(0, y0), min(len(rows), y1)):
        row = rows[y]
        lo, hi = max(0, x0), min(len(row) // 3, x1)
        if hi > lo:
            row[lo * 3:hi * 3] = px * (hi - lo)


def render_preview(scheme, width: int = 1280, height: int = 720, seed: str = "") -> list[bytearray]:
    """Wallpaper with a mock window: background card, accent border, bar, text lines, ANSI swatches."""
    c = scheme.colors
    rows = render_wallpaper(width, height, c["darker_background"], c["background"], c["accent"],
                            c["blue"], scheme.dark, seed)
    u = width / 1280
    bar_h = round(28 * u)
    fill_rect(rows, 0, 0, width, bar_h, c["darker_background"])
    fill_rect(rows, round(16 * u), round(9 * u), round(40 * u), bar_h - round(9 * u), c["accent"])
    fill_rect(rows, round(52 * u), round(11 * u), round(150 * u), bar_h - round(11 * u), c["foreground"])
    x0, y0, x1, y1 = round(120 * u), round(90 * u), round(1160 * u), round(650 * u)
    b = max(2, round(3 * u))
    fill_rect(rows, x0 - b, y0 - b, x1 + b, y1 + b, c["accent"])
    fill_rect(rows, x0, y0, x1, y1, c["background"])
    # "Text" lines in the text colours.
    line_keys = ["foreground", "dark_foreground", "muted", "accent", "light_foreground",
                 "red", "green", "yellow", "blue", "magenta", "cyan"]
    lh = round(24 * u)
    for i, key in enumerate(line_keys):
        y = y0 + round(30 * u) + i * lh
        w = round((260 + (i * 137) % 420) * u)
        fill_rect(rows, x0 + round(40 * u), y, x0 + round(40 * u) + w, y + round(10 * u), c[key])
    # Selection highlight behind one line.
    sy = y0 + round(30 * u) + len(line_keys) * lh
    fill_rect(rows, x0 + round(30 * u), sy - round(6 * u), x1 - round(30 * u), sy + round(16 * u), c["selection_background"])
    fill_rect(rows, x0 + round(40 * u), sy, x0 + round(400 * u), sy + round(10 * u), c["selection_foreground"])
    # Two rows of 8 ANSI swatches.
    sw = (x1 - x0 - round(80 * u)) // 8
    for i in range(16):
        r, col = divmod(i, 8)
        sx = x0 + round(40 * u) + col * sw
        syy = y1 - round(120 * u) + r * round(50 * u)
        fill_rect(rows, sx, syy, sx + sw - round(8 * u), syy + round(40 * u), c[f"color{i}"])
    return rows
