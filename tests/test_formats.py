"""Classification des formats de photo et géométrie des formats de sortie."""
import unittest
from pathlib import Path

from rkarrousel import formats, outputs as produce


class RatioDetectionTests(unittest.TestCase):
    def test_detects_supported_ratios(self):
        self.assertEqual(formats.detect_ratio_type(1200, 1600), "portrait_3_4")
        self.assertEqual(formats.detect_ratio_type(1200, 1800), "portrait_2_3")
        self.assertEqual(formats.detect_ratio_type(1800, 1200), "landscape_2_3")

    def test_every_other_format_is_classified(self):
        table = {
            (1000, 1000): "square", (1250, 1000): "square", (800, 1000): "portrait_other",  # 4:5
            (900, 1600): "portrait_other", (1200, 900): "landscape_other",                   # 9:16, 4:3
            (1600, 900): "landscape_other", (3000, 1000): "landscape_other",                 # 16:9, 3:1
        }
        for size, expected in table.items():
            self.assertEqual(formats.detect_ratio_type(*size), expected, size)
        self.assertIsNone(formats.detect_ratio_type(0, 100))

    def test_legacy_formats_keep_their_tolerance(self):
        self.assertEqual(formats.detect_ratio_type(1200, 1590), "portrait_3_4")
        self.assertEqual(formats.detect_ratio_type(1000, 1500), "portrait_2_3")
        self.assertEqual(formats.detect_ratio_type(1500, 1000), "landscape_2_3")

    def test_kinds_per_ratio(self):
        self.assertEqual(produce.kinds_for_ratio("portrait_3_4", {}), ["framed"])
        self.assertEqual(produce.kinds_for_ratio("portrait_2_3", {}), ["framed", "crop34"])
        self.assertEqual(produce.kinds_for_ratio("portrait_2_3", {"signature_path": "s.png"}), ["with_sig", "crop34"])
        self.assertEqual(produce.kinds_for_ratio("portrait_2_3", {"disabled_kinds": ["crop34"]}), ["framed"])
        self.assertEqual(len(produce.kinds_for_ratio("landscape_2_3", {})), 4)
        self.assertEqual(produce.kinds_for_ratio(None, {}), [])


if __name__ == "__main__":
    unittest.main()
