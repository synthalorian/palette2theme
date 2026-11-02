import random
import unittest

from palette2theme.color import Color, contrast
from palette2theme.derive import (MIN_CONTRAST, REQUIRED_KEYS, SLOT_HUES, ContrastError, derive_scheme)


def pal(*hexes):
    return [Color.from_hex(h) for h in hexes]


EMBER = pal("#191d22", "#d4cfc8", "#f28c38", "#fb5668", "#7f9fc0", "#afcd8b")
PAPER = pal("#f2ead8", "#2b2420", "#721d18", "#3a6546", "#2e4a7d", "#b0802a")


class DeriveTests(unittest.TestCase):
    def assert_all_pairs_pass(self, scheme):
        for text, surface, ratio in scheme.contrast_pairs():
            self.assertGreaterEqual(ratio, MIN_CONTRAST, f"{text} on {surface}")

    def test_all_keys_present(self):
        s = derive_scheme(EMBER)
        self.assertEqual(set(s.as_toml_values()), set(REQUIRED_KEYS))
        self.assertEqual(len(REQUIRED_KEYS), len(set(REQUIRED_KEYS)))

    def test_roles_from_input(self):
        s = derive_scheme(EMBER, accent=Color.from_hex("#f28c38"))
        self.assertEqual(s.mode, "dark")
        self.assertEqual(s["background"].hex, "#191d22")
        self.assertEqual(s["foreground"].hex, "#d4cfc8")
        self.assertEqual(s["accent"].hex, "#f28c38")
        self.assertEqual(s["red"].hex, "#fb5668")
        self.assertEqual(s["orange"].hex, "#f28c38")
        self.assertEqual(s["blue"].hex, "#7f9fc0")
        self.assertEqual(s["green"].hex, "#afcd8b")
        self.assertEqual(s.roles["yellow"], "derived")
        self.assert_all_pairs_pass(s)

    def test_ansi_layout(self):
        s = derive_scheme(EMBER)
        c = s.colors
        self.assertEqual(c["color0"], c["background"])
        self.assertEqual(c["color7"], c["foreground"])
        self.assertEqual(c["color8"], c["muted"])
        self.assertEqual(c["color15"], c["bright_foreground"])
        for i, name in enumerate(["red", "green", "yellow", "blue", "magenta", "cyan"], 1):
            self.assertEqual(c[f"color{i}"], c[name])
            self.assertEqual(c[f"color{i + 8}"], c[f"bright_{name}"])
            # Bright variants are lighter than their base in dark mode.
            self.assertGreater(c[f"bright_{name}"].oklch[0], c[name].oklch[0], name)
        self.assertEqual(c["cursor"], c["bright_foreground"])
        self.assertEqual(c["selection_background"], c["selection"])

    def test_synthesised_hues_land_near_their_slot(self):
        s = derive_scheme(EMBER)
        for slot, hue in SLOT_HUES.items():
            if s.roles[slot] == "derived":
                h = s[slot].oklch[2]
                self.assertLess(min(abs(h - hue), 360 - abs(h - hue)), 20, slot)

    def test_mode_auto_and_light(self):
        self.assertEqual(derive_scheme(pal("#fafafa", "#f0e0d0", "#e8f0ff", "#202020", "#ffd0d0")).mode, "light")
        # The first colour decides, even when most of the palette is dark ink.
        self.assertEqual(derive_scheme(PAPER).mode, "light")
        self.assertEqual(derive_scheme(EMBER).mode, "dark")
        s = derive_scheme(PAPER, mode="light")
        self.assertEqual(s.mode, "light")
        self.assertGreater(s["background"].luminance, s["foreground"].luminance)
        # Light themes: panel shades step towards the foreground (darker), as in vellum.
        self.assertLess(s["dark_background"].luminance, s["background"].luminance)
        self.assertLess(s["lighter_background"].luminance, s["background"].luminance)
        self.assert_all_pairs_pass(s)

    def test_adjustment_is_recorded_and_lightness_only(self):
        dim = pal("#101010", "#e0e0e0", "#602020", "#204060", "#305030", "#a06020")
        s = derive_scheme(dim)
        self.assertTrue(s.adjustments)
        for a in s.adjustments:
            self.assertLess(a.ratio_before, MIN_CONTRAST)
            self.assertGreaterEqual(a.ratio_after, MIN_CONTRAST)
            if a.before.oklch[1] > 0.05 and a.after.oklch[1] > 0.05:
                d = abs(a.before.oklch[2] - a.after.oklch[2]) % 360
                self.assertLess(min(d, 360 - d), 12, a.key)
        self.assert_all_pairs_pass(s)

    def test_strict_fails_loudly(self):
        dim = pal("#101010", "#e0e0e0", "#602020", "#204060", "#305030", "#a06020")
        with self.assertRaises(ContrastError) as cm:
            derive_scheme(dim, strict=True)
        msg = str(cm.exception)
        self.assertIn("--strict", msg)
        self.assertIn("red #602020", msg)
        self.assertTrue(cm.exception.failures)

    def test_strict_passes_when_nothing_needs_fixing(self):
        good = pal("#191d22", "#e0dcd5", "#f2a050", "#ff7080", "#8fb0d8", "#b0d890")
        s = derive_scheme(good, mode="dark", strict=True)
        self.assertEqual(s.adjustments, [])
        self.assert_all_pairs_pass(s)

    def test_fuzz_random_palettes_always_pass(self):
        rng = random.Random(1234)
        for i in range(150):
            n = rng.randint(2, 9)
            colors = [Color(rng.randrange(256), rng.randrange(256), rng.randrange(256)) for _ in range(n)]
            mode = rng.choice(["auto", "dark", "light"])
            with self.subTest(i=i, colors=[c.hex for c in colors], mode=mode):
                s = derive_scheme(colors, mode=mode)
                self.assert_all_pairs_pass(s)
                self.assertEqual(set(s.as_toml_values()), set(REQUIRED_KEYS))

    def test_degenerate_palettes(self):
        for colors in (pal("#808080", "#808080"), pal("#000000", "#ffffff"), pal("#ff0000", "#ff0000", "#ff0000"),
                       pal("#777777", "#787878", "#797979", "#7a7a7a")):
            for mode in ("dark", "light"):
                with self.subTest(colors=colors, mode=mode):
                    self.assert_all_pairs_pass(derive_scheme(colors, mode=mode))

    def test_selection_keeps_text_readable(self):
        s = derive_scheme(EMBER)
        self.assertGreaterEqual(contrast(s["selection_foreground"], s["selection_background"]), MIN_CONTRAST)

    def test_borders_format(self):
        s = derive_scheme(EMBER)
        self.assertRegex(s.active_border, r"^rgba\([0-9a-f]{6}ee\) rgba\([0-9a-f]{6}ee\) 45deg$")
        self.assertRegex(s.inactive_border, r"^rgba\([0-9a-f]{6}aa\)$")

    def test_input_validation(self):
        with self.assertRaises(ValueError):
            derive_scheme(pal("#000000"))
        with self.assertRaises(ValueError):
            derive_scheme(EMBER, mode="sepia")

    def test_deterministic(self):
        self.assertEqual(derive_scheme(EMBER).as_toml_values(), derive_scheme(EMBER).as_toml_values())


if __name__ == "__main__":
    unittest.main()
