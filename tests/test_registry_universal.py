"""Contract tests for the generic, reviewed Android application registry."""
import unittest
from builder.generate import classify, generate
from builder.registry import available_templates, register_templates, resolve_template
from pathlib import Path
from tempfile import TemporaryDirectory


class RegistryContracts(unittest.TestCase):
    def test_existing_families_available(self):
        self.assertTrue({'tasks', 'notes', 'inventory', 'expenses'}.issubset(set(available_templates())))

    def test_supported_objectives_resolve(self):
        self.assertEqual(classify('Bina aplikasi nota'), 'notes')
        self.assertEqual(classify('Bina aplikasi inventori'), 'inventory')

    def test_unsupported_and_ambiguous_fail_closed(self):
        for objective in ('Bina aplikasi pengimbas telefon', 'Bina aplikasi nota dan inventori'):
            with self.subTest(objective=objective):
                with self.assertRaises(ValueError):
                    classify(objective)

    def test_no_arbitrary_registry_names(self):
        with self.assertRaises(ValueError):
            register_templates({'../../unsafe': (r'.*', 'unsafe')})

    def test_source_generation_still_works(self):
        with TemporaryDirectory() as tmp:
            metadata = generate('Bina aplikasi nota', 'NM Nota', Path(tmp))
            self.assertEqual(metadata['template'], 'notes')
            self.assertTrue(list(Path(tmp).rglob('MainActivity.java')))


if __name__ == '__main__':
    unittest.main()
