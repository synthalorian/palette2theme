import tempfile
import unittest

from palette2theme import plasma
from palette2theme.derive import derive_scheme
from tests.test_derive import EMBER


class PlasmaStubTests(unittest.TestCase):
    def test_stub_raises_not_implemented_with_todo(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(NotImplementedError) as cm:
                plasma.write_plasma_scheme(derive_scheme(EMBER), "X", d)
        self.assertIn("TODO", str(cm.exception))

    def test_stub_is_clearly_marked(self):
        self.assertIn("STUB, NOT IMPLEMENTED YET", plasma.__doc__)
        self.assertIn("TODO(plasma)", plasma.__doc__)


if __name__ == "__main__":
    unittest.main()
