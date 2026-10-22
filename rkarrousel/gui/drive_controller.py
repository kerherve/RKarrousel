"""Logique Google Drive de l'interface : identifiants, connexion et envoi des images après le traitement."""
import logging
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Callable, List, Optional

from rkarrousel.gui.context import AppContext
from rkarrousel.gui.summary import MAX_ERRORS_SHOWN, show_summary
from rkarrousel.i18n import t
from rkarrousel.paths import GDRIVE_TOKEN_PATH, LOG_PATH
from rkarrousel.services import gdrive

logger = logging.getLogger("imagesplitter")


class DriveController:
    def __init__(self, ctx: AppContext, summary: Callable[[List[str], bool], None] = show_summary):
        self.ctx = ctx
        self.summary = summary
        self.status = tk.StringVar(value="")
        self.connect_button = None  # bouton « Se connecter » (posé par le groupe de réglages) : grisé pendant l'attente
        self._cancel_connect = threading.Event()
        self._pending = ([], False, "")  # (lignes du récapitulatif, avertissement, dossier) en attendant la fin de l'envoi
        bus = ctx.bus
        bus.on("gd_connected", self._on_connected)
        bus.on("gd_error", self._on_error)
        bus.on("upload_progress", self._on_upload_progress)
        bus.on("upload_done", self._on_upload_done)

    # ------------------------------------------------------------------ identifiants et connexion
    def client(self) -> Optional[gdrive.DriveClient]:
        config = self.ctx.config
        client_id, client_secret = config.get("gdrive_client_id"), config.get("gdrive_client_secret")
        if not client_id or not client_secret:
            return None
        return gdrive.DriveClient(client_id, client_secret, GDRIVE_TOKEN_PATH)

    def refresh_status(self) -> None:
        client = self.client()
        if client is None:
            self.status.set(t("gd_status_nocreds"))
        elif client.is_connected():
            self.status.set(t("gd_status_connected"))
        else:
            self.status.set(t("gd_status_disconnected"))

    def choose_credentials(self) -> None:
        path = filedialog.askopenfilename(
            title=t("gd_choose_json"), filetypes=[("JSON", "*.json"), (t("filetype_all"), "*.*")]
        )
        if not path:
            return
        try:
            client_id, client_secret = gdrive.load_client_secrets(path)
        except gdrive.DriveError as exc:
            messagebox.showerror(t("dlg_error"), t("gd_error", message=exc))
            return
        self.ctx.config["gdrive_client_id"], self.ctx.config["gdrive_client_secret"] = client_id, client_secret
        gdrive.clear_token(GDRIVE_TOKEN_PATH)  # d'autres identifiants : il faut se reconnecter
        self.ctx.save_config()
        self.refresh_status()
        messagebox.showinfo(t("gd_group"), t("gd_creds_ok"))

    def connect(self) -> None:
        client = self.client()
        if client is None:
            messagebox.showwarning(t("gd_group"), t("gd_need_creds"))
            return
        self._set_connect_enabled(False)
        self.status.set(t("gd_connecting"))
        self._cancel_connect = threading.Event()
        cancel, bus = self._cancel_connect, self.ctx.bus

        def work() -> None:
            try:
                token = gdrive.authorize(client.client_id, client.client_secret, cancel=cancel)
                gdrive.save_token(GDRIVE_TOKEN_PATH, token)
                bus.post("gd_connected")
            except gdrive.DriveError as exc:
                bus.post("gd_error", str(exc))
            except Exception as exc:
                logger.exception("Connexion Google Drive")
                bus.post("gd_error", str(exc) or exc.__class__.__name__)

        threading.Thread(target=work, daemon=True).start()

    def disconnect(self) -> None:
        self._cancel_connect.set()
        gdrive.clear_token(GDRIVE_TOKEN_PATH)
        self.refresh_status()

    def show_help(self) -> None:
        messagebox.showinfo(t("gd_help_title"), t("gd_help"))

    def _set_connect_enabled(self, enabled: bool) -> None:
        if self.connect_button is not None:
            try:
                self.connect_button.state(["!disabled"] if enabled else ["disabled"])
            except tk.TclError:  # bouton détruit par une reconstruction de l'interface
                pass

    def _on_connected(self) -> None:
        self._set_connect_enabled(True)
        self.refresh_status()
        self.ctx.set_status(t("gd_connected_msg"))

    def _on_error(self, message: str) -> None:
        self._set_connect_enabled(True)
        self.refresh_status()
        messagebox.showerror(t("dlg_error"), t("gd_error", message=message))

    # ------------------------------------------------------------------ envoi des images
    def ready(self) -> bool:
        client = self.client()
        return client is not None and client.is_connected()

    def start_upload(self, outputs: List[Path], config: dict, lines: List[str], warn: bool) -> None:
        """Envoie les images générées dans un thread ; la boîte de fin s'affiche quand l'envoi est terminé."""
        client = self.client()
        folder = (config.get("gdrive_folder") or "RKarrousel").strip() or "RKarrousel"
        self._pending = (lines, warn, folder)
        ctx, bus = self.ctx, self.ctx.bus
        ctx.set_processing(True)
        ctx.set_progress(0)
        ctx.set_status(t("gd_status_uploading", done=0, total=len(outputs), name=""))
        cancel = ctx.cancel_event

        def work() -> None:
            try:
                results = client.upload_files(
                    outputs,
                    folder,
                    progress=lambda done, total, path: bus.post("upload_progress", done, total, path.name),
                    cancel=cancel,
                )
                bus.post("upload_done", results)
            except Exception as exc:
                logger.exception("Envoi Drive")
                bus.post("upload_done", [{"path": p, "status": "error", "message": str(exc)} for p in outputs])

        threading.Thread(target=work, daemon=True).start()

    def _on_upload_progress(self, done: int, total: int, name: str) -> None:
        self.ctx.set_progress(100 * done / max(total, 1))
        self.ctx.set_status(t("gd_status_uploading", done=done, total=total, name=name))

    def _on_upload_done(self, results: List[dict]) -> None:
        lines, warn, folder = self._pending
        self.ctx.set_processing(False)
        sent = [r for r in results if r["status"] == "ok"]
        failed = [r for r in results if r["status"] == "error"]
        self.ctx.set_status(t("gd_status_done", ok=len(sent), total=len(results)))
        self.ctx.set_progress(100)
        lines.append(t("gd_summary_ok", ok=len(sent), total=len(results), folder=folder))
        if failed:
            warn = True
            lines.append(t("gd_summary_errors", count=len(failed)))
            lines.extend(f"  • {r['path'].name} : {r['message']}" for r in failed[:MAX_ERRORS_SHOWN])
            if len(failed) > MAX_ERRORS_SHOWN:
                lines.append(t("summary_more", count=len(failed) - MAX_ERRORS_SHOWN))
            lines.append(t("summary_log", log=str(LOG_PATH)))
        self.summary(lines, warn)
        self.refresh_status()
