# Changelog

All notable changes to palette2theme are recorded here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [SemVer](https://semver.org/).

## [0.2.0] - 2026-11-02
### Changed
- Output is unbranded by default. `--brand NAME` (or `$PALETTE2THEME_BRAND`) adds a label to the file headers.
- `--author` no longer defaults to a fixed name: it takes `$PALETTE2THEME_AUTHOR`, else `git config user.name`, else `Theme author`.
- The bundled installer writes `.theme-install.manifest`; uninstall still reads `.glyphsmith-install.manifest`. `$THEME_FALLBACK` replaces `$GLYPHSMITH_FALLBACK_THEME`, which is still accepted.
- The reference-theme tests read `$PALETTE2THEME_REFERENCE_THEMES` and skip when it is missing. The bundled scripts are no longer compared to `mesa`, as they now differ on purpose.

## [0.1.0] - not published
### Added
- `palette2theme` CLI: hex colours as arguments and/or `--palette` (JSON, TOML, one hex per line), `--name`, `--out`, `--mode auto|dark|light`, `--accent`, `--strict`, `--force`.
- Omarchy 4 theme output laid out like a hand-made Omarchy 4 theme: `colors.toml` (all 49 keys plus `mode`), `btop.theme`, `icons.theme`, `shell.lock.toml`, `backgrounds/1-<slug>.png`, `preview.png`, `VERSION`, `README.md`, `CHANGELOG.md`, `LICENSE`, and the Mesa `install.sh`/`uninstall.sh`.
- OKLCH role assignment and ANSI hue matching, with synthesised colours for empty hue slots.
- WCAG 2.x contrast enforcement (4.5:1) by moving lightness only; `--strict` fails instead.
- Stdlib PNG writer, palette-tinted wallpaper and swatch preview.
- `--target plasma` stub (raises `NotImplementedError`, exit code 4).
- `--date YYYY-MM-DD` for the theme CHANGELOG release date, so output can be reproduced byte for byte.
### Fixed
- `--force` no longer writes through symlinks: it refuses if a generated file or `backgrounds/` is a symlink, and files are opened with `O_NOFOLLOW`.
- Lock screen: light themes could leave the placeholder under 4.5:1 on the opaque card. The lock text colours are now moved in lightness when no card opacity is enough.
- Newlines in `--name`/`--description` (and other metadata) could inject keys into `colors.toml`; control characters now become spaces.
- Backslashes in `--author` crashed LICENSE generation or altered it; the author is now inserted literally.
- README no longer claims fully deterministic output without `--date`.
