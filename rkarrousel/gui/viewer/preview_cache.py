"""Cache des aperçus déjà calculés, à deux niveaux de qualité, plafonné en **mémoire** (et non en nombre d'images) : on
garde ainsi toutes les images du carrousel prêtes, à moins qu'il y en ait des centaines."""
from collections import OrderedDict
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image

from rkarrousel.gui.order.model import cache_key, render_signature
from rkarrousel.outputs import item_key

STRIP = 1    # petit aperçu (≈ 900 px) : les images lointaines du carrousel, prêtes d'avance
PREVIEW = 2  # aperçu net (1800 px) : l'image affichée et ses voisines proches
MAX_BYTES = 450 * 1024 * 1024


def weight(image: Image.Image) -> int:
    return image.width * image.height * 3


class PreviewCache:
    """Les aperçus les plus récemment utilisés d'abord. Une clé change dès qu'un réglage qui influe sur le rendu change
    (voir `render_signature`). Quand la mémoire est pleine, les petits aperçus partent les premiers."""

    def __init__(self, max_bytes: int = MAX_BYTES):
        self.max_bytes = max_bytes
        self._items: "OrderedDict[str, Tuple[Image.Image, int]]" = OrderedDict()
        self.total_bytes = 0

    @staticmethod
    def key(source: Path, kind: str, config: dict) -> str:
        return f"{cache_key(item_key(source, kind), source, config)}|{render_signature(config)}"

    def get(self, source: Path, kind: str, config: dict, minimum: int = STRIP) -> Optional[Image.Image]:
        """L'aperçu de cette image, s'il est au moins de la qualité `minimum`."""
        key = self.key(source, kind, config)
        entry = self._items.get(key)
        if entry is None or entry[1] < minimum:
            return None
        self._items.move_to_end(key)
        return entry[0]

    def put(self, source: Path, kind: str, config: dict, image: Image.Image, tier: int = PREVIEW) -> None:
        """Garde `image` ; un petit aperçu ne remplace jamais un aperçu net."""
        key = self.key(source, kind, config)
        old = self._items.get(key)
        if old is not None:
            if old[1] > tier:
                return
            self.total_bytes -= weight(old[0])
        self._items[key] = (image, tier)
        self._items.move_to_end(key)
        self.total_bytes += weight(image)
        self._evict()

    def _evict(self) -> None:
        for tier in (STRIP, PREVIEW):  # d'abord les petits aperçus, les plus anciens en tête
            for key in [k for k, (_, t) in self._items.items() if t == tier]:
                if self.total_bytes <= self.max_bytes:
                    return
                image, _ = self._items.pop(key)
                self.total_bytes -= weight(image)

    def __len__(self) -> int:
        return len(self._items)
