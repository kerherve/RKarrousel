# Développement

## Mise en place

```bash
python -m pip install -r requirements.txt     # Pillow, tkinterdnd2, sv-ttk
python -m rkarrousel                          # interface graphique
python -m rkarrousel.cli photos/ -d sortie --number --workers 3   # ligne de commande (--help pour les options)
```

`tkinterdnd2` et `sv-ttk` sont facultatifs au développement : sans eux l'appli fonctionne sans glisser-déposer et avec
le thème Tk par défaut (l'aspect diffère de l'exécutable publié).

Sous WSL, l'interface demande un serveur d'affichage (WSLg). Les chemins `/mnt/c/…` et `C:\…` sont convertis par
`config.normalize_path`.

## Tests

```bash
python -m unittest discover -s tests -t .
python -m pyflakes rkarrousel tests tools
python tools/build_docs.py --check            # les guides Markdown sont-ils à jour ?
```

| Fichier | Couvre |
|---|---|
| `test_formats`, `test_rendering`, `test_pipeline` | Maths des formats, rendus, découpe, numérotation |
| `test_config`, `test_presets`, `test_photo_colors` | Réglages, préréglages, couleurs tirées de la photo |
| `test_i18n`, `test_guide` | Clés et paramètres identiques en FR/EN, textes utilisés existent, guide complet et à jour |
| `test_gdrive`, `test_updater` | Google Drive et mise à jour contre de **faux serveurs** locaux (jamais le vrai réseau) |
| `test_order_model` | Ordre et exclusions |
| `test_gui_smoke`, `test_gui_flow` | Construction de toute l'interface et parcours complets (ignorés sans affichage) |
| `test_installer` | Cohérence de l'installateur Inno Setup |

**Piège Tkinter** : les variables Tk d'une fenêtre détruite peuvent être libérées dans un thread de travail et bloquer. Tout
test qui crée une racine Tk doit finir par `self.app = self.root = None` puis `gc.collect()` dans `tearDown`.

### Contrôle de non-régression des rendus

Une refonte ne doit jamais changer un pixel. Avant et après, rendre un jeu de photos (`input/` plus quelques formats
variés) avec les réglages par défaut et comparer les empreintes des fichiers produits : elles doivent être identiques.
Les tests couvrent la logique, mais seule cette comparaison attrape un décalage d'un pixel.

## Compiler

Sous Windows : `build_windows.bat` → `dist\RKarrousel.exe` (PyInstaller `--onefile --windowed`). Depuis WSL, compiler
avec le Python Windows dans un dossier Windows (les chemins UNC `\\wsl$` font échouer `cmd.exe`). Test de fumée de
l'exécutable : `RKarrousel.exe --smoke-test`.

L'installateur : `ISCC.exe /DAppVersion=X.Y.Z installer\RKarrousel.iss` → `dist\RKarrousel-Setup-vX.Y.Z.exe`
(Inno Setup 6 ; pas de droits administrateur ; réglages par défaut dans `installer/default_config.json`).

## Publier une version

1. Mettre `rkarrousel/version.py` à jour (semver : `0.MINOR.0` pour une fonctionnalité, `0.x.PATCH` pour un correctif) et ajouter en tête de `CHANGELOG.md` une section `## vX.Y.Z` écrite pour l'utilisateur **dans les deux langues** (`### English` puis `### Français`) : elle devient le texte de la release et s'affiche dans la fenêtre de mise à jour (un test vérifie qu'elle existe).
2. Fusionner dans `master`, puis pousser un tag `vX.Y.Z` égal à la version.
3. Le workflow `.github/workflows/release.yml` exécute les tests, compile l'exécutable, vérifie son démarrage, fabrique
   l'installateur, teste une installation et une désinstallation silencieuses, puis ajoute à la release
   `RKarrousel-vX.Y.Z.exe` (portable, **nom imposé par la mise à jour automatique**) et `RKarrousel-Setup-vX.Y.Z.exe`.
4. Essai sans publier : `gh workflow run release.yml --ref <branche>`.

Les détails (et les pièges rencontrés) sont dans `.claude/skills/rkarrousel-release/SKILL.md`.

## Conventions

- Commentaires et docstrings en français, noms de code en anglais ; un module = une responsabilité, et pas de fichier de plus de quelques centaines de lignes.
- Tout texte visible passe par `t("clé")` et existe en français **et** en anglais.
- Une nouvelle fonctionnalité visible met à jour le guide (`i18n/guide_*.py`, puis `python tools/build_docs.py`) et `docs/config.md` si elle ajoute un réglage.
- Pas de ligne `Co-Authored-By` dans les commits.
