"""Les étapes du flux (Photos → Ordre → Ajustements → Export) et les règles pour avancer : de simples nombres."""
from typing import Optional

STEP_IDS = ("photos", "order", "adjust", "export")
LAST_STEP = len(STEP_IDS) - 1


def blocker(has_photos: bool, has_destination: bool, included_images: Optional[int]) -> Optional[str]:
    """Pourquoi on ne peut pas avancer au-delà de la première étape (clé de texte), ou None.
    `included_images` : nombre d'images à produire si la grille est déjà calculée, sinon None (inconnu : pas bloquant)."""
    if not (has_photos and has_destination):
        return "flow_need_photos"
    if included_images is not None and included_images <= 0:
        return "flow_need_images"
    return None


def last_reachable(has_photos: bool, has_destination: bool, included_images: Optional[int]) -> int:
    """Index de la dernière étape qu'on peut atteindre : sans photo ni destination on reste sur « Photos » ; sans aucune
    image à produire (tout est exclu) on ne dépasse pas « Ordre »."""
    if not (has_photos and has_destination):
        return 0
    if included_images is not None and included_images <= 0:
        return 1
    return LAST_STEP
