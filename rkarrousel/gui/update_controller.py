"""Mises à jour automatiques : recherche au démarrage, fenêtre de proposition, installation et relance."""
import logging
import os
import sys
import threading
import webbrowser
from pathlib import Path
from tkinter import messagebox
from typing import Optional

from rkarrousel.gui.context import AppContext
from rkarrousel.gui.system import FROZEN, UPDATE_API, UPDATE_REPO
from rkarrousel.gui.update_dialog import UpdateDialog
from rkarrousel.i18n import t
from rkarrousel.services import updater
from rkarrousel.version import __version__

logger = logging.getLogger("imagesplitter")


class UpdateController:
    def __init__(self, ctx: AppContext):
        self.ctx = ctx
        self.dialog: Optional[UpdateDialog] = None
        self._cancel = threading.Event()
        bus = ctx.bus
        bus.on("upd_check", self._on_check)
        bus.on("upd_progress", self._on_progress)
        bus.on("upd_status", self._on_status)
        bus.on("upd_done", self._on_done)
        bus.on("upd_error", self._on_error)

    # ------------------------------------------------------------------ recherche
    def auto_check(self) -> None:
        """À chaque démarrage (sauf réglage désactivé) : une seule requête légère vers GitHub."""
        if not self.ctx.model.update_check.get() or not (FROZEN or os.environ.get("RKARROUSEL_UPDATE_API")):
            return
        self.check(manual=False)

    def check(self, manual: bool = False) -> None:
        if manual:
            self.ctx.set_status(t("upd_checking"))
        bus = self.ctx.bus

        def work() -> None:
            try:
                bus.post("upd_check", updater.fetch_latest_release(UPDATE_REPO, UPDATE_API), None, manual)
            except updater.UpdateError as exc:
                bus.post("upd_check", None, exc, manual)
            except Exception as exc:
                logger.exception("Recherche de mise à jour")
                bus.post("upd_check", None, updater.UpdateError(str(exc)), manual)

        threading.Thread(target=work, daemon=True).start()

    def _on_check(self, info, error, manual: bool) -> None:
        ctx = self.ctx
        if error is not None:
            logger.info("Recherche de mise à jour : %s", error)
            if manual:
                ctx.set_status(t("status_ready"))
                messagebox.showerror(t("upd_group"), t("upd_error", message=error))
            return
        if updater.is_newer(info.version, __version__):
            if manual or info.version != ctx.config.get("skipped_version"):
                self.show_dialog(info)
            ctx.set_status(t("status_ready") if manual else t("upd_available_status", latest=info.version))
        elif manual:
            ctx.set_status(t("status_ready"))
            messagebox.showinfo(t("upd_group"), t("upd_uptodate", version=__version__))

    # ------------------------------------------------------------------ proposition et installation
    def show_dialog(self, info) -> None:
        if self.dialog is not None and self.dialog.winfo_exists():
            self.dialog.lift()
            return

        def on_update() -> None:
            if FROZEN:
                self.install(info)
            else:  # lancé depuis les sources : pas d'exécutable à remplacer
                webbrowser.open(info.page_url)
                self.dialog.close()

        def on_skip() -> None:
            self.ctx.config["skipped_version"] = info.version
            self.ctx.save_config()
            self.dialog.close()

        self.dialog = UpdateDialog(
            self.ctx.root, info, __version__, FROZEN, on_update, on_skip, lambda: setattr(self, "dialog", None)
        )

    def install(self, info) -> None:
        self.dialog.set_busy(True)
        self._cancel = threading.Event()
        cancel, bus, current = self._cancel, self.ctx.bus, Path(sys.executable)

        def work() -> None:
            try:
                updater.perform_update(
                    info,
                    current,
                    progress=lambda done, total: bus.post("upd_progress", done, total),
                    cancel=cancel,
                    status=lambda step: bus.post("upd_status", step),
                )
                bus.post("upd_done")
            except updater.UpdateError as exc:
                bus.post("upd_error", str(exc), exc.code, info.page_url)
            except Exception as exc:
                logger.exception("Mise à jour")
                bus.post("upd_error", str(exc) or exc.__class__.__name__, "error", info.page_url)

        threading.Thread(target=work, daemon=True).start()

    def _dialog_alive(self) -> bool:
        return self.dialog is not None and self.dialog.winfo_exists()

    def _on_progress(self, done: int, total: int) -> None:
        if self._dialog_alive():
            percent = 100 * done / total if total else 0
            self.dialog.set_progress(percent)
            self.dialog.set_status(t("upd_downloading", percent=percent))

    def _on_status(self, step: str) -> None:
        if self._dialog_alive():
            self.dialog.set_status(t(f"upd_{step}"))
            self.dialog.set_progress(100 if step != "downloading" else 0)

    def _on_error(self, message: str, code: str, page: str) -> None:
        if self._dialog_alive():
            self.dialog.set_busy(False)
            self.dialog.set_status("")
            self.dialog.set_progress(0)
        if code == "permission":
            if messagebox.askyesno(t("upd_group"), t("upd_failed_permission", url=page)):
                webbrowser.open(page)
        elif code != "cancelled":
            messagebox.showerror(t("upd_group"), t("upd_error", message=message))

    def _on_done(self) -> None:
        """La nouvelle version est en place : on enregistre les réglages, on la relance et on quitte."""
        ctx = self.ctx
        try:
            ctx.collect_config()
            ctx.save_config()
            updater.relaunch(Path(sys.executable))
        except Exception as exc:
            logger.exception("Relance après mise à jour")
            messagebox.showwarning(t("upd_group"), t("upd_restart_manually", error=exc))
        ctx.cancel_event.set()
        ctx.root.destroy()
