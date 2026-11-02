"""Colour primitives: hex parsing, sRGB <-> OKLab/OKLCH, WCAG contrast.

Everything is stdlib-only. Colours are stored as 8-bit sRGB so the contrast
ratio we report is the ratio of the hex value that actually ships.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

_HEX_RE = re.compile(r"^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


class ColorError(ValueError):
    """Raised for unparseable colour input."""


def _srgb_to_linear(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _linear_to_srgb(c: float) -> float:
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def _linear_to_oklab(r: float, g: float, b: float) -> tuple[float, float, float]:
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l_, m_, s_ = (math.copysign(abs(v) ** (1 / 3), v) for v in (l, m, s))
    return (
        0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
        1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
        0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_,
    )


def _oklab_to_linear(L: float, a: float, b: float) -> tuple[float, float, float]:
    l_ = L + 0.3963377774 * a + 0.2158037573 * b
    m_ = L - 0.1055613458 * a - 0.0638541728 * b
    s_ = L - 0.0894841775 * a - 1.2914855480 * b
    l, m, s = l_ ** 3, m_ ** 3, s_ ** 3
    return (
        4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
        -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
        -0.0041960863 * l - 0.7034186147 * m + 1.7076127010 * s,
    )


def _in_gamut(rgb: tuple[float, float, float], eps: float = 1e-6) -> bool:
    return all(-eps <= c <= 1 + eps for c in rgb)


@dataclass(frozen=True)
class Color:
    r: int
    g: int
    b: int

    # -- construction ---------------------------------------------------
    @classmethod
    def from_hex(cls, text: str) -> "Color":
        m = _HEX_RE.match(text.strip())
        if not m:
            raise ColorError(f"not a hex colour: {text!r} (expected #rrggbb or #rgb)")
        h = m.group(1)
        if len(h) == 3:
            h = "".join(ch * 2 for ch in h)
        return cls(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))

    @classmethod
    def from_oklch(cls, L: float, C: float, h: float) -> "Color":
        """Build from OKLCH, reducing chroma until the colour fits in sRGB."""
        L = min(1.0, max(0.0, L))
        C = max(0.0, C)
        hr = math.radians(h)

        def lin(c: float) -> tuple[float, float, float]:
            return _oklab_to_linear(L, c * math.cos(hr), c * math.sin(hr))

        rgb = lin(C)
        if not _in_gamut(rgb):
            lo, hi = 0.0, C
            for _ in range(24):
                mid = (lo + hi) / 2
                if _in_gamut(lin(mid)):
                    lo = mid
                else:
                    hi = mid
            rgb = lin(lo)
        return cls(*(round(min(1.0, max(0.0, _linear_to_srgb(min(1.0, max(0.0, c))))) * 255) for c in rgb))

    # -- views ----------------------------------------------------------
    @property
    def hex(self) -> str:
        return f"#{self.r:02x}{self.g:02x}{self.b:02x}"

    @property
    def bare(self) -> str:
        return self.hex[1:]

    @property
    def linear(self) -> tuple[float, float, float]:
        return tuple(_srgb_to_linear(c / 255) for c in (self.r, self.g, self.b))  # type: ignore[return-value]

    @property
    def oklab(self) -> tuple[float, float, float]:
        return _linear_to_oklab(*self.linear)

    @property
    def oklch(self) -> tuple[float, float, float]:
        L, a, b = self.oklab
        C = math.hypot(a, b)
        h = math.degrees(math.atan2(b, a)) % 360 if C > 1e-6 else 0.0
        return L, C, h

    @property
    def luminance(self) -> float:
        """WCAG 2.x relative luminance."""
        r, g, b = self.linear
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    # -- helpers --------------------------------------------------------
    def with_l(self, L: float) -> "Color":
        _, C, h = self.oklch
        return Color.from_oklch(L, C, h)

    def adjust(self, dl: float = 0.0, chroma_scale: float = 1.0, max_chroma: float | None = None) -> "Color":
        L, C, h = self.oklch
        C *= chroma_scale
        if max_chroma is not None:
            C = min(C, max_chroma)
        return Color.from_oklch(L + dl, C, h)

    def mix(self, other: "Color", t: float) -> "Color":
        """Mix in OKLab; t=0 is self, t=1 is other."""
        a, b = self.oklab, other.oklab
        L, A, B = (x + (y - x) * t for x, y in zip(a, b))
        C = math.hypot(A, B)
        return Color.from_oklch(L, C, math.degrees(math.atan2(B, A)) % 360)

    def over(self, other: "Color", alpha: float) -> "Color":
        """Composite self at `alpha` over `other` (plain sRGB alpha blend, as compositors do)."""
        return Color(*(round(s * alpha + o * (1 - alpha)) for s, o in zip(
            (self.r, self.g, self.b), (other.r, other.g, other.b))))

    def __str__(self) -> str:
        return self.hex


BLACK = Color(0, 0, 0)
WHITE = Color(255, 255, 255)


def contrast(a: Color, b: Color) -> float:
    """WCAG 2.x contrast ratio between two colours (1.0 .. 21.0)."""
    la, lb = a.luminance, b.luminance
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def hue_distance(h1: float, h2: float) -> float:
    d = abs(h1 - h2) % 360
    return min(d, 360 - d)


def push_to_contrast(color: Color, surfaces: list[Color], ratio: float, prefer_lighter: bool,
                     step: float = 0.004) -> Color | None:
    """Move `color` along OKLCH lightness (keeping hue and, where gamut allows, chroma)
    until it reaches `ratio` against every surface. Tries the preferred direction first,
    then the other. Returns None if no lightness works."""
    def ok(c: Color) -> bool:
        return all(contrast(c, s) >= ratio for s in surfaces)

    if ok(color):
        return color
    L0, C, h = color.oklch
    for direction in ((1, -1) if prefer_lighter else (-1, 1)):
        L = L0
        while 0.0 <= L <= 1.0:
            L += direction * step
            cand = Color.from_oklch(L, C, h)
            if ok(cand):
                return cand
        edge = WHITE if direction > 0 else BLACK
        if ok(edge):
            return edge
    return None
