"""Règles de format et de géométrie, sans aucune dépendance graphique : formats de sortie, classification des
photos, recadrage et nombre de tranches d'un panorama."""

import math
from typing import Optional, Tuple


RATIO_TOLERANCE = 0.03
SQUARE_MIN_RATIO = 0.95   # en dessous : portrait « autre » ; entre les deux : quasi carré
LANDSCAPE_MIN_RATIO = 1.3  # au-dessus : paysage « autre » (découpé en panorama)
MAX_PANORAMA_PARTS = 10    # un carrousel Instagram ne dépasse pas 10 images
OUTPUT_FORMATS = {"3:4": (3, 4), "4:5": (4, 5), "1:1": (1, 1), "9:16": (9, 16)}  # grille, feed, carré, stories
DEFAULT_OUTPUT_FORMAT = "3:4"
DEFAULT_TARGET = (3, 4)
OUTPUT_WIDTHS = (0, 1080, 1440, 2048)  # 0 = taille d'origine
WIDE_FACTOR = 1.7333  # au-delà de format × WIDE_FACTOR, un paysage est découpé en panorama (0,75 × 1,733 = 1,3)


def output_format_of(config: dict) -> Tuple[int, int]:
    """Format des images produites, (largeur, hauteur) : 3:4 par défaut."""
    return OUTPUT_FORMATS.get(str(config.get("output_format", DEFAULT_OUTPUT_FORMAT)), DEFAULT_TARGET)


def output_width_of(config: dict) -> int:
    """Largeur maximale des images produites en pixels ; 0 = taille d'origine."""
    try:
        value = int(config.get("output_width", 0))
    except (TypeError, ValueError):
        return 0
    return value if 200 <= value <= 20000 else 0


def format_tag(target: Tuple[int, int]) -> str:
    return f"{target[0]}{target[1]}"


def border_px_for(side: float, frame_ratio: float) -> int:
    """Épaisseur du cadre en pixels : 0 sans cadre, sinon au moins 1 px."""
    return 0 if frame_ratio <= 0 else max(1, int(round(side * frame_ratio)))


def crop_box_for(
    width: int, height: int, frame_ratio: float, target: Tuple[int, int] = DEFAULT_TARGET
) -> Tuple[str, int, int]:
    """Zone conservée d'un recadrage au format de sortie : (axe libre, largeur, hauteur), de sorte que l'image,
    une fois encadrée, ait exactement ce format. Plus étroite que le format : toute la largeur est gardée et on
    règle la position verticale (axe « y »). Sinon : toute la hauteur est gardée et on règle la position
    horizontale (axe « x »). Le cadre suit la règle des autres sorties : frame_ratio × plus petit côté."""
    tw, th = target
    if width * th <= height * tw:
        border = border_px_for(width, frame_ratio)
        crop_h = int(round((th * width + 2 * border * (th - tw)) / tw))
        if crop_h <= height:
            return "y", width, crop_h
        # image à peine plus étroite que le format : le cadre ne tient pas en rognant la hauteur, on rogne la largeur
    crop_w = int(round((tw * height / th) / (1 + 2 * max(0.0, frame_ratio) * (1 - tw / th))))
    return "x", max(1, min(width, crop_w)), height


def detect_ratio_type(width: int, height: int, target: Tuple[int, int] = DEFAULT_TARGET) -> Optional[str]:
    """Classe une image selon son format. « portrait_3_4 » désigne une image déjà au format de sortie (±3 %).
    En 3:4, les formats 2:3 et 3:2 gardent leur traitement historique ; tous les autres sont pris en charge :
    portrait « autre », quasi carré, paysage « autre » (panorama)."""
    if width <= 0 or height <= 0:
        return None
    ratio = width / height
    goal = target[0] / target[1]
    if abs(ratio - goal) / goal <= RATIO_TOLERANCE:
        return "portrait_3_4"
    if target != DEFAULT_TARGET:
        if ratio < goal:
            return "portrait_other"
        return "square" if ratio <= goal * WIDE_FACTOR else "landscape_other"
    if abs(ratio - 2 / 3) / (2 / 3) <= RATIO_TOLERANCE:
        return "portrait_2_3"
    if abs(ratio - 3 / 2) / (3 / 2) <= RATIO_TOLERANCE:
        return "landscape_2_3"
    if ratio < SQUARE_MIN_RATIO:
        return "portrait_other"
    if ratio <= LANDSCAPE_MIN_RATIO:
        return "square"
    return "landscape_other"


def panorama_parts(width: int, height: int, target: Tuple[int, int] = DEFAULT_TARGET) -> int:
    """Nombre d'images dans lesquelles découper un paysage : le plus petit N dont chaque tranche
    (largeur/N) peut prendre le format de sortie en rognant seulement le haut et le bas."""
    tw, th = target
    parts = max(2, int(math.ceil(th * (width / height) / tw - 0.01)))
    if parts > MAX_PANORAMA_PARTS:
        raise ValueError(
            f"Format trop panoramique ({width}x{height}) : il faudrait {parts} images, le maximum est {MAX_PANORAMA_PARTS}."
        )
    return parts
