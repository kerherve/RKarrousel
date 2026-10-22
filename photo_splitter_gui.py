#!/usr/bin/env python3
import logging
import os
import queue
import sys
import threading
import tkinter as tk
from logging.handlers import RotatingFileHandler
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox, ttk
from typing import Dict, List, Optional, Set, Tuple

from PIL import Image, ImageOps, ImageTk

import i18n
from i18n import kind_label, t
from order_window import OrderWindow
from utils import (
    CONFIG_PATH,
    DEFAULT_BACKGROUND_COLOR_HEX,
    DEFAULT_BLUR_STRENGTH,
    DEFAULT_BORDER_COLOR_HEX,
    DEFAULT_FRAME_RATIO,
    DEFAULT_JPEG_QUALITY,
    DEFAULT_LANDSCAPE_FILL_MODE,
    DEFAULT_NUMBER_FILES,
    DEFAULT_SIGNATURE_POSITION,
    DEFAULT_SIGNATURE_SCALE,
    KIND_CROP,
    LOG_PATH,
    OPTIONAL_KINDS,
    SIGNATURE_POSITIONS,
    FileResult,
    gather_input_files,
    disabled_kinds_of,
    load_config,
    parse_color,
    process_batch,
    save_config,
)
from version import __version__

# Le glisser-déposer de fichiers est optionnel : sans `tkinterdnd2`, l'appli fonctionne comme avant.
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
except Exception:  # pragma: no cover - dépend de l'installation
    DND_FILES = None
    TkinterDnD = None

# Thème moderne (Sun Valley) optionnel : sans `sv_ttk`, l'appli garde le thème Tk de base.
try:
    import sv_ttk
except Exception:  # pragma: no cover - dépend de l'installation
    sv_ttk = None

logger = logging.getLogger("imagesplitter")
WORKERS = max(1, min(3, os.cpu_count() or 1))
MAX_ERRORS_SHOWN = 10
THEME_CHOICES = ("auto", "light", "dark")


def setup_logging() -> None:
    """Journal à côté de l'exécutable : en mode fenêtré il n'y a pas de console pour voir les erreurs."""
    logger.setLevel(logging.INFO)
    if any(isinstance(h, RotatingFileHandler) for h in logger.handlers):
        return
    try:
        handler = RotatingFileHandler(LOG_PATH, maxBytes=500_000, backupCount=1, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
    except OSError:
        pass


def system_prefers_dark() -> bool:
    """Vrai si Windows est réglé sur le mode d'application sombre."""
    if os.name != "nt":
        return False
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        ) as key:
            return winreg.QueryValueEx(key, "AppsUseLightTheme")[0] == 0
    except OSError:
        return False


def enable_dpi_awareness() -> None:
    """Évite le texte flou sur les écrans mis à l'échelle (125 %, 150 %…) sous Windows."""
    if os.name != "nt":
        return
    try:
        import ctypes

        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def _var_value(var: tk.Variable, default):
    """Lit une variable Tk saisie à la main (Spinbox) sans planter si le champ est vide ou invalide."""
    try:
        return var.get()
    except (tk.TclError, ValueError):
        return default


