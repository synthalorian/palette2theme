import contextlib
import datetime
import io
import os
import random
import shutil
import subprocess
import tempfile
import tomllib
import unittest
from unittest import mock
from pathlib import Path

from palette2theme.cli import EXIT_CONTRAST, EXIT_NOT_IMPLEMENTED, EXIT_USAGE, main
from palette2theme.color import BLACK, WHITE, Color, contrast
from palette2theme.derive import MIN_CONTRAST, REQUIRED_KEYS, derive_scheme
from palette2theme.omarchy import DATA_DIR, OutputError, render_shell_lock, slugify
from tests.helpers import REPO, decode_png

# Light palette whose placeholder (dark_foreground) is only 4.40:1 on the opaque lock card.
LOCK_LIGHT = ["#e58e03", "#51d8ae", "#8e4f6e", "#ac342f", "#c231b7", "#b08716"]
EMBER = ["#191d22", "#d4cfc8", "#f28c38", "#fb5668", "#7f9fc0", "#afcd8b"]
SMALL = ["--wallpaper-size", "64x36", "--preview-size", "64x36"]
# Optional folder of hand-made reference themes (steel-and-ember, ...). Tests that need it skip
# when it isn't there. Override with PALETTE2THEME_REFERENCE_THEMES.
REFERENCE = Path(os.environ.get("PALETTE2THEME_REFERENCE_THEMES", "/workspace/glyphsmith/themes"))
EXPECTED_FILES = {
    "colors.toml", "btop.theme", "icons.theme", "shell.lock.toml", "VERSION", "README.md",
    "CHANGELOG.md", "LICENSE", "install.sh", "uninstall.sh", "preview.png",
}
# Omarchy 4 removed or ignores these (see templates/OMARCHY-THEME-SPEC.md), so we must not ship them.
NOT_SHIPPED = {"waybar.css", "mako.ini", "walker.css", "swayosd.css", "hyprland.conf", "hyprlock.conf",
               "alacritty.toml", "kitty.conf", "ghostty.conf", "foot.ini", "light.mode"}


