#!/usr/bin/env python3
"""Affiche la section de CHANGELOG.md d'une version (utilisé par le workflow de release).

    python tools/release_notes.py v0.11.1     # texte de la section, ou rien (code 1) si elle n'existe pas
"""
import sys
from pathlib import Path

CHANGELOG = Path(__file__).resolve().parent.parent / "CHANGELOG.md"


def section_for(version: str, text: str) -> str:
    """Corps de la section `## vX.Y.Z` (sans son titre), ou '' si elle n'existe pas."""
    heading = f"## v{version.lstrip('v')}"
    lines, found = [], False
    for line in text.splitlines():
        if line.startswith("## "):
            if found:
                break
            found = line.strip() == heading
            continue
        if found:
            lines.append(line)
    return "\n".join(lines).strip()


if __name__ == "__main__":
    body = section_for(sys.argv[1], CHANGELOG.read_text(encoding="utf-8")) if len(sys.argv) == 2 else ""
    if body:
        sys.stdout.buffer.write((body + "\n").encode("utf-8"))  # UTF-8 quelle que soit la console (cp1252 sur Windows)
    sys.exit(0 if body else 1)
