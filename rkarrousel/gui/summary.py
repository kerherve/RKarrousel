"""Boîte de fin de traitement."""
from tkinter import messagebox
from typing import List

from rkarrousel.i18n import t

MAX_ERRORS_SHOWN = 10


def show_summary(lines: List[str], warn: bool) -> None:
    """Affiche le récapitulatif (en avertissement s'il y a des erreurs ou des fichiers ignorés)."""
    (messagebox.showwarning if warn else messagebox.showinfo)(t("dlg_done_title"), "\n".join(lines))
