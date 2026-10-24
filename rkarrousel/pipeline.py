"""Traitement d'un fichier ou d'un lot : découverte des fichiers, ordre et numérotation, écriture sur disque."""

import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Collection, Dict, List, Optional, Sequence, Tuple

from PIL import Image

from rkarrousel.config import config_for_photo, crop_offset_for, jpeg_quality_of
from rkarrousel.formats import detect_ratio_type, output_format_of
from rkarrousel.imaging.frames import open_image, save_image
from rkarrousel.outputs import finalize_size, item_key, iter_outputs, kinds_for_size, output_name

logger = logging.getLogger("imagesplitter")


SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp"}


def say(message: str) -> None:
    """print() qui ne plante jamais : consoles Windows en cp1252 (→, ⚠️ non encodables) ou sans console (exe fenêtré)."""
    try:
        print(message)
    except Exception:
        pass


def is_supported_image(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED_EXTENSIONS


def peek_size(path: Path) -> Tuple[int, int]:
    """Dimensions affichées (orientation EXIF comprise), en ne lisant que l'en-tête de l'image."""
    with Image.open(path) as img:
        width, height = img.size
        try:
            orientation = img.getexif().get(0x0112, 1)
        except Exception:
            orientation = 1
    if orientation in (5, 6, 7, 8):
        width, height = height, width
    return width, height


def planned_items(files: Sequence[Path], config: dict) -> List[Tuple[Path, str]]:
    """Liste à plat (source, kind) de toutes les images de sortie prévues, dans l'ordre naturel."""
    items: List[Tuple[Path, str]] = []
    for path in files:
        try:
            width, height = peek_size(path)
            kinds = kinds_for_size(width, height, config)
        except Exception:
            logger.exception("Lecture impossible : %s", path)
            continue
        for kind in kinds:
            items.append((path, kind))
    return items


def merge_order(order: Sequence[str], items: Sequence[Tuple[Path, str]]) -> List[str]:
    """Ordre final des clés : l'ordre choisi par l'utilisateur d'abord (sans les éléments disparus),
    puis les nouveaux éléments à la suite dans l'ordre naturel."""
    available = [item_key(path, kind) for path, kind in items]
    available_set = set(available)
    merged = [key for key in order if key in available_set]
    seen = set(merged)
    merged.extend(key for key in available if key not in seen)
    return merged


def build_prefixes(ordered_keys: Sequence[str]) -> Dict[str, str]:
    width = max(2, len(str(len(ordered_keys))))
    return {key: f"{index:0{width}d}_" for index, key in enumerate(ordered_keys, start=1)}


def process_image(
    input_path: Path,
    output_dir: Path,
    config: dict,
    prefixes: Optional[Dict[str, str]] = None,
    excluded: Optional[Collection[str]] = None,
) -> List[Path]:
    crop_offset = crop_offset_for(config, input_path)
    config = config_for_photo(config, input_path)  # réglages propres à cette photo (couleur du cadre…)
    img = open_image(input_path)
    width, height = img.size
    ratio_type = detect_ratio_type(width, height, output_format_of(config))
    labels = {
        "portrait_3_4": "portrait 3/4",
        "portrait_2_3": "portrait 2/3",
        "landscape_2_3": "paysage 3/2",
        "portrait_other": "portrait (autre format)",
        "square": "format carré ou proche",
        "landscape_other": "paysage (autre format)",
    }
    if ratio_type is None:
        say(f"⚠️ Ignoré : ratio non supporté pour {input_path.name} ({width}x{height})")
        return []
    say(f"→ {input_path.name} : {labels[ratio_type]} détecté")

    quality = jpeg_quality_of(config)
    output_files: List[Path] = []
    wanted = [k for k in kinds_for_size(width, height, config) if item_key(input_path, k) not in (excluded or ())]
    for kind, out_img in iter_outputs(img, config, only=wanted, crop_offset=crop_offset):
        prefix = (prefixes or {}).get(item_key(input_path, kind), "")
        out_path = output_dir / output_name(input_path, kind, prefix, config)
        save_image(finalize_size(out_img, config), out_path, quality)
        output_files.append(out_path)
    return output_files


@dataclass
class FileResult:
    path: Path
    status: str  # "ok" | "skipped" | "excluded" | "error" | "cancelled"
    outputs: List[Path] = field(default_factory=list)
    message: str = ""


def process_batch(
    files: Sequence[Path],
    output_dir: Path,
    config: dict,
    order: Optional[Sequence[str]] = None,
    number_files: bool = False,
    progress: Optional[Callable[[int, int, Path], None]] = None,
    cancel: Optional[threading.Event] = None,
    workers: int = 1,
    excluded: Optional[Collection[str]] = None,
) -> List[FileResult]:
    """Traite un lot de photos. Si `number_files`, chaque sortie reçoit un préfixe 01_, 02_… selon
    `order` (liste de clés item_key ; les éléments absents suivent dans l'ordre naturel).
    `excluded` : clés item_key des images de sortie à ne pas produire (elles ne sont pas numérotées)."""
    excluded = set(excluded or ())
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    prefixes = None
    if number_files:
        items = [item for item in planned_items(files, config) if item_key(*item) not in excluded]
        prefixes = build_prefixes(merge_order(order or [], items))

    total = len(files)
    results: Dict[Path, FileResult] = {}
    lock = threading.Lock()
    done = 0

    def work(path: Path) -> FileResult:
        if cancel is not None and cancel.is_set():
            return FileResult(path, "cancelled")
        try:
            outputs = process_image(path, output_dir, config, prefixes, excluded)
        except Exception as exc:
            logger.exception("Erreur sur %s", path)
            return FileResult(path, "error", message=str(exc) or exc.__class__.__name__)
        if not outputs:
            if any(key.startswith(f"{path}|") for key in excluded):
                return FileResult(path, "excluded", message="toutes les images exclues")
            return FileResult(path, "skipped", message="ratio non supporté")
        return FileResult(path, "ok", outputs)

    def finished(result: FileResult) -> None:
        nonlocal done
        with lock:
            results[result.path] = result
            done += 1
            count = done
        if progress is not None:
            progress(count, total, result.path)

    workers = max(1, min(workers, total or 1))
    if workers == 1:
        for path in files:
            finished(work(path))
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(work, path) for path in files]
            for future in as_completed(futures):
                finished(future.result())

    return [results[path] for path in files if path in results]


def gather_input_files(paths: List[str]) -> List[Path]:
    result: List[Path] = []
    for raw in paths:
        source = Path(raw).expanduser()
        if not source.exists():
            say(f"⚠️ Chemin introuvable : {raw}")
            continue
        if source.is_dir():
            for candidate in sorted(source.iterdir()):
                if candidate.is_file() and is_supported_image(candidate):
                    result.append(candidate)
        elif source.is_file():
            if is_supported_image(source):
                result.append(source)
            else:
                say(f"⚠️ Format non supporté : {source.name}")
        else:
            say(f"⚠️ Ignoré : {raw}")
    return result
