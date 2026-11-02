import unittest

from palette2theme.color import BLACK, WHITE, Color, ColorError, contrast, hue_distance, push_to_contrast


class ColorTests(unittest.TestCase):
    def test_hex_parsing(self):
        self.assertEqual(Color.from_hex("#ff8000"), Color(255, 128, 0))
        self.assertEqual(Color.from_hex("FF8000"), Color(255, 128, 0))
        self.assertEqual(Color.from_hex("#f80"), Color(255, 136, 0))
        self.assertEqual(Color.from_hex(" #abcdef ").hex, "#abcdef")
        for bad in ("", "#12", "#12345", "#gggggg", "red", "#1234567"):
            with self.assertRaises(ColorError, msg=bad):
                Color.from_hex(bad)

    def test_wcag_contrast_reference_values(self):
        self.assertAlmostEqual(contrast(BLACK, WHITE), 21.0, places=6)
        self.assertAlmostEqual(contrast(WHITE, WHITE), 1.0, places=6)
        # Known WCAG value: #767676 on white is 4.54:1.
        self.assertAlmostEqual(contrast(Color.from_hex("#767676"), WHITE), 4.54, places=2)
        self.assertEqual(contrast(Color.from_hex("#123456"), WHITE), contrast(WHITE, Color.from_hex("#123456")))

    def test_oklch_round_trip(self):
        for h in ("#191d22", "#f28c38", "#7f9fc0", "#ffffff", "#000000", "#00ff00", "#721d18"):
            c = Color.from_hex(h)
            back = Color.from_oklch(*c.oklch)
            for a, b in zip((c.r, c.g, c.b), (back.r, back.g, back.b)):
                self.assertLessEqual(abs(a - b), 1, h)

    def test_oklab_reference(self):
        L, a, b = WHITE.oklab
        self.assertAlmostEqual(L, 1.0, places=3)
        self.assertAlmostEqual(a, 0.0, places=3)
        self.assertAlmostEqual(b, 0.0, places=3)

    def test_out_of_gamut_is_clamped_by_chroma(self):
        c = Color.from_oklch(0.9, 0.4, 260)  # far outside sRGB
        for ch in (c.r, c.g, c.b):
            self.assertTrue(0 <= ch <= 255)
        self.assertAlmostEqual(c.oklch[0], 0.9, delta=0.02)

    def test_hue_distance_wraps(self):
        self.assertEqual(hue_distance(350, 10), 20)
        self.assertEqual(hue_distance(10, 350), 20)
        self.assertEqual(hue_distance(0, 180), 180)

    def test_push_to_contrast(self):
        bg = Color.from_hex("#191d22")
        dim = Color.from_hex("#5a3030")
        fixed = push_to_contrast(dim, [bg], 4.5, prefer_lighter=True)
        self.assertGreaterEqual(contrast(fixed, bg), 4.5)
        self.assertGreater(fixed.oklch[0], dim.oklch[0])
        self.assertAlmostEqual(fixed.oklch[2], dim.oklch[2], delta=6)  # hue kept
        # Already fine: returned unchanged.
        self.assertIs(push_to_contrast(WHITE, [bg], 4.5, True), WHITE)
        # Impossible: 21:1 against mid grey.
        self.assertIsNone(push_to_contrast(dim, [Color.from_hex("#777777")], 21, True))

    def test_mix_and_over(self):
        self.assertEqual(BLACK.mix(WHITE, 0), BLACK)
        self.assertEqual(BLACK.mix(WHITE, 1), WHITE)
        self.assertEqual(WHITE.over(BLACK, 0.5), Color(128, 128, 128))


if __name__ == "__main__":
    unittest.main()
