# Architecture

RKarrousel est un paquet Python (`rkarrousel/`) : Pillow pour l'image, Tkinter pour l'interface, aucune autre dépendance
obligatoire (`tkinterdnd2` et `sv-ttk` ajoutent le glisser-déposer et le thème moderne quand ils sont installés).

Le principe directeur : **la logique d'image ne connaît ni Tkinter ni le disque de l'utilisateur**. Les couches basses
(`formats`, `imaging`, `outputs`) sont des fonctions pures testables ; l'interface (`gui/`) ne fait que les appeler.

## Carte des modules

| Module | Rôle |
|---|---|
| `__main__.py`, `cli.py` | Points d'entrée : interface graphique (`python -m rkarrousel`) et ligne de commande (`python -m rkarrousel.cli`) |
| `version.py` | Numéro de version : **seule source**, lue par l'appli, le workflow de release et l'installateur |
| `paths.py` | Emplacements des fichiers (config, journal, jeton Drive), à côté de l'exécutable une fois compilé |
| `config.py` | Lecture/écriture du JSON de réglages, valeurs par défaut, accesseurs qui **valident** chaque réglage |
| `formats.py` | Formats de sortie (3:4, 4:5, 1:1, 9:16), largeurs, détection du type de ratio d'une photo, nombre de tranches d'un panorama |
| `kinds.py` | Les « types » d'images produites (`framed`, `with_sig`, `part1`…, `crop34`) et la place des deux « photos entières » d'un paysage dans le carrousel (avant / après le découpage, à la fin) |
| `outputs.py` | Quelles images produire pour une photo (`kinds_for_ratio`), leur rendu (`iter_outputs`), taille finale, noms de fichiers |
| `pipeline.py` | Traitement d'un lot : découverte des fichiers, ordre, numérotation, écriture, parallélisme, annulation |
| `presets.py` | Préréglages nommés (fournis + ceux de l'utilisateur dans la config) |
| `imaging/` | `frames` (ouverture, cadre, enregistrement), `signature`, `canvases` (rendus portrait/recadrage), `panorama` (découpe en tranches), `colors` (couleur dominante) |
| `services/updater.py` | Mise à jour automatique depuis les releases GitHub |
| `services/gdrive/` | Envoi sur Google Drive : `transport` (HTTP), `oauth` (connexion), `client` (dossiers, envoi) |
| `i18n/` | Textes en français et en anglais (`fr.py`, `en.py`) ; le guide d'utilisation (`guide_fr.py`, `guide_en.py`) |
| `gui/` | Interface (voir ci-dessous) |

## Du fichier source aux images

```
photo ──open_image──► détecter le ratio (formats.detect_ratio_type)
                       │
                       ▼
          kinds_for_ratio ── liste des types à produire (hors types désactivés)
                       │
                       ▼
   resolve_photo_colors ── cadre/fond « couleur de la photo » calculés pour CETTE photo
                       │
                       ▼
 iter_outputs ──► canvases / panorama ──► (kind, image) ──► finalize_size ──► save_image
```

- Le type de ratio (`portrait_3_4`, `portrait_2_3`, `landscape_2_3`, `portrait_other`, `square`, `landscape_other`)
  décide des types d'images. Le format de sortie choisi est le « 3:4 » de référence : en 4:5, une photo 4:5 est
  `portrait_3_4`.
- **Le format est exact.** Une image au format de sortie, cadre compris, a exactement le bon rapport (rognée de moins de
  1 %) ; `finalize_size` ramène ensuite à la largeur choisie en gardant des dimensions exactes (1080×1440).
- Les tranches d'un panorama sont contiguës : le cadre n'entoure que le haut, le bas et les deux extrémités.

### Clés d'ordre

Une image de sortie est identifiée par `item_key(source, kind)` = `"<chemin>|<type>"`. L'ordre choisi dans la grille, les
exclusions et le préfixe numérique (`01_`) s'expriment tous avec ces clés (`pipeline.merge_order`, `build_prefixes`) : un
élément nouveau se range à la suite dans l'ordre naturel, un élément disparu est ignoré.

## Interface (`gui/`)

L'appli est un **flux en quatre étapes** : Photos → Ordre → Ajustements → Export.

- `app.py` : `PhotoSplitterGUI` assemble le contexte, les contrôleurs, l'en-tête (Préférences, Guide, À propos) et le flux.
- `flow/` : le flux. `steps` (les étapes et les règles pour avancer, sans Tk : sans photo ni destination on reste sur « Photos », sans image à produire on ne dépasse pas « Ordre »), `stepper` (le bandeau cliquable), `navigation` (la barre « Précédent » / « Suivant » ; à la dernière étape « Suivant » devient « Lancer le traitement »), `flow` (le conteneur : affiche une page, appelle `on_show` / `on_hide`). `pages/` : une page par étape — `photos_page` (+ `preview_panel`), `order_page` (la grille et la colonne « images produites »), `adjust_page` (la visionneuse), `export_page` (récapitulatif, sortie, Drive).
- `context.py` : `AppContext`, état partagé (config, modèle des réglages, thème, barre d'état, bus d'événements).
- `session.py` : l'état de la session (photos choisies, ordre, exclusions, cache d'aperçus). Quand la place des « photos entières » change, l'ordre choisi est remis à zéro (`sync_layout`).
- `settings_model.py` : `SettingsModel`, les variables Tk de tous les réglages ; `collect()` / `apply(valeurs)` font le lien avec le JSON.
- `settings_groups/` : un groupe par bloc de réglages, rangés par thème — `presets_group`, `look` (cadre, fond, signature), `output` (format, taille, types d'images), `appearance` (langue, thème, mises à jour), `drive_group`. Chaque groupe est posé là où il sert : le format à l'étape Photos, les types d'images à l'étape Ordre, les réglages d'apparence à l'étape Ajustements, la sortie et Drive à l'étape Export, langue / thème / mises à jour dans les Préférences (`preferences_dialog.py`).
- `events.py` : **bus d'événements**. Les threads de travail y *postent* des messages ; seul le thread Tk les distribue. Aucun widget n'est touché hors du thread Tk.
- `batch_controller`, `drive_controller`, `update_controller` : un contrôleur par fonction, chacun porte son propre thread et ses messages. `summary.py` : récapitulatif de fin de traitement.
- `order/` : la grille de l'étape Ordre (les vignettes gardent leur taille, une fenêtre plus large ajoute des colonnes ; avertissement au-delà de 20 images, `formats.INSTAGRAM_MAX_IMAGES`), en pièces — `grid_layout` (géométrie), `model` (ordre, exclusions, sélection), `thumbnails` (rendu des vignettes en arrière-plan), `grid_canvas` (dessin et glisser-déposer), `view` (assemble le tout ; sert aussi de « navigateur » à la visionneuse).
- `viewer/` : la visionneuse de l'étape Ajustements, en pièces — `viewport` (zoom et déplacement, sans Tk), `render_jobs` (calculs en arrière-plan, avec numéro de génération pour ignorer les résultats périmés), `loader` (lance les rendus, aperçus de la grille pour les voisines, relève les résultats), `carousel` (voisines, défilement à la souris, animation), `ruler` (mesure en pixels), `toolbar`, `frame_report` (couleur et épaisseur du cadre obtenus), `settings_panel` (préréglages et réglages en direct), `view` (assemble le tout). Les voisines et l'aperçu de la nouvelle image viennent d'abord du cache d'aperçus de la grille (instantané) ; la pleine résolution n'est calculée qu'une fois qu'on s'arrête.
- `photo_frame_group.py` : couleur du cadre propre à une photo, couleur obtenue et retouche fine (utilisé par la visionneuse).
- `crop_editor.py`, `guide_window.py`, `update_dialog.py` : fenêtres secondaires.
- `widgets.py` : composants communs (`ChoiceBox`, `ColorPicker`, `HintLabel`, `make_scrollable`, `bind_trace`).
- Changer la langue ou le thème **reconstruit** toute l'interface (`PhotoSplitterGUI._rebuild`), en restant sur la même étape.

## Le guide d'utilisation

Le contenu vit une fois, dans `i18n/guide_fr.py` et `guide_en.py` (rubriques → blocs). L'appli l'affiche
(`gui/guide_window.py`) et `tools/build_docs.py` en tire `docs/guide-utilisateur.md` et `docs/user-guide.md`. Un test
échoue si les fichiers Markdown ne sont pas à jour : après avoir modifié le guide, lancer `python tools/build_docs.py`.

## Mise à jour automatique

`services/updater.py` interroge la dernière release GitHub, cherche l'asset **`RKarrousel-vX.Y.Z.exe`** (le nom est un
contrat : ne pas le changer), le télécharge, contrôle taille et SHA-256, vérifie que la nouvelle version démarre
(`--smoke-test`), remplace l'exécutable en place (l'ancien devient `.old`) et relance avec
`PYINSTALLER_RESET_ENVIRONMENT=1`. Le déroulé complet est dans `docs/development.md` (section Release).
