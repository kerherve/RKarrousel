"""Le flux : Photos → Ordre → Ajustements → Export. Un bandeau d'étapes en haut, la page de l'étape au milieu, et en bas
« Précédent » / « Suivant » (« Lancer le traitement » à la dernière étape)."""
import tkinter as tk
from tkinter import ttk
from typing import Dict, Optional

from rkarrousel.gui.context import AppContext
from rkarrousel.gui.flow.navigation import NavigationBar
from rkarrousel.gui.flow.pages.adjust_page import AdjustPage
from rkarrousel.gui.flow.pages.base import Page
from rkarrousel.gui.flow.pages.export_page import ExportPage
from rkarrousel.gui.flow.pages.order_page import OrderPage
from rkarrousel.gui.flow.pages.photos_page import PhotosPage
from rkarrousel.gui.flow.stepper import Stepper
from rkarrousel.gui.flow.steps import LAST_STEP, STEP_IDS, blocker, last_reachable
from rkarrousel.gui.order.view import OrderView
from rkarrousel.gui.widgets import bind_trace
from rkarrousel.i18n import t


class Flow(ttk.Frame):
    def __init__(self, parent: tk.Misc, ctx: AppContext, drive, batch, step: int = 0):
        super().__init__(parent)
        self.ctx, self.batch = ctx, batch
        self.index = 0
        self._ready = False  # les pages envoient des signaux dès leur création, avant que le flux soit complet
        accent = "#3aa0ff" if ctx.theme.dark else "#0067c0"
        self.stepper = Stepper(self, [t(f"step_{step_id}") for step_id in STEP_IDS], self.go, accent)
        self.stepper.pack(fill=tk.X, pady=(0, 12))
        self.content = ttk.Frame(self)
        self.nav = NavigationBar(self, ctx, self.previous, self.next, batch.cancel)
        self.nav.pack(side=tk.BOTTOM, fill=tk.X, pady=(14, 0))  # avant le contenu : il reste collé en bas
        self.content.pack(fill=tk.BOTH, expand=True)

        self.pages: Dict[str, Page] = {
            "photos": PhotosPage(self.content, ctx, on_change=self.refresh_controls),
            "order": OrderPage(self.content, ctx, on_adjust=lambda: self.go(2), on_change=self.refresh_controls),
            "adjust": None,
            "export": None,
        }
        order = self.pages["order"]
        self.pages["adjust"] = AdjustPage(self.content, ctx, lambda: order.view)
        self.pages["export"] = ExportPage(self.content, ctx, drive, lambda: order.view)
        bind_trace(self, ctx.model.dest_dir, self.refresh_controls)
        self._ready = True
        self._show(0)
        if step:
            self.go(min(step, self.last_reachable()))

    # ------------------------------------------------------------------ état
    def _inputs(self):
        model, session = self.ctx.model, self.ctx.session
        return bool(session.selected_paths), bool(model.dest_dir.get().strip()), self.pages["order"].included_images()

    def last_reachable(self) -> int:
        return last_reachable(*self._inputs())

    def blocked_message(self) -> str:
        key = blocker(*self._inputs())
        return t(key) if key else ""

    def refresh_controls(self) -> None:
        """Met à jour le bandeau et la barre du bas (étape atteignable, bouton « Suivant » grisé, traitement en cours)."""
        if not self._ready:
            return
        processing = self.ctx.processing
        self.stepper.update_state(self.index, self.last_reachable(), enabled=not processing)
        blocked = self.blocked_message() if self.index < LAST_STEP else ""
        self.nav.update_state(self.index, self.index == LAST_STEP, processing, blocked)

    # ------------------------------------------------------------------ navigation
    def go(self, index: int) -> None:
        """Affiche l'étape `index` si elle est atteignable (jamais pendant un traitement)."""
        if self.ctx.processing or not 0 <= index <= self.last_reachable() or index == self.index:
            return
        if index >= 2 and self.pages["order"].view is None:
            self.pages["order"].ensure_view()  # la grille alimente les étapes suivantes, même si on l'a sautée
        self.pages[STEP_IDS[self.index]].on_hide()
        self.pages[STEP_IDS[self.index]].pack_forget()
        self._show(index)

    def _show(self, index: int) -> None:
        self.index = index
        page = self.pages[STEP_IDS[index]]
        page.pack(fill=tk.BOTH, expand=True)
        page.on_show()
        self.refresh_controls()

    def next(self) -> None:
        if self.index == LAST_STEP:
            self.batch.start()
        else:
            self.go(self.index + 1)

    def previous(self) -> None:
        self.go(self.index - 1)

    @property
    def current_page(self) -> Page:
        return self.pages[STEP_IDS[self.index]]

    @property
    def order_view(self) -> Optional[OrderView]:
        return self.pages["order"].view
