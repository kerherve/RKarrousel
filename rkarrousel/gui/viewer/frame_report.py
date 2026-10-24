"""Ce que la visionneuse sait dire du cadre d'une image rendue : sa couleur obtenue et son épaisseur mesurée."""
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

from PIL import Image

from rkarrousel.config import background_color_of, border_color_of, config_for_photo
from rkarrousel.imaging.colors import resolve_photo_colors_for_path
from rkarrousel.imaging.frames import measure_border


@dataclass
class FrameReport:
    width: int
    height: int
    color: Tuple[int, int, int]  # couleur du cadre pour cette photo (couleurs « de la photo » et retouche comprises)
    border: int                  # épaisseur mesurée en pixels (0 : aucun cadre trouvé)

    @property
    def percent(self) -> float:
        return 100 * self.border / min(self.width, self.height)


def report_for(image: Image.Image, source: Path, config: dict) -> FrameReport:
    """Mesure le cadre de `image`, rendue depuis `source` avec `config` (réglages propres à la photo compris)."""
    resolved = resolve_photo_colors_for_path(source, config_for_photo(config, source))
    color = border_color_of(resolved)
    border = measure_border(image, color, skip_color=background_color_of(resolved))
    return FrameReport(image.width, image.height, color, border or 0)
