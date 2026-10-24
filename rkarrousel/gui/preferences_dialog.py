"""Fenêtre « Préférences » : langue, thème et mises à jour (les réglages de l'appli elle-même, pas ceux des images)."""
import tkinter as tk
from tkinter import ttk
from typing import Callable

from rkarrousel.gui.context import AppContext
from rkarrousel.gui.settings_groups import AppearanceGroup, UpdateGroup
from rkarrousel.i18n import t


class PreferencesDialog(tk.Toplevel):
    def __init__(self, parent: tk.Misc, ctx: AppContext, on_language: Callable[[int], None],
                 on_theme: Callable[[int], None], on_check_updates: Callable[[], None]):
        super().__init__(parent)
        self.title(t("prefs_title"))
        self.transient(parent)
        self.resizable(False, False)
        frame = ttk.Frame(self, padding=16)
        frame.pack(fill=tk.BOTH, expand=True)
        frame.columnconfigure(0, weight=1)
        AppearanceGroup(frame, ctx, on_language, on_theme).grid(row=0, column=0, sticky=tk.EW)
        UpdateGroup(frame, ctx, on_check_updates).grid(row=1, column=0, sticky=tk.EW, pady=(10, 0))
        ttk.Button(frame, text=t("order_close"), command=self.destroy).grid(row=2, column=0, sticky=tk.E, pady=(14, 0))
        self.bind("<Escape>", lambda e: self.destroy())
        self.update_idletasks()
        width, height = self.winfo_reqwidth(), self.winfo_reqheight()
        x = parent.winfo_rootx() + max(0, (parent.winfo_width() - width) // 2)
        y = parent.winfo_rooty() + max(0, (parent.winfo_height() - height) // 3)
        self.geometry(f"+{x}+{y}")
