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
from typing import Dict, List, Optional, Tuple

from PIL import Image, ImageOps, ImageTk

import i18n
from i18n import t
from order_window import OrderWindow
from utils import (
    CONFIG_PATH,
    DEFAULT_BLUR_STRENGTH,
    DEFAULT_BORDER_COLOR_HEX,
    DEFAULT_FRAME_RATIO,
    DEFAULT_JPEG_QUALITY,
    DEFAULT_LANDSCAPE_FILL_MODE,
    DEFAULT_NUMBER_FILES,
    DEFAULT_SIGNATURE_POSITION,
    DEFAULT_SIGNATURE_SCALE,
    LOG_PATH,
    SIGNATURE_POSITIONS,
    FileResult,
    gather_input_files,
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

logger = logging.getLogger("imagesplitter")
WORKERS = max(1, min(3, os.cpu_count() or 1))
MAX_ERRORS_SHOWN = 10


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
        self.root.geometry("1100x720")
        self.root.minsize(1000, 640)

        self.selected_paths: List[str] = []
        self.preview_image = None
        self.order: List[str] = []
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
        self.status_bar = ttk.Label(status_frame, textvariable=self.status_text, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(fill=tk.X)

        container = ttk.Frame(self.root, padding=12)
        container.pack(fill=tk.BOTH, expand=True)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(1, weight=1)

        header = ttk.Frame(container)
        header.grid(row=0, column=0, columnspan=2, sticky=tk.EW, pady=(0, 8))
        ttk.Label(header, text=t("app_heading"), font=("Segoe UI", 18, "bold")).pack(side=tk.LEFT)
        ttk.Button(header, text=t("about"), command=self.show_about).pack(side=tk.RIGHT)
        language_box = ttk.Combobox(
            header,
            state="readonly",
            width=10,
            values=[i18n.LANGUAGES[code] for code in i18n.LANGUAGES],
        )
        language_box.set(i18n.LANGUAGES[i18n.get_language()])
        language_box.bind("<<ComboboxSelected>>", lambda e: self.change_language(language_box.current()))
        language_box.pack(side=tk.RIGHT, padx=(0, 8))
        ttk.Label(header, text=t("language")).pack(side=tk.RIGHT, padx=(0, 4))

        self.notebook = notebook = ttk.Notebook(container)
        notebook.grid(row=1, column=0, sticky=tk.NSEW)
        tab_files = ttk.Frame(notebook, padding=10)
        tab_settings = ttk.Frame(notebook, padding=10)
        notebook.add(tab_files, text=t("tab_files"))
        notebook.add(tab_settings, text=t("tab_settings"))
        self.build_files_tab(tab_files)
        self.build_settings_tab(tab_settings)

        preview_frame = ttk.LabelFrame(container, text=t("preview_group"), padding=10)
        preview_frame.grid(row=1, column=1, sticky=tk.NSEW, padx=(12, 0))
        self.canvas = tk.Canvas(preview_frame, width=400, height=360, bg="#f0f0f0", highlightthickness=1)
        self.canvas.pack(fill=tk.BOTH, expand=False)
        ttk.Label(preview_frame, textvariable=self.selected_file_info, wraplength=380, justify=tk.LEFT).pack(
            fill=tk.X, pady=(8, 0)
        )

        control_frame = ttk.Frame(container)
        control_frame.grid(row=2, column=0, columnspan=2, sticky=tk.EW, pady=(12, 0))
        self.progress = ttk.Progressbar(control_frame, variable=self.progress_value, maximum=100)
        self.progress.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 12))
        self.order_button = ttk.Button(control_frame, text=t("btn_order"), command=self.open_order_window)
        self.order_button.pack(side=tk.LEFT, padx=(0, 8))
        self.process_button = ttk.Button(control_frame, text=t("btn_process"), command=self.start_processing)
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
        self.listbox = tk.Listbox(list_frame, selectmode=tk.SINGLE, height=8)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.listbox.bind("<<ListboxSelect>>", self.on_list_select)
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.listbox.yview)
        scrollbar.pack(side=tk.LEFT, fill=tk.Y)
        self.listbox.config(yscrollcommand=scrollbar.set)
        self.drop_hint = ttk.Label(
            tab, text=t("drop_hint") if DND_FILES else "", foreground="#666666"
        )
        self.drop_hint.grid(row=2, column=0, sticky=tk.W, pady=(4, 0))

        dest = ttk.LabelFrame(tab, text=t("dest_group"), padding=8)
        dest.grid(row=3, column=0, sticky=tk.EW, pady=(10, 0))
        dest.columnconfigure(0, weight=1)
        ttk.Entry(dest, textvariable=self.dest_dir, state="readonly").grid(row=0, column=0, sticky=tk.EW, padx=(0, 8))
        ttk.Button(dest, text=t("choose_folder"), command=self.choose_dest).grid(row=0, column=1, padx=(0, 4))
        ttk.Button(dest, text=t("open"), command=self.open_dest_folder).grid(row=0, column=2)
        ttk.Checkbutton(dest, text=t("number_files"), variable=self.number_files).grid(
            row=1, column=0, columnspan=3, sticky=tk.W, pady=(8, 0)
        )

    def build_settings_tab(self, tab):
        tab.columnconfigure(0, weight=1)

        frame_group = ttk.LabelFrame(tab, text=t("frame_group"), padding=8)
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

        fill_group = ttk.LabelFrame(tab, text=t("fill_group"), padding=8)
        fill_group.grid(row=1, column=0, sticky=tk.EW, pady=(0, 8))
        ttk.Radiobutton(fill_group, text=t("fill_black"), value="black", variable=self.landscape_fill_mode).grid(
            row=0, column=0, sticky=tk.W, padx=(0, 16)
        )
        ttk.Radiobutton(fill_group, text=t("fill_blur"), value="blur", variable=self.landscape_fill_mode).grid(
            row=0, column=1, sticky=tk.W
        )
        ttk.Label(fill_group, text=t("blur_strength")).grid(row=1, column=0, sticky=tk.W, pady=(8, 0))
        blur_row = ttk.Frame(fill_group)
        blur_row.grid(row=1, column=1, sticky=tk.W, pady=(8, 0))
        ttk.Spinbox(blur_row, from_=0.2, to=5.0, increment=0.1, textvariable=self.blur_strength, width=6).pack(
            side=tk.LEFT, padx=(0, 8)
        )
        ttk.Label(blur_row, text=t("blur_strength_hint")).pack(side=tk.LEFT)

        sig_group = ttk.LabelFrame(tab, text=t("signature_group"), padding=8)
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

        output_group = ttk.LabelFrame(tab, text=t("output_group"), padding=8)
        output_group.grid(row=3, column=0, sticky=tk.EW)
        ttk.Label(output_group, text=t("jpeg_quality")).grid(row=0, column=0, sticky=tk.W)
        ttk.Spinbox(output_group, from_=50, to=100, increment=1, textvariable=self.jpeg_quality, width=6).grid(
            row=0, column=1, padx=8
        )
        ttk.Label(output_group, text=t("jpeg_quality_hint")).grid(row=0, column=2, sticky=tk.W)

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
        self.listbox.delete(0, tk.END)
        self.preview_image = None
        self.canvas.delete("all")
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

    def update_color_swatch(self):
        rgb = parse_color(self.border_color.get())
        try:
            self.color_swatch.configure(bg="#%02x%02x%02x" % rgb)
        except tk.TclError:
            pass

    def refresh_list(self):
        self.listbox.delete(0, tk.END)
        unique_paths = []
        for path in self.selected_paths:
            if path not in unique_paths:
                unique_paths.append(path)
        self.selected_paths = unique_paths
        for path in unique_paths:
            self.listbox.insert(tk.END, path)

    def on_list_select(self, event):
        if not self.listbox.curselection():
            return
        index = self.listbox.curselection()[0]
        path = self.selected_paths[index]
        path_obj = Path(path)
        if path_obj.is_file():
            self.show_preview(path_obj)
        else:
            self.canvas.delete("all")
            self.selected_file_info.set(t("preview_folder", path=path))

    def show_preview(self, path: Path):
        try:
            img = Image.open(path)
            img = ImageOps.exif_transpose(img)
            img.thumbnail((400, 360))
            self.preview_image = ImageTk.PhotoImage(img)
            self.canvas.delete("all")
            self.canvas.create_image(200, 180, image=self.preview_image)
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
        cfg["blur_strength"] = _var_value(self.blur_strength, DEFAULT_BLUR_STRENGTH)
        cfg["jpeg_quality"] = _var_value(self.jpeg_quality, DEFAULT_JPEG_QUALITY)
        cfg["signature_position"] = self.signature_position.get()
        cfg["signature_scale"] = _var_value(self.signature_scale, DEFAULT_SIGNATURE_SCALE)
        cfg["language"] = i18n.get_language()
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
            on_change=self.set_order,
            get_config=lambda: dict(self.collect_config()),
        )

    def set_order(self, order: List[str]):
        self.order = list(order)

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

        thread = threading.Thread(target=self.run_batch, args=(files, config, list(self.order)), daemon=True)
        thread.start()

    def cancel_processing(self):
        self.cancel_event.set()
        self.set_status(t("status_cancelling"))

    def run_batch(self, files: List[Path], config: dict, order: List[str]):
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
            summary = f"ok v{__version__} dnd={'yes' if hasattr(root, 'drop_target_register') else 'no'}"
            if out_file:
                out_file.write_text(summary, encoding="utf-8")
            root.destroy()

        root.after(300, finish)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
