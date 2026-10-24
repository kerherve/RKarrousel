"""Calcul de l'image affichée et de ses voisines dans des threads.

L'image affichée se calcule d'abord en **aperçu** (`PREVIEW_SIDE` pixels de côté : net à l'écran et rapide) ; la pleine
résolution n'est demandée que si l'on zoome au-delà. Les résultats arrivent dans une file que le thread Tk relève avec
`drain()`. L'image affichée porte un numéro de **génération** (un résultat périmé est ignoré) ; les voisines portent une
**époque**, qui ne change que lorsque les réglages changent : l'aperçu d'une voisine reste utile même si l'on a changé
d'image entre-temps (il va dans le cache)."""
import queue
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

from rkarrousel.outputs import render_output

PREVIEW_SIDE = 1800  # côté de l'aperçu (en pixels de la photo source) : assez pour un affichage net même sur grand écran
STRIP_SIDE = 900     # côté du petit aperçu des images lointaines du carrousel (préparées d'avance en arrière-plan)

Peeks = Dict[int, Tuple[Path, str]]  # côté (-1 / +1) → (photo, type d'image)


class RenderJobs:
    def __init__(self):
        self.events: "queue.Queue[tuple]" = queue.Queue()
        self.generation = 0
        self.epoch = 0
        # trois ouvriers au plus : en feuilletant vite, les rendus périmés en attente sont sautés au lieu de s'empiler
        self._pool = ThreadPoolExecutor(max_workers=3, thread_name_prefix="viewer-render")
        # un seul ouvrier pour la préparation d'avance de toutes les images : elle ne gêne jamais l'affichage
        self._background = ThreadPoolExecutor(max_workers=1, thread_name_prefix="viewer-prefetch")
        self._prefetch_round = 0

    def next_generation(self) -> int:
        """Invalide les résultats en cours (la demande suivante est servie sans calcul, par exemple depuis le cache)."""
        self.generation += 1
        return self.generation

    def new_epoch(self) -> int:
        """Les réglages ont changé : les aperçus de voisines en cours de calcul ne sont plus valables."""
        self.epoch += 1
        return self.epoch

    def launch(self, source: Path, kind: str, config: dict, peeks: Peeks, main: bool = True, full: bool = False) -> int:
        """Lance le rendu de l'image affichée (si `main` ; en pleine résolution si `full`, sinon en aperçu) et celui des
        voisines `peeks` (aperçus) ; renvoie le numéro de génération."""
        generation = self.next_generation()
        if main:
            self._pool.submit(self._render_main, generation, source, kind, config, full)
        for delta, target in peeks.items():  # une tâche par voisine : elles se calculent en parallèle
            self._pool.submit(self._render_neighbor, self.epoch, config, delta, target)
        return generation

    def prefetch(self, config: dict, targets: Sequence[Tuple[Path, str]]) -> None:
        """Prépare en arrière-plan un petit aperçu de chacune de ces images (les plus proches d'abord). Une nouvelle demande
        remplace la précédente, qui s'arrête à l'image en cours."""
        self._prefetch_round += 1
        if targets:
            self._background.submit(self._prefetch, self._prefetch_round, self.epoch, config, list(targets))

    def close(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)
        self._background.shutdown(wait=False, cancel_futures=True)
        self._prefetch_round += 1

    def drain(self) -> List[tuple]:
        """Résultats reçus depuis le dernier appel : ("image", (image, pleine_résolution, photo, type)) et ("error",
        message) pour la génération courante ; ("neighbor", (côté, image ou None, photo, type)) et ("strip", (image, photo,
        type)) pour l'époque courante."""
        current = []
        try:
            while True:
                kind, payload, number = self.events.get_nowait()
                if number == (self.epoch if kind in ("neighbor", "strip") else self.generation):
                    current.append((kind, payload))
        except queue.Empty:
            return current

    def _render_main(self, generation: int, source: Path, kind: str, config: dict, full: bool) -> None:
        if generation != self.generation:
            return  # un rendu plus récent a été demandé entre-temps
        try:
            image = render_output(source, config, kind, max_side=None if full else PREVIEW_SIDE)
            self.events.put(("image", (image, full, source, kind), generation))
        except Exception as exc:
            self.events.put(("error", str(exc) or exc.__class__.__name__, generation))

    def _render_neighbor(self, epoch: int, config: dict, delta: int, target: Tuple[Path, str]) -> None:
        if epoch != self.epoch:
            return
        source, kind = target
        try:
            image = render_output(source, config, kind, max_side=PREVIEW_SIDE)
        except Exception:
            image = None
        self.events.put(("neighbor", (delta, image, source, kind), epoch))

    def _prefetch(self, round_number: int, epoch: int, config: dict, targets: List[Tuple[Path, str]]) -> None:
        for source, kind in targets:
            if round_number != self._prefetch_round or epoch != self.epoch:
                return  # une demande plus récente, ou d'autres réglages : on s'arrête
            try:
                image = render_output(source, config, kind, max_side=STRIP_SIDE)
            except Exception:
                continue
            self.events.put(("strip", (image, source, kind), epoch))
