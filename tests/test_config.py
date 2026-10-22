"""Réglages : lecture/écriture, validation des valeurs et chemins WSL/Windows."""
import tempfile
import os
import unittest
from pathlib import Path

from rkarrousel import config as conf


class ConfigTests(unittest.TestCase):
    def test_parse_color(self):
        self.assertEqual(conf.parse_color("#ff0000"), (255, 0, 0))
        self.assertEqual(conf.parse_color("0f0"), (0, 255, 0))
        self.assertEqual(conf.parse_color("zzz"), conf.DEFAULT_BORDER_COLOR)
        self.assertEqual(conf.parse_color(None), conf.DEFAULT_BORDER_COLOR)

    def test_settings_are_clamped(self):
        self.assertEqual(conf.jpeg_quality_of({"jpeg_quality": 500}), 100)
        self.assertEqual(conf.jpeg_quality_of({"jpeg_quality": "abc"}), conf.DEFAULT_JPEG_QUALITY)
        self.assertEqual(conf.signature_position_of({"signature_position": "nowhere"}), "bottom-right")

    def test_wsl_and_windows_paths_are_converted(self):
        if os.name == "nt":
            self.assertEqual(conf.normalize_path("/mnt/c/Users/x"), "C:/Users/x")
        else:
            self.assertEqual(conf.normalize_path("C:\\Users\\x"), "/mnt/c/Users/x")
            self.assertEqual(conf.normalize_path("/home/x"), "/home/x")

    def test_config_roundtrip_utf8(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "c.json"
            conf.save_config(path, {"language": "fr", "last_dest_dir": "/tmp/é"})
            self.assertEqual(conf.load_config(path)["last_dest_dir"], "/tmp/é")


if __name__ == "__main__":
    unittest.main()
