"""Accès au guide d'utilisation (contenu dans `guide_fr.py` / `guide_en.py`) et sa version Markdown."""
from typing import List, Tuple

from rkarrousel.i18n import DEFAULT_LANGUAGE, get_language
from rkarrousel.i18n import guide_en, guide_fr

Topic = Tuple[str, str, list]  # (identifiant, titre, blocs)

_MODULES = {"fr": guide_fr, "en": guide_en}

MARKDOWN_TITLES = {"fr": "Guide d'utilisation de RKarrousel", "en": "RKarrousel user guide"}
MARKDOWN_NOTE = {"fr": "Remarque", "en": "Note"}
MARKDOWN_FILES = {"fr": "docs/guide-utilisateur.md", "en": "docs/user-guide.md"}


def get_guide(lang: str = None) -> Tuple[str, List[Topic]]:
    """(introduction, rubriques) dans la langue demandée, ou la langue active."""
    module = _MODULES.get(lang or get_language(), _MODULES[DEFAULT_LANGUAGE])
    return module.INTRO, module.GUIDE


def to_markdown(lang: str) -> str:
    """Le guide en Markdown, tel qu'il est publié dans `docs/`."""
    intro, topics = get_guide(lang)
    lines = [
        f"<!-- Généré par tools/build_docs.py à partir de rkarrousel/i18n/guide_{lang}.py : ne pas modifier à la main. -->",
        f"# {MARKDOWN_TITLES[lang]}", "", intro, "", "## " + ("Sommaire" if lang == "fr" else "Contents"), "",
    ]
    lines += [f"{n}. [{title}](#{_anchor(title)})" for n, (_, title, _) in enumerate(topics, 1)]
    for _, title, blocks in topics:
        lines += ["", f"## {title}", ""]
        for kind, content in blocks:
            if kind == "p":
                lines += [content, ""]
            elif kind == "h":
                lines += [f"### {content}", ""]
            elif kind == "note":
                lines += [f"> **{MARKDOWN_NOTE[lang]}** — {content}", ""]
            elif kind == "bullets":
                lines += [f"- {item}" for item in content] + [""]
            elif kind == "steps":
                lines += [f"{n}. {item}" for n, item in enumerate(content, 1)] + [""]
    return "\n".join(lines).rstrip() + "\n"


def _anchor(title: str) -> str:
    """Ancre GitHub d'un titre : minuscules, ponctuation retirée, espaces en tirets."""
    kept = [c for c in title.lower() if c.isalnum() or c in " -_"]
    return "".join(kept).replace(" ", "-")
