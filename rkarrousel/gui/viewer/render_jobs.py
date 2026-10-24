"""Calcul de l'image affichée (pleine résolution) et de ses voisines (réduites) dans des threads.

Les threads postent leurs résultats dans une file ; le thread Tk les relève avec `drain()`. Chaque demande porte un
numéro de génération : le résultat d'un rendu déjà remplacé par un réglage plus récent est ignoré."""
import queue
import threading
from pathlib import Path
from typing import Dict, List, Tuple

from rkarrousel.outputs import render_output

NEIGHBOR_SIDE = 1400  # les voisines du carrousel sont rendues à partir d'une source réduite : c'est un simple aperçu

Peeks = Dict[int, Tuple[Path, str]]  # côté (-1 / +1) → (photo, type d'image)


class RenderJobs:
    def __init__(self):
        self.events: "queue.Queue[tuple]" = queue.Queue()
        self.generation = 0

    def launch(self, source: Path, kind: str, config: dict, peeks: Peeks) -> int:
        """Lance le rendu de l'image affichée et celui des voisines `peeks` ; renvoie le numéro de génération."""
        self.generation += 1
        generation = self.generation
        threading.Thread(target=self._render_main, args=(generation, source, kind, config), daemon=True).start()
        if peeks:
            threading.Thread(target=self._render_neighbors, args=(generation, config, peeks), daemon=True).start()
        return generation

    def drain(self) -> List[tuple]:
        """Résultats reçus depuis le dernier appel, pour la génération courante : ("image", image), ("error", message)
        ou ("neighbor", (côté, image ou None))."""
        current = []
        try:
            while True:
                kind, payload, generation = self.events.get_nowait()
                if generation == self.generation:
                    current.append((kind, payload))
        except queue.Empty:
            return current

    def _render_main(self, generation: int, source: Path, kind: str, config: dict) -> None:
        try:
            self.events.put(("image", render_output(source, config, kind), generation))
        except Exception as exc:
            self.events.put(("error", str(exc) or exc.__class__.__name__, generation))

    def _render_neighbors(self, generation: int, config: dict, peeks: Peeks) -> None:
        for delta, (source, kind) in peeks.items():
            try:
                image = render_output(source, config, kind, max_side=NEIGHBOR_SIDE)
            except Exception:
                image = None
            self.events.put(("neighbor", (delta, image), generation))
