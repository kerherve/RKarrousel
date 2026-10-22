"""État de la session de travail : photos choisies, ordre des images, images exclues et aperçus en cache."""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Set, Tuple

from PIL import Image

from rkarrousel.pipeline import gather_input_files


@dataclass
class Session:
    selected_paths: List[str] = field(default_factory=list)   # fichiers et dossiers ajoutés
    order: List[str] = field(default_factory=list)            # clés des images de sortie, dans l'ordre choisi
    excluded: Set[str] = field(default_factory=set)           # clés des images de sortie exclues
    preview_cache: Dict[str, Tuple[str, Image.Image]] = field(default_factory=dict)

    def selected_files(self) -> List[Path]:
        return gather_input_files(self.selected_paths)

    def clear(self) -> None:
        self.selected_paths = []
        self.order = []
        self.excluded = set()
