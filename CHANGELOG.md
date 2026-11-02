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
