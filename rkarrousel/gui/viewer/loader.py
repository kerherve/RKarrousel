"""Chargement des images de la visionneuse : l'image affichée en pleine résolution, ses voisines pour le carrousel, et
l'interrogation régulière des résultats (les calculs tournent dans des threads, voir `render_jobs`)."""
import tkinter as tk
from pathlib import Path
from typing import Callable, Optional

from PIL import Image

from rkarrousel.gui.viewer.carousel import Carousel
from rkarrousel.gui.viewer.render_jobs import RenderJobs

POLL_MS = 80


class ImageLoader:
    def __init__(
        self,
        widget: tk.Misc,
        navigator,
        carousel: Carousel,
        on_image: Callable[[Image.Image], None],
        on_error: Callable[[str], None],
        on_neighbor: Callable[[], None],
    ):
        """`on_image(image)` : l'image affichée est prête ; `on_error(message)` ; `on_neighbor()` : une voisine est arrivée."""
        self.widget, self.navigator, self.carousel = widget, navigator, carousel
        self.on_image, self.on_error, self.on_neighbor = on_image, on_error, on_neighbor
        self.jobs = RenderJobs()
        self._job: Optional[str] = None
        self._closed = False

    def preview(self, tile, config: dict) -> Optional[Image.Image]:
        """Aperçu de `tile` déjà calculé par la grille (instantané), ou None s'il n'est pas à jour."""
        if self.navigator is None:
            return None
        image = self.navigator.viewer_preview(tile, config)
        return image.convert("RGB") if image is not None else None

    def launch(self, source: Path, kind: str, config: dict, main: bool, keep_neighbors: bool) -> None:
        """Voisines du carrousel : aperçus de la grille s'ils sont à jour (instantané), sinon rendu réduit en tâche de
        fond. Image affichée (si `main`) : rendu en pleine résolution. `keep_neighbors` garde celles déjà là."""
        peeks = {}
        if self.navigator is not None:
            for delta in (-1, 1):
                tile = self.navigator.viewer_peek(delta)
                if tile is None:
                    self.carousel.set_neighbor(delta, None)
                elif keep_neighbors and self.carousel.neighbors.get(delta) is not None:
                    continue
                elif (preview := self.preview(tile, config)) is not None:
                    self.carousel.set_neighbor(delta, preview)
                else:
                    peeks[delta] = (tile.source, tile.kind)
        if main or peeks:
            self.jobs.launch(source, kind, dict(config), peeks, main=main)

    def start_polling(self) -> None:
        self._job = self.widget.after(POLL_MS, self._poll)

    def close(self) -> None:
        self._closed = True
        if self._job is not None:
            try:
                self.widget.after_cancel(self._job)
            except tk.TclError:
                pass
        self.jobs.close()

    def _poll(self) -> None:
        if self._closed:
            return
        for kind, payload in self.jobs.drain():
            if kind == "neighbor":
                delta, image = payload
                self.carousel.set_neighbor(delta, image.convert("RGB") if image is not None else None)
                self.on_neighbor()
            elif kind == "image" and payload is not None:
                self.on_image(payload.convert("RGB"))
            elif kind == "error":
                self.on_error(payload)
            else:
                self.on_error("?")
        self._job = self.widget.after(POLL_MS, self._poll)
