"""Turn a handful of input colours into a full Omarchy 4 scheme.

Roles are assigned in OKLCH:

* background  - darkest input (lightest in light mode), pulled into a usable lightness band
                and desaturated so it reads as a surface.
* foreground  - lightest input (darkest in light mode), as a near-neutral tinted by its hue.
* accent      - the most chromatic remaining input (or --accent).
* ANSI hues   - each remaining chromatic input is matched to the nearest hue slot (red, orange,
                yellow, green, cyan, blue, magenta) within HUE_TOLERANCE degrees; empty slots
                are synthesised at the slot hue with the palette's typical lightness/chroma.

Every text colour is then checked against the WCAG 2.x 4.5:1 threshold on the surfaces it is
drawn on. By default failing colours are moved along OKLCH lightness until they pass (hue kept);
with strict=True the first failures are raised as ContrastError instead.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field

from .color import Color, contrast, hue_distance, push_to_contrast

MIN_CONTRAST = 4.5
HUE_TOLERANCE = 35.0
MIN_CHROMA = 0.06  # below this an input is treated as a neutral, not an ANSI hue

# Approximate OKLCH hues of the conventional terminal colours.
SLOT_HUES = {
    "red": 25.0,
    "orange": 55.0,
    "yellow": 90.0,
    "green": 145.0,
    "cyan": 200.0,
    "blue": 255.0,
    "magenta": 330.0,
}

# Keys every hand-made Omarchy 4 colors.toml carries (besides `mode`), in file order.
COLOR_KEYS = [
    "accent", "selection", "muted",
    "background", "dark_background", "darker_background", "lighter_background",
    "foreground", "dark_foreground", "light_foreground", "bright_foreground",
    "red", "yellow", "orange", "green", "cyan", "blue", "magenta", "brown",
    "bright_red", "bright_yellow", "bright_green", "bright_cyan", "bright_blue", "bright_magenta",
]
TERMINAL_KEYS = ["cursor", "selection_foreground", "selection_background"] + [f"color{i}" for i in range(16)]
BORDER_KEYS = ["hyprland_active_border", "hyprland_inactive_border"]
REQUIRED_KEYS = ["mode"] + COLOR_KEYS + BORDER_KEYS + TERMINAL_KEYS

ANSI_ORDER = ["red", "green", "yellow", "blue", "magenta", "cyan"]

# Text colours that must reach MIN_CONTRAST on the main background and its panel shades.
TEXT_ON_SURFACES = ["foreground", "light_foreground", "bright_foreground"]
TEXT_ON_BACKGROUND = [
    "dark_foreground", "muted", "accent", "brown",
    "red", "yellow", "orange", "green", "cyan", "blue", "magenta",
    "bright_red", "bright_yellow", "bright_green", "bright_cyan", "bright_blue", "bright_magenta",
]
SURFACES = ["background", "dark_background", "darker_background", "lighter_background"]


class ContrastError(RuntimeError):
    def __init__(self, failures: list["Adjustment"]):
        self.failures = failures
        lines = [f"  {a.key} {a.before.hex} on {a.against}: {a.ratio_before:.2f}:1 < {MIN_CONTRAST}:1"
                 for a in failures]
        super().__init__("contrast check failed (--strict):\n" + "\n".join(lines))


@dataclass
class Adjustment:
    key: str
    before: Color
    after: Color | None
    against: str
    ratio_before: float
    ratio_after: float | None

    def describe(self) -> str:
        if self.after is None:
            return f"{self.key}: {self.before.hex} cannot reach {MIN_CONTRAST}:1 on {self.against}"
        return (f"{self.key}: {self.before.hex} -> {self.after.hex} "
                f"({self.ratio_before:.2f}:1 -> {self.ratio_after:.2f}:1 on {self.against})")


@dataclass
class Scheme:
    mode: str
    colors: dict[str, Color]
    active_border: str
    inactive_border: str
    inputs: list[Color]
    roles: dict[str, str] = field(default_factory=dict)  # key -> "input #n" / "derived"
    adjustments: list[Adjustment] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def dark(self) -> bool:
        return self.mode == "dark"

    def __getitem__(self, key: str) -> Color:
        return self.colors[key]

    def as_toml_values(self) -> dict[str, str]:
        out = {"mode": self.mode}
        out.update({k: self.colors[k].hex for k in COLOR_KEYS})
        out["hyprland_active_border"] = self.active_border
        out["hyprland_inactive_border"] = self.inactive_border
        out.update({k: self.colors[k].hex for k in TERMINAL_KEYS})
        return out

    def contrast_pairs(self) -> list[tuple[str, str, float]]:
        """Every (text, surface, ratio) pair that is required to reach MIN_CONTRAST."""
        c = self.colors
        pairs = [(t, s, contrast(c[t], c[s])) for t in TEXT_ON_SURFACES for s in SURFACES]
        pairs += [(t, "background", contrast(c[t], c["background"])) for t in TEXT_ON_BACKGROUND]
        pairs.append(("selection_foreground", "selection_background",
                      contrast(c["selection_foreground"], c["selection_background"])))
        return pairs


def _pick_mode(inputs: list[Color], mode: str) -> str:
    if mode in ("dark", "light"):
        return mode
    if mode != "auto":
        raise ValueError(f"mode must be auto, dark or light (got {mode!r})")
    # Palettes conventionally list the background first, so its lightness decides.
    return "light" if inputs[0].oklch[0] > 0.7 else "dark"


def derive_scheme(inputs: list[Color], mode: str = "auto", accent: Color | None = None,
                  strict: bool = False) -> Scheme:
    if len(inputs) < 2:
        raise ValueError("need at least 2 colours (about 6 works best)")
    mode = _pick_mode(inputs, mode)
    dark = mode == "dark"
    notes: list[str] = []
    roles: dict[str, str] = {}

    def label(c: Color) -> str:
        return f"input {inputs.index(c) + 1} ({c.hex})"

    by_l = sorted(range(len(inputs)), key=lambda i: inputs[i].oklch[0])
    bg_i, fg_i = (by_l[0], by_l[-1]) if dark else (by_l[-1], by_l[0])
    bg_src, fg_src = inputs[bg_i], inputs[fg_i]
    rest = [c for i, c in enumerate(inputs) if i not in (bg_i, fg_i)]

    # -- surfaces ----------------------------------------------------------------
    L, C, h = bg_src.oklch
    bg_L = min(max(L, 0.16), 0.28) if dark else min(max(L, 0.93), 0.975)
    background = Color.from_oklch(bg_L, min(C, 0.035), h)
    if background != bg_src:
        notes.append(f"background {bg_src.hex} -> {background.hex} (kept the hue, moved into the "
                     f"{'dark' if dark else 'light'} surface range)")
    roles["background"] = label(bg_src)
    sign = 1 if dark else -1  # "towards the foreground"
    bL, bC, bh = background.oklch
    dark_background = Color.from_oklch(bL - 0.03 if dark else bL - 0.035, bC, bh)
    darker_background = Color.from_oklch(bL - 0.06 if dark else bL - 0.07, bC, bh)
    # Light themes (see vellum) use a slightly *darker* panel shade for lighter_background.
    lighter_background = Color.from_oklch(bL + 0.035 if dark else bL - 0.018, bC, bh)

    L, C, h = fg_src.oklch
    fg_L = max(L, 0.84) if dark else min(L, 0.32)
    foreground = Color.from_oklch(fg_L, min(C, 0.03), h)
    roles["foreground"] = label(fg_src)
    fL, fC, fh = foreground.oklch
    light_foreground = Color.from_oklch(fL + sign * 0.04, fC, fh)
    bright_foreground = Color.from_oklch(fL + sign * 0.08, fC * 0.8, fh)
    dark_foreground = foreground.mix(background, 0.3)
    muted = Color.from_oklch(0.62 if dark else 0.52, max(bC * 1.4, 0.015), bh)

    # -- chromatic slots -------------------------------------------------------
    chromatic = [c for c in rest if c.oklch[1] >= MIN_CHROMA]
    if accent is not None:
        roles["accent"] = f"--accent ({accent.hex})"
    elif chromatic:
        accent = max(chromatic, key=lambda c: c.oklch[1])
        roles["accent"] = label(accent)

    if chromatic:
        typ_L = statistics.median(c.oklch[0] for c in chromatic)
        typ_C = statistics.median(c.oklch[1] for c in chromatic)
    else:
        typ_L, typ_C = (0.74, 0.11) if dark else (0.5, 0.12)
        notes.append("no saturated input colours: every ANSI hue was synthesised")
    typ_L = min(max(typ_L, 0.68), 0.82) if dark else min(max(typ_L, 0.42), 0.56)
    typ_C = min(max(typ_C, 0.08), 0.16)

    candidates = sorted(
        (hue_distance(c.oklch[2], hue), i, slot)
        for i, c in enumerate(chromatic) for slot, hue in SLOT_HUES.items()
        if hue_distance(c.oklch[2], hue) <= HUE_TOLERANCE)
    slots: dict[str, Color] = {}
    used: set[int] = set()
    for _, i, slot in candidates:
        if slot in slots or i in used:
            continue
        slots[slot] = chromatic[i]
        used.add(i)
        roles[slot] = label(chromatic[i])
    for slot, hue in SLOT_HUES.items():
        if slot not in slots:
            slots[slot] = Color.from_oklch(typ_L, typ_C, hue)
            roles[slot] = "derived"
    if accent is None:  # no saturated input at all: borrow the synthesised blue
        accent = slots["blue"]
        roles["accent"] = "derived (blue)"
    for i, c in enumerate(chromatic):
        if i not in used and c != accent:
            notes.append(f"input {inputs.index(c) + 1} ({c.hex}) matched no free ANSI hue; "
                         f"it is used only where it is the accent or border")

    colors: dict[str, Color] = {
        "accent": accent, "muted": muted,
        "background": background, "dark_background": dark_background,
        "darker_background": darker_background, "lighter_background": lighter_background,
        "foreground": foreground, "dark_foreground": dark_foreground,
        "light_foreground": light_foreground, "bright_foreground": bright_foreground,
        **slots,
    }

    # -- contrast enforcement ----------------------------------------------------
    adjustments: list[Adjustment] = []
    failures: list[Adjustment] = []

    def enforce(key: str, surface_keys: list[str]) -> None:
        col = colors[key]
        surfaces = [colors[s] for s in surface_keys]
        ratios = [contrast(col, s) for s in surfaces]
        worst = min(range(len(ratios)), key=ratios.__getitem__)
        if ratios[worst] >= MIN_CONTRAST:
            return
        if strict:
            failures.append(Adjustment(key, col, None, surface_keys[worst], ratios[worst], None))
            return
        fixed = push_to_contrast(col, surfaces, MIN_CONTRAST, prefer_lighter=dark)
        adj = Adjustment(key, col, fixed, surface_keys[worst], ratios[worst],
                         None if fixed is None else min(contrast(fixed, s) for s in surfaces))
        if fixed is None:
            raise ContrastError([adj])
        colors[key] = fixed
        adjustments.append(adj)

    for key in TEXT_ON_SURFACES:
        enforce(key, SURFACES)
    base_keys = [k for k in TEXT_ON_BACKGROUND if k != "brown" and not k.startswith("bright_")]
    for key in base_keys:
        enforce(key, ["background"])

    # Brown and the bright variants derive from the (already readable) base colours.
    oL, oC, oh = colors["orange"].oklch
    colors["brown"] = Color.from_oklch(oL - 0.12 if dark else oL - 0.08, oC * 0.85, oh)
    roles["brown"] = "derived"
    for slot in ANSI_ORDER:
        colors[f"bright_{slot}"] = colors[slot].adjust(dl=0.07 if dark else -0.05, chroma_scale=1.05)
        roles[f"bright_{slot}"] = "derived"
    for key in TEXT_ON_BACKGROUND:
        if key not in base_keys:
            enforce(key, ["background"])
    if failures:
        raise ContrastError(failures)

    # Selection: an accent-tinted surface that keeps bright_foreground readable.
    selection = background.mix(colors["accent"], 0.22)
    t = 0.22
    while contrast(colors["bright_foreground"], selection) < MIN_CONTRAST and t > 0:
        t = round(t - 0.02, 2)
        selection = background.mix(colors["accent"], max(t, 0))
    colors["selection"] = selection
    colors["cursor"] = colors["bright_foreground"]
    colors["selection_foreground"] = colors["bright_foreground"]
    colors["selection_background"] = selection
    ansi = ([colors["background"]] + [colors[s] for s in ANSI_ORDER] + [colors["foreground"], colors["muted"]]
            + [colors[f"bright_{s}"] for s in ANSI_ORDER] + [colors["bright_foreground"]])
    colors.update({f"color{i}": c for i, c in enumerate(ansi)})

    # Window borders: accent into the second most chromatic input, dim surface when inactive.
    others = sorted((c for c in chromatic if c != accent), key=lambda c: -c.oklch[1])
    second = others[0] if others else accent.adjust(dl=-0.12 if dark else 0.1)
    inactive = lighter_background.adjust(dl=sign * 0.08)
    active_border = f"rgba({colors['accent'].bare}ee) rgba({second.bare}ee) 45deg"
    inactive_border = f"rgba({inactive.bare}aa)"

    scheme = Scheme(mode, colors, active_border, inactive_border, list(inputs), roles, adjustments, notes)
    bad = [p for p in scheme.contrast_pairs() if p[2] < MIN_CONTRAST]
    if bad:  # pragma: no cover - guarded by the enforcement above
        raise AssertionError(f"internal error: pairs still failing: {bad}")
    return scheme
