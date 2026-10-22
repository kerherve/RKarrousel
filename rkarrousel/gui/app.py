"""Fenêtre principale : assemble les onglets, le panneau d'aperçu, la barre de progression et les contrôleurs."""
import logging
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from rkarrousel import i18n
from rkarrousel.config import load_config
from rkarrousel.gui.batch_controller import BatchController
from rkarrousel.gui.context import AppContext
from rkarrousel.gui.drive_controller import DriveController
from rkarrousel.gui.files_tab import FilesTab, PreviewPanel
from rkarrousel.gui.guide_window import GuideWindow
from rkarrousel.gui.order_flow import OrderController
from rkarrousel.gui.settings_tab import SettingsTab
from rkarrousel.gui.system import FROZEN
from rkarrousel.gui.theme import THEME_CHOICES, apply_theme, place_main_window
from rkarrousel.gui.update_controller import UpdateController
from rkarrousel.i18n import t
from rkarrousel.paths import CONFIG_PATH, LOG_PATH
from rkarrousel.services import updater
from rkarrousel.version import __version__

logger = logging.getLogger("imagesplitter")


class PhotoSplitterGUI:
    def __init__(self, root: tk.Tk, config_path: Path = CONFIG_PATH):
        self.root = root
        config = load_config(config_path)
        i18n.set_language(config.get("language"))
        theme = apply_theme(config.get("theme", "auto"), root)
        place_main_window(root, theme.scale)

        self.ctx = ctx = AppContext(root, config, theme, config_path)
        self.drive = DriveController(ctx)
        self.batch = BatchController(ctx, self.drive)
        self.updates = UpdateController(ctx)
        self.order = OrderController(ctx)
        ctx.on_processing_changed = self.apply_processing_state

        self.preview = self.files_tab = self.settings_tab = self.notebook = None
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        root.report_callback_exception = self.on_tk_exception
        root.bind("<F1>", lambda _e: self.show_guide())
        self.guide_window = None
        self.build_ui()
        ctx.set_status(t("status_ready"))
        ctx.bus.start()
        root.after(3000, self.updates.auto_check)
        if FROZEN:  # l'ancienne version (.old) est encore verrouillée juste après une mise à jour : on réessaie
            root.after(10000, lambda: updater.cleanup_leftovers(Path(sys.executable)))

    # ------------------------------------------------------------------ accès pratiques
    @property
    def config(self) -> dict:
        return self.ctx.config

    @property
    def model(self):
        return self.ctx.model

    def collect_config(self) -> dict:
        return self.ctx.collect_config()

    # ------------------------------------------------------------------ construction de l'interface
    def build_ui(self, select_tab: int = 0) -> None:
        ctx, root = self.ctx, self.root
        for child in root.winfo_children():
            child.destroy()
        root.title(f"{t('app_title')} v{__version__}")

        # barre d'état d'abord : elle reste collée en bas
        status_frame = ttk.Frame(root)
        status_frame.pack(side=tk.BOTTOM, fill=tk.X)
        ttk.Label(
            status_frame, textvariable=ctx.status_text, style="Hint.TLabel", anchor=tk.W, padding=(22, 4, 22, 8)
        ).pack(fill=tk.X)

        container = ttk.Frame(root, padding=(22, 16, 22, 16))
        container.pack(fill=tk.BOTH, expand=True)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(1, weight=1)

        self._build_header(container)
        self.preview = PreviewPanel(container, ctx)
        self.preview.grid(row=1, column=1, sticky=tk.NSEW, padx=(16, 0))

        self.notebook = ttk.Notebook(container)
        self.notebook.grid(row=1, column=0, sticky=tk.NSEW)
        self.files_tab = FilesTab(self.notebook, ctx, self.preview)
        self.settings_tab = SettingsTab(
            self.notebook, ctx, self.drive, self.change_language, self.change_theme,
            on_check_updates=lambda: self.updates.check(manual=True),
        )
        self.notebook.add(self.files_tab, text=t("tab_files"))
        self.notebook.add(self.settings_tab, text=t("tab_settings"))
        if select_tab:
            self.notebook.select(select_tab)

        self._build_controls(container)

    def _build_header(self, container: ttk.Frame) -> None:
        header = ttk.Frame(container)
        header.grid(row=0, column=0, columnspan=2, sticky=tk.EW, pady=(0, 14))
        titles = ttk.Frame(header)
        titles.pack(side=tk.LEFT)
        ttk.Label(titles, text=t("app_heading"), style="Title.TLabel").pack(anchor=tk.W)
        ttk.Label(titles, text=t("app_subtitle"), style="Subtitle.TLabel").pack(anchor=tk.W)
        ttk.Button(header, text=t("about"), command=self.show_about).pack(side=tk.RIGHT, anchor=tk.S)
        ttk.Button(header, text=t("guide"), command=self.show_guide).pack(side=tk.RIGHT, anchor=tk.S, padx=(0, 8))

    def _build_controls(self, container: ttk.Frame) -> None:
        ctx = self.ctx
        controls = ttk.Frame(container)
        controls.grid(row=2, column=0, columnspan=2, sticky=tk.EW, pady=(16, 0))
        ttk.Progressbar(controls, variable=ctx.progress_value, maximum=100).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 16)
        )
        self.order_button = ttk.Button(controls, text=t("btn_order"), command=self.order.open)
        self.order_button.pack(side=tk.LEFT, padx=(0, 10))
        self.process_button = ttk.Button(
            controls, text=t("btn_process"), command=self.batch.start, style=ctx.theme.accent_style
        )
        self.process_button.pack(side=tk.LEFT)
        self.cancel_button = ttk.Button(controls, text=t("btn_cancel"), command=self.batch.cancel)
        self.apply_processing_state()

    def apply_processing_state(self) -> None:
        """Pendant un traitement : bouton « Annuler » à la place de « Lancer », et grille d'ordre indisponible."""
        try:
            if self.ctx.processing:
                self.process_button.pack_forget()
                self.cancel_button.pack(side=tk.LEFT)
                self.order_button.state(["disabled"])
            else:
                self.cancel_button.pack_forget()
                self.process_button.pack(side=tk.LEFT)
                self.order_button.state(["!disabled"])
        except tk.TclError:  # widgets détruits pendant une reconstruction
            pass

    # ------------------------------------------------------------------ langue et thème
    def change_language(self, index: int) -> None:
        codes = list(i18n.LANGUAGES)
        if not 0 <= index < len(codes) or codes[index] == i18n.get_language():
            return
        i18n.set_language(codes[index])
        self.config["language"] = codes[index]
        self.ctx.save_config()
        self._rebuild()

    def change_theme(self, index: int) -> None:
        if not 0 <= index < len(THEME_CHOICES) or THEME_CHOICES[index] == self.config.get("theme", "auto"):
            return
        self.config["theme"] = THEME_CHOICES[index]
        self.ctx.save_config()
        self.ctx.theme = apply_theme(THEME_CHOICES[index], self.root)
        self._rebuild()

    def _rebuild(self) -> None:
        """Reconstruit l'interface (nouvelle langue ou nouveau thème) en restant sur l'onglet Réglages."""
        self.order.close()
        if self.guide_window is not None and self.guide_window.winfo_exists():
            self.guide_window.destroy()
        self.build_ui(select_tab=1)
        self.ctx.set_status(t("status_ready"))

    # ------------------------------------------------------------------ divers
    def show_guide(self) -> None:
        """Ouvre le guide (une seule fenêtre : si elle existe déjà, on la ramène devant)."""
        if self.guide_window is not None and self.guide_window.winfo_exists():
            self.guide_window.lift()
            self.guide_window.focus_set()
            return
        self.guide_window = GuideWindow(self.root)

    def show_about(self) -> None:
        messagebox.showinfo(t("about"), t("about_text", version=__version__, log=str(LOG_PATH)))

    def on_close(self) -> None:
        ctx = self.ctx
        if ctx.processing and not messagebox.askyesno(t("dlg_quit_title"), t("dlg_quit_processing")):
            return
        ctx.cancel_event.set()
        try:
            ctx.collect_config()
            ctx.save_config()
        finally:
            self.root.destroy()

    def on_tk_exception(self, exc_type, exc, tb) -> None:
        logger.error("Erreur d'interface", exc_info=(exc_type, exc, tb))
        messagebox.showerror(t("dlg_error"), t("dlg_unexpected", error=exc, log=str(LOG_PATH)))
