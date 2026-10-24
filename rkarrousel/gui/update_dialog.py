#!/usr/bin/env python3
"""Boîte de dialogue « mise à jour disponible » : notes de version, choix, puis progression de l'installation."""
import tkinter as tk
from tkinter import ttk
from typing import Callable

from rkarrousel.i18n import get_language, t
from rkarrousel.services.updater import plain_notes


class UpdateDialog(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Misc,
        info,
        current_version: str,
        can_install: bool,
        on_update: Callable[[], None],
        on_skip: Callable[[], None],
        on_close: Callable[[], None],
    ):
        super().__init__(parent)
        self.title(t("upd_available_title"))
        self.on_close_cb = on_close
        scale = max(1.0, self.winfo_fpixels("1i") / 96)
        width, height = int(560 * scale), int(470 * scale)
        x = max(0, (self.winfo_screenwidth() - width) // 2)
        y = max(0, (self.winfo_screenheight() - height) // 2 - 30)
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.resizable(False, False)

        frame = ttk.Frame(self, padding=(20, 16, 20, 16))
        frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frame, text=t("upd_available", latest=info.version, current=current_version),
                  wraplength=width - int(70 * scale), justify=tk.LEFT).pack(anchor=tk.W)
        ttk.Label(frame, text=t("upd_notes_title"), style="Hint.TLabel").pack(anchor=tk.W, pady=(12, 4))

        box = ttk.Frame(frame)
        box.pack(fill=tk.BOTH, expand=True)
        self.notes = tk.Text(box, wrap=tk.WORD, height=8, relief=tk.FLAT, borderwidth=0, padx=8, pady=6, font=("Segoe UI", 10))
        scroll = ttk.Scrollbar(box, orient=tk.VERTICAL, command=self.notes.yview)
        self.notes.configure(yscrollcommand=scroll.set)
        self.notes.insert("1.0", plain_notes(info.notes, get_language()) or t("upd_no_notes"))
        self.notes.configure(state=tk.DISABLED)
        self.notes.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.LEFT, fill=tk.Y)

        self.status = tk.StringVar(value="")
        ttk.Label(frame, textvariable=self.status).pack(anchor=tk.W, pady=(12, 0))
        self.progress = ttk.Progressbar(frame, maximum=100)
        self.progress.pack(fill=tk.X, pady=(4, 0))

        bar = ttk.Frame(frame)
        bar.pack(fill=tk.X, pady=(14, 0))
        self.update_btn = ttk.Button(
            bar, text=t("upd_now") if can_install else t("upd_open_page"), command=on_update, style="Accent.TButton"
        )
        self.update_btn.pack(side=tk.RIGHT)
        self.later_btn = ttk.Button(bar, text=t("upd_later"), command=self.close)
        self.later_btn.pack(side=tk.RIGHT, padx=(0, 8))
        self.skip_btn = ttk.Button(bar, text=t("upd_skip"), command=on_skip)
        self.skip_btn.pack(side=tk.LEFT)

        self.protocol("WM_DELETE_WINDOW", self.close)
        self.transient(parent)
        self.busy = False

    def set_busy(self, busy: bool) -> None:
        self.busy = busy
        for button in (self.update_btn, self.later_btn, self.skip_btn):
            button.state(["disabled"] if busy else ["!disabled"])

    def set_status(self, text: str) -> None:
        self.status.set(text)

    def set_progress(self, percent: float) -> None:
        self.progress.configure(value=percent)

    def close(self) -> None:
        if self.busy:
            return
        self.on_close_cb()
        self.destroy()
