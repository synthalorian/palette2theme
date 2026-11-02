"""Write an Omarchy 4 theme folder, laid out like a hand-made Omarchy 4 theme.

Omarchy 4 renders hyprland, terminal, editor and shell configs from colors.toml, ignores
*.lua and terminal configs in git-installed themes, and has dropped waybar, mako, walker and
swayosd. So, as in hand-made Omarchy 4 themes, everything goes into colors.toml, plus the
colour-only overrides (btop.theme, shell.lock.toml) that every install method keeps.
"""

from __future__ import annotations

import dataclasses
import datetime as _dt
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from . import __version__
from .color import BLACK, WHITE, Color, contrast, push_to_contrast
from .derive import MIN_CONTRAST, Scheme
from .png import encode_png, render_preview, render_wallpaper

DATA_DIR = Path(__file__).parent / "data"
NAME_RE = re.compile(r"^[a-z0-9_][a-z0-9._+-]*$")
SCRIPT_HEADER = "# Mesa theme "
# Control characters (newlines included) are not allowed in TOML comments and would end a
# comment line early, letting metadata inject keys.
CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]+")


class OutputError(RuntimeError):
    pass


def slugify(name: str) -> str:
    """Theme folder name, normalised the way omarchy-theme-set/-install expect it."""
    s = name.strip().lower().replace("&", " and ")
    s = re.sub(r"[^a-z0-9._+-]+", "-", s).strip("-.")
    s = re.sub(r"-{2,}", "-", s)
    s = re.sub(r"^omarchy-", "", s)
    s = re.sub(r"-theme$", "", s)
    if not NAME_RE.match(s):
        raise OutputError(f"cannot make an Omarchy theme name from {name!r}; pass --slug")
    return s


@dataclass
class ThemeMeta:
    name: str
    slug: str
    version: str = "0.1.0"
    author: str = "Theme author"
    year: int = 2026
    date: str = ""
    description: str = ""
    repo_url: str = ""
    source: str = ""
    brand: str = ""  # optional label for headers ("by <brand>"); empty = unbranded
    wallpaper_size: tuple[int, int] = (2560, 1440)
    preview_size: tuple[int, int] = (1280, 720)


def _one_line(text: str) -> str:
    return CONTROL_RE.sub(" ", text).strip()


# -- file renderers -----------------------------------------------------------

def render_colors_toml(s: Scheme, meta: ThemeMeta) -> str:
    v = s.as_toml_values()
    desc = meta.description or "Generated from a palette by palette2theme."
    by = f" by {_one_line(meta.brand)}" if meta.brand.strip() else ""
    lines = [f"# {meta.name} — Omarchy theme{by}", f"# {desc}", "",
             f'mode = "{v["mode"]}"', ""]

    def block(keys: list[str]) -> None:
        lines.extend(f'{k} = "{v[k]}"' for k in keys)
        lines.append("")

    block(["accent", "selection", "muted"])
    block(["background", "dark_background", "darker_background", "lighter_background"])
    block(["foreground", "dark_foreground", "light_foreground", "bright_foreground"])
    block(["red", "yellow", "orange", "green", "cyan", "blue", "magenta", "brown"])
    block(["bright_red", "bright_yellow", "bright_green", "bright_cyan", "bright_blue", "bright_magenta"])
    lines.append("# Window borders: accent gradient on the active window, dim surface on inactive ones.")
    block(["hyprland_active_border", "hyprland_inactive_border"])
    lines.append("# Terminal and selection colors.")
    block(["cursor", "selection_foreground", "selection_background"])
    block([f"color{i}" for i in range(16)])
    return "\n".join(lines).rstrip() + "\n"


