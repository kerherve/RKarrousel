"""Carrousel façon post Instagram : l'image affichée est entourée de sa précédente et de sa suivante, et on les fait
défiler à la souris (glisser), aux flèches rondes ou au clavier, avec une animation qui décélère."""
import time
import tkinter as tk
from typing import Callable, Optional

from PIL import Image, ImageTk

from rkarrousel.gui.viewer.viewport import Viewport

SLIDE_MS = 260          # durée de l'animation de défilement
SLIDE_FRAME_MS = 15
SWIPE_FRACTION = 0.22   # part de la largeur à franchir pour passer à l'image voisine
SWIPE_MIN_FLICK = 0.08  # un coup de pouce rapide doit quand même parcourir cette part de la largeur
SWIPE_VELOCITY = 700    # ou vitesse (pixels par seconde) d'un coup de pouce rapide
RESISTANCE = 0.25       # en bout de carrousel, l'image ne suit le doigt que d'un quart
CAROUSEL_GAP = 0.02     # écart entre deux images, en fraction de la largeur
MAX_NEIGHBOR_DISPLAY = 2600  # au-delà (zoom fort), on ne dessine plus les voisines


def swipe_decision(slide_px: float, distance: float, velocity: float, can_prev: bool, can_next: bool) -> int:
    """Image à afficher après un glisser relâché à `slide_px` : +1 (suivante), -1 (précédente) ou 0 (on revient).
    Il faut franchir une part de la largeur, ou donner un coup de pouce assez rapide qui parcourt un minimum."""
    delta = 0
    if slide_px < 0 and can_next:
        delta = 1
    elif slide_px > 0 and can_prev:
        delta = -1
    if not delta:
        return 0
    moved = abs(slide_px)
    flick = velocity * -delta > SWIPE_VELOCITY and moved > SWIPE_MIN_FLICK * distance
    return delta if moved > SWIPE_FRACTION * distance or flick else 0


