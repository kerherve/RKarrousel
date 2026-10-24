"""Feuilleter les images dans la visionneuse : image précédente / suivante (flèches rondes, touches ← →, glisser),
passage à une autre image sans écran vide, rang dans la grille et bouton « Recadrer… ». Ces méthodes s'ajoutent à
`ViewerView` (elles s'appuient sur son état : image affichée, carrousel, chargeur, panneau de réglages)."""
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from PIL import Image

from rkarrousel.gui.viewer.carousel import CAROUSEL_GAP
from rkarrousel.gui.viewer.render_jobs import PREVIEW_SIDE
from rkarrousel.i18n import t
from rkarrousel.kinds import KIND_CROP


class BrowsingMixin:
    def activate(self) -> None:
        """L'étape devient visible : ← et → feuillettent les images."""
        if self.navigator is None or self._keys:
            return
        top = self.winfo_toplevel()
        self._keys = [("<Left>", top.bind("<Left>", lambda e: self._key_step(-1), add="+")),
                      ("<Right>", top.bind("<Right>", lambda e: self._key_step(1), add="+"))]

    def deactivate(self) -> None:
        """L'étape est quittée : les touches ← et → ne sont plus à nous."""
        top = self.winfo_toplevel()
        for sequence, _ in self._keys:
            top.unbind(sequence)
        self._keys = []

    # ------------------------------------------------------------------ navigation entre les images
    def _slide_distance(self) -> float:
        """Écart entre deux images du carrousel, en pixels écran."""
        if self.image is None:
            return float(self._view_size()[0])
        return self.image.width * self.view.zoom * (1 + CAROUSEL_GAP)

    def _update_crop_button(self) -> None:
        self.toolbar.set_crop_enabled(self.kind == KIND_CROP)

    def _open_crop(self) -> None:
        """« Recadrer… » : le même éditeur que dans la grille ; l'image se recalcule une fois le cadrage validé."""
        if self.navigator is not None and self.kind == KIND_CROP:
            self.navigator.viewer_crop(self, self._recalculate)

    def _update_position(self) -> None:
        if self.navigator is None:
            return
        self.toolbar.set_position(*self.navigator.viewer_position())

    def _key_step(self, delta: int) -> None:
        """Flèches du clavier : on n'intercepte pas la frappe quand on édite un champ du panneau de réglages."""
        try:
            focused = self.focus_get()
        except (KeyError, tk.TclError):
            focused = None
        if isinstance(focused, (tk.Entry, ttk.Entry, tk.Spinbox, ttk.Spinbox, ttk.Combobox)):
            return
        self.step(delta)

    def step(self, delta: int) -> None:
        """Image suivante (+1) ou précédente (-1) : en carrousel, elle arrive en glissant."""
        if self.carousel.animating or not self.carousel.can_step(delta):
            return
        if (self.carousel.enabled.get() and not self.view.zoomed_in and self.image is not None
                and self.carousel.neighbors.get(delta) is not None):
            self.carousel.step(delta)
            return
        tile = self.navigator.viewer_step(delta)
        if tile is not None:
            self.show(tile.source, tile.kind, placeholder=self.loader.preview(tile, self.config_snapshot))

    def _commit_step(self, delta: int) -> None:
        """Le glissement est terminé : l'image voisine devient l'image affichée, sans passer par un écran vide."""
        old, incoming = self.image, self.carousel.neighbors.get(delta)
        tile = self.navigator.viewer_step(delta)
        if tile is None:
            self.carousel.reset()
            return
        incoming = incoming or self.loader.preview(tile, self.config_snapshot)
        behind = None
        if old is not None:
            behind = old  # un aperçu est déjà petit : on le réutilise tel quel (et déjà redimensionné pour l'écran)
            if old.width > PREVIEW_SIDE * 1.3 or old.height > PREVIEW_SIDE * 1.3:  # pleine résolution : version réduite
                behind = old.copy()
                behind.thumbnail((PREVIEW_SIDE, PREVIEW_SIDE), Image.Resampling.BILINEAR)
        self.show(tile.source, tile.kind, placeholder=incoming, behind=(-delta, behind))

    def show(self, source: Path, kind: str, placeholder=None, behind=None) -> None:
        """Affiche une autre image dans la même fenêtre (zoom et règle repartent de zéro). `placeholder` : aperçu réduit
        montré en attendant la pleine résolution ; `behind` : (côté, image réduite) de l'image qu'on vient de quitter."""
        self._rerender.cancel()
        self._main_delay.cancel()
        self.source, self.kind = source, kind
        self.caption.set(self._caption())
        self.image = self.photo = None
        self.loaded_once = False
        self.pan = None
        self.carousel.reset(behind)
        self.ruler.clear()
        self.canvas.delete("img", "neigh")
        self.measure.set(t("viewer_hint"))
        self.info.set(t("viewer_loading"))
        self.resolution.reset()
        self._kept_ratio = self.view.ratio  # le zoom choisi (dézoomé, ajusté, zoomé) est gardé pour la nouvelle image
        self.placeholder = placeholder is not None
        if placeholder is not None:
            self.image = placeholder
            self.loaded_once = True
            self._place_image()
        if self.ctx is not None:
            self.config_snapshot = dict(self.ctx.collect_config())
        if self.panel is not None:
            self.panel.set_source(source)
            self.panel.apply_features(self._features())
        self._launch(main=False, keep_neighbors=True)  # voisines tout de suite (cache, ou aperçus de la grille)
        self._neighbor_arrived()  # et on les montre dans le même mouvement : pas d'image qui disparaît puis réapparaît
        if self.loader.cache.get(source, kind, self.config_snapshot) is not None:
            self._launch_main()  # déjà calculé : on l'affiche sans attendre
        else:
            self._main_delay.trigger()  # sinon une fois qu'on s'arrête
        self._update_position()
        self._update_crop_button()
        self.carousel.draw_arrows(self._view_size())

    def _launch_main(self) -> None:
        if not self._closing:
            self._launch(main=True, keep_neighbors=True)
