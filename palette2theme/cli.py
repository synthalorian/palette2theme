"""Command line interface: `palette2theme [colours...] [--palette FILE] --name NAME --out DIR`."""

from __future__ import annotations

import argparse
import datetime as _dt
import os
import re
import subprocess
import sys
from pathlib import Path

from . import __version__
from .color import Color, ColorError
from .derive import ContrastError, derive_scheme
from .omarchy import OutputError, ThemeMeta, slugify, write_theme
from .palette_io import PaletteError, parse_colors, read_palette_file
from .plasma import write_plasma_scheme

EXIT_USAGE, EXIT_CONTRAST, EXIT_NOT_IMPLEMENTED = 2, 3, 4
FALLBACK_AUTHOR = "Theme author"


def _git_user_name() -> str:
    """`git config user.name`, or "" when git is missing, unset, or fails."""
    try:
        r = subprocess.run(["git", "config", "--get", "user.name"], capture_output=True,
                           text=True, timeout=10, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        return ""
    return r.stdout.strip() if r.returncode == 0 else ""


def default_author() -> str:
    """$PALETTE2THEME_AUTHOR, else `git config user.name`, else a generic placeholder."""
    return (os.environ.get("PALETTE2THEME_AUTHOR", "").strip() or _git_user_name()
            or FALLBACK_AUTHOR)


def _size(text: str) -> tuple[int, int]:
    m = re.fullmatch(r"(\d+)x(\d+)", text)
    if not m or not (1 <= int(m.group(1)) <= 8192 and 1 <= int(m.group(2)) <= 8192):
        raise argparse.ArgumentTypeError("expected WIDTHxHEIGHT, each 1..8192 (e.g. 2560x1440)")
    return int(m.group(1)), int(m.group(2))


def _date(text: str) -> str:
    try:
        return _dt.date.fromisoformat(text).isoformat()
    except ValueError:
        raise argparse.ArgumentTypeError("expected YYYY-MM-DD (e.g. 2026-01-31)") from None


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="palette2theme",
        description="Build an Omarchy 4 theme folder from a handful of hex colours.",
        epilog="Example: palette2theme '#191d22' '#d4cfc8' '#f28c38' '#fb5668' '#7f9fc0' '#afcd8b' "
               "--name 'Steel Copy' --out ./steel-copy")
    p.add_argument("colors", nargs="*", metavar="HEX", help="palette colours (#rrggbb or #rgb); about 6 works best")
    p.add_argument("--palette", metavar="FILE", help="read colours from a JSON, TOML or one-hex-per-line file")
    p.add_argument("--name", required=True, help="display name, e.g. 'Steel & Ember'")
    p.add_argument("--slug", help="theme folder name (default: derived from --name)")
    p.add_argument("--out", help="theme folder to create (default: ./<slug>)")
    p.add_argument("--target", choices=["omarchy", "plasma"], default="omarchy",
                   help="output format (plasma is a stub and not implemented yet)")
    p.add_argument("--mode", choices=["auto", "dark", "light"], default="auto", help="theme mode (default: auto)")
    p.add_argument("--accent", metavar="HEX", help="use this accent instead of the most saturated input")
    p.add_argument("--strict", action="store_true",
                   help="fail instead of adjusting colours that miss 4.5:1 contrast")
    p.add_argument("--force", action="store_true", help="overwrite generated files in an existing, non-empty --out")
    p.add_argument("--description", default="", help="one-line description for README and colors.toml")
    p.add_argument("--version-string", dest="theme_version", default="0.1.0", help="theme VERSION (default 0.1.0)")
    p.add_argument("--author", default=None,
                   help="copyright holder (default: $PALETTE2THEME_AUTHOR, else `git config user.name`, "
                        f"else '{FALLBACK_AUTHOR}')")
    p.add_argument("--brand", default=os.environ.get("PALETTE2THEME_BRAND", ""),
                   help="optional label for file headers, e.g. 'by <brand>' (default: none, or $PALETTE2THEME_BRAND)")
    p.add_argument("--year", type=int, default=2026, help="copyright year (default: 2026)")
    p.add_argument("--date", type=_date, metavar="YYYY-MM-DD",
                   help="release date for the theme CHANGELOG (default: today)")
    p.add_argument("--repo-url", default="", help="git URL to show in the README install section")
    p.add_argument("--wallpaper-size", type=_size, default=(2560, 1440), metavar="WxH", help="default 2560x1440")
    p.add_argument("--preview-size", type=_size, default=(1280, 720), metavar="WxH", help="default 1280x720")
    p.add_argument("-q", "--quiet", action="store_true", help="only print errors")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    say = (lambda *a: None) if args.quiet else (lambda *a: print(*a, file=sys.stderr))

    try:
        colors = parse_colors(args.colors)
        if args.palette:
            colors = read_palette_file(args.palette) + colors
        if not colors:
            raise PaletteError("no colours given: pass hex colours or --palette FILE")
        if len(colors) < 2:
            raise PaletteError("need at least 2 colours (about 6 works best)")
        if len(colors) > 16:
            raise PaletteError(f"got {len(colors)} colours; at most 16 are supported")
        if not 4 <= len(colors) <= 8:
            say(f"note: {len(colors)} colours given; palette2theme is tuned for about 6")
        accent = Color.from_hex(args.accent) if args.accent else None
        slug = slugify(args.slug or args.name)
        scheme = derive_scheme(colors, mode=args.mode, accent=accent, strict=args.strict)
    except (PaletteError, ColorError, OutputError, ValueError) as e:
        print(f"palette2theme: error: {e}", file=sys.stderr)
        return EXIT_USAGE
    except ContrastError as e:
        print(f"palette2theme: {e}", file=sys.stderr)
        if args.strict:
            print("palette2theme: nothing written; drop --strict to let palette2theme adjust lightness", file=sys.stderr)
        return EXIT_CONTRAST

    for n in scheme.notes:
        say(f"note: {n}")
    for a in scheme.adjustments:
        say(f"contrast: {a.describe()}")

    out = Path(args.out) if args.out else Path.cwd() / slug
    if args.target == "plasma":
        try:
            write_plasma_scheme(scheme, args.name, out)
        except NotImplementedError as e:
            print(f"palette2theme: {e}", file=sys.stderr)
            return EXIT_NOT_IMPLEMENTED

    author = args.author if args.author is not None and args.author.strip() else default_author()
    meta = ThemeMeta(name=args.name, slug=slug, version=args.theme_version, author=author,
                     year=args.year, date=args.date or "", description=args.description,
                     repo_url=args.repo_url, brand=args.brand,
                     source=Path(args.palette).name if args.palette else "",
                     wallpaper_size=args.wallpaper_size, preview_size=args.preview_size)
    try:
        written = write_theme(scheme, meta, out, force=args.force)
    except OutputError as e:
        print(f"palette2theme: error: {e}", file=sys.stderr)
        return EXIT_USAGE
    say(f"wrote {len(written)} files to {out} ({scheme.mode} mode, accent {scheme['accent'].hex})")
    say(f"install: cd {out} && ./install.sh --dry-run")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
