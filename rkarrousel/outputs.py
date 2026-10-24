"""Quelles images produire pour une photo et comment : types, rendu, taille finale et noms de fichiers."""

from pathlib import Path
from typing import Collection, Iterator, List, Optional, Tuple

from PIL import Image

from rkarrousel.config import DEFAULT_CROP_OFFSET, crop_offset_for, disabled_kinds_of
from rkarrousel.formats import (
    detect_ratio_type,
    format_tag,
    output_format_of,
    output_width_of,
    panorama_parts,
)
from rkarrousel.imaging.canvases import render_crop_3_4, render_portrait_2_3, render_portrait_3_4
from rkarrousel.imaging.colors import resolve_photo_colors
from rkarrousel.imaging.frames import open_image
from rkarrousel.imaging.panorama import iter_landscape_other, iter_split_2_3_to_3_4
from rkarrousel.kinds import KIND_CROP, OPTIONAL_KINDS


def _main_kind(config: dict) -> str:
    return "with_sig" if config.get("signature_path") else "framed"


def kinds_for_ratio(ratio_type: Optional[str], config: dict, size: Optional[Tuple[int, int]] = None) -> List[str]:
    """Types de sorties produites pour un ratio donné (sans rien calculer), hors types désactivés.
    `size` (largeur, hauteur) sert à compter les tranches d'un panorama."""
    disabled = disabled_kinds_of(config)
    crop = [] if KIND_CROP in disabled else [KIND_CROP]
    if ratio_type == "portrait_3_4":
        return ["framed"]
    if ratio_type in ("portrait_2_3", "portrait_other", "square"):
        return [_main_kind(config)] + crop
    if ratio_type == "landscape_2_3":
        return [kind for kind in OPTIONAL_KINDS if kind not in disabled]
    if ratio_type == "landscape_other":
        parts = panorama_parts(*size, output_format_of(config)) if size else 2
        slices = [f"part{i}" for i in range(1, parts + 1)]
        # « part1 » règle la première tranche, « part2 » toutes les suivantes
        slices = [k for k in slices if k not in disabled and not (int(k[4:]) >= 2 and "part2" in disabled)]
        full = [k for k in ("part1_with_sig", "part2_with_sig") if k not in disabled]
        return slices + full + crop
    return []


SIGNED_KINDS = ("with_sig", "part1_with_sig", "part2_with_sig")  # les images « entières », seules à porter la signature


def kind_features(width: int, height: int, kind: str, config: dict) -> frozenset:
    """Réglages qui changent l'image `kind` d'une photo de cette taille : « fill » (fond uni ou flouté autour de la
    photo) et « signature ». Les tranches d'un panorama et les recadrages n'ont ni l'un ni l'autre, une photo déjà
    au format de sortie non plus. Sert à griser les réglages sans effet."""
    features = set()
    if kind in SIGNED_KINDS:
        features |= {"fill", "signature"}
    elif kind == "framed" and detect_ratio_type(width, height, output_format_of(config)) != "portrait_3_4":
        features.add("fill")  # image entière sans signature, posée sur un fond
    return frozenset(features)


def kinds_for_size(width: int, height: int, config: dict) -> List[str]:
    return kinds_for_ratio(detect_ratio_type(width, height, output_format_of(config)), config, (width, height))


def iter_outputs(
    img: Image.Image,
    config: dict,
    only: Optional[Collection[str]] = None,
    crop_offset: float = DEFAULT_CROP_OFFSET,
) -> Iterator[Tuple[str, Image.Image]]:
    """Génère (kind, image) pour une image déjà ouverte, sans rien écrire sur disque.
    `only` limite aux types demandés (les autres ne sont pas calculés) ; par défaut, tous les types actifs."""
    ratio_type = detect_ratio_type(*img.size, output_format_of(config))
    wanted = [k for k in kinds_for_ratio(ratio_type, config, img.size) if only is None or k in only]
    if not wanted:
        return
    config = resolve_photo_colors(img, config)  # cadre / fond « couleur de la photo » : calculés pour CETTE photo
    if ratio_type == "portrait_3_4":
        yield "framed", render_portrait_3_4(img, config)
    elif ratio_type in ("portrait_2_3", "portrait_other", "square"):
        for kind in wanted:
            if kind == KIND_CROP:
                yield kind, render_crop_3_4(img, config, crop_offset)
            else:
                yield kind, render_portrait_2_3(img, config)
    elif ratio_type == "landscape_2_3":
        yield from iter_split_2_3_to_3_4(img, config, only=[k for k in wanted if k != KIND_CROP])
    elif ratio_type == "landscape_other":
        parts = panorama_parts(*img.size, output_format_of(config))
        mine = [k for k in wanted if k != KIND_CROP]
        if mine:
            yield from iter_landscape_other(img, config, parts, only=mine)
        if KIND_CROP in wanted:
            yield KIND_CROP, render_crop_3_4(img, config, crop_offset)


def item_key(source: Path, kind: str) -> str:
    return f"{source}|{kind}"


def output_name(source: Path, kind: str, prefix: str = "", config: Optional[dict] = None) -> str:
    suffix = kind
    if kind == KIND_CROP and config is not None:
        suffix = f"crop{format_tag(output_format_of(config))}"  # crop34 en 3:4, crop45 en 4:5…
    return f"{prefix}{source.stem}_{suffix}{source.suffix or '.jpg'}"


def finalize_size(img: Image.Image, config: dict) -> Image.Image:
    """Réduit l'image à la largeur de sortie choisie (jamais d'agrandissement). Une image au format de sortie
    (à 0,5 % près) reçoit des dimensions exactes, par exemple 1080×1440 en 3:4."""
    width = output_width_of(config)
    if not width or img.width <= width:
        return img
    tw, th = output_format_of(config)
    height = int(round(img.height * width / img.width))
    exact = width * th / tw
    if abs(height - exact) <= max(2.0, exact * 0.005):
        height = int(round(exact))
    return img.resize((width, height), Image.Resampling.LANCZOS)


def render_outputs(path: Path, config: dict, max_side: Optional[int] = None) -> List[Tuple[str, Image.Image]]:
    """Rend toutes les sorties d'une photo en mémoire. `max_side` réduit la source (aperçus rapides)."""
    img = open_image(path)
    if max_side and max(img.size) > max_side:
        img.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    return list(iter_outputs(img, config, crop_offset=crop_offset_for(config, path)))


def render_output(path: Path, config: dict, kind: str, max_side: Optional[int] = None) -> Optional[Image.Image]:
    """Rend une seule sortie (pleine résolution par défaut), ou None si ce type n'existe pas pour cette photo."""
    img = open_image(path)
    if max_side and max(img.size) > max_side:
        img.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    for found, out in iter_outputs(img, config, only={kind}, crop_offset=crop_offset_for(config, path)):
        if found == kind:
            return finalize_size(out, config) if not max_side else out
    return None
