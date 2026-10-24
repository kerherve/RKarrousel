"""Quelle résolution la visionneuse montre : un **aperçu** (réduit, rapide) ou la **pleine résolution** (chargée à la demande).

Tout ce que l'écran annonce (zoom, règle, dimensions) est compté en pixels de la pleine résolution ; `factor` donne le
rapport entre ces pixels et ceux de l'image réellement affichée."""
from pathlib import Path
from typing import Dict, Optional

from PIL import Image

from rkarrousel.formats import output_width_of
from rkarrousel.gui.viewer.render_jobs import PREVIEW_SIDE
from rkarrousel.gui.viewer.viewport import Viewport
from rkarrousel.pipeline import peek_size

FULL_THRESHOLD = 1.0  # au-delà de ce zoom (pixels écran par pixel de l'aperçu), l'aperçu serait flou : pleine résolution
SAME_AS_FULL = 1.05   # un aperçu au plus 5 % plus petit que la pleine résolution est considéré comme complet


class Resolution:
    def __init__(self):
        self.factor = 1.0          # pixels de la pleine résolution par pixel de l'image affichée (> 1 pour un aperçu)
        self.full_loaded = False   # l'image affichée est la pleine résolution (chargée en zoomant)
        self.is_full = False       # … ou l'aperçu a déjà la taille finale (petite photo, ou largeur de sortie limitée)
        self.pending = False       # la pleine résolution est demandée, pas encore arrivée
        self._longest: Dict[Path, int] = {}  # photo → plus grand côté de la source, lu une fois

    def reset(self) -> None:
        """Nouvelle image : on repart d'un aperçu."""
        self.factor, self.full_loaded, self.is_full, self.pending = 1.0, False, False, False

    def update(self, image: Image.Image, full: bool, source: Path, config: dict) -> float:
        """Une image vient d'arriver ; renvoie le facteur précédent (pour recaler la vue lors du passage à la pleine résolution)."""
        previous = self.factor
        self.full_loaded = full
        self.factor = 1.0 if full else self._preview_factor(image, source, config)
        self.is_full = full or self.factor <= 1.0
        if full:
            self.pending = False
        return previous

    def wants_full(self, zoom: float) -> bool:
        """Faut-il demander la pleine résolution (une seule fois) pour ce zoom ?"""
        return not (self.is_full or self.pending) and zoom > FULL_THRESHOLD

    @staticmethod
    def rescale_view(view: Viewport, previous_factor: float) -> None:
        """Passage de l'aperçu à la pleine résolution : même zone visible, comptée dans les pixels de la pleine résolution."""
        if previous_factor > 1.0 and not view.fit_mode:
            view.zoom /= previous_factor
            view.ox *= previous_factor
            view.oy *= previous_factor

    def _preview_factor(self, preview: Image.Image, source: Path, config: dict) -> float:
        longest: Optional[int] = self._longest.get(source)
        if longest is None:
            try:
                longest = self._longest[source] = max(peek_size(source))
            except Exception:
                return 1.0
        estimated = preview.width * max(1.0, longest / PREVIEW_SIDE)  # largeur de la pleine résolution, estimée
        cap = output_width_of(config)  # largeur de sortie choisie : jamais plus grande
        full_width = min(estimated, cap) if cap else estimated
        factor = full_width / preview.width
        return factor if factor > SAME_AS_FULL else 1.0
