"""Géométrie de la grille de vignettes (aucune dépendance graphique : uniquement des nombres)."""
from typing import Optional, Tuple

MIN_COLUMNS = 3  # comme la grille d'un profil Instagram ; une fenêtre plus large en affiche davantage
BASE_TILE_W = 210
BASE_GAP = 4


class GridLayout:
    """Positions des vignettes, à l'échelle de l'écran. La taille d'une vignette ne change pas : agrandir la fenêtre
    ajoute des colonnes (`fit_width`), pour voir plus d'images à la fois et les ordonner à sa guise. L'ordre se lit
    de gauche à droite, ligne après ligne."""

    def __init__(self, scale: float, target: Tuple[int, int]):
        tw, th = target  # les vignettes ont le format de sortie choisi
        self.scale = scale
        self.tile_w = int(BASE_TILE_W * scale)
        self.tile_h = int(BASE_TILE_W * scale * th / tw)
        self.gap = max(2, int(BASE_GAP * scale))
        self.columns = MIN_COLUMNS

    def fit_width(self, width: int) -> bool:
        """Nombre de colonnes qui tiennent dans `width` pixels (au moins trois). Renvoie True s'il a changé."""
        columns = max(MIN_COLUMNS, (width - self.gap) // (self.tile_w + self.gap))
        if columns == self.columns:
            return False
        self.columns = columns
        return True

    @property
    def canvas_width(self) -> int:
        return self.columns * self.tile_w + (self.columns + 1) * self.gap

    def content_height(self, count: int) -> int:
        rows = (count + self.columns - 1) // self.columns
        return max(self.gap + rows * (self.tile_h + self.gap), 1)

    def slot_origin(self, index: int) -> Tuple[int, int]:
        col, row = index % self.columns, index // self.columns
        return self.gap + col * (self.tile_w + self.gap), self.gap + row * (self.tile_h + self.gap)

    def tile_at(self, x: float, y: float, count: int) -> Optional[int]:
        """Indice de la vignette sous le point (x, y), ou None."""
        col = int((x - self.gap) // (self.tile_w + self.gap))
        row = int((y - self.gap) // (self.tile_h + self.gap))
        if not 0 <= col < self.columns or row < 0:
            return None
        index = row * self.columns + col
        return index if index < count else None

    def slot_at(self, x: float, y: float, count: int) -> int:
        """Emplacement le plus proche du point (x, y), borné à la grille (cible d'un glisser-déposer)."""
        col = min(self.columns - 1, max(0, int((x - self.gap) // (self.tile_w + self.gap))))
        row = max(0, int((y - self.gap) // (self.tile_h + self.gap)))
        return min(count - 1, row * self.columns + col)

    def cross_rect(self, x: int, y: int) -> Tuple[int, int, int, int]:
        """Zone cliquable de la croix (exclure / réintégrer), en haut à droite d'une vignette d'origine (x, y)."""
        d, m = int(28 * self.scale), int(8 * self.scale)
        return x + self.tile_w - m - d, y + m, x + self.tile_w - m, y + m + d

    def hits_cross(self, index: int, x: float, y: float) -> bool:
        x0, y0, x1, y1 = self.cross_rect(*self.slot_origin(index))
        return x0 <= x <= x1 and y0 <= y <= y1