def render_btop(s: Scheme, meta: ThemeMeta) -> str:
    c = {k: v.hex for k, v in s.colors.items()}
    grad = sorted([c["background"], c["lighter_background"], c["selection"], c["muted"],
                   c["dark_foreground"], c["foreground"], c["light_foreground"], c["bright_foreground"]],
                  key=lambda h: Color.from_hex(h).oklch[0], reverse=not s.dark)
    entries = [
        ("Main background, empty for terminal default, need to be empty if you want transparent background", [("main_bg", "background")]),
        ("Main text color", [("main_fg", "foreground")]),
        ("Title color for boxes", [("title", "light_foreground")]),
        ("Highlight color for keyboard shortcuts", [("hi_fg", "accent")]),
        ("Background color of selected item in processes box", [("selected_bg", "selection")]),
        ("Foreground color of selected item in processes box", [("selected_fg", "bright_foreground")]),
        ("Color of inactive/disabled text", [("inactive_fg", "muted")]),
        ("Color of text appearing on top of graphs, i.e uptime and current network graph scaling", [("graph_text", "light_foreground")]),
        ("Background color of the percentage meters", [("meter_bg", "lighter_background")]),
        ("Misc colors for processes box including mini cpu graphs, details memory graph and details status text", [("proc_misc", "yellow")]),
        ("CPU, Memory, Network, Proc box outline colors", [("cpu_box", "accent"), ("mem_box", "blue"), ("net_box", "cyan"), ("proc_box", "muted")]),
        ("Box divider line and small boxes line color", [("div_line", "muted")]),
        ("Temperature graph color", [("temp_start", "blue"), ("temp_mid", "yellow"), ("temp_end", "red")]),
        ("CPU graph colors", [("cpu_start", "yellow"), ("cpu_mid", "orange"), ("cpu_end", "red")]),
        ("Mem/Disk free meter", [("free_start", "cyan"), ("free_mid", "blue"), ("free_end", "bright_blue")]),
        ("Mem/Disk cached meter", [("cached_start", "blue"), ("cached_mid", "bright_blue"), ("cached_end", "bright_cyan")]),
        ("Mem/Disk available meter", [("available_start", "green"), ("available_mid", "bright_green"), ("available_end", "yellow")]),
        ("Mem/Disk used meter", [("used_start", "yellow"), ("used_mid", "orange"), ("used_end", "red")]),
        ("Download graph colors", [("download_start", "blue"), ("download_mid", "cyan"), ("download_end", "bright_cyan")]),
        ("Upload graph colors", [("upload_start", "yellow"), ("upload_mid", "orange"), ("upload_end", "red")]),
        ("Process box color gradient for threads, mem and cpu usage", [("process_start", "yellow"), ("process_mid", "orange"), ("process_end", "red")]),
    ]
    by = f" — by {_one_line(meta.brand)}" if meta.brand.strip() else ""
    out = [f"# {meta.name} for btop{by} (generated by palette2theme)", ""]
    for comment, items in entries:
        out.append(f"# {comment}")
        out.extend(f'theme[{k}]="{c[role]}"' for k, role in items)
        out.append("")
    out.append("# Graph gradient colors (spectrum shades from background to foreground)")
    out.extend(f'theme[gradient_color_{i}]="{h}"' for i, h in enumerate(grad))
    return "\n".join(out) + "\n"


LOCK_TEXTS = (("text", "foreground"), ("placeholder", "dark_foreground"), ("text-error", "bright_red"))


def lock_palette(s: Scheme) -> tuple[float, float, dict[str, Color]]:
    """Card opacity, selection opacity and text colours for the lock screen.

    The card must keep every lock text colour at MIN_CONTRAST over a pure white *and* a pure
    black wallpaper; the selection highlight (accent) must keep the text readable on top of it.
    If no opacity works with the scheme colours (light themes, where the card is darker than the
    background the text was checked against), the card goes opaque and the failing text colours
    are moved in lightness, like any other contrast fix."""
    card = s["dark_background"]
    texts = {key: s[role] for key, role in LOCK_TEXTS}

    def readable(a: float) -> bool:
        return all(contrast(t, card.over(w, a)) >= MIN_CONTRAST for t in texts.values() for w in (WHITE, BLACK))

    alpha = next((a100 / 100 for a100 in range(85, 101) if readable(a100 / 100)), None)
    if alpha is None:
        alpha = 1.0
        for key, col in texts.items():
            fixed = push_to_contrast(col, [card], MIN_CONTRAST, prefer_lighter=s.dark)
            if fixed is None:  # pragma: no cover - black or white always clears 4.5:1 on a surface shade
                raise OutputError(f"lock screen {key} cannot reach {MIN_CONTRAST}:1 on {card.hex}")
            texts[key] = fixed
    # At 0 the highlight is invisible and the text is on the bare card, which passes above.
    sel = next((s100 / 100 for s100 in range(45, -1, -1)
                if all(contrast(texts["text"], s["accent"].over(card.over(w, alpha), s100 / 100)) >= MIN_CONTRAST
                       for w in (WHITE, BLACK))), 0.0)
    return alpha, sel, texts


