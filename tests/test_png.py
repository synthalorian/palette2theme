import unittest

from palette2theme.color import Color
from palette2theme.derive import derive_scheme
from palette2theme.png import encode_png, fill_rect, render_preview, render_wallpaper
from tests.helpers import decode_png
from tests.test_derive import EMBER


class PngTests(unittest.TestCase):
    def test_round_trip(self):
        rows = [bytes([10, 20, 30, 40, 50, 60]), bytes([70, 80, 90, 100, 110, 120])]
        w, h, back = decode_png(encode_png(2, 2, rows))
        self.assertEqual((w, h), (2, 2))
        self.assertEqual([bytes(r) for r in back], rows)

    def test_rejects_bad_dimensions(self):
        with self.assertRaises(ValueError):
            encode_png(0, 1, [])
        with self.assertRaises(ValueError):
            encode_png(2, 1, [b"\x00" * 3])

    def test_wallpaper_is_tinted_and_deterministic(self):
        bg, glow = Color.from_hex("#191d22"), Color.from_hex("#f28c38")
        a = render_wallpaper(96, 54, Color.from_hex("#0e1013"), bg, glow, Color.from_hex("#7f9fc0"), True, "s")
        b = render_wallpaper(96, 54, Color.from_hex("#0e1013"), bg, glow, Color.from_hex("#7f9fc0"), True, "s")
        c = render_wallpaper(96, 54, Color.from_hex("#0e1013"), bg, glow, Color.from_hex("#7f9fc0"), True, "t")
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)
        # The bottom-right glow pulls pixels towards the (orange) accent: red > blue there.
        row = a[46]
        r, g, bl = row[80 * 3], row[80 * 3 + 1], row[80 * 3 + 2]
        self.assertGreater(r, bl)
        # Stays dark overall for a dark theme.
        mean = sum(sum(r) for r in a) / (96 * 54 * 3)
        self.assertLess(mean, 90)
        w, h, _ = decode_png(encode_png(96, 54, a))
        self.assertEqual((w, h), (96, 54))

    def test_fill_rect_clips(self):
        rows = [bytearray(4 * 3) for _ in range(3)]
        fill_rect(rows, -5, -5, 2, 2, Color(1, 2, 3))
        self.assertEqual(bytes(rows[0][:6]), bytes([1, 2, 3, 1, 2, 3]))
        self.assertEqual(bytes(rows[2]), bytes(12))

    def test_preview_contains_palette_colours(self):
        s = derive_scheme(EMBER)
        rows = render_preview(s, 320, 180, "x")
        pixels = {bytes(r[i:i + 3]) for r in rows for i in range(0, len(r), 3)}
        for key in ("accent", "background", "red", "bright_cyan"):
            c = s[key]
            self.assertIn(bytes((c.r, c.g, c.b)), pixels, key)


if __name__ == "__main__":
    unittest.main()
