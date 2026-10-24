"""Modèle de la grille d'ordre (sans Tk) : vignettes, sélection, exclusions et réordonnancement."""
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Set, Tuple

from PIL import Image

from rkarrousel.config import crop_offset_for
from rkarrousel.kinds import KIND_CROP
from rkarrousel.outputs import item_key
from rkarrousel.pipeline import merge_order, planned_items

# Réglages qui changent le rendu : quand l'un d'eux change, les aperçus en cache ne sont plus valables.
RENDER_KEYS = (
    "frame_ratio", "frame_enabled", "output_format", "landscape_fill_mode", "signature_path", "border_color",
    "blur_strength", "signature_position", "signature_scale", "background_color", "disabled_kinds",
    "border_color_mode", "background_color_mode", "color_source", "photo_overrides",
)


def render_signature(config: dict) -> str:
    """Empreinte des réglages qui changent le rendu (sert à invalider le cache d'aperçus)."""
    return json.dumps({key: config.get(key) for key in RENDER_KEYS}, sort_keys=True)


def cache_key(key: str, path: Path, config: dict) -> str:
    """Clé de cache d'une vignette : image de sortie, date du fichier et, pour un recadrage, sa position."""
    try:
        mtime = path.stat().st_mtime
    except OSError:
        mtime = 0
    offset = f"|{crop_offset_for(config, path):.4f}" if key.endswith(f"|{KIND_CROP}") else ""
    return f"{key}|{mtime}{offset}"


@dataclass
class Tile:
    key: str
    source: Path
    kind: str
    thumb: Optional[Image.Image] = None
    photo: object = None      # image affichable (ImageTk), créée à la demande par la grille
    error: str = ""
    excluded: bool = False


class OrderModel:
    """Liste ordonnée des images de sortie d'un lot, avec ce qui est exclu et ce qui est sélectionné."""

    def __init__(self, files: Sequence[Path], excluded: Optional[Set[str]] = None):
        self.files = list(files)
        self.excluded: Set[str] = set(excluded or ())
        self.tiles: List[Tile] = []
        self.selected: Optional[int] = None

    def rebuild(
        self,
        config: dict,
        order: Sequence[str],
        lookup: Callable[[str, Path], Optional[Image.Image]],
    ) -> List[Path]:
        """Reconstruit les vignettes selon les réglages et l'ordre voulu. `lookup(clé, chemin)` renvoie la
        miniature en cache ou None. Renvoie les photos dont il reste des aperçus à calculer."""
        planned = planned_items(self.files, config)
        by_key = {item_key(path, kind): (path, kind) for path, kind in planned}
        previous = self.selected_tile().key if self.selected_tile() is not None else None
        self.tiles = []
        pending: Dict[Path, bool] = {}
        for key in merge_order(order, planned):
            path, kind = by_key[key]
            tile = Tile(key, path, kind, excluded=key in self.excluded)
            tile.thumb = lookup(key, path)
            if tile.thumb is None:
                pending[path] = True
            self.tiles.append(tile)
        self.excluded &= {tile.key for tile in self.tiles}
        self.selected = self.index_of(previous) if previous is not None else None  # la sélection survit à la reconstruction
        return list(pending)

    # ------------------------------------------------------------------ état
    def keys(self) -> List[str]:
        return [tile.key for tile in self.tiles]

    def selected_tile(self) -> Optional[Tile]:
        if self.selected is not None and 0 <= self.selected < len(self.tiles):
            return self.tiles[self.selected]
        return None

    def select(self, index: Optional[int]) -> None:
        self.selected = index

    def step_from_selection(self, delta: int) -> Optional[int]:
        """Index de l'image affichée (non exclue) la plus proche de la sélection dans le sens `delta` (±1), ou None."""
        index = self.selected
        if index is None:
            return None
        index += delta
        while 0 <= index < len(self.tiles):
            if not self.tiles[index].excluded:
                return index
            index += delta
        return None

    def position_of_selection(self) -> Tuple[int, int]:
        """(rang de l'image sélectionnée parmi les images non exclues, nombre d'images non exclues)."""
        total = sum(1 for tile in self.tiles if not tile.excluded)
        return (self.number_of(self.selected) if self.selected is not None else 0), total

    def index_of(self, key: str) -> Optional[int]:
        return next((i for i, tile in enumerate(self.tiles) if tile.key == key), None)

    def number_of(self, index: int) -> int:
        """Numéro d'ordre de la vignette (celui qui préfixera le fichier) ; les images exclues ne sont pas numérotées."""
        return sum(1 for tile in self.tiles[: index + 1] if not tile.excluded)

    def counts(self) -> Tuple[int, int, int, bool]:
        """(total, aperçus prêts, exclues, au moins une erreur sans aperçu)."""
        ready = sum(1 for tile in self.tiles if tile.thumb is not None)
        excluded = sum(1 for tile in self.tiles if tile.excluded)
        failed = any(tile.error for tile in self.tiles if tile.thumb is None)
        return len(self.tiles), ready, excluded, failed

    # ------------------------------------------------------------------ modifications
    def toggle_selected_exclusion(self) -> bool:
        """Exclut / réintègre l'image sélectionnée. Renvoie False s'il n'y a pas de sélection."""
        tile = self.selected_tile()
        if tile is None:
            return False
        tile.excluded = not tile.excluded
        (self.excluded.add if tile.excluded else self.excluded.discard)(tile.key)
        return True

    def move(self, source: int, target: int) -> bool:
        """Déplace une vignette ; la sélection la suit. Renvoie True si l'ordre a changé."""
        if source == target:
            return False
        self.tiles.insert(target, self.tiles.pop(source))
        self.selected = target
        return True

    def set_thumb(self, key: str, thumb: Image.Image) -> None:
        index = self.index_of(key)
        if index is not None:
            tile = self.tiles[index]
            tile.thumb, tile.photo, tile.error = thumb, None, ""

    def set_error(self, path: Path, message: str) -> None:
        for tile in self.tiles:
            if tile.source == path and tile.thumb is None:
                tile.error = message
