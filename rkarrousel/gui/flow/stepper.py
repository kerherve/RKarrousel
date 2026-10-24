"""Bandeau des étapes : « 1 Photos › 2 Ordre › 3 Ajustements › 4 Export », cliquable vers les étapes atteignables."""
import tkinter as tk
from tkinter import ttk
from typing import Callable, Sequence


class Stepper(ttk.Frame):
    def __init__(self, parent: tk.Misc, titles: Sequence[str], on_select: Callable[[int], None], accent: str):
        super().__init__(parent)
        self.on_select, self.accent = on_select, accent
        style = ttk.Style()
        self.normal = style.lookup("TLabel", "foreground") or "#dddddd"
        self.dim = "#7a7a7a"
        self.labels = []
        for index, title in enumerate(titles):
            if index:
                ttk.Label(self, text="›", style="Hint.TLabel", font=("Segoe UI", 14)).pack(side=tk.LEFT, padx=10)
            label = ttk.Label(self, text=f"{index + 1}   {title}", font=("Segoe UI", 12))
            label.pack(side=tk.LEFT)
            label.bind("<Button-1>", lambda e, i=index: self._click(i))
            self.labels.append(label)
        self.current, self.reachable, self.enabled = 0, 0, True

    def update_state(self, current: int, reachable: int, enabled: bool = True) -> None:
        """`current` : étape affichée ; `reachable` : dernière étape accessible ; `enabled` : faux pendant un traitement."""
        self.current, self.reachable, self.enabled = current, reachable, enabled
        for index, label in enumerate(self.labels):
            if index == current:
                label.configure(foreground=self.accent, font=("Segoe UI", 12, "bold"), cursor="")
            elif index <= reachable and enabled:
                label.configure(foreground=self.normal, font=("Segoe UI", 12), cursor="hand2")
            else:
                label.configure(foreground=self.dim, font=("Segoe UI", 12), cursor="")

    def _click(self, index: int) -> None:
        if self.enabled and index != self.current and index <= self.reachable:
            self.on_select(index)
