"""Barre du bas : progression, « Précédent », « Suivant » (« Lancer le traitement » à la dernière étape) et « Annuler »."""
import tkinter as tk
from tkinter import ttk
from typing import Callable

from rkarrousel.gui.context import AppContext
from rkarrousel.i18n import t


class NavigationBar(ttk.Frame):
    def __init__(self, parent: tk.Misc, ctx: AppContext, on_previous: Callable[[], None], on_next: Callable[[], None],
                 on_cancel: Callable[[], None]):
        super().__init__(parent)
        self.progress = ttk.Progressbar(self, variable=ctx.progress_value, maximum=100)
        self.progress.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 16))
        self.hint = ttk.Label(self, text="", style="Hint.TLabel")
        self.hint.pack(side=tk.LEFT, padx=(0, 12))
        self.previous_button = ttk.Button(self, text=t("nav_previous"), command=on_previous)
        self.previous_button.pack(side=tk.LEFT, padx=(0, 8))
        self.next_button = ttk.Button(self, text=t("nav_next"), command=on_next, style=ctx.theme.accent_style)
        self.next_button.pack(side=tk.LEFT)
        self.cancel_button = ttk.Button(self, text=t("btn_cancel"), command=on_cancel)

    def update_state(self, step: int, last: bool, processing: bool, blocked_message: str = "") -> None:
        """Pendant un traitement : seul « Annuler » reste ; sinon « Suivant » est grisé (avec la raison) s'il est bloqué."""
        if processing:
            self.previous_button.pack_forget()
            self.next_button.pack_forget()
            self.hint.configure(text="")
            self.cancel_button.pack(side=tk.LEFT)
            return
        self.cancel_button.pack_forget()
        if not self.previous_button.winfo_ismapped():
            self.previous_button.pack(side=tk.LEFT, padx=(0, 8))
        if not self.next_button.winfo_ismapped():
            self.next_button.pack(side=tk.LEFT)
        self.previous_button.state(["!disabled"] if step > 0 else ["disabled"])
        self.next_button.configure(text=t("btn_process") if last else t("nav_next"))
        self.next_button.state(["disabled"] if blocked_message else ["!disabled"])
        self.hint.configure(text=blocked_message)
