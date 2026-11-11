"""Regression: a complex objective must never silently become a tasks APK."""
import unittest
from builder.generate import classify

class UnsupportedObjectiveTests(unittest.TestCase):
    def test_phonecare_with_tasks_word_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "tidak disokong"):
            classify("Bina PhoneCare untuk imbas gambar pendua dan rekod tugasan")
    def test_worker_objective_is_not_tasks_app(self):
        with self.assertRaisesRegex(ValueError, "tidak disokong"):
            classify("Merekod tugasan worker dan heartbeat automasi")
    def test_simple_tasks_still_work(self):
        self.assertEqual(classify("Bina aplikasi senarai tugasan harian"), "tasks")
    def test_simple_notes_still_work(self):
        self.assertEqual(classify("Bina aplikasi nota"), "notes")

if __name__ == "__main__":
    unittest.main()