def run_cli(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            rc = main(list(argv))
        except SystemExit as e:  # argparse
            rc = e.code
    return rc, out.getvalue(), err.getvalue()


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def build(self, *extra, name="Test Ember", colors=EMBER):
        out = self.dir / slugify(name)
        rc, _, err = run_cli(*colors, "--name", name, "--out", str(out), *SMALL, *extra)
        self.assertEqual(rc, 0, err)
        return out

    def test_full_theme_layout(self):
        out = self.build()
        files = {str(p.relative_to(out)) for p in out.rglob("*") if p.is_file()}
        self.assertEqual(files, EXPECTED_FILES | {"backgrounds/1-test-ember.png"})
        self.assertFalse(files & NOT_SHIPPED)
        self.assertEqual((out / "VERSION").read_text(), "0.1.0\n")
        self.assertEqual(oct(out.stat().st_mode & 0o777), "0o755")
        self.assertFalse(list(self.dir.glob(".test-ember.*")), "temp build dir left behind")

    def test_colors_toml_complete_and_readable(self):
        out = self.build()
        data = tomllib.loads((out / "colors.toml").read_text())
        self.assertEqual(set(data), set(REQUIRED_KEYS))
        self.assertEqual(data["mode"], "dark")
        cols = {k: Color.from_hex(v) for k, v in data.items() if isinstance(v, str) and v.startswith("#")}
        for k in ["foreground", "dark_foreground", "muted", "accent", "red", "green", "yellow", "blue",
                  "magenta", "cyan", "orange", "brown"] + [f"color{i}" for i in range(1, 16)]:
            self.assertGreaterEqual(contrast(cols[k], cols["background"]), MIN_CONTRAST, k)
        self.assertEqual(data["color0"], data["background"])

    def test_matches_reference_theme_keys(self):
        ref = REFERENCE / "steel-and-ember" / "colors.toml"
        if not ref.exists():
            self.skipTest("reference theme not available")
        out = self.build()
        ours = tomllib.loads((out / "colors.toml").read_text())
        self.assertEqual(set(ours), set(tomllib.loads(ref.read_text())))
        ref_lock = tomllib.loads((REFERENCE / "steel-and-ember" / "shell.lock.toml").read_text())
        self.assertEqual(set(tomllib.loads((out / "shell.lock.toml").read_text())), set(ref_lock))

    def test_btop_and_icons(self):
        out = self.build()
        btop = (out / "btop.theme").read_text()
        self.assertIn('theme[main_bg]="#191d22"', btop)
        self.assertEqual(btop.count("theme[gradient_color_"), 8)
        ref = REFERENCE / "steel-and-ember" / "btop.theme"
        if ref.exists():
            import re
            keys = lambda t: set(re.findall(r"theme\[(\w+)\]", t))
            self.assertEqual(keys(btop), keys(ref.read_text()))
        self.assertRegex((out / "icons.theme").read_text(), r"^Yaru(-[a-z]+)?\n$")

    def test_lock_screen_text_readable_over_any_wallpaper(self):
        out = self.build()
        lock = tomllib.loads((out / "shell.lock.toml").read_text())
        card = Color.from_hex(lock["background"])
        for wall in (Color(255, 255, 255), Color(0, 0, 0)):
            comp = card.over(wall, lock["background-alpha"])
            for key in ("text", "placeholder", "text-error"):
                self.assertGreaterEqual(contrast(Color.from_hex(lock[key]), comp), MIN_CONTRAST, key)

    def assert_lock_readable(self, lock_text):
        lock = tomllib.loads(lock_text)
        card = Color.from_hex(lock["background"])
        accent = Color.from_hex(lock["selection"])
        text = Color.from_hex(lock["text"])
        for wall in (WHITE, BLACK):
            comp = card.over(wall, lock["background-alpha"])
            for key in ("text", "placeholder", "text-error"):
                self.assertGreaterEqual(contrast(Color.from_hex(lock[key]), comp), MIN_CONTRAST, key)
            self.assertGreaterEqual(contrast(text, accent.over(comp, lock["selection-alpha"])), MIN_CONTRAST,
                                    "text on selection")

    def test_lock_screen_light_theme_fallback(self):
        out = self.build(colors=LOCK_LIGHT, name="Lock Light")
        self.assertEqual(tomllib.loads((out / "colors.toml").read_text())["mode"], "light")
        self.assert_lock_readable((out / "shell.lock.toml").read_text())

    def test_lock_screen_fuzz_both_modes(self):
        rng = random.Random(4321)
        for i in range(200):
            colors = [Color(rng.randrange(256), rng.randrange(256), rng.randrange(256))
                      for _ in range(rng.randint(2, 9))]
            mode = ("dark", "light")[i % 2]
            with self.subTest(i=i, colors=[c.hex for c in colors], mode=mode):
                self.assert_lock_readable(render_shell_lock(derive_scheme(colors, mode=mode)))

    def test_pngs_valid(self):
        out = self.build()
        for rel in ("backgrounds/1-test-ember.png", "preview.png"):
            w, h, _ = decode_png((out / rel).read_bytes())
            self.assertEqual((w, h), (64, 36))

    def test_scripts_are_mesa_copies(self):
        out = self.build()
        for name in ("install.sh", "uninstall.sh"):
            ours = (out / name).read_text().splitlines()
            bundled = (DATA_DIR / name).read_text().splitlines()
            self.assertTrue(os.access(out / name, os.X_OK))
            self.assertTrue(ours[1].startswith("# Test Ember theme "), ours[1])
            self.assertEqual(ours[:1] + ours[2:], bundled[:1] + bundled[2:])
            subprocess.run(["bash", "-n", str(out / name)], check=True)

    @unittest.skipUnless(shutil.which("bash") and shutil.which("sha256sum"), "needs bash + coreutils")
    def test_install_uninstall_round_trip_in_sandbox_home(self):
        out = self.build()
        home = self.dir / "home"
        home.mkdir()
        env = {"HOME": str(home), "PATH": os.environ.get("PATH", "/usr/bin:/bin")}
        r = subprocess.run(["bash", str(out / "install.sh"), "--dry-run"], env=env,
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(list(home.iterdir()), [], "dry-run wrote files")
        r = subprocess.run(["bash", str(out / "install.sh")], env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        dest = home / ".config/omarchy/themes/test-ember"
        self.assertTrue((dest / "colors.toml").is_file())
        self.assertTrue((dest / "backgrounds/1-test-ember.png").is_file())
        self.assertFalse((dest / "install.sh").exists())
        r = subprocess.run(["bash", str(out / "uninstall.sh")], env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(list(home.iterdir()), [], "uninstall left files behind")

    def test_unbranded_by_default(self):
        env = {k: v for k, v in os.environ.items() if k != "PALETTE2THEME_BRAND"}
        with mock.patch.dict(os.environ, env, clear=True):
            out = self.build()
        for p in out.rglob("*"):
            if p.is_file() and p.suffix != ".png":
                self.assertNotIn("glyphsmith", p.read_text().lower().replace(".glyphsmith-install.manifest", "")
                                 .replace("glyphsmith_fallback_theme", ""), p.name)
        self.assertTrue((out / "colors.toml").read_text().startswith("# Test Ember — Omarchy theme\n"))
        self.assertTrue((out / "btop.theme").read_text().startswith("# Test Ember for btop (generated by palette2theme)\n"))

    def test_brand_flag_and_env(self):
        out = self.build("--brand", "Acme")
        self.assertTrue((out / "colors.toml").read_text().startswith("# Test Ember — Omarchy theme by Acme\n"))
        self.assertIn("# Test Ember for btop — by Acme (generated", (out / "btop.theme").read_text())
        self.assertTrue((out / "install.sh").read_text().splitlines()[1].startswith("# Test Ember (Acme) theme installer"))
        with mock.patch.dict(os.environ, {"PALETTE2THEME_BRAND": "Envco"}):
            out = self.build("--force")
        self.assertIn("by Envco", (out / "colors.toml").read_text())
        out = self.build("--force", "--brand", "Bad\nkey = 1")  # no header injection
        self.assertTrue((out / "colors.toml").read_text().startswith("# Test Ember — Omarchy theme by Bad key = 1\n"))

    @unittest.skipUnless(shutil.which("bash") and shutil.which("sha256sum"), "needs bash + coreutils")
    def test_uninstall_reads_old_manifest_name_and_fallback_alias(self):
        out = self.build()
        home = self.dir / "home"
        (home / ".local/state/omarchy/current").mkdir(parents=True)
        env = {"HOME": str(home), "PATH": "/usr/bin:/bin"}
        r = subprocess.run(["bash", str(out / "install.sh")], env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        dest = home / ".config/omarchy/themes/test-ember"
        self.assertTrue((dest / ".theme-install.manifest").is_file())
        (dest / ".theme-install.manifest").rename(dest / ".glyphsmith-install.manifest")  # an older install
        r = subprocess.run(["bash", str(out / "install.sh")], env=env, capture_output=True, text=True, timeout=60)
        self.assertNotEqual(r.returncode, 0, "install must see the old manifest as an existing install")
        r = subprocess.run(["bash", str(out / "install.sh"), "--force"], env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((dest / ".theme-install.manifest").is_file())
        self.assertFalse((dest / ".glyphsmith-install.manifest").exists())
        (dest / ".theme-install.manifest").rename(dest / ".glyphsmith-install.manifest")
        r = subprocess.run(["bash", str(out / "uninstall.sh"), "--no-switch"], env=env,
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(dest.exists())
        for var in ("THEME_FALLBACK", "GLYPHSMITH_FALLBACK_THEME"):
            r = subprocess.run(["bash", "-c", 'source <(sed -n "/^DRY_RUN=0/p" "$1"); echo "$FALLBACK"', "_",
                                str(out / "uninstall.sh")], env={**env, var: "my-fallback"},
                               capture_output=True, text=True, timeout=60)
            self.assertEqual(r.stdout.strip(), "my-fallback", var)

    def test_palette_file_and_positional_merge(self):
        out = self.dir / "t"
        rc, _, err = run_cli("--palette", str(REPO / "examples" / "tidepool.toml"), "#ffcc00",
                             "--name", "Tide", "--out", str(out), *SMALL)
        self.assertEqual(rc, 0, err)
        self.assertIn("`#ffcc00`", (out / "README.md").read_text())
        self.assertIn("tidepool.toml", (out / "CHANGELOG.md").read_text())

    def test_every_example_builds(self):
        for p in sorted((REPO / "examples").iterdir()):
            with self.subTest(p.name):
                out = self.dir / p.stem
                rc, _, err = run_cli("--palette", str(p), "--name", p.stem, "--out", str(out), *SMALL, "-q")
                self.assertEqual(rc, 0, err)
                self.assertEqual(err, "")

    def test_light_mode(self):
        out = self.dir / "paper"
        rc, _, err = run_cli("--palette", str(REPO / "examples" / "parchment.txt"),
                             "--name", "Paper", "--out", str(out), *SMALL)
        self.assertEqual(rc, 0, err)
        self.assertEqual(tomllib.loads((out / "colors.toml").read_text())["mode"], "light")

    def test_adjustments_reported_and_logged(self):
        out = self.dir / "dim"
        rc, _, err = run_cli("#101010", "#e0e0e0", "#602020", "#204060", "#305030", "#a06020",
                             "--name", "Dim", "--out", str(out), *SMALL)
        self.assertEqual(rc, 0)
        self.assertIn("contrast: red: #602020 ->", err)
        self.assertIn("Contrast: colours moved", (out / "CHANGELOG.md").read_text())

    def test_strict_fails_and_writes_nothing(self):
        out = self.dir / "dim"
        rc, _, err = run_cli("#101010", "#e0e0e0", "#602020", "#204060", "#305030", "#a06020",
                             "--name", "Dim", "--out", str(out), "--strict", *SMALL)
        self.assertEqual(rc, EXIT_CONTRAST)
        self.assertIn("contrast check failed", err)
        self.assertFalse(out.exists())

    def test_plasma_target_not_implemented(self):
        out = self.dir / "plasma"
        rc, _, err = run_cli(*EMBER, "--name", "P", "--out", str(out), "--target", "plasma")
        self.assertEqual(rc, EXIT_NOT_IMPLEMENTED)
        self.assertIn("not implemented", err)
        self.assertIn("TODO", err)
        self.assertFalse(out.exists())

    def test_refuses_non_empty_out_without_force(self):
        out = self.build()
        (out / "colors.toml").write_text("edited")
        (out / "mine.txt").write_text("keep me")
        rc, _, err = run_cli(*EMBER, "--name", "Test Ember", "--out", str(out), *SMALL)
        self.assertEqual(rc, EXIT_USAGE)
        self.assertIn("--force", err)
        self.assertEqual((out / "colors.toml").read_text(), "edited")
        rc, _, err = run_cli(*EMBER, "--name", "Test Ember", "--out", str(out), "--force", *SMALL)
        self.assertEqual(rc, 0, err)
        self.assertNotEqual((out / "colors.toml").read_text(), "edited")
        self.assertEqual((out / "mine.txt").read_text(), "keep me")

    def test_refuses_symlinked_out(self):
        real = self.dir / "real"
        real.mkdir()
        link = self.dir / "link"
        link.symlink_to(real)
        rc, _, err = run_cli(*EMBER, "--name", "L", "--out", str(link), *SMALL)
        self.assertEqual(rc, EXIT_USAGE)
        self.assertIn("symlink", err)

    def test_force_refuses_symlinked_generated_file(self):
        out = self.build()
        victim = self.dir / "victim.txt"
        victim.write_text("outside")
        (out / "colors.toml").unlink()
        (out / "colors.toml").symlink_to(victim)
        before = (out / "btop.theme").read_text()
        rc, _, err = run_cli(*EMBER, "--name", "Test Ember", "--out", str(out), "--force", "--accent", "#7f9fc0", *SMALL)
        self.assertEqual(rc, EXIT_USAGE)
        self.assertIn("symlink", err)
        self.assertEqual(victim.read_text(), "outside")
        self.assertEqual((out / "btop.theme").read_text(), before, "wrote files before refusing")

    def test_force_replaces_hard_link_instead_of_writing_through(self):
        out = self.build()
        victim = self.dir / "victim.txt"
        victim.write_text("outside")
        victim.chmod(0o600)
        (out / "colors.toml").unlink()
        os.link(victim, out / "colors.toml")
        rc, _, err = run_cli(*EMBER, "--name", "Test Ember", "--out", str(out), "--force", *SMALL)
        self.assertEqual(rc, 0, err)
        self.assertEqual(victim.read_text(), "outside")
        self.assertEqual(victim.stat().st_mode & 0o777, 0o600)
        self.assertNotEqual((out / "colors.toml").read_text(), "outside")
        self.assertEqual([p.name for p in out.rglob(".*p2t-tmp*")], [])

    def test_force_refuses_symlinked_backgrounds(self):
        out = self.build()
        elsewhere = self.dir / "elsewhere"
        elsewhere.mkdir()
        shutil.rmtree(out / "backgrounds")
        (out / "backgrounds").symlink_to(elsewhere)
        rc, _, err = run_cli(*EMBER, "--name", "Test Ember", "--out", str(out), "--force", *SMALL)
        self.assertEqual(rc, EXIT_USAGE)
        self.assertIn("symlink", err)
        self.assertEqual(list(elsewhere.iterdir()), [])

    def test_multiline_metadata_stays_in_comments(self):
        out = self.build("--description", 'first\nmode = "light"\r\naccent = "#000000"',
                         name='Two\nmode = "light"')
        text = (out / "colors.toml").read_text()
        data = tomllib.loads(text)
        self.assertEqual(data["mode"], "dark")
        self.assertEqual([l for l in text.splitlines() if l.startswith("mode")], ['mode = "dark"'])
        self.assertNotEqual(data["accent"], "#000000")
        self.assertIn('# first mode = "light" accent = "#000000"', text)
        self.assertEqual((out / "README.md").read_text().splitlines()[0], '# Two mode = "light"')
        self.assertNotIn("\nmode", (out / "btop.theme").read_text())

    def test_author_is_literal_in_license(self):
        for author in ("ACME\\q", r"Bob \1 \g<0> \\ Ltd"):
            with self.subTest(author=author):
                out = self.build("--author", author, "--force", name="Lic")
                self.assertIn(f"Copyright (c) 2026 {author}\n", (out / "LICENSE").read_text())

    def test_output_is_reproducible_with_date(self):
        a = self.build("--date", "2026-03-04", name="Same")
        b = self.dir / "copy"
        rc, _, err = run_cli(*EMBER, "--name", "Same", "--out", str(b), "--date", "2026-03-04", *SMALL)
        self.assertEqual(rc, 0, err)
        files = sorted(str(p.relative_to(a)) for p in a.rglob("*") if p.is_file())
        self.assertEqual(files, sorted(str(p.relative_to(b)) for p in b.rglob("*") if p.is_file()))
        for f in files:
            self.assertEqual((a / f).read_bytes(), (b / f).read_bytes(), f)
        self.assertIn("## [0.1.0] - 2026-03-04", (a / "CHANGELOG.md").read_text())
        today = self.build(name="Today")
        self.assertIn(f"- {datetime.date.today().isoformat()}\n", (today / "CHANGELOG.md").read_text())
        rc, _, err = run_cli(*EMBER, "--name", "X", "--date", "2026-13-01")
        self.assertEqual(rc, EXIT_USAGE)
        self.assertIn("YYYY-MM-DD", err)

    def test_usage_errors(self):
        cases = [
            (["--name", "X", "--out", str(self.dir / "a")], "no colours"),
            (["#fff", "--name", "X", "--out", str(self.dir / "b")], "at least 2"),
            (["#fff", "#zzz", "--name", "X", "--out", str(self.dir / "c")], "not a hex"),
            (EMBER + ["--name", "!!!", "--out", str(self.dir / "d")], "--slug"),
            (["#000"] * 17 + ["--name", "X", "--out", str(self.dir / "e")], "at most 16"),
        ]
        for argv, needle in cases:
            with self.subTest(needle):
                rc, _, err = run_cli(*argv)
                self.assertEqual(rc, EXIT_USAGE)
                self.assertIn(needle, err)
        rc, _, _ = run_cli(*EMBER, "--name", "X", "--wallpaper-size", "huge")
        self.assertEqual(rc, 2)

    def test_slugify(self):
        self.assertEqual(slugify("Steel & Ember"), "steel-and-ember")
        self.assertEqual(slugify("omarchy-Glyph-theme"), "glyph")
        self.assertEqual(slugify("  Neon   Horizon 2 "), "neon-horizon-2")
        with self.assertRaises(OutputError):
            slugify("***")

    def test_no_assistant_credit_in_output(self):
        out = self.build()
        for p in out.rglob("*"):
            if p.is_file() and p.suffix not in (".png",):
                text = p.read_text().lower()
                for bad in ("co-authored-by", "generated by ai"):
                    self.assertNotIn(bad, text, f"{bad!r} in {p.name}")
        self.assertIn("Copyright (c) 2026 synthalorian", (out / "LICENSE").read_text())

    def test_module_entry_point(self):
        r = subprocess.run([os.environ.get("PYTHON", "python3"), "-m", "palette2theme", "--version"],
                           cwd=REPO, capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("palette2theme 0.1.0", r.stdout)


if __name__ == "__main__":
    unittest.main()
