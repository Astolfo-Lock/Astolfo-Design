import unittest

from PyQt6.QtCore import QSizeF

from app import label_size_mm, mm_to_pixels, sizes_match


class PhysicalUnitsTests(unittest.TestCase):
    def test_mm_to_pixels_rounds_only_the_result(self):
        self.assertEqual(mm_to_pixels(80, 203), 639)
        self.assertEqual(mm_to_pixels(75, 203), 599)
        self.assertEqual(mm_to_pixels(80, 300), 945)
        self.assertEqual(mm_to_pixels(75, 600), 1772)

    def test_version_2_label_uses_millimeters(self):
        self.assertEqual(
            label_size_mm({"width_mm": 80, "height_mm": 75}),
            (80.0, 75.0),
        )

    def test_version_1_label_remains_compatible(self):
        self.assertEqual(
            label_size_mm({"width_cm": 8, "height_cm": 7.5}),
            (80.0, 75.0),
        )

    def test_driver_size_comparison_has_small_tolerance(self):
        self.assertTrue(sizes_match(QSizeF(80, 75), QSizeF(80.2, 74.8)))
        self.assertFalse(sizes_match(QSizeF(80, 75), QSizeF(75, 80)))


if __name__ == "__main__":
    unittest.main()
