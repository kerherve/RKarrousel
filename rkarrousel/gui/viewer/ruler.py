"""Règle de la visionneuse : clic droit + glisser mesure une distance en pixels de l'image (par exemple le cadre)."""
import math
import tkinter as tk
from typing import Callable, Optional, Tuple

from rkarrousel.i18n import t


class Ruler:
    def __init__(self, canvas: tk.Canvas, message: tk.StringVar, get_zoom: Callable[[], float]):
        self.canvas, self.message, self.get_zoom = canvas, message, get_zoom
        self.line: Optional[Tuple[int, int, int, int]] = None

    def start(self, x: int, y: int) -> None:
        self.line = (x, y, x, y)
        self.draw()

    def move(self, x: int, y: int) -> None:
        if self.line:
            self.line = (self.line[0], self.line[1], x, y)
            self.draw()

    def clear(self) -> None:
        self.line = None
        self.canvas.delete("ruler")

    def draw(self) -> None:
        self.canvas.delete("ruler")
        if not self.line:
            return
        x0, y0, x1, y1 = self.line
        self.canvas.create_line(x0, y0, x1, y1, fill="#ffb400", width=2, tags="ruler")
        for x, y in ((x0, y0), (x1, y1)):
            self.canvas.create_oval(x - 4, y - 4, x + 4, y + 4, outline="#ffb400", width=2, tags="ruler")
        zoom = self.get_zoom()
        dx, dy = abs(x1 - x0) / zoom, abs(y1 - y0) / zoom
        self.message.set(t("viewer_measure", length=math.hypot(dx, dy), dx=dx, dy=dy))
