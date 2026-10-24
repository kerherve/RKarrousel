"""La grille dessinée : vignettes numérotées, croix d'exclusion, sélection et glisser-déposer pour réordonner."""
import tkinter as tk
from dataclasses import dataclass
from typing import Callable, Optional

from PIL import ImageTk

from rkarrousel.gui.order.grid_layout import GridLayout
from rkarrousel.formats import INSTAGRAM_MAX_IMAGES
from rkarrousel.gui.order.model import OrderModel, Tile
from rkarrousel.i18n import kind_label, t

DRAG_THRESHOLD = 6  # pixels de déplacement avant qu'un clic devienne un glisser


@dataclass
class _Drag:
    index: int
    x0: int
    y0: int
    moved: bool = False
    target: Optional[int] = None


class GridCanvas(tk.Canvas):
    """Dessine le modèle et traduit la souris en évènements (sélection, réordonnancement, exclusion…)."""

    def __init__(
        self,
        parent: tk.Misc,
        layout: GridLayout,
        model: OrderModel,
        dark: bool,
        on_select: Callable[[Optional[int]], None],
        on_toggle_exclude: Callable[[], None],
        on_reorder: Callable[[int, int], None],
        on_open: Callable[[int], None],
        on_context: Callable[[int, int, int], None],
    ):
        super().__init__(parent, width=layout.canvas_width, bg="#000000" if dark else "#ffffff", highlightthickness=0)
        self.layout, self.model, self.dark = layout, model, dark
        self.on_select, self.on_toggle_exclude, self.on_reorder = on_select, on_toggle_exclude, on_reorder
        self.on_open, self.on_context = on_open, on_context
        self.drag: Optional[_Drag] = None
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_motion)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Double-Button-1>", self._on_double_click)
        self.bind("<ButtonPress-3>", self._on_context)
        self.bind("<MouseWheel>", lambda e: self.yview_scroll(-1 if e.delta > 0 else 1, "units"))
        self.bind("<Button-4>", lambda e: self.yview_scroll(-2, "units"))
        self.bind("<Button-5>", lambda e: self.yview_scroll(2, "units"))
        self._fit_job = None
        self.bind("<Configure>", self._on_configure)
        self.bind("<Destroy>", lambda e: self._cancel_fit() if e.widget is self else None, add="+")

    # ------------------------------------------------------------------ taille de la fenêtre
    def _cancel_fit(self) -> None:
        if self._fit_job is not None:
            try:
                self.after_cancel(self._fit_job)
            except tk.TclError:
                pass
            self._fit_job = None

    def _on_configure(self, event) -> None:
        """La fenêtre change de taille : la grille ajoute ou retire des colonnes (on attend la fin du geste pour ne pas
        tout redessiner à chaque pixel)."""
        self._cancel_fit()
        self._fit_job = self.after(120, lambda: self.fit_to_width(event.width))

    def fit_to_width(self, width: int) -> None:
        self._fit_job = None
        if self.layout.fit_width(width):
            self.redraw()

    # ------------------------------------------------------------------ dessin
    def redraw(self) -> None:
        self.delete("all")
        for index, tile in enumerate(self.model.tiles):
            self._draw_tile(tile, index, *self.layout.slot_origin(index))
        self.configure(
            scrollregion=(0, 0, self.layout.offset + self.layout.canvas_width, self.layout.content_height(len(self.model.tiles)))
        )

    def _photo(self, tile: Tile) -> Optional[ImageTk.PhotoImage]:
        """Image affichable de la vignette (créée une fois, ajustée à la taille d'une case)."""
        if tile.photo is None and tile.thumb is not None:
            fitted = tile.thumb.copy()
            fitted.thumbnail((self.layout.tile_w, self.layout.tile_h))
            tile.photo = ImageTk.PhotoImage(fitted)
        return tile.photo

    def _draw_tile(self, tile: Tile, index: int, x: int, y: int) -> None:
        layout, s = self.layout, self.layout.scale
        w, h = layout.tile_w, layout.tile_h
        cx, cy = x + w // 2, y + h // 2
        dragging = self.drag is not None and self.drag.moved and self.drag.index == index
        self.create_rectangle(x, y, x + w, y + h, fill="#161616" if self.dark else "#1e1e1e", outline="")
        photo = self._photo(tile)
        if photo is not None:
            self.create_image(cx, cy, image=photo)
            if dragging:
                self.create_rectangle(x, y, x + w, y + h, fill="#ffffff", stipple="gray50", outline="")
        elif tile.error:
            self.create_text(cx, cy, text=t("order_error", message=tile.error), fill="#ff8888", width=w - 16, justify=tk.CENTER)
        else:
            self.create_text(cx, cy, text="…", fill="#777777", font=("Segoe UI", 20))

        if tile.excluded:
            self.create_rectangle(x, y, x + w, y + h, fill="#000000", stipple="gray75", outline="")
            self.create_text(cx, cy - int(14 * s), text="✕", fill="#ff5a5a", font=("Segoe UI", 44, "bold"))
            self.create_text(cx, cy + int(26 * s), text=t("order_excluded"), fill="#ffffff", font=("Segoe UI", 10, "bold"))
        # numéro d'ordre (celui qui préfixera le fichier) ; les images exclues ne sont pas numérotées
        m, d = int(8 * s), int(30 * s)
        number = self.model.number_of(index)
        badge = "#6b6b6b" if tile.excluded else ("#e53935" if number > INSTAGRAM_MAX_IMAGES else "#0095f6")  # rouge : trop
        self.create_oval(x + m, y + m, x + m + d, y + m + d, fill=badge, outline="#ffffff", width=2)
        self.create_text(x + m + d // 2, y + m + d // 2, text="–" if tile.excluded else str(number),
                         fill="#ffffff", font=("Segoe UI", 10, "bold"))
        x0, y0, x1, y1 = layout.cross_rect(x, y)
        self.create_oval(x0, y0, x1, y1, fill="#2e7d32" if tile.excluded else "#222222", outline="#ffffff", width=2)
        self.create_text((x0 + x1) // 2, (y0 + y1) // 2, text="↺" if tile.excluded else "✕", fill="#ffffff",
                         font=("Segoe UI", 11, "bold"))
        if index == self.model.selected:
            self.create_rectangle(x + 2, y + 2, x + w - 2, y + h - 2, outline="#0095f6", width=max(3, int(4 * s)))
        cap = int(36 * s)  # légende
        self.create_rectangle(x, y + h - cap, x + w, y + h, fill="#000000", stipple="gray50", outline="")
        self.create_text(x + int(8 * s), y + h - cap // 2, anchor=tk.W, fill="#ffffff", font=("Segoe UI", 8),
                         text=f"{tile.source.name}\n{kind_label(tile.kind)}", width=w - int(16 * s))

    # ------------------------------------------------------------------ souris
    def _canvas_point(self, event):
        return self.canvasx(event.x), self.canvasy(event.y)

    def _tile_at(self, event) -> Optional[int]:
        return self.layout.tile_at(*self._canvas_point(event), len(self.model.tiles))

    def _click_cross(self, index: Optional[int], x: float, y: float) -> bool:
        """Clic sur la croix d'une vignette : on la sélectionne et on l'exclut / la réintègre."""
        if index is not None and self.layout.hits_cross(index, x, y):
            self.on_select(index)
            self.on_toggle_exclude()
            return True
        return False

    def _on_press(self, event) -> None:
        self.focus_set()  # les touches Suppr et Entrée agissent sur la vignette sélectionnée
        x, y = self._canvas_point(event)
        index = self.layout.tile_at(x, y, len(self.model.tiles))
        if self._click_cross(index, x, y):
            self.drag = None
            return
        self.drag = None if index is None else _Drag(index, event.x, event.y)

    def _on_motion(self, event) -> None:
        drag = self.drag
        if drag is None:
            return
        if not drag.moved:
            if abs(event.x - drag.x0) + abs(event.y - drag.y0) < DRAG_THRESHOLD:
                return
            drag.moved = True
            self.redraw()
        x, y = self._canvas_point(event)
        layout, tile = self.layout, self.model.tiles[drag.index]
        self.delete("ghost")
        photo = self._photo(tile)
        if photo is not None:
            self.create_image(x, y, image=photo, tags="ghost")
            self.create_rectangle(x - layout.tile_w // 2, y - layout.tile_h // 2, x + layout.tile_w // 2,
                                  y + layout.tile_h // 2, outline="#0095f6", width=3, tags="ghost")
        drag.target = layout.slot_at(x, y, len(self.model.tiles))
        tx, ty = layout.slot_origin(drag.target)
        self.delete("slot")
        self.create_rectangle(tx, ty, tx + layout.tile_w, ty + layout.tile_h, outline="#ffb400", width=4, tags="slot")
        self.tag_raise("ghost")
        if event.y < 30:  # défilement automatique près des bords
            self.yview_scroll(-1, "units")
        elif event.y > self.winfo_height() - 30:
            self.yview_scroll(1, "units")

    def _on_release(self, event) -> None:
        drag, self.drag = self.drag, None
        if drag is None:
            return
        if not drag.moved:
            self.on_select(drag.index)
            return
        target = drag.index if drag.target is None else drag.target
        if target != drag.index:
            self.on_reorder(drag.index, target)
        self.redraw()

    def _on_double_click(self, event) -> None:
        x, y = self._canvas_point(event)
        index = self.layout.tile_at(x, y, len(self.model.tiles))
        if self._click_cross(index, x, y):  # deux clics rapides sur la croix : pas de visionneuse
            return
        if index is not None:
            self.on_select(index)
            self.on_open(index)

    def _on_context(self, event) -> None:
        index = self._tile_at(event)
        if index is not None:
            self.on_select(index)
            self.on_context(index, event.x_root, event.y_root)
