import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    import tkinter as tk
    _probe = tk.Tk()
    _probe.destroy()
    HAVE_DISPLAY = True
except Exception:  # pas d'écran (CI Linux) : ces tests sont ignorés
    HAVE_DISPLAY = False


@unittest.skipUnless(HAVE_DISPLAY, "pas d'affichage graphique")
class GuiBuildTests(unittest.TestCase):
    """Construit toute l'interface : attrape les oublis d'ordre de création, de variables ou de textes."""

    def setUp(self):
        import photo_splitter_gui as gui

        self.gui = gui
        self.tmp = tempfile.TemporaryDirectory()
        self.config_path = Path(self.tmp.name) / "config.json"
        self.config_path.write_text(json.dumps({"theme": "light", "update_check": False, "github_token": "old"}))
        self._saved = gui.CONFIG_PATH
        gui.CONFIG_PATH = self.config_path
        self.root = gui.create_root()
        self.app = gui.PhotoSplitterGUI(self.root)

    def tearDown(self):
        self.root.destroy()
        self.gui.CONFIG_PATH = self._saved
        self.tmp.cleanup()

    def test_builds_and_collects_config(self):
        self.root.update()
        config = self.app.collect_config()
        self.assertNotIn("github_token", config)  # l'ancien jeton n'est plus conservé
        self.assertIn("output_format", config)

    def test_language_and_theme_changes_rebuild_the_ui(self):
        self.app.change_language(1)
        self.app.change_theme(2)
        self.app.change_language(0)
        self.root.update()
        self.assertEqual(self.app.config["theme"], "dark")

    def test_irrelevant_fill_controls_are_greyed_out(self):
        self.app.landscape_fill_mode.set("blur")
        self.assertTrue(self.app.bg_entry.instate(["disabled"]))
        self.assertTrue(self.app.blur_spin.instate(["!disabled"]))
        self.app.landscape_fill_mode.set("black")
        self.assertTrue(self.app.bg_entry.instate(["!disabled"]))
        self.assertTrue(self.app.blur_spin.instate(["disabled"]))

    def test_no_frame_greys_out_the_frame_controls(self):
        self.app.no_frame.set(True)
        self.app.update_frame_widgets()
        self.assertTrue(self.app.frame_spin.instate(["disabled"]))


if __name__ == "__main__":
    unittest.main()
