"""Bus d'évènements : les threads de travail y déposent des messages, la boucle Tk les distribue aux gestionnaires.

Les threads ne touchent jamais à Tk (qui n'est pas thread-safe) : ils appellent `post`, et les gestionnaires
enregistrés avec `on` s'exécutent dans le thread de l'interface.
"""
import logging
import queue
import tkinter as tk
from typing import Callable, Dict, List

logger = logging.getLogger("imagesplitter")


class EventBus:
    def __init__(self, root: tk.Misc, interval_ms: int = 100):
        self.root = root
        self.interval_ms = interval_ms
        self._queue: "queue.Queue[tuple]" = queue.Queue()
        self._handlers: Dict[str, List[Callable]] = {}
        self._after_id = None

    def post(self, kind: str, *args) -> None:
        self._queue.put((kind,) + args)

    def on(self, kind: str, handler: Callable) -> None:
        self._handlers.setdefault(kind, []).append(handler)

    def start(self) -> None:
        self._after_id = self.root.after(self.interval_ms, self._poll)
        self.root.bind("<Destroy>", self._on_root_destroy, add="+")

    def _on_root_destroy(self, event) -> None:
        if event.widget is self.root:
            self.stop()

    def stop(self) -> None:
        """Arrête la distribution (fermeture de la fenêtre)."""
        if self._after_id is not None:
            try:
                self.root.after_cancel(self._after_id)
            except tk.TclError:
                pass
            self._after_id = None

    def dispatch_pending(self) -> None:
        """Distribue tout ce qui est en attente (utilisé par la boucle Tk, et directement par les tests)."""
        try:
            while True:
                kind, *args = self._queue.get_nowait()
                for handler in self._handlers.get(kind, []):
                    try:
                        handler(*args)
                    except Exception:  # un gestionnaire défaillant ne doit pas arrêter les autres évènements
                        logger.exception("Gestionnaire d'évènement '%s'", kind)
        except queue.Empty:
            pass

    def _poll(self) -> None:
        self.dispatch_pending()
        try:
            self._after_id = self.root.after(self.interval_ms, self._poll)
        except tk.TclError:  # fenêtre déjà détruite
            self._after_id = None
