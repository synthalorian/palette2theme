# palette2theme

Turn about six hex colours into a complete, installable **Omarchy 4** theme folder, laid out like
a hand-made Omarchy 4 theme (originally written for the Glyphsmith themes). Contrast checks are built in.

- Pure Python 3 standard library (3.11+ for TOML palettes). No packages to install.
- Every text colour reaches **WCAG 2.x AA (4.5:1)** on the surfaces it is drawn on. Colours that
  miss it are moved in lightness, keeping their hue, or the run fails with `--strict`.
- Output is deterministic apart from the release date in the theme's CHANGELOG, which defaults to
  today. Pass `--date YYYY-MM-DD` and the same palette and options give byte-identical files.

```bash
bin/palette2theme '#191d22' '#d4cfc8' '#f28c38' '#fb5668' '#7f9fc0' '#afcd8b' \
  --name 'Forge Night' --accent '#f28c38' --out ./forge-night
cd forge-night && ./install.sh --dry-run
```

## Usage

```
palette2theme [HEX ...] [--palette FILE] --name NAME [--out DIR] [options]
```

| Option | Meaning |
|---|---|
| `HEX ...` | Palette colours, `#rrggbb` or `#rgb` (quote them in the shell). 2 to 16 are accepted; about 6 works best |
| `--palette FILE` | Read colours from a file (see below). Colours given as arguments are appended |
| `--name NAME` | Display name, e.g. `'Steel & Ember'`. The folder name (slug) comes from it: `steel-and-ember` |
| `--slug SLUG` | Override the folder name. It must match Omarchy's `^[a-z0-9_][a-z0-9._+-]*$` |
| `--out DIR` | Theme folder to create (default `./<slug>`). It must be missing or empty unless `--force` is given |
| `--mode auto\|dark\|light` | `auto` (the default) picks light when the **first** colour is light (palettes usually list the background first) |
| `--accent HEX` | Use this accent instead of the most saturated input |
| `--strict` | Do not adjust anything. Exit with code 3 and list every pair under 4.5:1 |
| `--force` | Write into an existing non-empty folder. It overwrites only the generated files and leaves other files alone. It refuses, before writing anything, if a generated file or `backgrounds/` is a symlink or not a regular file/folder |
| `--target omarchy\|plasma` | `plasma` is a **stub** and exits with code 4 (see [Unfinished](#unfinished)) |
| `--description`, `--author`, `--year`, `--version-string`, `--repo-url` | Metadata for README, CHANGELOG, LICENSE and VERSION. The author defaults to `$PALETTE2THEME_AUTHOR`, else your `git config user.name`, else `Theme author`; the year defaults to 2026. Newlines and other control characters in these and `--name` become spaces, so they cannot break `colors.toml` |
| `--brand NAME` | Optional label for the generated file headers ("Omarchy theme by NAME", "(NAME) theme installer"). Default: none, so output is unbranded. `$PALETTE2THEME_BRAND` sets it too |
| `--date YYYY-MM-DD` | Release date in the theme's CHANGELOG (default: today) |
| `--wallpaper-size WxH`, `--preview-size WxH` | Defaults `2560x1440` and `1280x720` |
| `-q` | Print errors only |

Exit codes: `0` ok, `2` usage or input error, `3` contrast failure under `--strict`, `4` target not implemented.

You can also run it as `python3 -m palette2theme` from the repo root.

### Palette files

All three formats are detected by extension (`.json`, `.toml`, anything else) or by content:

```json
{ "colors": ["#191d22", "#d4cfc8", "#f28c38", "#fb5668", "#7f9fc0", "#afcd8b"] }
```

```toml
colors = ["#191d22", "#d4cfc8", "#f28c38"]
# or a table of named colours (order is kept):
[palette]
bg = "#191d22"
fg = "#d4cfc8"
```

```text
# one hex per line; "# " lines and trailing comments are ignored
#191d22   # background
#d4cfc8
```

JSON can also be a bare list, or an object with `palette`. See [`examples/`](examples/).

## What it generates

```
<slug>/
├── colors.toml          # mode + all 49 Omarchy 4 keys (accent, surfaces, fg shades, ANSI, borders, color0-15)
├── btop.theme           # colour-only btop override
├── icons.theme          # nearest Yaru accent variant (Yaru-red, Yaru-blue, Yaru-sage, …)
├── shell.lock.toml      # lock screen; card and selection opacity computed for 4.5:1 over any wallpaper
│                        # (if no opacity works, the card goes opaque and the lock text colours are moved in lightness)
├── backgrounds/1-<slug>.png   # palette-tinted gradient + glow + grain, written by a stdlib PNG encoder
├── preview.png          # mock window: bar, text lines, selection, the 16 ANSI swatches
├── VERSION  README.md  CHANGELOG.md  LICENSE (MIT)
└── install.sh  uninstall.sh   # copied from themes/mesa; only the header line is renamed
```

**Why there is no `hyprland.conf`, `waybar.css`, `mako.ini`, `walker.css` or terminal configs:** the
Omarchy 4 spec (`templates/OMARCHY-THEME-SPEC.md`) says waybar, mako, walker and swayosd were
removed in 4.x. Hyprland, Alacritty, Kitty, Ghostty, Foot, Neovim and the other apps are rendered from
`colors.toml` templates. A git-installed theme has its `*.lua` and terminal configs ignored anyway.
So, like `steel-and-ember`, everything goes into `colors.toml`. `btop.theme` and `shell.lock.toml` are
the colour-only overrides that every install method keeps.

## How colours are derived

All the colour work happens in **OKLCH**, which is perceptually uniform, so lightness steps look even
across hues.

1. **Background**: the darkest input in dark mode (the lightest in light mode). Its hue is kept, it is
   moved into a surface lightness band (L 0.16–0.28 dark, 0.93–0.975 light), and its chroma is capped.
   `dark_background`, `darker_background` and `lighter_background` are lightness steps from it.
2. **Foreground**: the lightest input in dark mode (the darkest in light mode), turned into a near-neutral
   tinted by its own hue. `light_`, `bright_` and `dark_foreground` and `muted` derive from it and the background.
3. **Accent**: the most saturated remaining input, or `--accent`.
4. **ANSI hues**: each saturated input (chroma ≥ 0.06) is matched greedily to the nearest free slot
   among red, orange, yellow, green, cyan, blue and magenta, within 35° of hue. Empty slots are
   synthesised at the slot hue with the palette's median lightness and chroma. `brown` and the
   `bright_*` variants derive from these.
5. **Contrast**: `foreground`, `light_foreground` and `bright_foreground` must reach 4.5:1 on all four
   background shades. Every other text colour (all ANSI 1–15, `accent`, `muted`, `brown`,
   `dark_foreground`) must reach 4.5:1 on `background`, and `selection_foreground` on `selection_background`.
   A colour that fails is moved in OKLCH lightness, with hue and chroma kept where the gamut allows,
   until it passes. Each change is printed and logged in the theme's CHANGELOG. With `--strict`
   nothing is written.
6. **Terminal map**: `color0` = background, `1–6` = red, green, yellow, blue, magenta, cyan,
   `7` = foreground, `8` = muted, `9–14` = brights, `15` = bright foreground. This is the usual Omarchy convention.
7. **Borders**: an accent → second-most-saturated-input gradient at 45°, with a dim surface colour for inactive windows.

## Tests

```bash
./run-tests.sh            # = python3 -m unittest discover -s tests -t .
```

The suite has 66 tests. It covers colour maths against WCAG reference values, all three palette formats
and their errors, role assignment, contrast enforcement, `--strict`, light mode, 150 random fuzzed
palettes, PNG validity (decoded and CRC-checked), lock-screen contrast for 200 random dark and light palettes,
`--force` refusing symlinks, metadata sanitising, reproducible output with `--date`, the full CLI and Plasma stub, and a real
`install.sh` → `uninstall.sh` round trip in a throwaway `$HOME`, unbranded output by default, `--brand`,
and reading an older `.glyphsmith-install.manifest`. If a folder of reference themes is available
(`PALETTE2THEME_REFERENCE_THEMES`, default `/workspace/glyphsmith/themes`), it also checks key-for-key
parity with its `steel-and-ember`; without it those checks are skipped.

The bundled `install.sh` writes `.theme-install.manifest` in the installed theme folder. `uninstall.sh`
also reads the older `.glyphsmith-install.manifest`. Its fallback theme is set with `--fallback`,
`$THEME_FALLBACK`, or the older `$GLYPHSMITH_FALLBACK_THEME` (default `tokyo-night`).

## Layout

| Path | What |
|---|---|
| `palette2theme/color.py` | hex parsing, sRGB ↔ OKLab/OKLCH, gamut mapping, WCAG contrast |
| `palette2theme/palette_io.py` | JSON / TOML / line palette readers |
| `palette2theme/derive.py` | role assignment, ANSI slots, contrast enforcement (`Scheme`) |
| `palette2theme/omarchy.py` | Omarchy 4 file renderers and atomic folder writer |
| `palette2theme/png.py` | PNG encoder, wallpaper and preview renderers |
| `palette2theme/plasma.py` | **stub**: KDE Plasma colour scheme (TODO) |
| `palette2theme/data/` | `install.sh` and `uninstall.sh` from `themes/mesa`, plus the LICENSE template |

## Unfinished

- **KDE Plasma output**: `--target plasma` is a marked stub. It raises `NotImplementedError` with a TODO, and the
  planned `.colors` mapping is written down in `palette2theme/plasma.py`.
- Not generated: `unlock.png` / `preview-unlock.png` (the boot-unlock logo), `screenshots/`, and the
  Zed/Emacs `extras/` that the hand-made themes ship.
- The preview is a swatch mock-up, not a real desktop screenshot.
- Contrast is WCAG 2.x only. There is no APCA check and no colour-vision-deficiency (dE00) separation check like
  the hand-tuned themes have.
- No 3.x compatibility output (waybar, mako, walker). That is deliberate per the spec, and could be added behind a flag.

## License

MIT © 2026 synthalorian. See [LICENSE](LICENSE). Generated themes are MIT too, with the holder set by `--author` (see above).
