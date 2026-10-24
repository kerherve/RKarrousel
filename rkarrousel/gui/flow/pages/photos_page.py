"""Étape « Photos » : la liste des photos et dossiers à traiter, le dossier de destination, le format des images, et
l'aperçu de la photo sélectionnée."""
import logging
import os
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Callable, Iterable, Optional

from rkarrousel.gui.context import AppContext
from rkarrousel.gui.flow.pages.base import Page
from rkarrousel.gui.flow.pages.preview_panel import PreviewPanel
from rkarrousel.gui.settings_groups import FormatGroup
from rkarrousel.gui.system import DND_FILES
from rkarrousel.i18n import t

logger = logging.getLogger("imagesplitter")


class PhotosPage(Page):
    """Liste des photos et dossiers à traiter, choix du dossier de destination et du format des images."""

    def __init__(self, parent: tk.Misc, ctx: AppContext, on_change: Optional[Callable[[], None]] = None):
        """`on_change` : la liste de photos ou le dossier de destination ont changé (le flux met ses boutons à jour)."""
        super().__init__(parent)
        self.ctx, self.model, self.session, self.on_change = ctx, ctx.model, ctx.session, on_change
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        left = ttk.Frame(self)
        left.grid(row=0, column=0, sticky=tk.NSEW)
        left.columnconfigure(0, weight=1)
        left.rowconfigure(1, weight=1)
        self.preview = PreviewPanel(self, ctx)
        self.preview.grid(row=0, column=1, sticky=tk.NSEW, padx=(16, 0))
        self._build_list(left)
        self.setup_drop_target()
        self.refresh_list()

    def _build_list(self, left: ttk.Frame) -> None:
        buttons = ttk.Frame(left)
        buttons.grid(row=0, column=0, sticky=tk.EW, pady=(0, 8))
        ttk.Button(buttons, text=t("add_files"), command=self.add_files).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(buttons, text=t("add_folder"), command=self.add_folder).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(buttons, text=t("clear_selection"), command=self.clear_selection).pack(side=tk.LEFT)

        list_frame = ttk.Frame(left)
        list_frame.grid(row=1, column=0, sticky=tk.NSEW)
        self.listbox = ttk.Treeview(list_frame, show="tree", selectmode="browse", height=6)
        self.listbox.column("#0", stretch=True)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.listbox.bind("<<TreeviewSelect>>", self.on_list_select)
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.listbox.yview)
        scrollbar.pack(side=tk.LEFT, fill=tk.Y)
        self.listbox.configure(yscrollcommand=scrollbar.set)
        ttk.Label(left, text=t("drop_hint") if DND_FILES else "", style="Hint.TLabel").grid(
            row=2, column=0, sticky=tk.W, pady=(6, 0)
        )

        dest = ttk.LabelFrame(left, text=t("dest_group"), padding=12)
        dest.grid(row=3, column=0, sticky=tk.EW, pady=(14, 0))
        dest.columnconfigure(0, weight=1)
        ttk.Entry(dest, textvariable=self.model.dest_dir, state="readonly").grid(row=0, column=0, sticky=tk.EW, padx=(0, 8))
        ttk.Button(dest, text=t("choose_folder"), command=self.choose_dest).grid(row=0, column=1, padx=(0, 4))
        ttk.Button(dest, text=t("open"), command=self.open_dest_folder).grid(row=0, column=2)
        FormatGroup(left, self.ctx).grid(row=4, column=0, sticky=tk.EW, pady=(14, 0))
        self.model.dest_dir.trace_add("write", lambda *_: self._changed())

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
        self._changed()

    def _changed(self) -> None:
        if self.on_change is not None:
            self.on_change()

    def refresh_list(self) -> None:
        self.listbox.delete(*self.listbox.get_children())
        unique = []
        for path in self.session.selected_paths:
            if path not in unique:
                unique.append(path)
        self.session.selected_paths = unique
        for index, path in enumerate(unique):
            self.listbox.insert("", tk.END, iid=str(index), text=f"  {path}")
        self._changed()

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
