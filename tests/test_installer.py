import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import utils

KNOWN_KEYS = {
    "language", "theme", "frame_enabled", "frame_ratio", "border_color", "landscape_fill_mode", "background_color",
    "blur_strength", "jpeg_quality", "output_format", "output_width", "number_files", "signature_position", "signature_scale",
    "disabled_kinds", "last_dest_dir", "gdrive_enabled", "gdrive_folder",
}


def default_config(lang="fr", docs="C:/Users/x/Documents"):
    text = (ROOT / "installer" / "default_config.json").read_text(encoding="utf-8")
    return json.loads(text.replace("@LANG@", lang).replace("@DOCS@", docs))


class InstallerDefaultsTests(unittest.TestCase):
    def test_template_is_valid_json_once_filled(self):
        config = default_config()
        self.assertEqual(config["language"], "fr")
        self.assertEqual(config["last_dest_dir"], "C:/Users/x/Documents/RKarrousel")

    def test_only_settings_the_app_knows(self):
        self.assertEqual(set(default_config()) - KNOWN_KEYS, set())

    def test_values_are_accepted_by_the_app(self):
        config = default_config()
        self.assertTrue(0.001 <= config["frame_ratio"] <= 0.2)
        self.assertIn(config["landscape_fill_mode"], utils.LANDSCAPE_FILL_MODES)
        self.assertIn(config["signature_position"], utils.SIGNATURE_POSITIONS)
        self.assertEqual(utils.parse_color(config["border_color"]), (255, 255, 255))
        self.assertEqual(utils.parse_color(config["background_color"]), (0, 0, 0))
        self.assertEqual(utils.jpeg_quality_of(config), config["jpeg_quality"])
        self.assertEqual(utils.blur_strength_of(config), config["blur_strength"])
        self.assertEqual(utils.signature_scale_of(config), config["signature_scale"])
        self.assertEqual(utils.disabled_kinds_of(config), set())
        self.assertIn(config["theme"], ("auto", "light", "dark"))
        self.assertIn(config["output_format"], utils.OUTPUT_FORMATS)
        self.assertIn(config["output_width"], utils.OUTPUT_WIDTHS)

    def test_app_loads_the_default_config(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "c.json"
            path.write_text(json.dumps(default_config("en")), encoding="utf-8")
            loaded = utils.load_config(path)
        self.assertEqual(loaded["language"], "en")
        self.assertTrue(loaded["number_files"])

    def test_inno_script_is_consistent_with_the_repo(self):
        script = (ROOT / "installer" / "RKarrousel.iss").read_text(encoding="utf-8-sig")
        self.assertIn("default_config.json", script)
        self.assertIn(utils.CONFIG_FILE_NAME, script)  # même nom de fichier que celui lu par l'appli
        self.assertIn("PrivilegesRequired=lowest", script)  # la config doit rester inscriptible à côté de l'exe
        self.assertIn("@LANG@", (ROOT / "installer" / "default_config.json").read_text(encoding="utf-8"))
        for token in ("@LANG@", "@DOCS@"):
            self.assertIn(token, script)


if __name__ == "__main__":
    unittest.main()
