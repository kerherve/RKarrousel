"""Parcours complets de l'interface (ajout de photos, traitement, Drive, mises à jour) contre de faux serveurs locaux."""
import gc
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image

from tests.helpers import make_image

try:
    import tkinter as tk
    from tkinter import ttk
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
        # Les variables Tk d'une fenêtre détruite doivent être libérées ICI (thread principal) : sinon le ramasse-miettes
        # le fait dans un thread de travail, où Tk bloque. Sans objet dans l'appli, qui n'a qu'une fenêtre.
        self.app = self.root = None
        gc.collect()

    def pump(self, until, seconds=20):
        end = time.time() + seconds
        while time.time() < end and not until():
            self.root.update()
            self.app.ctx.bus.dispatch_pending()
            time.sleep(0.02)
        self.root.update()
        import threading

        state = f"processing={self.app.ctx.processing} dialogues={self.dialogs} threads={[th.name for th in threading.enumerate()]}"
        self.assertTrue(until(), "condition non atteinte à temps : " + state)

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
        from rkarrousel.services.gdrive import transport
        from tests.test_gdrive import FakeGoogle, authorize_with_fake_browser

        transport.RETRY_DELAY = 0.01
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

    def test_order_grid_grows_with_the_window(self):
        window = self.open_order_window(self.photos[:2])
        self.root.update()
        base = window.layout.tile_w
        window.geometry("1500x900")
        self.pump(lambda: window.layout.tile_w > base)
        self.assertEqual(window.grid_canvas.layout.tile_w, window.layout.tile_w)
        window.geometry("700x900")
        self.pump(lambda: window.layout.tile_w < 400)

    def test_viewer_adjusts_frame_and_fill_live_and_refreshes_the_grid(self):
        from rkarrousel.gui import viewer as viewer_pkg

        window = self.open_order_window(self.photos[:1])
        window.select(0)
        window.view_selected()
        viewer = next(w for w in window.winfo_children() if isinstance(w, viewer_pkg.ImageViewer))
        self.pump(lambda: viewer.image is not None)
        refreshed = []
        viewer.on_settings_changed = lambda: refreshed.append(True)

        self.assertIn("cadre mesuré", viewer.info.get())
        self.app.model.no_frame.set(True)  # l'image doit être recalculée, sans cadre
        self.pump(lambda: viewer.jobs.generation >= 2 and "px" in viewer.info.get() and "cadre mesuré" not in viewer.info.get())
        viewer.close()
        self.assertEqual(refreshed, [True])  # la grille est rafraîchie à la fermeture

    def test_viewer_greys_out_settings_the_displayed_image_does_not_use(self):
        from rkarrousel.gui import viewer as viewer_pkg

        self.app.model.signature_path.set(str(self.dir / "sig.png"))
        Image.new("RGBA", (200, 80), (255, 255, 255, 255)).save(self.dir / "sig.png")
        window = self.open_order_window(self.photos[1:2])  # paysage 3:2 : tranches, puis images entières

        def open_viewer(kind):
            index = next(i for i, tile in enumerate(window.tiles) if tile.kind == kind)
            window.select(index)
            window.view_selected()
            return [w for w in window.winfo_children() if isinstance(w, viewer_pkg.ImageViewer)][-1]

        def enabled(group):
            return all("disabled" not in child.state() for child in group.winfo_children()
                       if isinstance(child, ttk.Radiobutton))

        part = open_viewer("part1")
        self.assertFalse(enabled(part.panel.fill_group))
        self.assertIn("non applicable", part.panel.fill_group.cget("text"))
        self.assertIn("non applicable", part.panel.signature_group.cget("text"))
        part.close()
        whole = open_viewer("part1_with_sig")
        self.assertTrue(enabled(whole.panel.fill_group))
        self.assertNotIn("non applicable", whole.panel.signature_group.cget("text"))
        whole.close()

    def test_viewer_sets_a_frame_colour_for_this_photo_only(self):
        from rkarrousel.gui import viewer as viewer_pkg
        from rkarrousel.gui.photo_frame_group import PhotoFrameGroup

        window = self.open_order_window(self.photos[:2])
        window.select(0)
        window.view_selected()
        viewer = next(w for w in window.winfo_children() if isinstance(w, viewer_pkg.ImageViewer))
        self.pump(lambda: viewer.image is not None)
        group = self._find(viewer, PhotoFrameGroup)
        self.assertEqual(group.mode.get(), "global")
        group.mode.set("contrast")  # cette photo seulement
        key = str(self.photos[0])
        self.assertEqual(self.app.ctx.config["photo_overrides"][key]["border_color_mode"], "contrast")
        self.pump(lambda: viewer.jobs.generation >= 2 and viewer.settings_changed and "px" in viewer.info.get())
        self.assertEqual(self.app.model.border_color_mode.get(), "fixed")  # le réglage général n'a pas bougé
        self.assertRegex(group.resolved_text.cget("text"), r"^#[0-9A-F]{6}$")  # la couleur obtenue est affichée
        before = group.resolved_text.cget("text")
        group.tweaks[2].set(0.5)  # retouche fine : un peu plus clair
        self.pump(lambda: "border_tweak" in self.app.ctx.config["photo_overrides"].get(key, {}))
        self.assertGreater(self.app.ctx.config["photo_overrides"][key]["border_tweak"][2], 0)
        self.pump(lambda: viewer.jobs.generation >= 3 and group.resolved_text.cget("text") != before)
        group.tweaks[0].set(0.6)
        for name in ("ButtonPress-1", "ButtonRelease-1", "ButtonPress-1", "ButtonRelease-1"):  # un double-clic
            group.scales[0].event_generate(f"<{name}>", x=40, y=5)
        self.root.update()
        self.assertEqual(group.tweaks[0].get(), 0.0)
        group.reset_tweak()
        group.mode.set("global")
        self.pump(lambda: key not in self.app.ctx.config["photo_overrides"])
        viewer.close()

    def _find(self, widget, cls):
        for child in widget.winfo_children():
            if isinstance(child, cls):
                return child
            found = self._find(child, cls)
            if found is not None:
                return found
        return None

    def swipe(self, viewer, dx):
        """Glisse à la souris sur l'image, de `dx` pixels (négatif : vers la gauche)."""
        canvas, x, y = viewer.canvas, 300, 200
        canvas.event_generate("<ButtonPress-1>", x=x, y=y)
        for step in range(1, 9):
            canvas.event_generate("<B1-Motion>", x=x + dx * step // 8, y=y, state=0x100)
            self.root.update()
        canvas.event_generate("<ButtonRelease-1>", x=x + dx, y=y)

    def test_viewer_swipes_like_an_instagram_carousel(self):
        from rkarrousel.gui import viewer as viewer_pkg

        window = self.open_order_window(self.photos[:2])
        window.select(1)
        window.view_selected()
        viewer = next(w for w in window.winfo_children() if isinstance(w, viewer_pkg.ImageViewer))
        self.pump(lambda: viewer.image is not None and viewer.carousel.neighbors[1] is not None and viewer.carousel.neighbors[-1] is not None)
        self.assertTrue(viewer.view.fit_mode)
        width = viewer._slide_distance()
        self.swipe(viewer, -int(width * 0.6))  # vers la gauche, assez loin : image suivante
        self.pump(lambda: window.model.selected == 2 and not viewer.carousel.animating)
        self.assertEqual(viewer.carousel.slide_px, 0.0)
        self.assertIsNotNone(viewer.image)  # jamais d'écran vide : l'aperçu réduit prend le relais
        self.pump(lambda: viewer.carousel.neighbors[-1] is not None)  # l'image qu'on vient de quitter reste visible à gauche
        self.swipe(viewer, int(width * 0.05))  # trop court : l'image revient en place
        self.pump(lambda: not viewer.carousel.animating and viewer.carousel.slide_px == 0.0)
        self.assertEqual(window.model.selected, 2)
        self.swipe(viewer, int(width * 0.6))  # vers la droite : l'image précédente
        self.pump(lambda: window.model.selected == 1 and not viewer.carousel.animating)
        viewer.close()

    def test_swiping_past_the_last_image_springs_back(self):
        from rkarrousel.gui import viewer as viewer_pkg

        window = self.open_order_window(self.photos[:1])  # une seule image
        window.select(0)
        window.view_selected()
        viewer = next(w for w in window.winfo_children() if isinstance(w, viewer_pkg.ImageViewer))
        self.pump(lambda: viewer.image is not None)
        self.swipe(viewer, -400)
        self.pump(lambda: not viewer.carousel.animating and viewer.carousel.slide_px == 0.0)
        self.assertEqual(window.model.selected, 0)
        viewer.close()

    def test_zoomed_viewer_pans_instead_of_swiping(self):
        from rkarrousel.gui import viewer as viewer_pkg

        window = self.open_order_window(self.photos[:2])
        window.select(1)
        window.view_selected()
        viewer = next(w for w in window.winfo_children() if isinstance(w, viewer_pkg.ImageViewer))
        self.pump(lambda: viewer.image is not None)
        viewer.set_zoom(1.0)  # zoomée : le glisser déplace l'image
        self.assertFalse(viewer.view.fit_mode)
        before = viewer.view.ox
        self.swipe(viewer, -200)
        self.root.update()
        self.assertEqual(window.model.selected, 1)
        self.assertNotEqual(viewer.view.ox, before)
        viewer.close()

    def test_viewer_rerenders_when_the_colour_source_changes(self):
        from rkarrousel.gui import viewer as viewer_pkg

        self.app.model.border_color_mode.set("dominant")
        window = self.open_order_window(self.photos[:1])
        window.select(0)
        window.view_selected()
        viewer = next(w for w in window.winfo_children() if isinstance(w, viewer_pkg.ImageViewer))
        self.pump(lambda: viewer.image is not None)
        self.app.model.color_source.set("edges")
        self.pump(lambda: viewer.jobs.generation >= 2 and viewer.settings_changed and "px" in viewer.info.get())
        self.assertEqual(viewer.config_snapshot["color_source"], "edges")
        viewer.close()

    def test_viewer_steps_through_the_images_with_arrows_and_keys(self):
        from rkarrousel.gui import viewer as viewer_pkg
        from rkarrousel.i18n import kind_label

        window = self.open_order_window(self.photos[:2])  # 1 image + 4 images (paysage) = 5
        window.select(0)
        window.view_selected()
        viewer = next(w for w in window.winfo_children() if isinstance(w, viewer_pkg.ImageViewer))
        self.pump(lambda: viewer.image is not None)
        self.assertEqual(viewer.position_label.cget("text"), "1 / 5")
        self.assertFalse(window.viewer_can_step(-1))  # première image : pas de flèche précédente
        # carrousel : la suivante est affichée à droite, pas de précédente avant la première
        self.pump(lambda: viewer.carousel.neighbors[1] is not None)
        self.assertIsNone(viewer.carousel.neighbors[-1])
        self.root.update()
        self.assertEqual(len(viewer.canvas.find_withtag("neigh")), 1)
        viewer.carousel.enabled.set(False)
        viewer.redraw()
        self.assertEqual(len(viewer.canvas.find_withtag("neigh")), 0)
        viewer.carousel.enabled.set(True)
        first_source = viewer.source
        viewer.step(1)  # en carrousel, l'image suivante arrive en glissant
        self.pump(lambda: window.model.selected == 1 and not viewer.carousel.animating)
        self.assertEqual(viewer.position_label.cget("text"), "2 / 5")
        self.assertIn(kind_label(window.model.tiles[1].kind), viewer.title())
        self.pump(lambda: viewer.image is not None and viewer.jobs.generation >= 2)
        self.pump(lambda: viewer.image is not None and not viewer.placeholder and viewer.carousel.neighbors[1] is not None)
        viewer._key_step(1)
        self.pump(lambda: window.model.selected == 2 and not viewer.carousel.animating)
        # une image exclue est sautée
        window.select(3)
        window.toggle_exclude()
        window.select(2)
        viewer.show(window.model.tiles[2].source, window.model.tiles[2].kind)
        viewer.step(1)
        self.pump(lambda: window.model.selected == 4 and not viewer.carousel.animating)
        viewer.step(1)  # dernière : rien ne bouge
        self.assertEqual(window.model.selected, 4)
        self.assertNotEqual(first_source, None)
        viewer.close()

    def test_crop_button_is_only_enabled_on_a_crop_tile(self):
        window = self.open_order_window(self.photos[2:3])  # carré : image entière + recadrage
        crop_index = window.model.index_of([t.key for t in window.tiles if t.kind == "crop34"][0])
        window.select(0)
        self.assertTrue(window.crop_btn.instate(["disabled"]))
        window.select(crop_index)
        self.assertTrue(window.crop_btn.instate(["!disabled"]))

    # ------------------------------------------------------------------ préréglages et couleurs de la photo
    def preset_group(self):
        return self.app.settings_tab.presets

    def select_preset(self, preset_id):
        group = self.preset_group()
        group.box.current([p.id for p in group.entries].index(preset_id))
        group.apply_selected()

    def test_choosing_a_builtin_preset_sets_the_fields_and_the_dropdowns(self):
        model = self.app.model
        model.output_format.set("9:16")  # hors préréglage : ne doit pas bouger
        self.select_preset("no_frame")
        self.assertTrue(model.no_frame.get())
        self.assertEqual(model.landscape_fill_mode.get(), "blur")
        self.assertEqual(model.output_format.get(), "9:16")
        self.assertTrue(self.app.settings_tab.frame.spin.instate(["disabled"]))
        self.select_preset("photo_color")
        self.assertFalse(model.no_frame.get())
        self.assertEqual((model.border_color_mode.get(), model.background_color_mode.get()), ("light", "dark"))
        self.assertEqual(self.app.settings_tab.frame.mode.get(), "Photo, version claire")  # la liste affiche la valeur

    def test_saving_reapplying_and_deleting_a_user_preset(self):
        model, group = self.app.model, self.preset_group()
        model.frame_percent.set(3.5)
        model.output_format.set("4:5")
        model.output_width.set(1080)
        with mock.patch("tkinter.simpledialog.askstring", return_value="  Mon   style "):
            group.save()
        self.assertEqual(group.box.get(), "Mon style")
        saved = json.loads((self.dir / "config.json").read_text())["presets"]["Mon style"]
        self.assertEqual((saved["frame_ratio"], saved["output_format"], saved["output_width"]), (0.035, "4:5", 1080))
        self.assertNotIn("language", saved)

        model.frame_percent.set(1.0)
        model.output_format.set("3:4")
        model.output_width.set(0)
        self.select_preset("Mon style")
        self.assertEqual((model.frame_percent.get(), model.output_format.get(), model.output_width.get()), (3.5, "4:5", 1080))
        self.assertEqual(self.app.settings_tab.output.format_box.get(), "4:5 · Feed Instagram")

        with mock.patch("tkinter.messagebox.askyesno", return_value=True):
            group.delete()
        self.assertNotIn("Mon style", [p.id for p in group.entries])
        self.assertNotIn("Mon style", json.loads((self.dir / "config.json").read_text()).get("presets", {}))

    def test_builtin_presets_cannot_be_deleted_and_overwriting_asks_first(self):
        group = self.preset_group()
        group.box.current(0)
        group.apply_selected()
        self.assertTrue(group.delete_button.instate(["disabled"]))
        with mock.patch("tkinter.simpledialog.askstring", return_value="Perso"):
            group.save()
        with mock.patch("tkinter.simpledialog.askstring", return_value="Perso"), \
                mock.patch("tkinter.messagebox.askyesno", return_value=False) as ask:
            self.app.model.frame_percent.set(9.0)
            group.save()
        self.assertTrue(ask.called)
        self.assertNotEqual(self.app.config["presets"]["Perso"]["frame_ratio"], 0.09)  # refusé : inchangé

    def test_a_photo_colour_mode_replaces_the_colour_picker(self):
        frame = self.app.settings_tab.frame
        self.app.model.border_color_mode.set("fixed")
        self.assertTrue(frame.color.entry.instate(["!disabled"]))
        self.app.model.border_color_mode.set("dominant")
        self.assertTrue(frame.color.entry.instate(["disabled"]))

    def test_processing_with_a_photo_coloured_frame(self):
        from PIL import Image

        red = make_image(self.dir, "r_red.jpg", (900, 1200), (200, 30, 30))
        blue = make_image(self.dir, "s_blue.jpg", (900, 1200), (30, 40, 200))
        self.app.model.border_color_mode.set("dominant")
        self.app.files_tab.add_paths([str(red), str(blue)])
        self.run_batch()
        a = Image.open(self.out / "01_r_red_framed.jpg").convert("RGB")
        b = Image.open(self.out / "02_s_blue_framed.jpg").convert("RGB")
        self.assertGreater(a.getpixel((2, a.height // 2))[0], 150)
        self.assertGreater(b.getpixel((2, b.height // 2))[2], 150)


if __name__ == "__main__":
    unittest.main()
