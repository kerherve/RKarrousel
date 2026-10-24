"""Onglet « Fichiers » (liste des photos, dossier de destination) et panneau d'aperçu."""
import logging
import os
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Iterable

from PIL import Image, ImageOps, ImageTk

from rkarrousel.gui.context import AppContext
from rkarrousel.gui.system import DND_FILES
from rkarrousel.i18n import t
from rkarrousel.pipeline import gather_input_files

logger = logging.getLogger("imagesplitter")


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


class FilesTab(ttk.Frame):
    """Liste des photos et dossiers à traiter, choix du dossier de destination et de la numérotation."""

    def __init__(self, parent: tk.Misc, ctx: AppContext, preview: PreviewPanel):
        super().__init__(parent, padding=14)
        self.ctx, self.preview, self.model, self.session = ctx, preview, ctx.model, ctx.session
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        buttons = ttk.Frame(self)
        buttons.grid(row=0, column=0, sticky=tk.EW, pady=(0, 8))
        ttk.Button(buttons, text=t("add_files"), command=self.add_files).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(buttons, text=t("add_folder"), command=self.add_folder).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(buttons, text=t("clear_selection"), command=self.clear_selection).pack(side=tk.LEFT)

        list_frame = ttk.Frame(self)
        list_frame.grid(row=1, column=0, sticky=tk.NSEW)
        self.listbox = ttk.Treeview(list_frame, show="tree", selectmode="browse", height=6)
        self.listbox.column("#0", stretch=True)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.listbox.bind("<<TreeviewSelect>>", self.on_list_select)
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.listbox.yview)
        scrollbar.pack(side=tk.LEFT, fill=tk.Y)
        self.listbox.configure(yscrollcommand=scrollbar.set)
        ttk.Label(self, text=t("drop_hint") if DND_FILES else "", style="Hint.TLabel").grid(
            row=2, column=0, sticky=tk.W, pady=(6, 0)
        )

        dest = ttk.LabelFrame(self, text=t("dest_group"), padding=12)
        dest.grid(row=3, column=0, sticky=tk.EW, pady=(14, 0))
        dest.columnconfigure(0, weight=1)
        ttk.Entry(dest, textvariable=self.model.dest_dir, state="readonly").grid(row=0, column=0, sticky=tk.EW, padx=(0, 8))
        ttk.Button(dest, text=t("choose_folder"), command=self.choose_dest).grid(row=0, column=1, padx=(0, 4))
        ttk.Button(dest, text=t("open"), command=self.open_dest_folder).grid(row=0, column=2)
        self.setup_drop_target()
        self.refresh_list()

    # ------------------------------------------------------------------ glisser-déposer
    def setup_drop_target(self) -> None:
        if DND_FILES is None or not hasattr(self.ctx.root, "drop_target_register"):
            return
        try:
            for widget in (self.listbox, self.preview.canvas):
                widget.drop_target_register(DND_FILES)
                widget.dnd_bind("<<Drop>>", self.on_drop)
        except Exception:
            logger.exception("Glisser-déposer indisponible")

    def on_drop(self, event):
        self.add_paths(list(self.ctx.root.tk.splitlist(event.data)))
        return event.action

    # ------------------------------------------------------------------ sélection
    def add_paths(self, paths: Iterable[str]) -> None:
        paths = list(paths)
        added = False
        for raw in paths:
            if raw and raw not in self.session.selected_paths:
                self.session.selected_paths.append(raw)
                added = True
        if added:
            first = Path(paths[0])
            self.model.source_dir.set(str(first if first.is_dir() else first.parent))
            had_selection = bool(self.listbox.selection())
            self.refresh_list()
            if not had_selection and self.session.selected_paths:
                self.listbox.selection_set("0")  # la première entrée est prévisualisée d'office
                self.on_list_select(None)

    def add_files(self) -> None:
        files = filedialog.askopenfilenames(
            title=t("dlg_select_files"),
            initialdir=self.model.source_dir.get() or os.getcwd(),
            filetypes=[(t("filetype_images"), "*.jpg *.jpeg *.png *.tif *.tiff *.bmp"), (t("filetype_all"), "*.*")],
        )
        if files:
            self.add_paths(list(files))

    def add_folder(self) -> None:
        folder = filedialog.askdirectory(title=t("dlg_select_folder"), initialdir=self.model.source_dir.get() or os.getcwd())
        if folder:
            self.add_paths([folder])

    def clear_selection(self) -> None:
        self.session.clear()
        self.listbox.delete(*self.listbox.get_children())
        self.preview.clear()

    def refresh_list(self) -> None:
        self.listbox.delete(*self.listbox.get_children())
        unique = []
        for path in self.session.selected_paths:
            if path not in unique:
                unique.append(path)
        self.session.selected_paths = unique
        for index, path in enumerate(unique):
            self.listbox.insert("", tk.END, iid=str(index), text=f"  {path}")

    def on_list_select(self, event) -> None:
        selection = self.listbox.selection()
        if selection:
            self.preview.show_entry(self.session.selected_paths[int(selection[0])])

    # ------------------------------------------------------------------ destination
    def choose_dest(self) -> None:
        folder = filedialog.askdirectory(title=t("dlg_select_dest"), initialdir=self.model.dest_dir.get() or os.getcwd())
        if folder:
            self.model.dest_dir.set(folder)

    def open_dest_folder(self) -> None:
        folder = self.model.dest_dir.get()
        if not folder:
            messagebox.showwarning(t("dlg_missing_folder_title"), t("dlg_missing_folder"))
            return
        folder_path = Path(folder)
        folder_path.mkdir(parents=True, exist_ok=True)
        try:
            if os.name == "nt":
                os.startfile(folder_path)
            else:
                os.system(f"xdg-open '{folder_path}'")
        except Exception as exc:
            messagebox.showerror(t("dlg_error"), t("dlg_open_failed", error=exc))
