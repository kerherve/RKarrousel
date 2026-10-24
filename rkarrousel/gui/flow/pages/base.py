"""Une page du flux : un cadre qui sait quand il devient visible ou qu'on le quitte."""
from tkinter import ttk


class Page(ttk.Frame):
    def on_show(self) -> None:
        """La page vient d'être affichée."""

    def on_hide(self) -> None:
        """On quitte la page (avant d'afficher la suivante)."""
