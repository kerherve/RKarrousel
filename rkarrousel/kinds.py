"""Types d'images produites pour une photo (clés utilisées dans les noms de fichiers, l'ordre et les réglages), et
leur place dans le carrousel."""
from typing import List, Sequence

OPTIONAL_KINDS = ("part1", "part2", "part1_with_sig", "part2_with_sig")
KIND_CROP = "crop34"  # recadrage 3/4 (portrait 2/3, autres portraits, carrés, paysages)

# Les deux images « photo entière » d'un paysage (droite, puis pivotée) : leur place dans le carrousel se règle.
PLACEABLE_KINDS = ("part1_with_sig", "part2_with_sig")
PLACEMENTS = ("before", "inline", "end")  # avant le découpage, après le découpage, à la fin du carrousel
DEFAULT_PLACEMENTS = {"part1_with_sig": "before", "part2_with_sig": "inline"}


def placement_of(config: dict, kind: str) -> str:
    """Où va l'image `kind` : `before` (avant les tranches), `inline` (après les tranches, avec sa photo) ou `end`
    (après toutes les photos, dans l'ordre des photos). « Aucune » se règle avec `disabled_kinds`."""
    placements = config.get("kind_placement")
    value = placements.get(kind) if isinstance(placements, dict) else None
    return value if value in PLACEMENTS else DEFAULT_PLACEMENTS.get(kind, "inline")


def arrange(slices: Sequence[str], full: Sequence[str], crop: Sequence[str], config: dict) -> List[str]:
    """Ordre des images d'UNE photo : photos entières « avant », tranches, photos entières « après », recadrage,
    puis celles qui vont à la fin du carrousel (déplacées après toutes les photos par `pipeline.planned_items`)."""
    by_place = {place: [k for k in full if placement_of(config, k) == place] for place in PLACEMENTS}
    return by_place["before"] + list(slices) + by_place["inline"] + list(crop) + by_place["end"]


def is_at_end(config: dict, kind: str) -> bool:
    return kind in PLACEABLE_KINDS and placement_of(config, kind) == "end"
