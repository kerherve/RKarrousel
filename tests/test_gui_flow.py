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

from tests.helpers import build_settings_groups, make_image

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

    @property
    def settings_tab(self):
        """Les groupes de réglages, construits à la demande (voir tests/helpers.py)."""
        if getattr(self, "_groups", None) is None:
            self._groups = build_settings_groups(self.root, self.app.ctx)
        return self._groups

    def tearDown(self):
        self._groups = None
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
        self.app.flow.pages["photos"].add_paths([str(p) for p in self.photos])
        self.assertEqual(self.app.flow.pages["photos"].listbox.selection(), ("0",))
        self.assertIn("a_p34.jpg", self.app.flow.pages["photos"].preview.info.get())

    def test_a_single_photo_can_be_removed_with_the_button_the_key_and_the_cross(self):
        page = self.app.flow.pages["photos"]
        names = [str(p) for p in self.photos]
        page.add_paths(names)
        self.root.update()
        self.assertIn("disabled", page.remove_button.state()) if not page.listbox.selection() else None
        page.listbox.selection_set("1")
        page.on_list_select(None)
        page.remove_selected()  # bouton « Retirer »
        self.assertEqual(self.app.ctx.session.selected_paths, [names[0], names[2]])
        self.assertEqual(len(page.listbox.get_children()), 2)
        self.assertEqual(page.listbox.selection(), ("1",))  # la sélection passe à la suivante
        self.assertIn("c_sq.jpg", self.app.flow.pages["photos"].preview.info.get())
        self.assertTrue(page.listbox.bind("<Delete>") and page.listbox.bind("<BackSpace>"))  # touches Suppr et Retour arrière
        page.remove_selected()  # ce que fait la touche (le clavier dépend du focus de l'écran, variable selon les machines)
        self.assertEqual(self.app.ctx.session.selected_paths, [names[0]])
        x0, y0, width, height = page.listbox.bbox("0", "#1")  # croix de la ligne
        page.listbox.event_generate("<Button-1>", x=x0 + width // 2, y=y0 + height // 2)
        self.root.update()
        self.assertEqual(self.app.ctx.session.selected_paths, [])
        self.assertEqual(len(page.listbox.get_children()), 0)
        self.assertIn("disabled", page.remove_button.state())
        self.assertIn("photo", self.app.flow.nav.hint.cget("text"))  # plus rien à traiter : « Suivant » est bloqué

    def test_removing_a_photo_removes_its_images_from_the_grid(self):
        page = self.app.flow.pages["photos"]
        page.add_paths([str(p) for p in self.photos[:2]])
        window = self.open_order_window(self.photos[:0])  # étape Ordre avec les deux photos déjà ajoutées
        self.assertEqual(len(window.tiles), 1 + 4)
        self.app.flow.go(0)
        page.remove_entry(1)  # on retire le paysage 3:2
        self.app.flow.go(1)
        self.pump(lambda: len(self.app.flow.order_view.tiles) == 1)

    def test_adding_a_folder_previews_its_first_image(self):
        self.app.flow.pages["photos"].add_paths([str(self.dir)])
        self.assertIn("a_p34.jpg", self.app.flow.pages["photos"].preview.info.get())

    def test_processing_writes_numbered_files_and_a_summary(self):
        self.app.flow.pages["photos"].add_paths([str(p) for p in self.photos])
        self.run_batch()
        names = sorted(p.name for p in self.out.iterdir())
        self.assertEqual(names[0], "01_a_p34_framed.jpg")
        self.assertEqual(len(names), 1 + 4 + 2)  # 3:4 → 1 image ; 3:2 → 4 ; carré → 2 (entière + recadrage)
        self.assertIn("3/3", self.dialogs[-1][1])

    def test_excluded_images_are_not_generated(self):
        self.app.flow.pages["photos"].add_paths([str(self.photos[1])])
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
        self.app.flow.pages["photos"].add_paths([str(self.photos[0]), str(self.photos[2])])
        self.run_batch()
        uploaded = sorted(f["name"] for f in fake.files.values() if f["mime"] != gdrive.FOLDER_MIME)
        self.assertEqual(uploaded, sorted(p.name for p in self.out.iterdir()))
        self.assertIn("Insta/Test", self.dialogs[-1][1])

    def test_drive_is_skipped_with_a_message_when_not_connected(self):
        self.app.model.gdrive_enabled.set(True)
        self.app.flow.pages["photos"].add_paths([str(self.photos[0])])
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
        """Ajoute les photos, passe à l'étape « Ordre » et attend les aperçus ; renvoie la grille (OrderView)."""
        self.app.flow.pages["photos"].add_paths([str(p) for p in photos])
        self.app.flow.go(1)
        window = self.app.flow.order_view
        self.pump(lambda: window.model.counts()[1] == window.model.counts()[0])  # tous les aperçus sont prêts
        return window

    def show_viewer(self, window):
        """« Ajuster cette image » sur la vignette sélectionnée : l'étape « Ajustements » avec la visionneuse."""
        if self.app.flow.index == 2:
            self.app.flow.go(1)  # on revient à la grille pour que l'étape se rouvre sur la sélection
        window.adjust_selected()
        return self.app.flow.pages["adjust"].viewer

    def show_viewer_on(self, window, index):
        window.select(index)
        return self.show_viewer(window)

    def leave_viewer(self):
        if self.app.flow.index == 2:
            self.app.flow.go(1)

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
        self.run_batch()
        names = sorted(p.name for p in self.out.iterdir())
        self.assertTrue(any(name.startswith("04_a_p34_framed") for name in names), names)  # l'image déplacée est la 4e

    def test_excluding_in_the_grid_skips_the_image_and_its_number(self):
        window = self.open_order_window(self.photos[1:2])
        window.select(1)
        window.toggle_exclude()
        self.run_batch()
        names = sorted(p.name for p in self.out.iterdir())
        self.assertEqual(len(names), 3)
        self.assertEqual([n[:2] for n in names], ["01", "02", "03"])

    def test_a_wider_order_window_shows_more_columns(self):
        window = self.open_order_window(self.photos[:2])
        self.root.update()
        base = window.layout.columns
        # on donne directement la largeur à la grille : la taille de l'écran (celui du serveur de test est petit) ne compte pas
        window.grid_canvas.fit_to_width(2200)
        self.assertGreater(window.layout.columns, base)
        self.assertEqual(window.grid_canvas.layout.columns, window.layout.columns)
        self.assertEqual(len(window.grid_canvas.find_all()) > 0, True)  # la grille a été redessinée
        window.grid_canvas.fit_to_width(500)
        self.assertEqual(window.layout.columns, base)

    def test_order_window_warns_beyond_twenty_images(self):
        photos = [make_image(self.dir, f"w{i}.jpg", (900, 1200)) for i in range(21)]  # 21 images (3/4 : une chacune)
        window = self.open_order_window(photos)
        self.pump(lambda: all(tile.thumb is not None for tile in window.tiles))
        self.assertIn("20", window.warning.get())
        self.assertIn("21", window.warning.get())
        window.select(20)
        window.toggle_exclude()  # on exclut la 21e : plus d'avertissement
        self.assertEqual(window.warning.get(), "")

    def test_viewer_adjusts_frame_and_fill_live_and_refreshes_the_grid(self):

        window = self.open_order_window(self.photos[:1])
        window.select(0)
        viewer = self.show_viewer(window)
        self.pump(lambda: viewer.image is not None)
        refreshed = []
        viewer.on_settings_changed = lambda: refreshed.append(True)

        self.assertIn("cadre mesuré", viewer.info.get())
        self.app.model.no_frame.set(True)  # l'image doit être recalculée, sans cadre
        self.pump(lambda: viewer.loader.jobs.generation >= 2 and "px" in viewer.info.get() and "cadre mesuré" not in viewer.info.get())
        self.leave_viewer()
        self.assertEqual(refreshed, [True])  # la grille est rafraîchie à la fermeture

    def test_viewer_greys_out_settings_the_displayed_image_does_not_use(self):

        self.app.model.signature_path.set(str(self.dir / "sig.png"))
        Image.new("RGBA", (200, 80), (255, 255, 255, 255)).save(self.dir / "sig.png")
        window = self.open_order_window(self.photos[1:2])  # paysage 3:2 : tranches, puis images entières

        def open_viewer(kind):
            index = next(i for i, tile in enumerate(window.tiles) if tile.kind == kind)
            window.select(index)
            return self.show_viewer(window)

        def enabled(group):
            return all("disabled" not in child.state() for child in group.winfo_children()
                       if isinstance(child, ttk.Radiobutton))

        part = open_viewer("part1")
        self.assertFalse(enabled(part.panel.fill_group))
        self.assertIn("non applicable", part.panel.fill_group.cget("text"))
        self.assertIn("non applicable", part.panel.signature_group.cget("text"))
        self.leave_viewer()
        whole = open_viewer("part1_with_sig")
        self.assertTrue(enabled(whole.panel.fill_group))
        self.assertNotIn("non applicable", whole.panel.signature_group.cget("text"))
        self.leave_viewer()

    def test_viewer_sets_a_frame_colour_for_this_photo_only(self):
        from rkarrousel.gui.photo_frame_group import PhotoFrameGroup

        window = self.open_order_window(self.photos[:2])
        window.select(0)
        viewer = self.show_viewer(window)
        self.pump(lambda: viewer.image is not None)
        group = self._find(viewer, PhotoFrameGroup)
        self.assertEqual(group.mode.get(), "global")
        group.mode.set("contrast")  # cette photo seulement
        key = str(self.photos[0])
        self.assertEqual(self.app.ctx.config["photo_overrides"][key]["border_color_mode"], "contrast")
        self.pump(lambda: viewer.loader.jobs.generation >= 2 and viewer.settings_changed and "px" in viewer.info.get())
        self.assertEqual(self.app.model.border_color_mode.get(), "fixed")  # le réglage général n'a pas bougé
        self.assertRegex(group.resolved_text.cget("text"), r"^#[0-9A-F]{6}$")  # la couleur obtenue est affichée
        before = group.resolved_text.cget("text")
        group.tweaks[2].set(0.5)  # retouche fine : un peu plus clair
        self.pump(lambda: "border_tweak" in self.app.ctx.config["photo_overrides"].get(key, {}))
        self.assertGreater(self.app.ctx.config["photo_overrides"][key]["border_tweak"][2], 0)
        self.pump(lambda: viewer.loader.jobs.generation >= 3 and group.resolved_text.cget("text") != before)
        group.tweaks[0].set(0.6)
        for name in ("ButtonPress-1", "ButtonRelease-1", "ButtonPress-1", "ButtonRelease-1"):  # un double-clic
            group.scales[0].event_generate(f"<{name}>", x=40, y=5)
        self.root.update()
        self.assertEqual(group.tweaks[0].get(), 0.0)
        group.reset_tweak()
        group.mode.set("global")
        self.pump(lambda: key not in self.app.ctx.config["photo_overrides"])
        self.leave_viewer()

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

        window = self.open_order_window(self.photos[:2])
        window.select(1)
        viewer = self.show_viewer(window)
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
        self.leave_viewer()

    def test_swiping_past_the_last_image_springs_back(self):

        window = self.open_order_window(self.photos[:1])  # une seule image
        window.select(0)
        viewer = self.show_viewer(window)
        self.pump(lambda: viewer.image is not None)
        self.swipe(viewer, -400)
        self.pump(lambda: not viewer.carousel.animating and viewer.carousel.slide_px == 0.0)
        self.assertEqual(window.model.selected, 0)
        self.leave_viewer()

    def test_zoomed_viewer_pans_instead_of_swiping(self):

        window = self.open_order_window(self.photos[:2])
        window.select(1)
        viewer = self.show_viewer(window)
        self.pump(lambda: viewer.image is not None)
        viewer.set_zoom(1.0)  # zoomée : le glisser déplace l'image
        self.assertFalse(viewer.view.fit_mode)
        before = viewer.view.ox
        self.swipe(viewer, -200)
        self.root.update()
        self.assertEqual(window.model.selected, 1)
        self.assertNotEqual(viewer.view.ox, before)
        self.leave_viewer()

    def open_viewer(self, window, index):

        window.select(index)
        return self.show_viewer(window)

    def test_viewer_has_a_crop_button_that_works_on_crop_images(self):
        window = self.open_order_window(self.photos[2:3])  # carré : image entière + recadrage
        kinds = [tile.kind for tile in window.tiles]
        viewer = self.open_viewer(window, kinds.index("crop34"))
        self.pump(lambda: viewer.image is not None)
        self.assertNotIn("disabled", viewer.toolbar.crop_button.state())
        calls = []

        def fake_editor(parent, source, config, apply, dark=False):  # l'éditeur valide aussitôt un recadrage
            calls.append(parent)
            apply(0.3)

        before = viewer.loader.jobs.generation
        with mock.patch("rkarrousel.gui.order.view.CropEditor", fake_editor):
            viewer._open_crop()
        self.assertEqual(calls, [self.root])  # ouvert au-dessus de la fenêtre principale
        self.assertEqual(self.app.ctx.config["crop_offsets"][str(self.photos[2])], 0.3)
        self.pump(lambda: viewer.loader.jobs.generation > before and viewer.settings_changed)  # l'image est recalculée
        viewer.step(-1)  # image précédente : plus un recadrage, le bouton se grise
        self.pump(lambda: window.model.selected == kinds.index("crop34") - 1 and not viewer.carousel.animating)
        self.assertIn("disabled", viewer.toolbar.crop_button.state())
        self.leave_viewer()

    def test_browsing_uses_the_previews_already_computed_by_the_grid(self):
        window = self.open_order_window(self.photos[:2])  # 5 images
        viewer = self.open_viewer(window, 1)
        # sans attendre le moindre calcul : les deux voisines viennent des aperçus de la grille
        self.assertIsNotNone(viewer.carousel.neighbors[-1])
        self.assertIsNotNone(viewer.carousel.neighbors[1])
        viewer.carousel.enabled.set(False)  # pas d'animation : changement direct
        viewer.step(1)
        self.assertTrue(viewer.placeholder)  # l'aperçu s'affiche tout de suite…
        self.assertIsNotNone(viewer.image)
        self.pump(lambda: not viewer.placeholder)  # …puis la pleine résolution le remplace
        self.leave_viewer()

    def test_a_big_photo_shows_a_sharp_preview_and_loads_full_resolution_only_when_zooming(self):
        big = make_image(self.dir, "big.jpg", (3600, 4800))
        window = self.open_order_window([big])
        viewer = self.show_viewer_on(window, 0)
        self.pump(lambda: viewer.image is not None and viewer.loader.jobs.generation > 0)
        self.pump(lambda: viewer.image is not None and viewer.image.width < 3000)
        self.assertFalse(viewer.resolution.is_full)
        self.assertGreater(viewer.resolution.factor, 2.0)  # l'aperçu est environ 2,6 fois plus petit que la pleine résolution
        self.assertLess(viewer.image.height, 2400)
        self.assertIn("3", viewer.info.get())  # les dimensions annoncées sont celles de la pleine résolution (estimées)
        # zoom à 100 % : en pixels réels, donc la pleine résolution est chargée, et la vue reste au même endroit
        viewer.set_zoom(1.0)
        self.pump(lambda: viewer.resolution.full_loaded)
        self.assertEqual(viewer.resolution.factor, 1.0)
        self.assertGreater(viewer.image.height, 4800)
        self.assertAlmostEqual(viewer.view.zoom, 1.0, places=2)
        self.assertIn("100", viewer.toolbar.zoom_label.cget("text"))
        viewer.fit()
        self.assertTrue(viewer.view.fit_mode)

    def test_a_small_photo_needs_no_preview_level(self):
        window = self.open_order_window(self.photos[:1])  # 900×1200 : plus petit que l'aperçu
        viewer = self.show_viewer_on(window, 0)
        self.pump(lambda: viewer.image is not None)
        self.assertTrue(viewer.resolution.is_full)
        self.assertEqual(viewer.resolution.factor, 1.0)

    def test_going_back_to_a_photo_already_seen_is_instant(self):
        window = self.open_order_window(self.photos[:2])
        first = window.model.tiles[1]
        viewer = self.show_viewer_on(window, 1)
        self.pump(lambda: viewer.image is not None and viewer.loader.cache.get(first.source, first.kind, viewer.config_snapshot))
        seen = viewer.loader.cache.get(first.source, first.kind, viewer.config_snapshot)
        viewer.carousel.enabled.set(False)  # pas d'animation : changement direct
        viewer.step(1)
        self.pump(lambda: window.model.selected == 2 and viewer.image is not None and viewer.image is not seen)
        viewer.step(-1)  # retour : l'aperçu net vient du cache, aucun nouveau calcul n'est nécessaire
        self.pump(lambda: window.model.selected == 1 and viewer.image is seen)

    def test_swiping_through_images_never_leaves_a_side_empty_even_for_a_moment(self):
        photos = [make_image(self.dir, f"s{i}.jpg", (1500, 1000)) for i in range(3)]  # 3 paysages : 12 images
        window = self.open_order_window(photos)
        viewer = self.show_viewer_on(window, 2)
        recorded = []
        original_show = viewer.show

        def recording_show(*args, **kwargs):
            original_show(*args, **kwargs)  # dès la fin de la mise en place : y a-t-il une voisine de chaque côté ?
            expected = sum(1 for delta in (-1, 1) if window.viewer_can_step(delta))
            recorded.append((len(viewer.canvas.find_withtag("neigh")), expected, window.model.selected))

        viewer.show = recording_show
        for _ in range(6):
            tile = window.model.selected
            # le temps de regarder la photo : les voisines (et les deux suivantes) sont calculées d'avance
            self.pump(lambda: all(
                viewer.loader.cache.get(window.model.tiles[i].source, window.model.tiles[i].kind, viewer.config_snapshot)
                is not None for i in (tile - 1, tile, tile + 1, tile + 2) if 0 <= i < len(window.model.tiles)))
            viewer.step(1)
            self.pump(lambda: window.model.selected == tile + 1 and not viewer.carousel.animating)
        self.assertEqual(len(recorded), 6)
        for shown, expected, selected in recorded:
            self.assertEqual(shown, expected, f"image {selected} : voisines affichées {shown}/{expected} juste après le défilement")

    def test_every_image_of_the_carousel_is_prepared_in_the_background(self):
        photos = [make_image(self.dir, f"b{i}.jpg", (1500, 1000)) for i in range(3)]  # 12 images
        window = self.open_order_window(photos)
        viewer = self.show_viewer_on(window, 5)

        def everything_ready():
            return all(viewer.loader.cache.get(tile.source, tile.kind, viewer.config_snapshot) is not None
                       for tile in window.model.tiles)

        self.pump(everything_ready, seconds=60)  # pas de limite : même les images éloignées sont prêtes, sans attendre qu'on s'en approche

    def test_as_many_neighbours_as_the_window_can_show_are_drawn(self):
        window = self.open_order_window(self.photos[:2])
        viewer = self.show_viewer_on(window, 1)
        self.pump(lambda: viewer.image is not None)
        with mock.patch.object(viewer, "_view_size", return_value=(2400, 800)):
            self.assertGreaterEqual(viewer._neighbors_in_view(), 3)  # une grande fenêtre : plus de trois photos visibles
        with mock.patch.object(viewer, "_view_size", return_value=(viewer.image.width * viewer.view.zoom + 40, 800)):
            self.assertEqual(viewer._neighbors_in_view(), 1)  # une fenêtre étroite : une de chaque côté, au minimum
        from PIL import Image

        for delta in (-3, -2, -1, 1, 2, 3):
            viewer.carousel.set_neighbor(delta, Image.new("RGB", (300, 400)))
        viewer.view.fit(viewer.image.size, (4000, 800))  # la vue correspond à cette grande fenêtre
        viewer.carousel.redraw(viewer.image, viewer.view, (4000, 800))
        self.assertEqual(len(viewer.canvas.find_withtag("neigh")), 6)  # toutes dessinées, de part et d'autre

    def test_zooming_out_brings_in_more_photos_with_no_fixed_limit(self):
        photos = [make_image(self.dir, f"z{i}.jpg", (1500, 1000)) for i in range(4)]  # 16 images
        window = self.open_order_window(photos)
        viewer = self.show_viewer_on(window, 8)  # au milieu : des images de chaque côté
        self.pump(lambda: viewer.image is not None)
        start = viewer._reach
        for _ in range(10):  # on dézoome : l'image devient toute petite, la fenêtre peut en montrer beaucoup
            viewer.zoom_by(0.7)
        self.assertGreater(viewer._reach, max(start, 6))  # bien plus que les six d'avant
        self.pump(lambda: all(viewer.carousel.neighbors.get(d) is not None
                              for d in range(-min(viewer._reach, 8), min(viewer._reach, 7) + 1) if d != 0), seconds=60)

    def test_the_chosen_zoom_is_kept_when_moving_to_another_image(self):
        photos = [make_image(self.dir, f"k{i}.jpg", (1500, 1000)) for i in range(4)]  # 16 images
        window = self.open_order_window(photos)
        viewer = self.show_viewer_on(window, 8)
        self.pump(lambda: viewer.image is not None)
        for _ in range(6):
            viewer.zoom_by(0.7)  # on dézoome pour voir un ruban de photos
        ratio, reach = viewer.view.ratio, viewer._reach
        self.assertLess(ratio, 0.3)
        self.assertGreater(reach, 3)
        viewer.step(1)  # image suivante : le dézoom ne revient PAS à « ajusté »
        self.pump(lambda: window.model.selected == 9 and not viewer.carousel.animating and viewer.image is not None)
        self.assertAlmostEqual(viewer.view.ratio, ratio, places=2)
        self.assertGreaterEqual(viewer._reach, reach - 1)
        self.pump(lambda: viewer.carousel.neighbors.get(-3) is not None and viewer.carousel.neighbors.get(3) is not None)
        viewer.fit()  # le bouton « Ajuster » remet l'image entière
        self.assertAlmostEqual(viewer.view.ratio, 1.0)

    def test_the_swipe_works_when_zoomed_out_and_the_drag_pans_when_zoomed_in(self):
        photos = [make_image(self.dir, f"w{i}.jpg", (1500, 1000)) for i in range(3)]
        window = self.open_order_window(photos)
        viewer = self.show_viewer_on(window, 5)
        self.pump(lambda: viewer.image is not None)
        for _ in range(3):
            viewer.zoom_by(0.7)
        self.assertFalse(viewer.view.zoomed_in)
        self.swipe(viewer, -int(viewer._slide_distance() * 0.6))  # dézoomé : on fait défiler d'une image
        self.pump(lambda: window.model.selected == 6 and not viewer.carousel.animating)
        viewer.set_zoom(1.0)  # zoomé : le glisser déplace l'image
        self.assertTrue(viewer.view.zoomed_in)
        before, selected = viewer.view.ox, window.model.selected
        self.swipe(viewer, -200)
        self.root.update()
        self.assertEqual(window.model.selected, selected)
        self.assertNotEqual(viewer.view.ox, before)
        viewer.step(1)  # zoomé aussi, on peut passer à l'image suivante en gardant le zoom
        self.pump(lambda: window.model.selected == selected + 1 and viewer.image is not None)
        self.assertTrue(viewer.view.zoomed_in)

    def test_a_neighbour_arriving_redraws_only_the_neighbours(self):
        window = self.open_order_window(self.photos[:2])
        viewer = self.show_viewer_on(window, 1)
        self.pump(lambda: viewer.image is not None and viewer.carousel.neighbors[1] is not None)
        with mock.patch.object(viewer, "redraw") as redraw:
            viewer._neighbor_arrived()
        redraw.assert_not_called()  # l'image affichée n'est pas recréée à l'arrivée d'une voisine
        self.assertGreaterEqual(len(viewer.canvas.find_withtag("neigh")), 1)
    def test_choosing_a_background_colour_changes_the_bands_and_never_the_frame(self):
        from rkarrousel.gui import widgets

        self.app.model.landscape_fill_mode.set("black")
        window = self.open_order_window(self.photos[1:2])
        kinds = [tile.kind for tile in window.tiles]
        viewer = self.show_viewer_on(window, kinds.index("part1_with_sig"))
        self.pump(lambda: viewer.image is not None)
        picker = viewer.panel.fill_group.background

        def pixels():
            image = viewer.image
            return image.getpixel((image.width // 2, image.height // 10)), image.getpixel((1, 1))

        self.assertEqual(pixels(), ((0, 0, 0), (255, 255, 255)))  # bande noire, cadre blanc
        before = viewer.loader.jobs.generation
        with mock.patch.object(widgets.colorchooser, "askcolor", return_value=((255, 0, 0), "#ff0000")):
            picker.choose()
        self.assertEqual(self.app.model.background_color.get(), "#FF0000")
        self.assertEqual(self.app.model.border_color.get(), "#FFFFFF")  # le cadre n'a pas bougé
        self.pump(lambda: viewer.loader.jobs.generation > before and pixels()[0] == (255, 0, 0))
        self.assertEqual(pixels()[1], (255, 255, 255))

    def test_same_colour_for_background_and_frame_is_pointed_out(self):
        group = self.settings_tab.fill
        self.app.model.landscape_fill_mode.set("black")
        self.app.model.background_color.set("#FFFFFF")  # cadre blanc par défaut
        self.assertIn("même couleur", group.same_color.get())
        self.app.model.background_color.set("#FF0000")
        self.assertEqual(group.same_color.get(), "")
        self.app.model.background_color.set("#ffffff")
        self.app.model.no_frame.set(True)  # sans cadre : rien à confondre
        self.assertEqual(group.same_color.get(), "")
        self.app.model.no_frame.set(False)
        self.app.model.landscape_fill_mode.set("blur")  # fond flouté : la couleur du fond uni ne compte pas
        self.assertEqual(group.same_color.get(), "")

    def test_viewer_rerenders_when_the_colour_source_changes(self):

        self.app.model.border_color_mode.set("dominant")
        window = self.open_order_window(self.photos[:1])
        window.select(0)
        viewer = self.show_viewer(window)
        self.pump(lambda: viewer.image is not None)
        self.app.model.color_source.set("edges")
        self.pump(lambda: viewer.loader.jobs.generation >= 2 and viewer.settings_changed and "px" in viewer.info.get())
        self.assertEqual(viewer.config_snapshot["color_source"], "edges")
        self.leave_viewer()

    def test_viewer_steps_through_the_images_with_arrows_and_keys(self):
        from rkarrousel.i18n import kind_label

        window = self.open_order_window(self.photos[:2])  # 1 image + 4 images (paysage) = 5
        window.select(0)
        viewer = self.show_viewer(window)
        self.pump(lambda: viewer.image is not None)
        self.assertEqual(viewer.toolbar.position_label.cget("text"), "1 / 5")
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
        self.assertEqual(viewer.toolbar.position_label.cget("text"), "2 / 5")
        self.assertIn(kind_label(window.model.tiles[1].kind), viewer.caption.get())
        self.pump(lambda: viewer.image is not None and viewer.loader.jobs.generation >= 2)
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
        self.leave_viewer()

    def test_crop_button_is_only_enabled_on_a_crop_tile(self):
        window = self.open_order_window(self.photos[2:3])  # carré : image entière + recadrage
        crop_index = window.model.index_of([t.key for t in window.tiles if t.kind == "crop34"][0])
        window.select(0)
        self.assertTrue(window.crop_btn.instate(["disabled"]))
        window.select(crop_index)
        self.assertTrue(window.crop_btn.instate(["!disabled"]))

    # ------------------------------------------------------------------ préréglages et couleurs de la photo
    def preset_group(self):
        return self.settings_tab.presets

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
        self.assertTrue(self.settings_tab.frame.spin.instate(["disabled"]))
        self.select_preset("photo_color")
        self.assertFalse(model.no_frame.get())
        self.assertEqual((model.border_color_mode.get(), model.background_color_mode.get()), ("light", "dark"))
        self.assertEqual(self.settings_tab.frame.mode.get(), "Photo, version claire")  # la liste affiche la valeur

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
        self.assertEqual(self.settings_tab.format.format_box.get(), "4:5 · Feed Instagram")

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
        frame = self.settings_tab.frame
        self.app.model.border_color_mode.set("fixed")
        self.assertTrue(frame.color.entry.instate(["!disabled"]))
        self.app.model.border_color_mode.set("dominant")
        self.assertTrue(frame.color.entry.instate(["disabled"]))

    def test_processing_with_a_photo_coloured_frame(self):
        from PIL import Image

        red = make_image(self.dir, "r_red.jpg", (900, 1200), (200, 30, 30))
        blue = make_image(self.dir, "s_blue.jpg", (900, 1200), (30, 40, 200))
        self.app.model.border_color_mode.set("dominant")
        self.app.flow.pages["photos"].add_paths([str(red), str(blue)])
        self.run_batch()
        a = Image.open(self.out / "01_r_red_framed.jpg").convert("RGB")
        b = Image.open(self.out / "02_s_blue_framed.jpg").convert("RGB")
        self.assertGreater(a.getpixel((2, a.height // 2))[0], 150)
        self.assertGreater(b.getpixel((2, b.height // 2))[2], 150)


if __name__ == "__main__":
    unittest.main()