class Carousel:
    """Dessine les voisines sur le canevas (étiquette « neigh ») et gère le défilement horizontal de l'ensemble
    (« img » et « neigh »). `navigator` donne les voisines ; `on_commit(delta)` est appelé quand un défilement aboutit."""

    def __init__(self, canvas: tk.Canvas, navigator, scale: float, get_distance: Callable[[], float],
                 on_commit: Callable[[int], None]):
        self.canvas, self.navigator, self.scale = canvas, navigator, scale
        self.get_distance, self.on_commit = get_distance, on_commit
        self.enabled = tk.BooleanVar(master=canvas, value=True)  # case « Aperçu carrousel »
        self.neighbors = {-1: None, 1: None}  # images voisines (PIL)
        self.slide_px = 0.0                   # décalage horizontal actuel
        self.animating = False
        self._photos = {}                     # voisine → (taille, image Tk) : évite de redimensionner à chaque dessin
        self._swipe: Optional[dict] = None
        self._closing = False

    # ------------------------------------------------------------------ état
    def reset(self, behind=None) -> None:
        """Nouvelle image affichée : plus de décalage, voisines à recharger. `behind` : (côté, image) de celle qu'on
        quitte, qui reste visible de l'autre côté en attendant le rendu des voisines."""
        self.neighbors = {-1: None, 1: None}
        self._photos = {}
        self.slide_px = 0.0
        self._swipe = None
        if behind is not None and behind[1] is not None:
            self.neighbors[behind[0]] = behind[1]

    def set_neighbor(self, delta: int, image: Optional[Image.Image]) -> None:
        self.neighbors[delta] = image
        self._photos.pop(delta, None)

    def can_step(self, delta: int) -> bool:
        return self.navigator is not None and self.navigator.viewer_can_step(delta)

    def close(self) -> None:
        self._closing = True

    # ------------------------------------------------------------------ dessin
    def draw(self, image: Optional[Image.Image], view: Viewport, view_size) -> None:
        """Les images voisines, de part et d'autre de l'image affichée (au même zoom, avec un petit écart)."""
        if self.navigator is None or not self.enabled.get() or image is None:
            return
        iw, _ = image.size
        if iw * view.zoom > MAX_NEIGHBOR_DISPLAY:
            return
        vw, vh = view_size
        gap = iw * CAROUSEL_GAP
        for delta in (-1, 1):
            neighbor = self.neighbors.get(delta)
            if neighbor is None:
                continue
            dw = max(1, int(round(iw * view.zoom)))
            dh = max(1, int(round(dw * neighbor.height / neighbor.width)))
            x = ((-(gap + iw) if delta < 0 else iw + gap) - view.ox) * view.zoom + self.slide_px
            y = -view.oy * view.zoom
            if x + dw < 0 or x > vw or y + dh < 0 or y > vh:
                continue  # hors de la zone visible
            cached = self._photos.get(delta)
            if cached is None or cached[0] != (dw, dh):
                cached = ((dw, dh), ImageTk.PhotoImage(neighbor.resize((dw, dh), Image.Resampling.BILINEAR)))
                self._photos[delta] = cached
            self.canvas.create_image(x, y, anchor=tk.NW, image=cached[1], tags="neigh")
        self.canvas.tag_lower("neigh")

    def draw_arrows(self, view_size) -> None:
        """Flèches rondes sur les bords gauche et droit : précédente / suivante (absentes aux extrémités)."""
        canvas = self.canvas
        canvas.delete("nav")
        if self.navigator is None:
            return
        vw, vh = view_size
        s = self.scale
        radius = int(24 * s)
        for delta, tag, x, symbol in ((-1, "nav_prev", radius + int(10 * s), "‹"),
                                       (1, "nav_next", vw - radius - int(10 * s), "›")):
            if not self.can_step(delta):
                continue
            y = vh // 2
            canvas.create_oval(x - radius, y - radius, x + radius, y + radius, fill="#202020", outline="#9a9a9a",
                               width=2, tags=("nav", tag))
            canvas.create_text(x, y - int(3 * s), text=symbol, fill="#ffffff", font=("Segoe UI", int(24 * s), "bold"),
                               tags=("nav", tag))
        canvas.tag_raise("nav")
        for tag in ("nav_prev", "nav_next"):
            canvas.tag_bind(tag, "<Enter>", lambda e: canvas.configure(cursor="hand2"))
            canvas.tag_bind(tag, "<Leave>", lambda e: canvas.configure(cursor="fleur"))

    # ------------------------------------------------------------------ défilement
    def _set_slide(self, value: float) -> None:
        """Décale l'ensemble sans le redessiner : on déplace les éléments du canevas."""
        self.canvas.move("img", value - self.slide_px, 0)
        self.canvas.move("neigh", value - self.slide_px, 0)
        self.slide_px = value

    def begin_swipe(self, x: int) -> bool:
        """Début d'un glisser à la souris. Renvoie False pendant une animation (le geste est ignoré)."""
        if self.animating:
            return False
        self._swipe = {"x0": x, "last": (x, time.monotonic()), "velocity": 0.0}
        return True

    @property
    def swiping(self) -> bool:
        return self._swipe is not None

    def swipe_move(self, x: int) -> None:
        swipe = self._swipe
        dx = x - swipe["x0"]
        if dx and not self.can_step(1 if dx < 0 else -1):  # glisser vers la gauche montre la suivante
            dx *= RESISTANCE  # pas d'image de ce côté : résistance, comme en bout de carrousel
        limit = self.get_distance()
        self._set_slide(max(-limit, min(limit, dx)))
        now = time.monotonic()
        last_x, last_t = swipe["last"]
        if now - last_t > 0.01:
            swipe["velocity"] = (x - last_x) / (now - last_t)
            swipe["last"] = (x, now)

    def end_swipe(self) -> None:
        """Relâchement : on passe à l'image voisine (animation) ou on revient en place."""
        swipe, self._swipe = self._swipe, None
        if swipe is None:
            return
        distance = self.get_distance()
        delta = swipe_decision(self.slide_px, distance, swipe["velocity"], self.can_step(-1), self.can_step(1))
        if delta:
            self.animate(-delta * distance, lambda: self.on_commit(delta))
        else:
            self.animate(0.0, None)

    def step(self, delta: int) -> None:
        """Passe à la voisine en glissant (flèche ou clavier)."""
        self.animate(-delta * self.get_distance(), lambda: self.on_commit(delta))

    def animate(self, target: float, done: Optional[Callable[[], None]]) -> None:
        """Fait glisser l'ensemble jusqu'à `target` (décélération), puis appelle `done`."""
        start, began = self.slide_px, time.monotonic()
        self.animating = True

        def frame() -> None:
            if self._closing:
                return
            progress = min(1.0, (time.monotonic() - began) * 1000 / SLIDE_MS)
            eased = 1 - (1 - progress) ** 3
            self._set_slide(start + (target - start) * eased)
            if progress < 1.0:
                self.canvas.after(SLIDE_FRAME_MS, frame)
            else:
                self.animating = False
                if done is not None:
                    done()

        frame()
