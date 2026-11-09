import tempfile
import unittest
from pathlib import Path
from builder import registry
from builder.generate import generate


class UnimplementedFamilyTests(unittest.TestCase):
    def test_registered_family_needs_real_generator(self):
        before = dict(registry._REGISTRY)
        try:
            registry.register_templates({"phonecare": (r"phonecare", "PhoneCare")})
            with tempfile.TemporaryDirectory() as tmp:
                target = Path(tmp) / "app"
                with self.assertRaisesRegex(ValueError, "penjana Android"):
                    generate("phonecare", "PhoneCare NM", target)
                self.assertFalse(target.exists())
        finally:
            registry._REGISTRY.clear()
            registry._REGISTRY.update(before)


if __name__ == "__main__":
    unittest.main()