def render_shell_lock(s: Scheme) -> str:
    alpha, sel, texts = lock_palette(s)
    rows = [
        ("background", f'"{s["dark_background"].hex}"'), ("background-alpha", f"{alpha:g}"),
        ("text", f'"{texts["text"].hex}"'), ("placeholder", f'"{texts["placeholder"].hex}"'),
        ("text-error", f'"{texts["text-error"].hex}"'), ("border", f'"{s["dark_foreground"].hex}"'),
        ("border-active", f'"{s["accent"].hex}"'), ("border-error", f'"{s["bright_red"].hex}"'),
        ("border-alpha", "1.0"), ("border-width", "1"),
        ("selection", f'"{s["accent"].hex}"'), ("selection-alpha", f"{sel:g}"),
    ]
    return ("# Full [lock] replacement. Theme set swaps this section in over shell.toml.\n"
            + "".join(f"{k:<16} = {v}\n" for k, v in rows))


def pick_icon_theme(s: Scheme) -> str:
    """Nearest Yaru accent variant to the theme accent."""
    L, C, h = s["accent"].oklch
    if C < 0.05:
        return "Yaru-bark" if L < 0.6 else "Yaru"
    for limit, name in [(40, "Yaru-red"), (75, "Yaru" if C > 0.1 else "Yaru-wartybrown"),
                        (120, "Yaru-olive"), (165, "Yaru-sage"), (215, "Yaru-viridian"),
                        (275, "Yaru-blue"), (310, "Yaru-purple"), (350, "Yaru-magenta"), (361, "Yaru-red")]:
        if h < limit:
            return name
    return "Yaru"  # pragma: no cover


def _palette_table(s: Scheme) -> str:
    c = {k: v.hex for k, v in s.colors.items()}
    rows = [("background", "foreground"), ("dark_background", "light_foreground"),
            ("darker_background", "bright_foreground"), ("lighter_background", "dark_foreground"),
            ("selection", "muted"), ("accent", "brown")]
    out = ["| Role | Hex | | Role | Hex |", "|---|---|---|---|---|"]
    out += [f"| {a} | `{c[a]}` | | {b} | `{c[b]}` |" for a, b in rows]
    out += ["", "| ANSI | Normal | Bright |", "|---|---|---|"]
    names = ["black", "red", "green", "yellow", "blue", "magenta", "cyan", "white"]
    out += [f"| {n} | `{c[f'color{i}']}` ({i}) | `{c[f'color{i + 8}']}` ({i + 8}) |" for i, n in enumerate(names)]
    return "\n".join(out)


def render_readme(s: Scheme, meta: ThemeMeta, icon: str, wallpaper: str) -> str:
    pairs = s.contrast_pairs()
    worst = min(pairs, key=lambda p: p[2])
    title = meta.name
    slug = meta.slug
    w, h = meta.wallpaper_size
    inputs = ", ".join(f"`{c.hex}`" for c in s.inputs)
    adjusted = (f"{len(s.adjustments)} colour(s) were moved in lightness to get there; see CHANGELOG.md."
                if s.adjustments else "No colour needed adjusting.")
    git_methods = ""
    if meta.repo_url:
        git_methods = f"""**Omarchy's installer**

```bash
omarchy-theme-install {meta.repo_url}
```

**Git clone into the themes folder**

```bash
git clone {meta.repo_url} ~/.config/omarchy/themes/{slug}
omarchy-theme-set {slug}
```

"""
    return f"""# {title}

{meta.description or f"A {s.mode} Omarchy theme generated from the palette {inputs}."}

**Version:** {meta.version} · **For:** Omarchy (Hyprland) 4.0+ · **Mode:** {s.mode}

![{title} preview](preview.png)

## What it themes

Omarchy 4 renders every app config from `colors.toml`, so this theme ships a palette rather than
per-app files. Switching to it colours:

- **Hyprland** window borders: an accent gradient on the active window, a dim surface colour on inactive ones
- **Omarchy shell**: top bar, menus, launcher, notifications, OSD, polkit prompt and lock screen
- **Terminals**: Alacritty, Ghostty, Kitty and Foot (all 16 ANSI colours)
- **Editors**: Neovim, Helix, VS Code/Cursor (generated theme), Obsidian
- **btop**: a colour-only `btop.theme`
- **Lock screen**: `shell.lock.toml` keeps every lock text colour at 4.5:1 or more over any wallpaper
- **GTK icons**: `{icon}`, the Yaru variant closest to the accent
- **Wallpaper**: `{wallpaper}` ({w}x{h}), a procedural gradient tinted by the palette

## Theme files

| File | Purpose |
|---|---|
| `colors.toml` | The palette. Omarchy renders Hyprland, terminal, shell, editor and app configs from it |
| `btop.theme` | Colour-only btop override (kept by every install method) |
| `icons.theme` | GTK icon theme name (`{icon}`) |
| `{wallpaper}` | Default wallpaper |
| `preview.png` | Theme picker preview |
| `shell.lock.toml` | Lock screen colours (merged into the `[lock]` section of the generated `shell.toml`) |
| `install.sh`, `uninstall.sh` | Optional installer for the release tarball |

## Palette

{_palette_table(s)}

All text colours reach at least {MIN_CONTRAST}:1 (WCAG 2.x AA) against the background, and the main
text colours against every panel shade too. The lowest pair is `{worst[0]}` on `{worst[1]}` at
{worst[2]:.2f}:1. {adjusted} ANSI 0 is the background itself, the Omarchy convention.

## Requirements

- Omarchy 4.0 or newer (Omarchy 4 renders app configs from `colors.toml`)
- Optional: icon theme `{icon.split('-')[0]}` (named in `icons.theme`)
- No root access needed

## Install

{git_methods}**Bundled installer** (refuses to replace a folder it didn't install, and writes a manifest)

```bash
cd {slug}
./install.sh --dry-run   # preview
./install.sh --apply     # install and switch to it
```

**Copy it by hand** (a plain copy without `.git` counts as your own theme, so Omarchy uses every file)

```bash
cp -r {slug} ~/.config/omarchy/themes/{slug}
omarchy-theme-set {slug}
```

## Uninstall

- Installed by hand or with git: switch to another theme, then `omarchy-theme-remove {slug}`
- Installed with `install.sh`: `./uninstall.sh` (switches away if the theme is active and removes only the files it added). Use `./uninstall.sh --dry-run` to preview.

## Changelog

See [CHANGELOG.md](CHANGELOG.md).

## License

MIT © {meta.year} {meta.author}. See [LICENSE](LICENSE).

## Credits

- Design and packaging: {meta.author}
- Generated with palette2theme {__version__} from {inputs}
- Wallpaper: `{wallpaper}` is procedural artwork generated from the palette (MIT, same as the theme)
- Built for [Omarchy](https://omarchy.org)
"""


