import unittest
from builder import registry


class RegistryAtomicTests(unittest.TestCase):
    def setUp(self):
        self.previous = dict(registry._REGISTRY)
        registry._REGISTRY.clear()

    def tearDown(self):
        registry._REGISTRY.clear()
        registry._REGISTRY.update(self.previous)

    def test_rejects_partial_registration(self):
        with self.assertRaises(ValueError):
            registry.register_templates({"valid": (r"valid", "Valid"), "invalid": ("(", "Invalid")})
        self.assertEqual(registry.available_templates(), ())

    def test_rejects_malformed_spec(self):
        with self.assertRaises(ValueError):
            registry.register_templates({"invalid": (r"abc",)})
        self.assertEqual(registry.available_templates(), ())

    def test_registers_new_family(self):
        registry.register_templates({"new_family": (r"\bnew\b", "New")})
        self.assertEqual(registry.resolve_template("new"), "new_family")


if __name__ == "__main__":
    unittest.main()