class PhotoSplitterGUI:
    def __init__(self, root):
        self.root = root
        self.config = load_config(CONFIG_PATH)
        i18n.set_language(self.config.get("language"))
        self.dark = self.apply_theme()
        self.scale = max(1.0, self.root.winfo_fpixels("1i") / 96)
        self.setup_geometry()

        self.selected_paths: List[str] = []
        self.preview_image = None
        self.order: List[str] = []
        self.excluded: Set[str] = set()
        self.preview_cache: Dict[str, Tuple[str, Image.Image]] = {}
        self.order_window: Optional[OrderWindow] = None
        self.events: "queue.Queue[tuple]" = queue.Queue()
        self.cancel_event = threading.Event()
        self.processing = False

        cfg = self.config
        self.source_dir = tk.StringVar(value=cfg.get("last_source_dir", ""))
        self.dest_dir = tk.StringVar(value=cfg.get("last_dest_dir", "output"))
        self.frame_ratio = tk.DoubleVar(value=cfg.get("frame_ratio", DEFAULT_FRAME_RATIO))
        self.landscape_fill_mode = tk.StringVar(value=cfg.get("landscape_fill_mode", DEFAULT_LANDSCAPE_FILL_MODE))
        self.signature_path = tk.StringVar(value=cfg.get("signature_path", ""))
        self.number_files = tk.BooleanVar(value=cfg.get("number_files", DEFAULT_NUMBER_FILES))
        self.border_color = tk.StringVar(value=cfg.get("border_color", DEFAULT_BORDER_COLOR_HEX))
        self.background_color = tk.StringVar(value=cfg.get("background_color", DEFAULT_BACKGROUND_COLOR_HEX))
        disabled = disabled_kinds_of(cfg)
        self.kind_vars = {kind: tk.BooleanVar(value=kind not in disabled) for kind in OPTIONAL_KINDS + (KIND_CROP,)}
        self.blur_strength = tk.DoubleVar(value=cfg.get("blur_strength", DEFAULT_BLUR_STRENGTH))
        self.jpeg_quality = tk.IntVar(value=cfg.get("jpeg_quality", DEFAULT_JPEG_QUALITY))
        self.signature_position = tk.StringVar(value=cfg.get("signature_position", DEFAULT_SIGNATURE_POSITION))
        self.signature_scale = tk.DoubleVar(value=cfg.get("signature_scale", DEFAULT_SIGNATURE_SCALE))
        self.language = tk.StringVar(value=i18n.get_language())
        self.status_text = tk.StringVar(value="")
        self.selected_file_info = tk.StringVar(value="")
        self.progress_value = tk.DoubleVar(value=0)

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.report_callback_exception = self.on_tk_exception
        self.build_ui()
        self.set_status(t("status_ready"))
        self.root.after(100, self.poll_events)

    # ------------------------------------------------------------------ apparence
    def apply_theme(self) -> bool:
        """Applique le thème (clair/sombre selon Windows, ou `theme` de la config). Renvoie True si sombre."""
        choice = self.config.get("theme", "auto")
        dark = system_prefers_dark() if choice == "auto" else choice == "dark"
        if sv_ttk is not None:
            try:
                sv_ttk.set_theme("dark" if dark else "light")
            except Exception:
                logger.exception("Thème indisponible")
        style = ttk.Style()
        style.configure("Title.TLabel", font=("Segoe UI", 20, "bold"))
        style.configure("Subtitle.TLabel", font=("Segoe UI", 10), foreground="#8a8a8a")
        style.configure("Hint.TLabel", font=("Segoe UI", 9), foreground="#8a8a8a")
        self.accent_style = "Accent.TButton" if sv_ttk is not None else "TButton"
        return dark

    def setup_geometry(self):
        """Taille adaptée à l'écran (échelle Windows comprise) et fenêtre centrée, barre des tâches exclue."""
        screen_w, screen_h = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        width = min(int(1120 * self.scale), screen_w - 40)
        height = min(int(760 * self.scale), screen_h - 140)
        x = max(0, (screen_w - width) // 2)
        y = max(0, (screen_h - height) // 2 - 30)
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.root.minsize(min(int(980 * self.scale), width), min(int(600 * self.scale), height))

    def surface_color(self) -> str:
        return ttk.Style().lookup("TFrame", "background") or ("#1c1c1c" if self.dark else "#fafafa")

    # ------------------------------------------------------------------ construction de l'UI
    def build_ui(self):
        for child in self.root.winfo_children():
            if child is not self.order_window:
                child.destroy()
        self.root.title(f"{t('app_title')} v{__version__}")
        self.selected_file_info.set(t("preview_hint"))

        # barre d'état d'abord : elle reste collée en bas
        status_frame = ttk.Frame(self.root)
        status_frame.pack(side=tk.BOTTOM, fill=tk.X)
        self.status_bar = ttk.Label(
            status_frame, textvariable=self.status_text, style="Hint.TLabel", anchor=tk.W, padding=(22, 4, 22, 8)
        )
        self.status_bar.pack(fill=tk.X)

        container = ttk.Frame(self.root, padding=(22, 16, 22, 16))
        container.pack(fill=tk.BOTH, expand=True)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(1, weight=1)

        header = ttk.Frame(container)
        header.grid(row=0, column=0, columnspan=2, sticky=tk.EW, pady=(0, 14))
        titles = ttk.Frame(header)
        titles.pack(side=tk.LEFT)
        ttk.Label(titles, text=t("app_heading"), style="Title.TLabel").pack(anchor=tk.W)
        ttk.Label(titles, text=t("app_subtitle"), style="Subtitle.TLabel").pack(anchor=tk.W)
        ttk.Button(header, text=t("about"), command=self.show_about).pack(side=tk.RIGHT, anchor=tk.S)
        language_box = ttk.Combobox(
            header,
            state="readonly",
            width=10,
            values=[i18n.LANGUAGES[code] for code in i18n.LANGUAGES],
        )
        language_box.set(i18n.LANGUAGES[i18n.get_language()])
        language_box.bind("<<ComboboxSelected>>", lambda e: self.change_language(language_box.current()))
        language_box.pack(side=tk.RIGHT, padx=(0, 10), anchor=tk.S)
        ttk.Label(header, text=t("language"), style="Subtitle.TLabel").pack(side=tk.RIGHT, padx=(0, 6), anchor=tk.S, pady=(0, 6))
        theme_box = ttk.Combobox(
            header, state="readonly", width=9, values=[t("theme_auto"), t("theme_light"), t("theme_dark")]
        )
        theme_box.current(THEME_CHOICES.index(self.config.get("theme", "auto")) if self.config.get("theme", "auto") in THEME_CHOICES else 0)
        theme_box.bind("<<ComboboxSelected>>", lambda e: self.change_theme(theme_box.current()))
        theme_box.pack(side=tk.RIGHT, padx=(0, 16), anchor=tk.S)
        ttk.Label(header, text=t("theme"), style="Subtitle.TLabel").pack(side=tk.RIGHT, padx=(0, 6), anchor=tk.S, pady=(0, 6))

        self.notebook = notebook = ttk.Notebook(container)
        notebook.grid(row=1, column=0, sticky=tk.NSEW)
        tab_files = ttk.Frame(notebook, padding=14)
        tab_settings = ttk.Frame(notebook, padding=14)
        notebook.add(tab_files, text=t("tab_files"))
        notebook.add(tab_settings, text=t("tab_settings"))
        self.build_files_tab(tab_files)
        self.build_settings_tab(tab_settings)

        preview_frame = ttk.LabelFrame(container, text=t("preview_group"), padding=12)
        preview_frame.grid(row=1, column=1, sticky=tk.NSEW, padx=(16, 0))
        self.preview_w, self.preview_h = int(400 * self.scale), int(380 * self.scale)
        self.canvas = tk.Canvas(
            preview_frame, width=self.preview_w, height=self.preview_h, bg=self.surface_color(), highlightthickness=0
        )
        self.canvas.pack(fill=tk.BOTH, expand=False)
        ttk.Label(
            preview_frame, textvariable=self.selected_file_info, wraplength=self.preview_w - 20, justify=tk.LEFT
        ).pack(fill=tk.X, pady=(10, 0))
        self.draw_preview_placeholder()

        control_frame = ttk.Frame(container)
        control_frame.grid(row=2, column=0, columnspan=2, sticky=tk.EW, pady=(16, 0))
        self.progress = ttk.Progressbar(control_frame, variable=self.progress_value, maximum=100)
        self.progress.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 16))
        self.order_button = ttk.Button(control_frame, text=t("btn_order"), command=self.open_order_window)
        self.order_button.pack(side=tk.LEFT, padx=(0, 10))
        self.process_button = ttk.Button(
            control_frame, text=t("btn_process"), command=self.start_processing, style=self.accent_style
        )
        self.process_button.pack(side=tk.LEFT)
        self.cancel_button = ttk.Button(control_frame, text=t("btn_cancel"), command=self.cancel_processing)
        self.apply_processing_state()

        self.setup_drop_target()
        self.refresh_list()

    def build_files_tab(self, tab):
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(1, weight=1)

        btn_frame = ttk.Frame(tab)
        btn_frame.grid(row=0, column=0, sticky=tk.EW, pady=(0, 8))
        ttk.Button(btn_frame, text=t("add_files"), command=self.add_files).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(btn_frame, text=t("add_folder"), command=self.add_folder).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(btn_frame, text=t("clear_selection"), command=self.clear_selection).pack(side=tk.LEFT)

        list_frame = ttk.Frame(tab)
        list_frame.grid(row=1, column=0, sticky=tk.NSEW)
        self.listbox = ttk.Treeview(list_frame, show="tree", selectmode="browse", height=6)
        self.listbox.column("#0", stretch=True)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.listbox.bind("<<TreeviewSelect>>", self.on_list_select)
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.listbox.yview)
        scrollbar.pack(side=tk.LEFT, fill=tk.Y)
        self.listbox.configure(yscrollcommand=scrollbar.set)
        self.drop_hint = ttk.Label(tab, text=t("drop_hint") if DND_FILES else "", style="Hint.TLabel")
        self.drop_hint.grid(row=2, column=0, sticky=tk.W, pady=(6, 0))

        dest = ttk.LabelFrame(tab, text=t("dest_group"), padding=12)
        dest.grid(row=3, column=0, sticky=tk.EW, pady=(14, 0))
        dest.columnconfigure(0, weight=1)
        ttk.Entry(dest, textvariable=self.dest_dir, state="readonly").grid(row=0, column=0, sticky=tk.EW, padx=(0, 8))
        ttk.Button(dest, text=t("choose_folder"), command=self.choose_dest).grid(row=0, column=1, padx=(0, 4))
        ttk.Button(dest, text=t("open"), command=self.open_dest_folder).grid(row=0, column=2)
        ttk.Checkbutton(dest, text=t("number_files"), variable=self.number_files).grid(
            row=1, column=0, columnspan=3, sticky=tk.W, pady=(8, 0)
        )

    def build_settings_tab(self, tab):
        tab.columnconfigure(0, weight=1)

        frame_group = ttk.LabelFrame(tab, text=t("frame_group"), padding=12)
        frame_group.grid(row=0, column=0, sticky=tk.EW, pady=(0, 8))
        ttk.Label(frame_group, text=t("frame_ratio")).grid(row=0, column=0, sticky=tk.W)
        ttk.Spinbox(frame_group, from_=0.01, to=0.2, increment=0.01, textvariable=self.frame_ratio, width=8).grid(
            row=0, column=1, padx=8
        )
        ttk.Label(frame_group, text=t("frame_ratio_hint")).grid(row=0, column=2, sticky=tk.W)
        ttk.Label(frame_group, text=t("frame_color")).grid(row=1, column=0, sticky=tk.W, pady=(8, 0))
        color_row = ttk.Frame(frame_group)
        color_row.grid(row=1, column=1, columnspan=2, sticky=tk.W, pady=(8, 0), padx=8)
        self.color_swatch = tk.Label(color_row, width=4, relief=tk.SOLID, borderwidth=1)
        self.color_swatch.pack(side=tk.LEFT, padx=(0, 8))
        ttk.Entry(color_row, textvariable=self.border_color, width=10).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(color_row, text=t("choose_color"), command=self.choose_border_color).pack(side=tk.LEFT)
        self.border_color.trace_add("write", lambda *_: self.update_color_swatch())
        self.update_color_swatch()

        fill_group = ttk.LabelFrame(tab, text=t("fill_group"), padding=12)
        fill_group.grid(row=1, column=0, sticky=tk.EW, pady=(0, 8))
        ttk.Radiobutton(fill_group, text=t("fill_black"), value="black", variable=self.landscape_fill_mode).grid(
            row=0, column=0, sticky=tk.W, padx=(0, 16)
        )
        ttk.Radiobutton(fill_group, text=t("fill_blur"), value="blur", variable=self.landscape_fill_mode).grid(
            row=0, column=1, sticky=tk.W
        )
        ttk.Label(fill_group, text=t("bg_color")).grid(row=1, column=0, sticky=tk.W, padx=(0, 12), pady=(10, 0))
        bg_row = ttk.Frame(fill_group)
        bg_row.grid(row=1, column=1, columnspan=2, sticky=tk.W, pady=(10, 0))
        self.bg_swatch = tk.Label(bg_row, width=4, relief=tk.SOLID, borderwidth=1)
        self.bg_swatch.pack(side=tk.LEFT, padx=(0, 8))
        ttk.Entry(bg_row, textvariable=self.background_color, width=10).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(bg_row, text=t("choose_color"), command=self.choose_background_color).pack(side=tk.LEFT)
        self.background_color.trace_add("write", lambda *_: self.update_color_swatch())
        self.update_color_swatch()
        ttk.Label(fill_group, text=t("blur_strength")).grid(row=2, column=0, sticky=tk.W, pady=(10, 0))
        blur_row = ttk.Frame(fill_group)
        blur_row.grid(row=2, column=1, columnspan=2, sticky=tk.W, pady=(10, 0))
        ttk.Spinbox(blur_row, from_=0.2, to=5.0, increment=0.1, textvariable=self.blur_strength, width=6).pack(
            side=tk.LEFT, padx=(0, 8)
        )
        ttk.Label(blur_row, text=t("blur_strength_hint")).pack(side=tk.LEFT)

        sig_group = ttk.LabelFrame(tab, text=t("signature_group"), padding=12)
        sig_group.grid(row=2, column=0, sticky=tk.EW, pady=(0, 8))
        sig_group.columnconfigure(0, weight=1)
        sig_row = ttk.Frame(sig_group)
        sig_row.grid(row=0, column=0, columnspan=4, sticky=tk.EW)
        sig_row.columnconfigure(0, weight=1)
        ttk.Entry(sig_row, textvariable=self.signature_path, state="readonly").grid(row=0, column=0, sticky=tk.EW, padx=(0, 8))
        ttk.Button(sig_row, text=t("choose_signature"), command=self.choose_signature).grid(row=0, column=1, padx=(0, 4))
        ttk.Button(sig_row, text=t("clear"), command=self.clear_signature).grid(row=0, column=2)
        ttk.Label(sig_group, text=t("signature_position")).grid(row=1, column=0, sticky=tk.W, pady=(8, 0))
        position_box = ttk.Combobox(
            sig_group, state="readonly", width=16, values=[t(f"pos_{p}") for p in SIGNATURE_POSITIONS]
        )
        current = self.signature_position.get()
        position_box.current(SIGNATURE_POSITIONS.index(current) if current in SIGNATURE_POSITIONS else 0)
        position_box.bind(
            "<<ComboboxSelected>>", lambda e: self.signature_position.set(SIGNATURE_POSITIONS[position_box.current()])
        )
        position_box.grid(row=1, column=1, sticky=tk.W, pady=(8, 0), padx=8)
        ttk.Label(sig_group, text=t("signature_scale")).grid(row=1, column=2, sticky=tk.E, pady=(8, 0))
        ttk.Spinbox(sig_group, from_=0.3, to=3.0, increment=0.1, textvariable=self.signature_scale, width=6).grid(
            row=1, column=3, sticky=tk.W, pady=(8, 0), padx=8
        )

        output_group = ttk.LabelFrame(tab, text=t("output_group"), padding=12)
        output_group.grid(row=3, column=0, sticky=tk.EW, pady=(0, 8))
        ttk.Label(output_group, text=t("jpeg_quality")).grid(row=0, column=0, sticky=tk.W)
        ttk.Spinbox(output_group, from_=50, to=100, increment=1, textvariable=self.jpeg_quality, width=6).grid(
            row=0, column=1, padx=8
        )
        ttk.Label(output_group, text=t("jpeg_quality_hint")).grid(row=0, column=2, sticky=tk.W)

        kinds_group = ttk.LabelFrame(tab, text=t("kinds_group"), padding=12)
        kinds_group.grid(row=4, column=0, sticky=tk.EW)
        for position, kind in enumerate(OPTIONAL_KINDS + (KIND_CROP,)):
            ttk.Checkbutton(kinds_group, text=kind_label(kind).capitalize(), variable=self.kind_vars[kind]).grid(
                row=position // 2, column=position % 2, sticky=tk.W, padx=(0, 24), pady=2
            )
        ttk.Label(kinds_group, text=t("kinds_hint"), style="Hint.TLabel", wraplength=int(620 * self.scale)).grid(
            row=3, column=0, columnspan=2, sticky=tk.W, pady=(6, 0)
        )

    # ------------------------------------------------------------------ glisser-déposer
    def setup_drop_target(self):
        if DND_FILES is None or not hasattr(self.root, "drop_target_register"):
            return
        try:
            for widget in (self.listbox, self.canvas):
                widget.drop_target_register(DND_FILES)
                widget.dnd_bind("<<Drop>>", self.on_drop)
        except Exception:
            logger.exception("Glisser-déposer indisponible")

    def on_drop(self, event):
        paths = [p for p in self.root.tk.splitlist(event.data)]
        self.add_paths(paths)
        return event.action

    # ------------------------------------------------------------------ langue / à propos
    def change_language(self, index: int):
        codes = list(i18n.LANGUAGES)
        if not 0 <= index < len(codes) or codes[index] == i18n.get_language():
            return
        i18n.set_language(codes[index])
        self.language.set(codes[index])
        self.config["language"] = codes[index]
        save_config(CONFIG_PATH, self.config)
        if self.order_window is not None:
            self.order_window.close()
            self.order_window = None
        self.build_ui()
        self.set_status(t("status_ready"))

    def change_theme(self, index: int):
        if not 0 <= index < len(THEME_CHOICES) or THEME_CHOICES[index] == self.config.get("theme", "auto"):
            return
        self.config["theme"] = THEME_CHOICES[index]
        save_config(CONFIG_PATH, self.config)
        if self.order_window is not None:
            self.order_window.close()
            self.order_window = None
        self.dark = self.apply_theme()
        self.build_ui()
        self.set_status(t("status_ready"))

    def show_about(self):
        messagebox.showinfo(
            t("about"),
            t("about_text", version=__version__, log=str(LOG_PATH)),
        )

    # ------------------------------------------------------------------ sélection
    def add_paths(self, paths):
        added = False
        for raw in paths:
            if raw and raw not in self.selected_paths:
                self.selected_paths.append(raw)
                added = True
        if added:
            first = Path(paths[0])
            self.source_dir.set(str(first if first.is_dir() else first.parent))
            self.refresh_list()

    def add_files(self):
        initial_dir = self.source_dir.get() or os.getcwd()
        files = filedialog.askopenfilenames(
            title=t("dlg_select_files"),
            initialdir=initial_dir,
            filetypes=[(t("filetype_images"), "*.jpg *.jpeg *.png *.tif *.tiff *.bmp"), (t("filetype_all"), "*.*")],
        )
        if files:
            self.add_paths(list(files))

    def add_folder(self):
        folder = filedialog.askdirectory(title=t("dlg_select_folder"), initialdir=self.source_dir.get() or os.getcwd())
        if folder:
            self.add_paths([folder])

    def clear_selection(self):
        self.selected_paths = []
        self.order = []
        self.excluded = set()
        self.listbox.delete(*self.listbox.get_children())
        self.preview_image = None
        self.draw_preview_placeholder()
        self.selected_file_info.set(t("preview_hint"))

    def choose_dest(self):
        folder = filedialog.askdirectory(title=t("dlg_select_dest"), initialdir=self.dest_dir.get() or os.getcwd())
        if folder:
            self.dest_dir.set(folder)

    def open_dest_folder(self):
        folder = self.dest_dir.get()
        if not folder:
            messagebox.showwarning(t("dlg_missing_folder_title"), t("dlg_missing_folder"))
            return
        folder_path = Path(folder)
        if not folder_path.exists():
            folder_path.mkdir(parents=True, exist_ok=True)
        try:
            if os.name == "nt":
                os.startfile(folder_path)
            else:
                os.system(f"xdg-open '{folder_path}'")
        except Exception as exc:
            messagebox.showerror(t("dlg_error"), t("dlg_open_failed", error=exc))

    def choose_signature(self):
        sig_file = filedialog.askopenfilename(
            title=t("dlg_select_signature"),
            initialdir=os.path.dirname(self.signature_path.get()) or os.path.expanduser("~"),
            filetypes=[("PNG", "*.png"), (t("filetype_images"), "*.jpg *.jpeg *.bmp"), (t("filetype_all"), "*.*")],
        )
        if sig_file:
            self.signature_path.set(sig_file)

    def clear_signature(self):
        self.signature_path.set("")

    def choose_border_color(self):
        rgb = parse_color(self.border_color.get())
        picked = colorchooser.askcolor(color="#%02x%02x%02x" % rgb, title=t("choose_color"))
        if picked and picked[1]:
            self.border_color.set(picked[1].upper())

    def choose_background_color(self):
        rgb = parse_color(self.background_color.get(), (0, 0, 0))
        picked = colorchooser.askcolor(color="#%02x%02x%02x" % rgb, title=t("bg_color"))
        if picked and picked[1]:
            self.background_color.set(picked[1].upper())

    def update_color_swatch(self):
        for swatch, var, default in (
            (getattr(self, "color_swatch", None), self.border_color, (255, 255, 255)),
            (getattr(self, "bg_swatch", None), self.background_color, (0, 0, 0)),
        ):
            if swatch is None:
                continue
            try:
                swatch.configure(bg="#%02x%02x%02x" % parse_color(var.get(), default))
            except tk.TclError:
                pass

    def refresh_list(self):
        self.listbox.delete(*self.listbox.get_children())
        unique_paths = []
        for path in self.selected_paths:
            if path not in unique_paths:
                unique_paths.append(path)
        self.selected_paths = unique_paths
        for index, path in enumerate(unique_paths):
            self.listbox.insert("", tk.END, iid=str(index), text=f"  {path}")

    def on_list_select(self, event):
        selection = self.listbox.selection()
        if not selection:
            return
        path = self.selected_paths[int(selection[0])]
        path_obj = Path(path)
        if path_obj.is_file():
            self.show_preview(path_obj)
        else:
            self.draw_preview_placeholder()
            self.selected_file_info.set(t("preview_folder", path=path))

    def draw_preview_placeholder(self):
        self.canvas.delete("all")
        self.canvas.create_rectangle(
            2, 2, self.preview_w - 2, self.preview_h - 2, outline="#8a8a8a", dash=(4, 4), width=1
        )
        self.canvas.create_text(
            self.preview_w // 2,
            self.preview_h // 2,
            text=t("preview_empty"),
            fill="#8a8a8a",
            font=("Segoe UI", 12),
            justify=tk.CENTER,
        )

    def show_preview(self, path: Path):
        try:
            img = Image.open(path)
            img = ImageOps.exif_transpose(img)
            img.thumbnail((self.preview_w, self.preview_h))
            self.preview_image = ImageTk.PhotoImage(img)
            self.canvas.delete("all")
            self.canvas.create_image(self.preview_w // 2, self.preview_h // 2, image=self.preview_image)
            width, height = img.size
            ratio = width / height if height else 0
            self.selected_file_info.set(t("preview_info", name=path.name, width=width, height=height, ratio=ratio))
        except Exception as exc:
            self.selected_file_info.set(t("preview_error", error=exc))

    # ------------------------------------------------------------------ configuration
    def collect_config(self) -> dict:
        """Recopie les réglages de l'écran dans la config (valeurs invalides → défaut)."""
        cfg = self.config
        cfg["last_source_dir"] = self.source_dir.get()
        cfg["last_dest_dir"] = self.dest_dir.get()
        cfg["frame_ratio"] = _var_value(self.frame_ratio, DEFAULT_FRAME_RATIO)
        cfg["landscape_fill_mode"] = self.landscape_fill_mode.get()
        cfg["signature_path"] = self.signature_path.get()
        cfg["number_files"] = bool(self.number_files.get())
        cfg["border_color"] = self.border_color.get()
        cfg["background_color"] = self.background_color.get()
        cfg["disabled_kinds"] = [kind for kind, var in self.kind_vars.items() if not var.get()]
        cfg["blur_strength"] = _var_value(self.blur_strength, DEFAULT_BLUR_STRENGTH)
        cfg["jpeg_quality"] = _var_value(self.jpeg_quality, DEFAULT_JPEG_QUALITY)
        cfg["signature_position"] = self.signature_position.get()
        cfg["signature_scale"] = _var_value(self.signature_scale, DEFAULT_SIGNATURE_SCALE)
        cfg["language"] = i18n.get_language()
        cfg.setdefault("theme", "auto")
        return cfg

    def on_close(self):
        if self.processing and not messagebox.askyesno(t("dlg_quit_title"), t("dlg_quit_processing")):
            return
        self.cancel_event.set()
        try:
            save_config(CONFIG_PATH, self.collect_config())
        finally:
            self.root.destroy()

    def on_tk_exception(self, exc_type, exc, tb):
        logger.error("Erreur d'interface", exc_info=(exc_type, exc, tb))
        messagebox.showerror(t("dlg_error"), t("dlg_unexpected", error=exc, log=str(LOG_PATH)))

    # ------------------------------------------------------------------ ordre / aperçu
    def selected_files(self) -> List[Path]:
        return gather_input_files(self.selected_paths)

    def open_order_window(self):
        if self.order_window is not None and self.order_window.winfo_exists():
            self.order_window.lift()
            return
        if not self.selected_paths:
            messagebox.showwarning(t("dlg_no_file_title"), t("dlg_no_file"))
            return
        files = self.selected_files()
        if not files:
            messagebox.showwarning(t("dlg_no_file_title"), t("status_no_image"))
            return
        self.order_window = OrderWindow(
            self.root,
            files,
            dict(self.collect_config()),
            self.order,
            self.preview_cache,
            dark=self.dark,
            excluded=self.excluded,
            on_crop=self.set_crop_offset,
            on_change=self.set_order,
            get_config=lambda: dict(self.collect_config()),
        )

    def set_crop_offset(self, path: Path, offset: float):
        """Mémorise le recadrage 3/4 choisi pour une photo (conservé d'une session à l'autre)."""
        self.config.setdefault("crop_offsets", {})[str(path)] = round(float(offset), 4)
        save_config(CONFIG_PATH, self.config)

    def set_order(self, order: List[str], excluded: Set[str]):
        self.order = list(order)
        self.excluded = set(excluded)

    # ------------------------------------------------------------------ traitement
    def set_status(self, text: str):
        self.status_text.set(text)

    def apply_processing_state(self):
        if self.processing:
            self.process_button.pack_forget()
            self.cancel_button.pack(side=tk.LEFT)
            self.order_button.state(["disabled"])
        else:
            self.cancel_button.pack_forget()
            self.process_button.pack(side=tk.LEFT)
            self.order_button.state(["!disabled"])

    def start_processing(self):
        if not self.selected_paths:
            messagebox.showwarning(t("dlg_no_file_title"), t("dlg_no_file"))
            return
        if not self.dest_dir.get():
            messagebox.showwarning(t("dlg_no_dest_title"), t("dlg_no_dest"))
            return

        config = dict(self.collect_config())
        save_config(CONFIG_PATH, self.config)
        files = self.selected_files()
        if not files:
            self.set_status(t("status_no_image"))
            return

        self.processing = True
        self.cancel_event = threading.Event()
        self.progress_value.set(0)
        self.apply_processing_state()
        self.set_status(t("status_processing"))
        logger.info("Traitement de %d fichier(s) vers %s", len(files), config["last_dest_dir"])

        thread = threading.Thread(target=self.run_batch, args=(files, config, list(self.order), set(self.excluded)), daemon=True)
        thread.start()

    def cancel_processing(self):
        self.cancel_event.set()
        self.set_status(t("status_cancelling"))

    def run_batch(self, files: List[Path], config: dict, order: List[str], excluded: Set[str]):
        """Exécuté dans un thread : ne touche jamais à Tk, tout passe par la file `events`."""
        try:
            results = process_batch(
                files,
                Path(config["last_dest_dir"]),
                config,
                order=order,
                number_files=bool(config.get("number_files")),
                progress=lambda done, total, path: self.events.put(("progress", done, total, path.name)),
                cancel=self.cancel_event,
                workers=WORKERS,
                excluded=excluded,
            )
            self.events.put(("finished", results))
        except Exception as exc:
            logger.exception("Échec du traitement")
            self.events.put(("crashed", str(exc) or exc.__class__.__name__))

    def poll_events(self):
        try:
            while True:
                event = self.events.get_nowait()
                kind = event[0]
                if kind == "progress":
                    _, done, total, name = event
                    self.progress_value.set(100 * done / max(total, 1))
                    self.set_status(t("status_progress", done=done, total=total, name=name))
                elif kind == "finished":
                    self.on_batch_finished(event[1])
                elif kind == "crashed":
                    self.processing = False
                    self.apply_processing_state()
                    self.set_status(t("status_failed"))
                    messagebox.showerror(t("dlg_error"), t("dlg_unexpected", error=event[1], log=str(LOG_PATH)))
        except queue.Empty:
            pass
        self.root.after(100, self.poll_events)

    def on_batch_finished(self, results: List[FileResult]):
        self.processing = False
        self.apply_processing_state()
        results = [r for r in results if r.status != "excluded"]
        ok = [r for r in results if r.status == "ok"]
        skipped = [r for r in results if r.status == "skipped"]
        errors = [r for r in results if r.status == "error"]
        cancelled = [r for r in results if r.status == "cancelled"]
        outputs = sum(len(r.outputs) for r in ok)
        total = len(results)

        if cancelled:
            self.set_status(t("status_cancelled", done=len(ok), total=total))
        else:
            self.set_status(t("status_done", done=len(ok), total=total))
        self.progress_value.set(100 if not cancelled else self.progress_value.get())

        lines = [t("summary_ok", ok=len(ok), total=total, outputs=outputs)]
        if skipped:
            lines.append(t("summary_skipped", count=len(skipped)))
            lines.extend(f"  • {r.path.name}" for r in skipped[:MAX_ERRORS_SHOWN])
        if errors:
            lines.append(t("summary_errors", count=len(errors)))
            lines.extend(f"  • {r.path.name} : {r.message}" for r in errors[:MAX_ERRORS_SHOWN])
        if len(errors) > MAX_ERRORS_SHOWN:
            lines.append(t("summary_more", count=len(errors) - MAX_ERRORS_SHOWN))
        if cancelled:
            lines.append(t("summary_cancelled", count=len(cancelled)))
        if errors:
            lines.append(t("summary_log", log=str(LOG_PATH)))

        text = "\n".join(lines)
        if errors or skipped:
            messagebox.showwarning(t("dlg_done_title"), text)
        else:
            messagebox.showinfo(t("dlg_done_title"), text)


def create_root():
    """Fenêtre racine avec glisser-déposer si `tkinterdnd2` est disponible, sinon Tk standard."""
    enable_dpi_awareness()
    if TkinterDnD is not None:
        try:
            return TkinterDnD.Tk()
        except Exception:
            logger.exception("tkinterdnd2 indisponible, retour à Tk standard")
    return tk.Tk()


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    setup_logging()
    root = create_root()
    app = PhotoSplitterGUI(root)
    if "--smoke-test" in argv:
        # Vérifie qu'on peut construire toute l'interface (utile pour l'exe sans console), puis quitte.
        out_index = argv.index("--smoke-test") + 1
        out_file = Path(argv[out_index]) if out_index < len(argv) else None

        def finish():
            root.update_idletasks()
            summary = (
                f"ok v{__version__} dnd={'yes' if hasattr(root, 'drop_target_register') else 'no'}"
                f" theme={ttk.Style().theme_use()}"
            )
            if out_file:
                out_file.write_text(summary, encoding="utf-8")
            root.destroy()

        root.after(300, finish)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
