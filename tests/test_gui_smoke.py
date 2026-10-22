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
        from rkarrousel.gui.app import PhotoSplitterGUI
        from rkarrousel.gui.system import create_root

        self.tmp = tempfile.TemporaryDirectory()
        self.config_path = Path(self.tmp.name) / "config.json"
        self.config_path.write_text(json.dumps({"theme": "light", "update_check": False, "github_token": "old"}))
        self.root = create_root()
        self.app = PhotoSplitterGUI(self.root, config_path=self.config_path)

    def tearDown(self):
        self.root.destroy()
        self.tmp.cleanup()

    def test_builds_and_collects_config(self):
        self.root.update()
        config = self.app.collect_config()
        self.assertNotIn("github_token", config)  # l'ancien jeton n'est plus conservé
        self.assertIn("output_format", config)

    def test_startup_check_runs_every_launch_even_right_after_a_check(self):
        import os
        from unittest import mock

        calls = []
        self.app.updates.check = lambda manual=False: calls.append(manual)
        self.app.model.update_check.set(True)
        self.app.config["last_update_check"] = 9999999999  # une vérification « toute récente » ne doit rien bloquer
        with mock.patch.dict(os.environ, {"RKARROUSEL_UPDATE_API": "http://127.0.0.1:1"}):
            self.app.updates.auto_check()
            self.app.updates.auto_check()
        self.assertEqual(calls, [False, False])
        self.app.model.update_check.set(False)  # sauf si l'utilisateur a désactivé la vérification
        with mock.patch.dict(os.environ, {"RKARROUSEL_UPDATE_API": "http://127.0.0.1:1"}):
            self.app.updates.auto_check()
        self.assertEqual(len(calls), 2)
        self.assertNotIn("last_update_check", self.app.collect_config())

    def test_language_and_theme_changes_rebuild_the_ui(self):
        self.app.change_language(1)
        self.app.change_theme(2)
        self.app.change_language(0)
        self.root.update()
        self.assertEqual(self.app.config["theme"], "dark")

    def test_irrelevant_fill_controls_are_greyed_out(self):
        self.app.model.landscape_fill_mode.set("blur")
        self.assertTrue(self.app.settings_tab.fill.background.entry.instate(["disabled"]))
        self.assertTrue(self.app.settings_tab.fill.blur_spin.instate(["!disabled"]))
        self.app.model.landscape_fill_mode.set("black")
        self.assertTrue(self.app.settings_tab.fill.background.entry.instate(["!disabled"]))
        self.assertTrue(self.app.settings_tab.fill.blur_spin.instate(["disabled"]))

    def test_no_frame_greys_out_the_frame_controls(self):
        self.app.model.no_frame.set(True)
        self.app.settings_tab.frame.refresh_state()
        self.assertTrue(self.app.settings_tab.frame.spin.instate(["disabled"]))


if __name__ == "__main__":
    unittest.main()
