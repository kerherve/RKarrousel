"""Rendu des aperçus en arrière-plan, avec un cache partagé entre les ouvertures de la fenêtre."""
import queue
import threading
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from PIL import Image

from rkarrousel.gui.order.model import cache_key
from rkarrousel.outputs import item_key, render_outputs

PREVIEW_SOURCE_SIDE = 1600  # la source est réduite avant rendu : cadre et flou sont relatifs, le rendu reste fidèle


class ThumbnailService:
    def __init__(self, cache: Dict[str, Tuple[str, Image.Image]], thumb_size: Tuple[int, int]):
        self.cache = cache                  # clé → (empreinte des réglages, miniature)
        self.thumb_size = thumb_size        # taille maximale des miniatures conservées
        self._events: "queue.Queue[tuple]" = queue.Queue()
        self._stop = threading.Event()

    def lookup(self, key: str, path: Path, config: dict, signature: str) -> Optional[Image.Image]:
        cached = self.cache.get(cache_key(key, path, config))
        return cached[1] if cached and cached[0] == signature else None

    def store(self, key: str, path: Path, config: dict, signature: str, thumb: Image.Image) -> None:
        self.cache[cache_key(key, path, config)] = (signature, thumb)

    def start(self, paths: Sequence[Path], config: dict, signature: str) -> None:
        """Calcule les aperçus des photos données dans un thread (annule le calcul précédent)."""
        self.stop()
        self._stop = threading.Event()
        threading.Thread(
            target=self._work, args=(list(paths), dict(config), signature, self._stop), daemon=True
        ).start()

    def stop(self) -> None:
        self._stop.set()

    def drain(self) -> List[tuple]:
        """Évènements reçus depuis le dernier appel : ("thumb", clé, chemin, empreinte, miniature),
        ("error", chemin, message) ou ("done",)."""
        events = []
        try:
            while True:
                events.append(self._events.get_nowait())
        except queue.Empty:
            return events

    def _work(self, paths: List[Path], config: dict, signature: str, stop: threading.Event) -> None:
        for path in paths:
            if stop.is_set():
                return
            try:
                for kind, image in render_outputs(path, config, max_side=PREVIEW_SOURCE_SIDE):
                    thumb = image.copy()
                    thumb.thumbnail(self.thumb_size, Image.Resampling.LANCZOS)
                    if stop.is_set():
                        return
                    self._events.put(("thumb", item_key(path, kind), path, signature, thumb))
            except Exception as exc:
                self._events.put(("error", path, str(exc) or exc.__class__.__name__))
        self._events.put(("done",))
