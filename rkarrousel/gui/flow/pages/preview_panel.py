"""Aperçu de la photo (ou de la première photo d'un dossier) sélectionnée dans la liste de l'étape « Photos »."""
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from PIL import Image, ImageOps, ImageTk

from rkarrousel.gui.context import AppContext
from rkarrousel.i18n import t
from rkarrousel.pipeline import gather_input_files


class PreviewPanel(ttk.LabelFrame):
    """Aperçu de la photo (ou de la première photo d'un dossier) sélectionnée dans la liste."""

    def __init__(self, parent: tk.Misc, ctx: AppContext):
        super().__init__(parent, text=t("preview_group"), padding=12)
        scale = ctx.theme.scale
        self.width, self.height = int(400 * scale), int(380 * scale)
        self.canvas = tk.Canvas(
            self, width=self.width, height=self.height, bg=ctx.theme.surface_color(), highlightthickness=0
        )
        self.canvas.pack(fill=tk.BOTH, expand=False)
        self.info = tk.StringVar(value=t("preview_hint"))
        ttk.Label(self, textvariable=self.info, wraplength=self.width - 20, justify=tk.LEFT).pack(fill=tk.X, pady=(10, 0))
        self.photo = None
        self.draw_placeholder()

    def draw_placeholder(self) -> None:
        self.canvas.delete("all")
        self.canvas.create_rectangle(2, 2, self.width - 2, self.height - 2, outline="#8a8a8a", dash=(4, 4), width=1)
        self.canvas.create_text(
            self.width // 2, self.height // 2, text=t("preview_empty"), fill="#8a8a8a",
            font=("Segoe UI", 12), justify=tk.CENTER,
        )

    def clear(self) -> None:
        self.photo = None
        self.draw_placeholder()
        self.info.set(t("preview_hint"))

    def show_entry(self, entry: str) -> None:
        """Aperçu d'une entrée de la liste : une photo, ou la première photo d'un dossier."""
        path = Path(entry)
        if path.is_file():
            self.show_image(path)
            return
        images = gather_input_files([entry])
        if images:
            self.show_image(images[0], extra=t("preview_folder", path=entry, count=len(images)))
        else:
            self.draw_placeholder()
            self.info.set(t("preview_folder_empty", path=entry))

    def show_image(self, path: Path, extra: str = "") -> None:
        try:
            img = ImageOps.exif_transpose(Image.open(path))
            img.thumbnail((self.width, self.height))
            self.photo = ImageTk.PhotoImage(img)
            self.canvas.delete("all")
            self.canvas.create_image(self.width // 2, self.height // 2, image=self.photo)
            width, height = img.size
            ratio = width / height if height else 0
            info = t("preview_info", name=path.name, width=width, height=height, ratio=ratio)
            self.info.set(f"{extra}\n{info}" if extra else info)
        except Exception as exc:
            self.info.set(t("preview_error", error=exc))
