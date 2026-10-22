#!/usr/bin/env python3
"""Génère les guides Markdown de `docs/` à partir du contenu du guide intégré à l'appli.

    python tools/build_docs.py          # écrit docs/guide-utilisateur.md et docs/user-guide.md
    python tools/build_docs.py --check  # échoue si les fichiers ne sont pas à jour (utilisé par les tests)
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from rkarrousel.i18n.guide import MARKDOWN_FILES, to_markdown  # noqa: E402


def stale_files() -> list:
    return [name for lang, name in MARKDOWN_FILES.items()
            if not (ROOT / name).exists() or (ROOT / name).read_text(encoding="utf-8") != to_markdown(lang)]


def main(argv) -> int:
    if "--check" in argv:
        stale = stale_files()
        for name in stale:
            print(f"périmé : {name} (lancer python tools/build_docs.py)")
        return 1 if stale else 0
    for lang, name in MARKDOWN_FILES.items():
        (ROOT / name).write_text(to_markdown(lang), encoding="utf-8", newline="\n")
        print(f"écrit : {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
