"""Chargement des images de la visionneuse : l'aperçu de l'image affichée (ou sa pleine résolution à la demande), les
aperçus des images voisines pour le carrousel, la préparation d'avance de TOUTES les autres images (petits aperçus, en
arrière-plan, les plus proches d'abord) et l'interrogation régulière des résultats. Les calculs tournent dans des
threads (voir `render_jobs`) et alimentent un cache plafonné en mémoire (voir `preview_cache`)."""
import tkinter as tk
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from PIL import Image

from rkarrousel.gui.order.model import render_signature
from rkarrousel.gui.viewer.carousel import Carousel
from rkarrousel.gui.viewer.preview_cache import PREVIEW, STRIP, PreviewCache
from rkarrousel.gui.viewer.render_jobs import RenderJobs

POLL_MS = 80
MAX_PREFETCH_DISTANCE = 400  # on ne cherche pas plus loin que ça dans la grille


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
        voisine affichée est arrivée."""
        self.widget, self.navigator, self.carousel = widget, navigator, carousel
        self.on_image, self.on_error, self.on_neighbor = on_image, on_error, on_neighbor
        self.jobs = RenderJobs()
        self.cache = PreviewCache()
        self._config: dict = {}
        self._signature = ""
        self._expected: Dict[int, Tuple[Path, str]] = {}  # côté → (photo, type) attendu : une voisine périmée va au cache mais pas à l'écran
        self._inflight: set = set()  # aperçus nets de voisines déjà demandés (pas de doublon)
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

    def launch(self, source: Path, kind: str, config: dict, main: bool, keep_neighbors: bool, full: bool = False,
               reach: int = 1) -> None:
        """Image affichée (si `main`) : depuis le cache, sinon rendue en aperçu, ou en pleine résolution si `full`.
        Voisines affichées (jusqu'à `reach` de chaque côté) : depuis le cache, sinon le petit aperçu de la grille en
        attendant le rendu net ; la suivante de chaque côté est aussi préparée en aperçu net. Toutes les autres images sont préparées en arrière-plan pour le cache : après un
        défilement, la nouvelle voisine est déjà là. `keep_neighbors` garde celles déjà là."""
        self._config = dict(config)
        signature = render_signature(config)
        if signature != self._signature:  # réglages changés : les voisines en cours de calcul sont périmées
            self._signature = signature
            self.jobs.new_epoch()
            self._inflight.clear()
        peeks = {}
        self._expected = {}
        background: List[Tuple[Path, str]] = []
        if self.navigator is not None:
            self._plan_neighbors(config, keep_neighbors, reach, peeks, background)
        cached_main = None if full or not main else self.cache.get(source, kind, config, PREVIEW)
        if cached_main is not None:
            generation = self.jobs.launch(source, kind, config, peeks, main=False) if peeks else self.jobs.next_generation()
            self.widget.after(1, lambda: self._deliver_cached(generation, cached_main))
        elif main or peeks:
            self.jobs.launch(source, kind, dict(config), peeks, main=main, full=full)
        self.jobs.prefetch(config, background)

    def _plan_neighbors(self, config: dict, keep: bool, reach: int, peeks: dict, background: list) -> None:
        """Pour chaque voisine affichée : l'aperçu du cache, sinon un stand-in et une demande de rendu net ; pour toutes les
        autres : un petit aperçu à préparer en arrière-plan (les plus proches d'abord)."""
        for distance in range(1, MAX_PREFETCH_DISTANCE):
            tiles = {delta: self.navigator.viewer_peek(delta) for delta in (-distance, distance)}
            if all(tile is None for tile in tiles.values()):
                break
            for delta, tile in tiles.items():
                shown = distance <= reach
                if tile is None:
                    if shown:
                        self.carousel.set_neighbor(delta, None)
                    continue
                if shown:
                    self._expected[delta] = (tile.source, tile.kind)
                    best = self.cache.get(tile.source, tile.kind, config)
                    if best is not None:
                        self.carousel.set_neighbor(delta, best)  # net, ou petit en attendant (voir plus bas)
                    elif not (keep and self.carousel.neighbors.get(delta) is not None):
                        stand_in = self.grid_preview(tile, config)
                        if stand_in is not None:
                            self.carousel.set_neighbor(delta, stand_in)  # flou, mais tout de suite
                    if self.cache.get(tile.source, tile.kind, config, PREVIEW) is None:
                        key = PreviewCache.key(tile.source, tile.kind, config)
                        if key not in self._inflight:  # l'aperçu net arrive ensuite (sauf s'il est déjà en route)
                            self._inflight.add(key)
                            peeks[delta] = (tile.source, tile.kind)
                elif distance == reach + 1 and self.cache.get(tile.source, tile.kind, config, PREVIEW) is None:
                    key = PreviewCache.key(tile.source, tile.kind, config)  # la prochaine à entrer dans la vue : aperçu net d'avance
                    if key not in self._inflight:
                        self._inflight.add(key)
                        peeks[delta] = (tile.source, tile.kind)
                elif self.cache.get(tile.source, tile.kind, config) is None:
                    background.append((tile.source, tile.kind))

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
                self._neighbor_arrived(*payload)
            elif kind == "strip":
                self._strip_arrived(*payload)
            elif kind == "image" and payload is not None:
                image, full, source, image_kind = payload
                image = image.convert("RGB")
                if not full:
                    self.cache.put(source, image_kind, self._config, image, PREVIEW)
                self.on_image(image, full)
            elif kind == "error":
                self.on_error(payload)
            else:
                self.on_error("?")
        self._job = self.widget.after(POLL_MS, self._poll)

    def _neighbor_arrived(self, delta: int, image: Optional[Image.Image], source: Path, kind: str) -> None:
        self._inflight.discard(PreviewCache.key(source, kind, self._config))
        if image is not None:
            image = image.convert("RGB")
            self.cache.put(source, kind, self._config, image, PREVIEW)  # utile même si l'on a déjà changé d'image
        if self._expected.get(delta) == (source, kind):
            self.carousel.set_neighbor(delta, image)
            self.on_neighbor()

    def _strip_arrived(self, image: Image.Image, source: Path, kind: str) -> None:
        """Un petit aperçu préparé d'avance : il va au cache ; s'il correspond à une voisine déjà affichable mais encore
        vide, il s'affiche tout de suite."""
        self.cache.put(source, kind, self._config, image.convert("RGB"), STRIP)
        for delta, target in self._expected.items():
            if target == (source, kind) and self.carousel.neighbors.get(delta) is None:
                self.carousel.set_neighbor(delta, self.cache.get(source, kind, self._config))
                self.on_neighbor()
