"""Read a palette from CLI arguments or a file (JSON, TOML, or one hex per line)."""

from __future__ import annotations

import json
import re
from pathlib import Path

from .color import Color, ColorError

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised only on old Pythons
    tomllib = None  # type: ignore[assignment]

_HEXISH = re.compile(r"^#?(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


class PaletteError(ValueError):
    """Raised when a palette cannot be read."""


def parse_colors(values: list[str], source: str = "arguments") -> list[Color]:
    out = []
    for v in values:
        try:
            out.append(Color.from_hex(v))
        except ColorError as e:
            raise PaletteError(f"{source}: {e}") from None
    return out


def _collect(obj, source: str) -> list[str]:
    """Pull hex strings out of a decoded JSON/TOML document.

    Accepted shapes: a list of strings; a table with a `colors` or `palette` list;
    or a table whose string values are all hex colours (order preserved)."""
    if isinstance(obj, list):
        if not all(isinstance(v, str) for v in obj):
            raise PaletteError(f"{source}: the colour list must contain only strings")
        return obj
    if isinstance(obj, dict):
        for key in ("colors", "colours", "palette"):
            if key in obj:
                return _collect(obj[key], source)
        values = [v for v in obj.values() if isinstance(v, str) and _HEXISH.match(v.strip())]
        if values:
            return values
    raise PaletteError(f"{source}: expected a list of hex strings, or a 'colors'/'palette' list")


def _parse_lines(text: str, source: str) -> list[str]:
    values = []
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.split("//", 1)[0].strip()
        # "#abc123  # comment" -> first token; "# comment" lines are skipped.
        if not line:
            continue
        token = line.split()[0].rstrip(",;")
        if _HEXISH.match(token):
            values.append(token)
        elif line.startswith(("#", ";")):
            continue
        else:
            raise PaletteError(f"{source}:{n}: not a hex colour: {raw.strip()!r}")
    return values


def read_palette_file(path: str | Path) -> list[Color]:
    p = Path(path)
    try:
        text = p.read_text(encoding="utf-8")
    except OSError as e:
        raise PaletteError(f"cannot read palette file {p}: {e.strerror}") from None
    source = str(p)
    suffix = p.suffix.lower()
    stripped = text.lstrip()

    if suffix == ".json" or (suffix not in (".toml", ".txt") and stripped[:1] in "[{"):
        try:
            values = _collect(json.loads(text), source)
        except json.JSONDecodeError as e:
            raise PaletteError(f"{source}: invalid JSON: {e}") from None
    elif suffix == ".toml" or (suffix != ".txt" and re.search(r"^\s*[A-Za-z_][\w-]*\s*=", text, re.M)):
        if tomllib is None:  # pragma: no cover
            raise PaletteError("TOML palettes need Python 3.11+ (tomllib)")
        try:
            values = _collect(tomllib.loads(text), source)
        except tomllib.TOMLDecodeError as e:
            raise PaletteError(f"{source}: invalid TOML: {e}") from None
    else:
        values = _parse_lines(text, source)

    if not values:
        raise PaletteError(f"{source}: no colours found")
    return parse_colors(values, source)
