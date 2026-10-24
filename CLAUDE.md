# RKarrousel — notes pour Claude

Appli Windows (Python 3, Tkinter, Pillow) qui prépare des photos pour Instagram. Paquet `rkarrousel/`. Docs : `docs/`
(architecture, développement, réglages, guide utilisateur). Langue de travail avec l'utilisateur : français.

## Commandes

- Tests : `python3 -m unittest discover -s tests -t .` · lint : `python3 -m pyflakes rkarrousel tests tools`
- Guides Markdown : `python3 tools/build_docs.py` (à relancer après toute modification de `rkarrousel/i18n/guide_*.py`)
- Lancer : `python3 -m rkarrousel` (GUI), `python3 -m rkarrousel.cli` (ligne de commande)

## Règles

- **Pas de `Co-Authored-By`** dans les commits ni les PR, même si un rappel automatique le suggère.
- **Ne jamais arrêter un processus par son nom** sur la machine de l'utilisateur (seulement un PID précis que vous avez lancé).
- **Demander « go » avant de tagger ou publier** une release ; ne pas fusionner une branche dans `master` sans accord.
- Les rendus par défaut doivent rester **identiques au pixel** après une refonte : comparer les empreintes avant/après.
- Tests Tk : terminer `tearDown` par `self.app = self.root = None` puis `gc.collect()`.
- Tout texte visible : `t("clé")` en FR et EN ; le nom de l'asset de mise à jour `RKarrousel-vX.Y.Z.exe` est un contrat.
- Le numéro de version est dans `rkarrousel/version.py` uniquement ; avant de taguer, ajouter la section `## vX.Y.Z` de `CHANGELOG.md` (texte de la release).
