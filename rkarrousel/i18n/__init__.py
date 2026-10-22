"""Textes de l'interface (français / anglais). `t("clé", nom=valeur)` renvoie le texte dans la langue active."""
from typing import Optional

from rkarrousel.i18n.en import STRINGS as EN
from rkarrousel.i18n.fr import STRINGS as FR

LANGUAGES = {"fr": "Français", "en": "English"}
DEFAULT_LANGUAGE = "fr"

_current = DEFAULT_LANGUAGE

STRINGS = {"fr": FR, "en": EN}


def get_language() -> str:
    return _current


def set_language(code: Optional[str]) -> str:
    global _current
    _current = code if code in STRINGS else DEFAULT_LANGUAGE
    return _current


def t(key: str, **values) -> str:
    text = STRINGS.get(_current, {}).get(key)
    if text is None:
        text = STRINGS[DEFAULT_LANGUAGE].get(key, key)
    try:
        return text.format(**values) if values else text
    except (KeyError, IndexError, ValueError):
        return text


def kind_label(kind: str) -> str:
    """Libellé d'un type d'image ; « part3 », « part4 »… (tranches d'un grand panorama) sont numérotées."""
    if f"kind_{kind}" not in STRINGS[DEFAULT_LANGUAGE] and kind.startswith("part") and kind[4:].isdigit():
        return t("kind_part_n", n=int(kind[4:]))
    return t(f"kind_{kind}")


def kind_setting_label(kind: str) -> str:
    """Libellé d'une case à cocher des Réglages : « part1 » règle la première tranche d'un panorama,
    « part2 » toutes les suivantes."""
    if kind in ("part1", "part2"):
        return t(f"set_kind_{kind}")
    label = kind_label(kind)
    return label[:1].upper() + label[1:]