def render_changelog(s: Scheme, meta: ThemeMeta, wallpaper: str) -> str:
    adj = "".join(f"  - {a.describe()}\n" for a in s.adjustments)
    notes = "".join(f"  - {n}\n" for n in s.notes)
    extra = ""
    if adj:
        extra += "- Contrast: colours moved in OKLCH lightness to reach 4.5:1:\n" + adj
    if notes:
        extra += "- Derivation notes:\n" + notes
    src = f" (`{meta.source}`)" if meta.source else ""
    return f"""# Changelog

All notable changes to {meta.name} are recorded here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [SemVer](https://semver.org/).

## [{meta.version}] - {meta.date}
### Added
- First release, generated by palette2theme {__version__} from {len(s.inputs)} input colours{src}: `colors.toml` ({s.mode}, 16 ANSI colours, accent border gradient), `btop.theme`, `icons.theme`, `shell.lock.toml`, wallpaper `{wallpaper}`, `preview.png`, and the bundled `install.sh`/`uninstall.sh`.
{extra}
<!-- Sections to use: Added, Changed, Deprecated, Removed, Fixed, Security -->
"""


def render_license(meta: ThemeMeta) -> str:
    body = (DATA_DIR / "LICENSE").read_text(encoding="utf-8")
    holder = f"Copyright (c) {meta.year} {meta.author}"
    # A function replacement, so backslashes in the author are kept literally.
    return re.sub(r"Copyright \(c\) .*", lambda _: holder, body, count=1)


def render_script(which: str, meta: ThemeMeta) -> str:
    body = (DATA_DIR / which).read_text(encoding="utf-8")
    display = _one_line(meta.name)
    if SCRIPT_HEADER not in body:  # pragma: no cover - guards a changed upstream script
        raise OutputError(f"unexpected header in bundled {which}")
    brand = f" ({_one_line(meta.brand)})" if meta.brand.strip() else ""
    return body.replace(SCRIPT_HEADER, f"# {display}{brand} theme ", 1)


# -- output -------------------------------------------------------------------

def _check_target(out: Path, force: bool) -> None:
    if out.is_symlink():
        raise OutputError(f"{out} is a symlink; refusing to write through it")
    if out.exists():
        if not out.is_dir():
            raise OutputError(f"{out} exists and is not a folder")
        if any(out.iterdir()) and not force:
            raise OutputError(f"{out} exists and is not empty (pass --force to overwrite the generated files)")


