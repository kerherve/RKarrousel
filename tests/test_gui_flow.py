"""Parcours complets de l'interface (ajout de photos, traitement, Drive, mises à jour) contre de faux serveurs locaux."""
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers import make_image

try:
    import tkinter as tk
    tk.Tk().destroy()
    HAVE_DISPLAY = True
except Exception:  # pas d'écran (CI Linux) : ces tests sont ignorés
    HAVE_DISPLAY = False


@unittest.skipUnless(HAVE_DISPLAY, "pas d'affichage graphique")
class GuiFlowTests(unittest.TestCase):
    def setUp(self):
        from rkarrousel.gui.app import PhotoSplitterGUI
        from rkarrousel.gui.system import create_root

        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.out = self.dir / "out"
        config_path = self.dir / "config.json"
        config_path.write_text(json.dumps({"theme": "light", "update_check": False, "frame_ratio": 0.02,
                                           "last_dest_dir": str(self.out), "number_files": True}))
        self.dialogs = []
        for name in ("showinfo", "showwarning", "showerror"):
            patcher = mock.patch(f"tkinter.messagebox.{name}", lambda title, text, _n=name, **k: self.dialogs.append((_n, text)))
            patcher.start()
            self.addCleanup(patcher.stop)
        self.root = create_root()
        self.app = PhotoSplitterGUI(self.root, config_path=config_path)
        self.photos = [
            make_image(self.dir, "a_p34.jpg", (900, 1200)),
            make_image(self.dir, "b_l32.jpg", (1500, 1000)),
            make_image(self.dir, "c_sq.jpg", (1000, 1000)),
        ]

    def tearDown(self):
        self.root.destroy()
        self.tmp.cleanup()

    def pump(self, until, seconds=20):
        end = time.time() + seconds
        while time.time() < end and not until():
            self.root.update()
            self.app.ctx.bus.dispatch_pending()
            time.sleep(0.02)
        self.root.update()
        self.assertTrue(until(), "condition non atteinte à temps")

    def run_batch(self):
        self.app.batch.start()
        self.pump(lambda: not self.app.ctx.processing and self.dialogs)

    def test_adding_photos_selects_and_previews_the_first(self):
        self.app.files_tab.add_paths([str(p) for p in self.photos])
        self.assertEqual(self.app.files_tab.listbox.selection(), ("0",))
        self.assertIn("a_p34.jpg", self.app.preview.info.get())

    def test_adding_a_folder_previews_its_first_image(self):
        self.app.files_tab.add_paths([str(self.dir)])
        self.assertIn("a_p34.jpg", self.app.preview.info.get())

    def test_processing_writes_numbered_files_and_a_summary(self):
        self.app.files_tab.add_paths([str(p) for p in self.photos])
        self.run_batch()
        names = sorted(p.name for p in self.out.iterdir())
        self.assertEqual(names[0], "01_a_p34_framed.jpg")
        self.assertEqual(len(names), 1 + 4 + 2)  # 3:4 → 1 image ; 3:2 → 4 ; carré → 2 (entière + recadrage)
        self.assertIn("3/3", self.dialogs[-1][1])

    def test_excluded_images_are_not_generated(self):
        self.app.files_tab.add_paths([str(self.photos[1])])
        from rkarrousel.outputs import item_key

        self.app.ctx.session.excluded = {item_key(self.photos[1], "part2_with_sig")}
        self.run_batch()
        self.assertFalse(any("part2_with_sig" in p.name for p in self.out.iterdir()))

    def test_drive_upload_after_processing(self):
        from rkarrousel.services import gdrive
        from tests.test_gdrive import FakeGoogle, authorize_with_fake_browser

        gdrive.RETRY_DELAY = 0.01
        fake = FakeGoogle()
        self.addCleanup(fake.stop)
        token_path = self.dir / "token.json"
        gdrive.save_token(token_path, authorize_with_fake_browser(fake))
        self.app.drive.client = lambda: gdrive.DriveClient(
            "cid", "secret", token_path, api_url=fake.base + "/drive/v3",
            upload_url=fake.base + "/upload/drive/v3", token_url=fake.base + "/token",
        )
        self.app.model.gdrive_enabled.set(True)
        self.app.model.gdrive_folder.set("Insta/Test")
        self.app.files_tab.add_paths([str(self.photos[0]), str(self.photos[2])])
        self.run_batch()
        uploaded = sorted(f["name"] for f in fake.files.values() if f["mime"] != gdrive.FOLDER_MIME)
        self.assertEqual(uploaded, sorted(p.name for p in self.out.iterdir()))
        self.assertIn("Insta/Test", self.dialogs[-1][1])

    def test_drive_is_skipped_with_a_message_when_not_connected(self):
        self.app.model.gdrive_enabled.set(True)
        self.app.files_tab.add_paths([str(self.photos[0])])
        self.run_batch()
        self.assertIn("Google Drive", self.dialogs[-1][1])
        self.assertEqual(self.dialogs[-1][0], "showwarning")

    def test_update_dialog_appears_for_a_newer_release(self):
        from rkarrousel.gui import update_controller
        from tests.test_updater import FakeGitHub

        fake = FakeGitHub(tag="v99.0.0")
        self.addCleanup(fake.stop)
        with mock.patch.object(update_controller, "UPDATE_API", fake.base), mock.patch.object(update_controller, "UPDATE_REPO", "o/r"):
            self.app.updates.check(manual=True)
            self.pump(lambda: self.app.updates.dialog is not None)
        self.assertIn("99.0.0", self.app.updates.dialog.title() + "".join(w.cget("text") for w in self.app.updates.dialog.winfo_children()[0].winfo_children() if w.winfo_class() == "TLabel"))
        self.app.updates.dialog.close()

    def test_manual_check_reports_when_up_to_date(self):
        from rkarrousel.gui import update_controller
        from tests.test_updater import FakeGitHub

        fake = FakeGitHub(tag="v0.0.1")
        self.addCleanup(fake.stop)
        with mock.patch.object(update_controller, "UPDATE_API", fake.base), mock.patch.object(update_controller, "UPDATE_REPO", "o/r"):
            self.app.updates.check(manual=True)
            self.pump(lambda: self.dialogs)
        self.assertEqual(self.dialogs[-1][0], "showinfo")

    # ------------------------------------------------------------------ fenêtre « Aperçu et ordre »
    def open_order_window(self, photos):
        self.app.files_tab.add_paths([str(p) for p in photos])
        self.app.order.open()
        window = self.app.order.window
        self.pump(lambda: window.model.counts()[1] == window.model.counts()[0])  # tous les aperçus sont prêts
        return window

    def test_order_window_lists_every_output_and_renders_previews(self):
        window = self.open_order_window(self.photos[:2])
        self.assertEqual(len(window.tiles), 1 + 4)
        self.assertTrue(all(tile.thumb is not None for tile in window.tiles))
        self.assertEqual(window.status.get(), "5 image(s)")

    def test_clicking_the_cross_excludes_then_restores(self):
        window = self.open_order_window(self.photos[:1])
        canvas = window.grid_canvas
        x0, y0, x1, y1 = window.layout.cross_rect(*window.layout.slot_origin(0))
        point = dict(x=(x0 + x1) // 2, y=(y0 + y1) // 2)
        for expected in (1, 0):
            canvas.event_generate("<ButtonPress-1>", **point)
            canvas.event_generate("<ButtonRelease-1>", **point)
            self.root.update()
            self.assertEqual(len(self.app.ctx.session.excluded), expected)

    def test_drag_and_drop_reorders_and_changes_the_numbering(self):
        window = self.open_order_window(self.photos[:2])
        first_key = window.tiles[0].key
        canvas, layout = window.grid_canvas, window.layout

        class Ev:
            def __init__(self, point):
                self.x, self.y = point
                self.x_root, self.y_root = point

        sx, sy = layout.slot_origin(0)
        tx, ty = layout.slot_origin(3)
        canvas._on_press(Ev((sx + 40, sy + 60)))
        for step in range(1, 6):
            canvas._on_motion(Ev((sx + 40 + (tx - sx) * step // 5, sy + 60 + (ty - sy) * step // 5)))
        canvas._on_release(Ev((tx + 40, ty + 60)))
        self.assertEqual(window.tiles[3].key, first_key)
        self.assertEqual(self.app.ctx.session.order[3], first_key)
        window.close()
        self.app.order.window = None
        self.run_batch()
        names = sorted(p.name for p in self.out.iterdir())
        self.assertTrue(any(name.startswith("04_a_p34_framed") for name in names), names)  # l'image déplacée est la 4e

    def test_excluding_in_the_grid_skips_the_image_and_its_number(self):
        window = self.open_order_window(self.photos[1:2])
        window.select(1)
        window.toggle_exclude()
        window.close()
        self.app.order.window = None
        self.run_batch()
        names = sorted(p.name for p in self.out.iterdir())
        self.assertEqual(len(names), 3)
        self.assertEqual([n[:2] for n in names], ["01", "02", "03"])

    def test_crop_button_is_only_enabled_on_a_crop_tile(self):
        window = self.open_order_window(self.photos[2:3])  # carré : image entière + recadrage
        crop_index = window.model.index_of([t.key for t in window.tiles if t.kind == "crop34"][0])
        window.select(0)
        self.assertTrue(window.crop_btn.instate(["disabled"]))
        window.select(crop_index)
        self.assertTrue(window.crop_btn.instate(["!disabled"]))


if __name__ == "__main__":
    unittest.main()
