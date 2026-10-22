"""Lancement de l'application : interface graphique, mode « test de démarrage » et mise à jour sans interface."""
import sys
from pathlib import Path
from tkinter import ttk
from typing import List, Optional

from rkarrousel.gui.app import PhotoSplitterGUI
from rkarrousel.gui.system import FROZEN, UPDATE_API, UPDATE_REPO, create_root, setup_logging
from rkarrousel.services import updater
from rkarrousel.version import __version__


def run_self_update(log_path: Optional[Path]) -> int:
    """Mise à jour sans interface (utilisée par les tests et les scripts) : `--self-update [fichier-journal]`."""
    lines: List[str] = []

    def log(message: str) -> None:
        lines.append(message)
        if log_path:
            log_path.write_text("\n".join(lines), encoding="utf-8")

    if not FROZEN:
        log("error: --self-update only works with the packaged executable")
        return 2
    try:
        info = updater.fetch_latest_release(UPDATE_REPO, UPDATE_API)
        log(f"latest={info.version} current={__version__}")
        if not updater.is_newer(info.version, __version__):
            log("up-to-date")
            return 0
        current = Path(sys.executable)
        updater.perform_update(info, current, status=log)
        log("relaunching")
        updater.relaunch(current)
        return 0
    except updater.UpdateError as exc:
        log(f"error: {exc}")
        return 2


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    setup_logging()
    if "--self-update" in argv:
        index = argv.index("--self-update") + 1
        return run_self_update(Path(argv[index]) if index < len(argv) else None)
    if FROZEN:
        updater.cleanup_leftovers(Path(sys.executable))
    root = create_root()
    PhotoSplitterGUI(root)
    if "--smoke-test" in argv:
        # Vérifie qu'on peut construire toute l'interface (utile pour l'exe sans console), puis quitte.
        out_index = argv.index("--smoke-test") + 1
        out_file = Path(argv[out_index]) if out_index < len(argv) else None

        def finish() -> None:
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