def _check_generated_paths(dest: Path, rels: list[str]) -> None:
    """Refuse before writing anything if a generated path, or a folder on the way to one, is a
    symlink or not what we would write. Writing through it could land outside the theme."""
    seen: set[Path] = set()
    for rel in rels:
        parts = rel.split("/")
        for i in range(1, len(parts)):
            d = dest.joinpath(*parts[:i])
            if d in seen:
                continue
            seen.add(d)
            if d.is_symlink() or (d.exists() and not d.is_dir()):
                raise OutputError(f"{d} is a symlink or not a folder; refusing to write through it")
        p = dest / rel
        if p.is_symlink() or (p.exists() and not p.is_file()):
            raise OutputError(f"{p} is a symlink or not a regular file; refusing to overwrite it")


def _write(dest: Path, rel: str, data: bytes, mode: int = 0o644) -> None:
    """Write dest/rel without following a symlink at any step below dest."""
    *dirs, name = rel.split("/")
    fd = os.open(dest, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for d in dirs:
            try:
                os.mkdir(d, 0o755, dir_fd=fd)
            except FileExistsError:
                pass
            sub = os.open(d, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = sub
        # Write a fresh temp file and rename it over the entry, so an existing hard link
        # (or any other file the name points at) is replaced, never written through.
        tmp = f".{name}.p2t-tmp-{os.getpid()}"
        try:
            os.unlink(tmp, dir_fd=fd)
        except FileNotFoundError:
            pass
        f = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode, dir_fd=fd)
        try:
            with os.fdopen(f, "wb") as fh:
                os.fchmod(fh.fileno(), mode)
                fh.write(data)
            os.replace(tmp, name, src_dir_fd=fd, dst_dir_fd=fd)
        except BaseException:
            try:
                os.unlink(tmp, dir_fd=fd)
            except OSError:
                pass
            raise
    except OSError as e:
        raise OutputError(f"cannot write {dest / rel}: {e.strerror}") from e
    finally:
        os.close(fd)


def generate_files(s: Scheme, meta: ThemeMeta, dest: Path) -> list[str]:
    """Write every theme file into `dest` (which must exist). Returns relative paths written."""
    meta = dataclasses.replace(
        meta, name=_one_line(meta.name), description=_one_line(meta.description),
        author=_one_line(meta.author), version=_one_line(meta.version),
        repo_url=_one_line(meta.repo_url), source=_one_line(meta.source),
        date=meta.date or _dt.date.today().isoformat())
    wallpaper = f"backgrounds/1-{meta.slug}.png"
    icon = pick_icon_theme(s)
    text_files = {
        "colors.toml": render_colors_toml(s, meta),
        "btop.theme": render_btop(s, meta),
        "icons.theme": icon + "\n",
        "shell.lock.toml": render_shell_lock(s),
        "VERSION": meta.version + "\n",
        "README.md": render_readme(s, meta, icon, wallpaper),
        "CHANGELOG.md": render_changelog(s, meta, wallpaper),
        "LICENSE": render_license(meta),
        "install.sh": render_script("install.sh", meta),
        "uninstall.sh": render_script("uninstall.sh", meta),
    }
    written = sorted(list(text_files) + [wallpaper, "preview.png"])
    _check_generated_paths(dest, written)
    for rel, text in text_files.items():
        _write(dest, rel, text.encode("utf-8"), 0o755 if rel.endswith(".sh") else 0o644)

    c = s.colors
    seed = meta.slug + "".join(x.hex for x in s.inputs)
    w, h = meta.wallpaper_size
    _write(dest, wallpaper, encode_png(w, h, render_wallpaper(
        w, h, c["darker_background"], c["background"], c["accent"], c["blue"], s.dark, seed)))
    pw, ph = meta.preview_size
    _write(dest, "preview.png", encode_png(pw, ph, render_preview(s, pw, ph, seed)))
    return written


def write_theme(s: Scheme, meta: ThemeMeta, out: str | Path, force: bool = False) -> list[str]:
    """Write the theme to `out`. A new folder is built next to it and renamed into place, so an
    interrupted run never leaves a half-written theme behind."""
    out = Path(out)
    _check_target(out, force)
    if out.exists():
        return generate_files(s, meta, out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix=f".{out.name}.", dir=out.parent))
    try:
        written = generate_files(s, meta, tmp)
        os.chmod(tmp, 0o755)
        tmp.rename(out)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    return written
