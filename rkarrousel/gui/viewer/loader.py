"""Chargement des images de la visionneuse : l'aperçu de l'image affichée (ou sa pleine résolution à la demande), les
aperçus de ses voisines pour le carrousel, un cache des aperçus déjà calculés et l'interrogation régulière des résultats
(les calculs tournent dans des threads, voir `render_jobs`)."""
import tkinter as tk
from collections import OrderedDict
from pathlib import Path
from typing import Callable, Optional

from PIL import Image

from rkarrousel.gui.order.model import cache_key, render_signature
from rkarrousel.gui.viewer.carousel import Carousel
from rkarrousel.gui.viewer.render_jobs import RenderJobs
from rkarrousel.outputs import item_key

POLL_MS = 80
CACHE_SIZE = 10  # aperçus gardés en mémoire (≈ 13 Mo chacun) : revenir en arrière est instantané
PREFETCH = (-1, 1, -2, 2)  # voisines préparées d'avance : les deux premières s'affichent, les autres attendent dans le cache


class PreviewCache:
    """Aperçus déjà calculés, les plus récemment utilisés d'abord ; une clé change dès qu'un réglage qui influe sur le rendu
    change (voir `render_signature`)."""

    def __init__(self, size: int = CACHE_SIZE):
        self.size = size
        self._items: "OrderedDict[str, Image.Image]" = OrderedDict()

    @staticmethod
    def key(source: Path, kind: str, config: dict) -> str:
        return f"{cache_key(item_key(source, kind), source, config)}|{render_signature(config)}"

    def get(self, source: Path, kind: str, config: dict) -> Optional[Image.Image]:
        key = self.key(source, kind, config)
        image = self._items.get(key)
        if image is not None:
            self._items.move_to_end(key)
        return image

    def put(self, source: Path, kind: str, config: dict, image: Image.Image) -> None:
        key = self.key(source, kind, config)
        self._items[key] = image
        self._items.move_to_end(key)
        while len(self._items) > self.size:
            self._items.popitem(last=False)

    def __len__(self) -> int:
        return len(self._items)


class ImageLoader:
    def __init__(
        self,
        widget: tk.Misc,
        navigator,
        carousel: Carousel,
        on_image: Callable[[Image.Image, bool], None],
        on_error: Callable[[str], None],
        on_neighbor: Callable[[], None],
    ):
        """`on_image(image, pleine_résolution)` : l'image affichée est prête ; `on_error(message)` ; `on_neighbor()` : une
        voisine est arrivée."""
        self.widget, self.navigator, self.carousel = widget, navigator, carousel
        self.on_image, self.on_error, self.on_neighbor = on_image, on_error, on_neighbor
        self.jobs = RenderJobs()
        self.cache = PreviewCache()
        self._config: dict = {}
        self._signature = ""
        self._expected: dict = {}   # côté → (photo, type) attendu : une voisine périmée va au cache mais pas à l'écran
        self._inflight: set = set()  # aperçus de voisines déjà demandés (pas de doublon)
        self._job: Optional[str] = None
        self._closed = False

    def grid_preview(self, tile, config: dict) -> Optional[Image.Image]:
        """Petit aperçu déjà calculé par la grille (instantané mais peu défini), ou None s'il n'est pas à jour."""
        if self.navigator is None:
            return None
        image = self.navigator.viewer_preview(tile, config)
        return image.convert("RGB") if image is not None else None

    def preview(self, tile, config: dict) -> Optional[Image.Image]:
        """Le meilleur aperçu immédiatement disponible pour `tile` : celui du cache, sinon celui de la grille."""
        cached = self.cache.get(tile.source, tile.kind, config)
        return cached if cached is not None else self.grid_preview(tile, config)

    def launch(self, source: Path, kind: str, config: dict, main: bool, keep_neighbors: bool, full: bool = False) -> None:
        """Image affichée (si `main`) : depuis le cache, sinon rendue en aperçu, ou en pleine résolution si `full`.
        Voisines du carrousel (±1) : depuis le cache, sinon le petit aperçu de la grille en attendant le rendu net. Les
        deux suivantes (±2) sont préparées d'avance pour le cache : après un défilement, la nouvelle voisine est déjà là.
        `keep_neighbors` garde celles déjà là."""
        self._config = dict(config)
        signature = render_signature(config)
        if signature != self._signature:  # réglages changés : les voisines en cours de calcul sont périmées
            self._signature = signature
            self.jobs.new_epoch()
            self._inflight.clear()
        peeks = {}
        self._expected = {}
        if self.navigator is not None:
            for delta in PREFETCH:
                tile = self.navigator.viewer_peek(delta)
                shown = abs(delta) == 1  # ±1 : à l'écran ; ±2 : seulement dans le cache
                if tile is None:
                    if shown:
                        self.carousel.set_neighbor(delta, None)
                    continue
                if shown:
                    self._expected[delta] = (tile.source, tile.kind)
                cached = self.cache.get(tile.source, tile.kind, config)
                if cached is not None:
                    if shown:
                        self.carousel.set_neighbor(delta, cached)
                    continue
                if shown:
                    keep = keep_neighbors and self.carousel.neighbors.get(delta) is not None
                    stand_in = None if keep else self.grid_preview(tile, config)
                    if stand_in is not None:
                        self.carousel.set_neighbor(delta, stand_in)  # flou, mais tout de suite
                key = PreviewCache.key(tile.source, tile.kind, config)
                if key not in self._inflight:  # l'aperçu net arrive ensuite (sauf s'il est déjà en route)
                    self._inflight.add(key)
                    peeks[delta] = (tile.source, tile.kind)
        cached_main = None if full or not main else self.cache.get(source, kind, config)
        if cached_main is not None:
            generation = self.jobs.launch(source, kind, config, peeks, main=False) if peeks else self.jobs.next_generation()
            self.widget.after(1, lambda: self._deliver_cached(generation, cached_main))
        elif main or peeks:
            self.jobs.launch(source, kind, dict(config), peeks, main=main, full=full)

    def _deliver_cached(self, generation: int, image: Image.Image) -> None:
        if not self._closed and generation == self.jobs.generation:
            self.on_image(image, False)

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
                delta, image, source, neighbor_kind = payload
                self._inflight.discard(PreviewCache.key(source, neighbor_kind, self._config))
                if image is not None:
                    image = image.convert("RGB")
                    self.cache.put(source, neighbor_kind, self._config, image)  # utile même si l'on a déjà changé d'image
                if abs(delta) == 1 and self._expected.get(delta) == (source, neighbor_kind):
                    self.carousel.set_neighbor(delta, image)
                    self.on_neighbor()
            elif kind == "image" and payload is not None:
                image, full, source, image_kind = payload
                image = image.convert("RGB")
                if not full:
                    self.cache.put(source, image_kind, self._config, image)
                self.on_image(image, full)
            elif kind == "error":
                self.on_error(payload)
            else:
                self.on_error("?")
        self._job = self.widget.after(POLL_MS, self._poll)
