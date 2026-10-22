"""Widgets réutilisables : zone défilante et sélecteur de couleur."""
import tkinter as tk
from tkinter import colorchooser, ttk
from typing import Callable, Tuple

from rkarrousel.config import parse_color
from rkarrousel.i18n import t


def bind_trace(widget: tk.Misc, variable: tk.Variable, callback: Callable[[], None]) -> None:
    """Appelle `callback` à chaque changement de `variable`, et retire l'observateur quand `widget` est détruit
    (les variables survivent aux reconstructions de l'interface, pas les widgets)."""
    trace_id = variable.trace_add("write", lambda *_: callback())

    def cleanup(event) -> None:
        if event.widget is widget:
            try:
                variable.trace_remove("write", trace_id)
            except tk.TclError:
                pass

    widget.bind("<Destroy>", cleanup, add="+")


def make_scrollable(parent: tk.Misc, background: str) -> ttk.Frame:
    """Zone défilante (molette comprise) : un onglet peut grandir sans être coupé. Renvoie le cadre intérieur."""
    canvas = tk.Canvas(parent, highlightthickness=0, bg=background, borderwidth=0)
    scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=canvas.yview)
    canvas.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    inner = ttk.Frame(canvas, padding=14)
    window = canvas.create_window((0, 0), window=inner, anchor=tk.NW)
    inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.bind("<Configure>", lambda e: canvas.itemconfigure(window, width=e.width))

    def on_wheel(event) -> None:
        if inner.winfo_reqheight() > canvas.winfo_height():
            canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")

    canvas.bind("<Enter>", lambda _: canvas.bind_all("<MouseWheel>", on_wheel))
    canvas.bind("<Leave>", lambda _: canvas.unbind_all("<MouseWheel>"))
    return inner


class ColorPicker(ttk.Frame):
    """Échantillon de couleur + champ « #RRGGBB » + bouton « Choisir la couleur »."""

    def __init__(self, parent: tk.Misc, variable: tk.StringVar, default: Tuple[int, int, int], title: str):
        super().__init__(parent)
        self.variable, self.default, self.title = variable, default, title
        self.swatch = tk.Label(self, width=4, relief=tk.SOLID, borderwidth=1)
        self.swatch.pack(side=tk.LEFT, padx=(0, 8))
        self.entry = ttk.Entry(self, textvariable=variable, width=10)
        self.entry.pack(side=tk.LEFT, padx=(0, 8))
        self.button = ttk.Button(self, text=t("choose_color"), command=self.choose)
        self.button.pack(side=tk.LEFT)
        bind_trace(self, variable, self.refresh_swatch)
        self.refresh_swatch()

    def refresh_swatch(self) -> None:
        try:
            self.swatch.configure(bg="#%02x%02x%02x" % parse_color(self.variable.get(), self.default))
        except tk.TclError:
            pass

    def choose(self) -> None:
        rgb = parse_color(self.variable.get(), self.default)
        picked = colorchooser.askcolor(color="#%02x%02x%02x" % rgb, title=self.title)
        if picked and picked[1]:
            self.variable.set(picked[1].upper())

    def set_enabled(self, enabled: bool) -> None:
        state = ["!disabled"] if enabled else ["disabled"]
        self.entry.state(state)
        self.button.state(state)
