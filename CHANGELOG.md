# Changelog

All notable changes to palette2theme are recorded here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [SemVer](https://semver.org/).

## [0.1.0] - Unreleased
### Added
- `palette2theme` CLI: hex colours as arguments and/or `--palette` (JSON, TOML, one hex per line), `--name`, `--out`, `--mode auto|dark|light`, `--accent`, `--strict`, `--force`.
- Omarchy 4 theme output laid out like the Glyphsmith themes: `colors.toml` (all 49 keys plus `mode`), `btop.theme`, `icons.theme`, `shell.lock.toml`, `backgrounds/1-<slug>.png`, `preview.png`, `VERSION`, `README.md`, `CHANGELOG.md`, `LICENSE`, and the Mesa `install.sh`/`uninstall.sh`.
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
