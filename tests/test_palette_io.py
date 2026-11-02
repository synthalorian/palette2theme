import tempfile
import unittest
from pathlib import Path

from palette2theme.color import Color
from palette2theme.palette_io import PaletteError, parse_colors, read_palette_file
from tests.helpers import REPO

EXPECTED = ["#191d22", "#d4cfc8", "#f28c38", "#fb5668", "#7f9fc0", "#afcd8b"]


class PaletteFileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, text):
        p = self.dir / name
        p.write_text(text)
        return p

    def hexes(self, path):
        return [c.hex for c in read_palette_file(path)]

    def test_json_shapes(self):
        self.assertEqual(self.hexes(self.write("a.json", '["#191d22","#d4cfc8"]')), EXPECTED[:2])
        self.assertEqual(self.hexes(self.write("b.json", '{"colors":["#191d22","d4cfc8"]}')), EXPECTED[:2])
        self.assertEqual(self.hexes(self.write("c.json", '{"palette":{"bg":"#191d22","fg":"#d4cfc8","n":3}}')),
                         EXPECTED[:2])
        # Content sniffing without an extension.
        self.assertEqual(self.hexes(self.write("noext", '["#191d22"]')), EXPECTED[:1])

    def test_toml_shapes(self):
        self.assertEqual(self.hexes(self.write("a.toml", 'colors = ["#191d22", "#d4cfc8"]\n')), EXPECTED[:2])
        self.assertEqual(self.hexes(self.write("b.toml", '[palette]\nbg = "#191d22"\nfg = "#d4cfc8"\n')),
                         EXPECTED[:2])
        self.assertEqual(self.hexes(self.write("c.toml", 'bg = "#191d22"\nfg = "#d4cfc8"\nmode = "dark"\n')),
                         EXPECTED[:2])

    def test_line_format(self):
        text = "# my palette\n\n#191d22  # bg\nd4cfc8\n#F28C38, // ember\n; note\n"
        self.assertEqual(self.hexes(self.write("p.txt", text)), EXPECTED[:3])

    def test_errors(self):
        with self.assertRaisesRegex(PaletteError, "invalid JSON"):
            read_palette_file(self.write("bad.json", "[oops"))
        with self.assertRaisesRegex(PaletteError, "invalid TOML"):
            read_palette_file(self.write("bad.toml", "colors = [\n"))
        with self.assertRaisesRegex(PaletteError, r"p\.txt:2"):
            read_palette_file(self.write("p.txt", "#191d22\nnot-a-colour\n"))
        with self.assertRaisesRegex(PaletteError, "no colours"):
            read_palette_file(self.write("empty.txt", "# nothing\n"))
        with self.assertRaisesRegex(PaletteError, "not a hex colour"):
            read_palette_file(self.write("x.json", '["#191d22", "#zzzzzz"]'))
        with self.assertRaisesRegex(PaletteError, "cannot read"):
            read_palette_file(self.dir / "missing.json")

    def test_parse_colors(self):
        self.assertEqual(parse_colors(["#fff", "000000"]), [Color(255, 255, 255), Color(0, 0, 0)])
        with self.assertRaises(PaletteError):
            parse_colors(["#fff", "nope"])

    def test_bundled_examples_parse(self):
        for p in sorted((REPO / "examples").iterdir()):
            with self.subTest(p.name):
                self.assertEqual(len(read_palette_file(p)), 6)


if __name__ == "__main__":
    unittest.main()
