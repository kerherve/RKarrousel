"""Réglages de l'appli elle-même : langue et thème, mises à jour automatiques."""
import tkinter as tk
from tkinter import ttk
from typing import Callable

from rkarrousel import i18n
from rkarrousel.gui.context import AppContext
from rkarrousel.gui.theme import THEME_CHOICES
from rkarrousel.i18n import t
from rkarrousel.version import __version__


class AppearanceGroup(ttk.LabelFrame):
    """Langue et thème (clair / sombre / auto)."""

    def __init__(self, parent, ctx: AppContext, on_language: Callable[[int], None], on_theme: Callable[[int], None]):
        super().__init__(parent, text=t("appearance_group"), padding=12)
        ttk.Label(self, text=t("language")).grid(row=0, column=0, sticky=tk.W, padx=(0, 8))
        language_box = ttk.Combobox(
            self, state="readonly", width=12, values=[i18n.LANGUAGES[code] for code in i18n.LANGUAGES]
        )
        language_box.set(i18n.LANGUAGES[i18n.get_language()])
        language_box.bind("<<ComboboxSelected>>", lambda e: on_language(language_box.current()))
        language_box.grid(row=0, column=1, padx=(0, 28))
        ttk.Label(self, text=t("theme")).grid(row=0, column=2, sticky=tk.W, padx=(0, 8))
        theme_box = ttk.Combobox(
            self, state="readonly", width=10, values=[t("theme_auto"), t("theme_light"), t("theme_dark")]
        )
        current = ctx.config.get("theme", "auto")
        theme_box.current(THEME_CHOICES.index(current) if current in THEME_CHOICES else 0)
        theme_box.bind("<<ComboboxSelected>>", lambda e: on_theme(theme_box.current()))
        theme_box.grid(row=0, column=3)


class UpdateGroup(ttk.LabelFrame):
    """Recherche de mises à jour."""

    def __init__(self, parent, ctx: AppContext, on_check_now: Callable[[], None]):
        super().__init__(parent, text=t("upd_group"), padding=12)
        self.columnconfigure(1, weight=1)
        ttk.Checkbutton(self, text=t("upd_check_startup"), variable=ctx.model.update_check).grid(
            row=0, column=0, columnspan=3, sticky=tk.W
        )
        ttk.Label(self, text=t("upd_current", version=__version__)).grid(row=1, column=0, sticky=tk.W, pady=(10, 0))
        ttk.Button(self, text=t("upd_check_now"), command=on_check_now).grid(
            row=1, column=1, sticky=tk.W, padx=(12, 0), pady=(10, 0)
        )
