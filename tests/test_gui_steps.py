"""Le flux dans la vraie fenêtre : boutons « Précédent » / « Suivant », bandeau d'étapes, traitement, langue."""
import gc
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, Path(__file__).resolve().parent.parent.as_posix())

from tests.helpers import make_image

try:
    import tkinter as tk

    tk.Tk().destroy()
    HAVE_DISPLAY = True
except Exception:  # pas d'écran (CI Linux) : ces tests sont ignorés
    HAVE_DISPLAY = False


@unittest.skipUnless(HAVE_DISPLAY, "pas d'affichage graphique")
class FlowTests(unittest.TestCase):
    def setUp(self):
        from rkarrousel.gui.app import PhotoSplitterGUI
        from rkarrousel.gui.system import create_root

        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        config = self.dir / "config.json"
        config.write_text(json.dumps({"theme": "light", "update_check": False, "last_dest_dir": ""}))
        self.root = create_root()
        self.app = PhotoSplitterGUI(self.root, config_path=config)
        self.flow = self.app.flow
        self.photo = make_image(self.dir, "a.jpg", (900, 1200))
        self.land = make_image(self.dir, "b.jpg", (1500, 1000))

    def tearDown(self):
        self.root.destroy()
        self.tmp.cleanup()
        self.app = self.flow = self.root = None
        gc.collect()

    def pump(self, until, seconds=20):
        end = time.time() + seconds
        while time.time() < end and not until():
            self.root.update()
            self.app.ctx.bus.dispatch_pending()
            time.sleep(0.02)
        self.assertTrue(until())

    def ready(self, *photos):
        """Des photos et un dossier de destination : le flux peut avancer."""
        self.flow.pages["photos"].add_paths([str(p) for p in (photos or (self.photo,))])
        self.app.ctx.model.dest_dir.set(str(self.dir / "out"))
        self.root.update()

    def test_starts_on_photos_with_next_disabled_and_the_reason(self):
        self.assertEqual(self.flow.index, 0)
        self.assertIn("disabled", self.flow.nav.next_button.state())
        self.assertIn("disabled", self.flow.nav.previous_button.state())
        self.assertIn("photo", self.flow.nav.hint.cget("text"))
        self.flow.next()  # sans effet tant que c'est bloqué
        self.assertEqual(self.flow.index, 0)

    def test_next_and_previous_walk_through_the_four_steps(self):
        self.ready()
        for expected in (1, 2, 3):
            self.flow.next()
            self.root.update()
            self.assertEqual(self.flow.index, expected)
        self.assertIn("Lancer", self.flow.nav.next_button.cget("text"))  # la dernière étape lance le traitement
        for expected in (2, 1, 0):
            self.flow.previous()
            self.assertEqual(self.flow.index, expected)
        self.assertNotIn("Lancer", self.flow.nav.next_button.cget("text"))

    def test_last_step_next_starts_the_processing(self):
        self.ready()
        self.flow.go(3)
        with mock.patch.object(self.app.batch, "start") as start:
            self.flow.next()
        start.assert_called_once()

    def test_clicking_a_reachable_step_in_the_stepper_jumps_there_and_builds_the_grid(self):
        self.ready()
        self.assertIsNone(self.flow.order_view)
        self.flow.stepper._click(3)  # directement à l'export : la grille est quand même calculée
        self.assertEqual(self.flow.index, 3)
        self.assertIsNotNone(self.flow.order_view)
        self.assertIn("image(s) à produire", self.flow.pages["export"].recap_text.get())

    def test_steps_are_not_reachable_without_photos(self):
        self.flow.stepper._click(2)
        self.assertEqual(self.flow.index, 0)

    def test_excluding_everything_blocks_the_following_steps(self):
        self.ready(self.land)
        self.flow.go(1)
        view = self.flow.order_view
        self.pump(lambda: view.model.counts()[1] == view.model.counts()[0])
        for index in range(len(view.tiles)):
            view.select(index)
            view.toggle_exclude()
        self.root.update()
        self.assertEqual(self.flow.last_reachable(), 1)
        self.assertIn("disabled", self.flow.nav.next_button.state())
        self.assertIn("Ordre", self.flow.nav.hint.cget("text"))
        view.select(0)
        view.toggle_exclude()  # une image est réintégrée : on peut avancer
        self.assertEqual(self.flow.last_reachable(), 3)

    def test_the_adjust_step_says_so_when_there_is_nothing_to_adjust(self):
        self.ready()
        self.flow.go(1)
        view = self.flow.order_view
        self.pump(lambda: view.model.counts()[1] == view.model.counts()[0])
        self.flow.go(2)
        self.assertIsNotNone(self.flow.pages["adjust"].viewer)
        self.flow.go(1)
        for index in range(len(view.tiles)):  # tout exclure puis forcer l'accès : message vide, pas de plantage
            view.select(index)
            view.toggle_exclude()
        self.flow.pages["adjust"].on_show()
        self.assertTrue(self.flow.pages["adjust"].empty.winfo_ismapped() or self.flow.pages["adjust"].empty.winfo_manager())

    def test_during_processing_only_cancel_remains_and_navigation_is_locked(self):
        self.ready()
        self.flow.go(3)
        self.app.ctx.set_processing(True)
        self.root.update()
        self.assertTrue(self.flow.nav.cancel_button.winfo_ismapped())
        self.assertFalse(self.flow.nav.next_button.winfo_ismapped())
        self.flow.go(0)
        self.assertEqual(self.flow.index, 3)  # pas de changement d'étape pendant un traitement
        self.flow.stepper._click(1)
        self.assertEqual(self.flow.index, 3)
        self.app.ctx.set_processing(False)
        self.root.update()
        self.assertFalse(self.flow.nav.cancel_button.winfo_ismapped())
        self.assertTrue(self.flow.nav.next_button.winfo_ismapped())

    def test_changing_the_language_keeps_the_current_step(self):
        self.ready()
        self.flow.go(1)
        self.app.change_language(1)
        self.root.update()
        self.assertEqual(self.app.flow.index, 1)
        self.assertIn("Order", self.app.flow.stepper.labels[1].cget("text"))

    def test_preferences_open_once_and_close_on_rebuild(self):
        self.app.show_preferences()
        first = self.app.preferences
        self.app.show_preferences()
        self.assertIs(self.app.preferences, first)
        self.app.change_theme(2)
        self.root.update()
        self.assertFalse(first.winfo_exists())

    def test_going_back_keeps_the_selected_image_and_the_order(self):
        self.ready(self.land)
        self.flow.go(1)
        view = self.flow.order_view
        self.pump(lambda: view.model.counts()[1] == view.model.counts()[0])
        view.select(2)
        key = view.model.tiles[2].key
        self.flow.go(2)
        self.flow.go(1)
        self.assertEqual(view.model.selected_tile().key, key)
        self.assertEqual(self.app.ctx.session.order[2], key)


if __name__ == "__main__":
    unittest.main()
