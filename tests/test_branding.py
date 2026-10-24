"""Le logo : les fichiers sont là, bien formés, et branchés sur l'appli, l'exécutable et l'installateur."""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, ROOT.as_posix())

from PIL import Image

from rkarrousel.gui import branding

try:
    import tkinter as tk

    tk.Tk().destroy()
    HAVE_DISPLAY = True
except Exception:  # pas d'écran (CI Linux) : les tests de fenêtre sont ignorés
    HAVE_DISPLAY = False


class AssetTests(unittest.TestCase):
    def test_the_files_exist_and_are_square_with_transparent_corners(self):
        for path, side in ((branding.LOGO_256, 256), (branding.LOGO_64, 64)):
            with Image.open(path) as image:
                self.assertEqual(image.size, (side, side))
                self.assertEqual(image.mode, "RGBA")
                self.assertEqual(image.getpixel((0, 0))[3], 0, path.name)  # coins arrondis : transparents
                self.assertGreater(image.getpixel((side // 2, side // 2))[3], 200, path.name)

    def test_the_icon_holds_every_windows_size(self):
        with Image.open(branding.ICON_PATH) as icon:
            self.assertTrue({(16, 16), (32, 32), (48, 48), (256, 256)} <= set(icon.info["sizes"]))

    def test_the_generator_reproduces_the_committed_logo(self):
        sys.path.insert(0, str(ROOT / "tools"))
        import make_logo

        fresh = make_logo.draw_logo(make_logo.SIZE).resize((256, 256), Image.Resampling.LANCZOS)  # même chaîne que `write_assets`
        with Image.open(branding.LOGO_256) as committed:
            self.assertEqual(fresh.tobytes(), committed.convert("RGBA").tobytes())

    def test_the_build_and_the_installer_use_the_icon(self):
        bat = (ROOT / "build_windows.bat").read_text(encoding="utf-8")
        self.assertIn("--icon rkarrousel\\assets\\icon.ico", bat)
        self.assertIn("--add-data \"rkarrousel\\assets;rkarrousel\\assets\"", bat)  # le logo de l'en-tête voyage avec l'exe
        iss = (ROOT / "installer" / "RKarrousel.iss").read_text(encoding="utf-8-sig")
        icon = re.search(r"^SetupIconFile=(.+)$", iss, re.M).group(1).strip()
        self.assertTrue((ROOT / "installer" / icon.replace("\\", "/")).exists())


@unittest.skipUnless(HAVE_DISPLAY, "pas d'affichage graphique")
class WindowTests(unittest.TestCase):
    def test_header_logo_has_the_requested_height_and_missing_files_are_tolerated(self):
        root = tk.Tk()
        try:
            image = branding.header_logo(root, 52)
            self.assertEqual((image.width(), image.height()), (52, 52))
            original = branding.LOGO_256
            branding.LOGO_256 = Path("absent.png")
            try:
                self.assertIsNone(branding.header_logo(root, 52))  # sans le fichier : pas de logo, pas de plantage
            finally:
                branding.LOGO_256 = original
            branding.apply_window_icon(root)  # ne plante pas
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
