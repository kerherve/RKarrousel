"""Zoom et déplacement d'une image dans une fenêtre : de simples nombres, sans aucune dépendance graphique."""
import math
from typing import Optional, Tuple

MIN_SCALE = 0.02
MAX_SCALE = 32.0
ZOOM_STEP = 1.25

Size = Tuple[int, int]
Box = Tuple[int, int, int, int]


class Viewport:
    """Échelle (`zoom`) et coin haut-gauche (`ox`, `oy`, en pixels de l'image) de la zone visible.
    `fit_mode` : l'image entière est ajustée à la fenêtre (elle suit alors les redimensionnements)."""

    def __init__(self):
        self.zoom = 1.0
        self.ox = 0.0
        self.oy = 0.0
        self.fit_mode = True

    def fit(self, image_size: Size, view_size: Size) -> None:
        """Ajuste l'image entière à la fenêtre, centrée."""
        iw, ih = image_size
        vw, vh = view_size
        self.fit_mode = True
        self.zoom = min(MAX_SCALE, max(MIN_SCALE, min(vw / iw, vh / ih)))
        self.ox = iw / 2 - vw / (2 * self.zoom)
        self.oy = ih / 2 - vh / (2 * self.zoom)

    def zoom_at(self, cx: float, cy: float, factor: float) -> bool:
        """Zoome autour du point écran (cx, cy), qui reste fixe. Renvoie False si l'échelle n'a pas changé (limites)."""
        new_zoom = min(MAX_SCALE, max(MIN_SCALE, self.zoom * factor))
        if new_zoom == self.zoom:
            return False
        ix, iy = self.ox + cx / self.zoom, self.oy + cy / self.zoom
        self.zoom = new_zoom
        self.ox, self.oy = ix - cx / new_zoom, iy - cy / new_zoom
        self.fit_mode = False
        return True

    def zoom_to(self, zoom: float, view_size: Size) -> bool:
        """Passe à l'échelle `zoom` (1 = 100 %) en gardant le centre de la fenêtre fixe."""
        vw, vh = view_size
        return self.zoom_at(vw / 2, vh / 2, zoom / self.zoom)

    def pan_to(self, ox: float, oy: float) -> None:
        self.ox, self.oy = ox, oy
        self.fit_mode = False

    def visible_box(self, image_size: Size, view_size: Size) -> Optional[Box]:
        """Partie de l'image visible dans la fenêtre (pixels entiers, rognée aux limites de l'image), ou None."""
        iw, ih = image_size
        vw, vh = view_size
        left, top = max(0.0, self.ox), max(0.0, self.oy)
        right, bottom = min(float(iw), self.ox + vw / self.zoom), min(float(ih), self.oy + vh / self.zoom)
        if right - left < 1e-6 or bottom - top < 1e-6:
            return None
        return int(math.floor(left)), int(math.floor(top)), int(math.ceil(right)), int(math.ceil(bottom))
