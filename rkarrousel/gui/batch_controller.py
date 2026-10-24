"""Traitement des photos : lancement, annulation, progression et récapitulatif (puis envoi Drive si demandé)."""
import logging
import os
import threading
from pathlib import Path
from tkinter import messagebox
from typing import List, Set

from rkarrousel.gui.context import AppContext
from rkarrousel.gui.drive_controller import DriveController
from rkarrousel.gui.summary import MAX_ERRORS_SHOWN, show_summary
from rkarrousel.i18n import t
from rkarrousel.paths import LOG_PATH
from rkarrousel.pipeline import FileResult, process_batch

logger = logging.getLogger("imagesplitter")
WORKERS = max(1, min(3, os.cpu_count() or 1))  # photos traitées en parallèle


class BatchController:
    def __init__(self, ctx: AppContext, drive: DriveController):
        self.ctx, self.drive = ctx, drive
        self.batch_config: dict = {}
        ctx.bus.on("progress", self._on_progress)
        ctx.bus.on("finished", self._on_finished)
        ctx.bus.on("crashed", self._on_crashed)

    def start(self) -> None:
        ctx, model, session = self.ctx, self.ctx.model, self.ctx.session
        if not session.selected_paths:
            messagebox.showwarning(t("dlg_no_file_title"), t("dlg_no_file"))
            return
        if not model.dest_dir.get():
            messagebox.showwarning(t("dlg_no_dest_title"), t("dlg_no_dest"))
            return
        config = dict(ctx.collect_config())
        session.sync_layout(config)
        ctx.save_config()
        self.batch_config = config
        files = session.selected_files()
        if not files:
            ctx.set_status(t("status_no_image"))
            return

        ctx.cancel_event = threading.Event()
        ctx.set_processing(True)
        ctx.set_progress(0)
        ctx.set_status(t("status_processing"))
        logger.info("Traitement de %d fichier(s) vers %s", len(files), config["last_dest_dir"])
        threading.Thread(
            target=self._run, args=(files, config, list(session.order), set(session.excluded), ctx.cancel_event), daemon=True
        ).start()

    def cancel(self) -> None:
        self.ctx.cancel_event.set()
        self.ctx.set_status(t("status_cancelling"))

    def _run(self, files: List[Path], config: dict, order: List[str], excluded: Set[str], cancel: threading.Event) -> None:
        """Exécuté dans un thread : ne touche jamais à Tk, tout passe par le bus d'évènements."""
        bus = self.ctx.bus
        try:
            results = process_batch(
                files,
                Path(config["last_dest_dir"]),
                config,
                order=order,
                number_files=bool(config.get("number_files")),
                progress=lambda done, total, path: bus.post("progress", done, total, path.name),
                cancel=cancel,
                workers=WORKERS,
                excluded=excluded,
            )
            bus.post("finished", results)
        except Exception as exc:
            logger.exception("Échec du traitement")
            bus.post("crashed", str(exc) or exc.__class__.__name__)

    # ------------------------------------------------------------------ évènements
    def _on_progress(self, done: int, total: int, name: str) -> None:
        self.ctx.set_progress(100 * done / max(total, 1))
        self.ctx.set_status(t("status_progress", done=done, total=total, name=name))

    def _on_crashed(self, message: str) -> None:
        self.ctx.set_processing(False)
        self.ctx.set_status(t("status_failed"))
        messagebox.showerror(t("dlg_error"), t("dlg_unexpected", error=message, log=str(LOG_PATH)))

    def _on_finished(self, results: List[FileResult]) -> None:
        ctx = self.ctx
        ctx.set_processing(False)
        results = [r for r in results if r.status != "excluded"]
        ok = [r for r in results if r.status == "ok"]
        skipped = [r for r in results if r.status == "skipped"]
        errors = [r for r in results if r.status == "error"]
        cancelled = [r for r in results if r.status == "cancelled"]
        outputs = sum(len(r.outputs) for r in ok)
        total = len(results)

        ctx.set_status(t("status_cancelled" if cancelled else "status_done", done=len(ok), total=total))
        if not cancelled:
            ctx.set_progress(100)

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

        warn = bool(errors or skipped)
        if self.batch_config.get("gdrive_enabled") and not cancelled:
            generated = sorted((p for r in ok for p in r.outputs), key=lambda p: p.name)
            if generated and self.drive.ready():
                self.drive.start_upload(generated, self.batch_config, lines, warn)
                return  # la boîte de fin s'affiche quand l'envoi est terminé
            if generated:
                lines.append(t("gd_skip"))
                warn = True
        show_summary(lines, warn)
