"""The API documentation must describe exactly the routes the code serves."""
import sys
import unittest
from pathlib import Path

from studysync import create_app

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "docs"))
import spec  # noqa: E402


class DocsMatchCodeTests(unittest.TestCase):
    def test_every_route_is_documented_and_every_documented_route_exists(self):
        import tempfile, os
        app = create_app({"ENV": "testing", "DATABASE": os.path.join(tempfile.mkdtemp(), "d.db")})
        served = {(m, r.rule) for r in app.url_map.iter_rules() if r.rule.startswith("/api") for m in r.methods - {"HEAD", "OPTIONS"}}
        documented = {(e[0], spec.flask_path(e[1])) for e in spec.ENDPOINTS}
        self.assertEqual(served - documented, set(), "routes missing from docs/spec.py")
        self.assertEqual(documented - served, set(), "documented routes that do not exist")

    def test_documented_error_codes_have_descriptions(self):
        for e in spec.ENDPOINTS:
            for code in e[9]:
                self.assertIn(code, spec.ERROR_TEXT)
