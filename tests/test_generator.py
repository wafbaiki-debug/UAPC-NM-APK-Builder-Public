"""Offline unit tests for public Android APK builder (no Neon or private data)."""
import tempfile
from pathlib import Path
import unittest

from builder.generate import TEMPLATES, classify, generate
from builder.verify import verify_apk


class GeneratorTest(unittest.TestCase):
    def test_supported_families(self):
        expected = {
            "Bina aplikasi nota untuk saya": "notes",
            "Bina UAPC Controller": "controller",
            "Bina aplikasi tugasan harian": "tasks",
            "Urus inventori stok": "inventory",
            "Catat perbelanjaan bulanan": "expenses",
        }
        for objective, kind in expected.items():
            with self.subTest(objective=objective):
                self.assertEqual(classify(objective), kind)

    def test_unsupported_and_ambiguous_rejected(self):
        for objective in ("", "Bina aplikasi sesuka hati", "Aplikasi nota dan stok",
                          "x" * 181):
            with self.subTest(objective=objective[:50]):
                with self.assertRaises(ValueError):
                    classify(objective)

    def test_source_is_isolated_and_contains_no_permissions(self):
        for kind, (_, label) in TEMPLATES.items():
            with tempfile.TemporaryDirectory() as directory:
                output = Path(directory)
                result = generate(label, "", output)
                self.assertEqual(result["template"], kind)
                self.assertFalse(result["apk_built"])
                self.assertEqual(result["files"], 7)
                self.assertTrue((output / "app/build.gradle").is_file())
                manifest = (output / "app/src/main/AndroidManifest.xml").read_text()
                self.assertIn('android:exported="true"', manifest)
                self.assertNotIn("uses-permission", manifest)
                java = next(output.rglob("MainActivity.java")).read_text()
                self.assertIn("SharedPreferences", java)
                self.assertIn("Padam rekod", java)

    def test_xml_title_escaped_and_no_java_injection(self):
        with tempfile.TemporaryDirectory() as directory:
            result = generate("nota", 'Hi & <Hello> "Test"', Path(directory))
            self.assertTrue(result["package"].startswith("my.nm.publicbuilder.notes."))
            content = (Path(directory) /
                       "app/src/main/res/values/strings.xml").read_text()
            self.assertIn("&amp;", content)
            self.assertIn("&lt;Hello&gt;", content)
            java = next(Path(directory).rglob("MainActivity.java")).read_text()
            self.assertNotIn("Hello", java)

    def test_controller_objectives_and_safety(self):
        with tempfile.TemporaryDirectory() as directory:
            result = generate("UAPC Controller", "UAPC NM", Path(directory))
            self.assertEqual(result["template"], "controller")
            java = next(Path(directory).rglob("MainActivity.java")).read_text()
            self.assertIn("Daftar objektif", java)
            self.assertIn("Objektif sudah wujud", java)
            self.assertIn("Padam objektif?", java)
            self.assertIn("Objektif siap:", java)
            manifest = next(Path(directory).rglob("AndroidManifest.xml")).read_text()
            self.assertNotIn("uses-permission", manifest)

    def test_title_length(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                generate("nota", "x" * 49, Path(directory))

    def test_not_claiming_apk_from_source(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / "only-source.apk"
            with self.assertRaises(ValueError):
                verify_apk(p)


if __name__ == "__main__":
    unittest.main()
