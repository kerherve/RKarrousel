# Photo Splitter LR → Instagram

Prépare des photos exportées de Lightroom pour Instagram : cadre blanc, découpe des paysages 2/3 en
deux portraits 3/4, fond flouté ou noir, signature, et numérotation des fichiers selon l'ordre voulu.

## Ce que fait l'appli

| Photo source | Images produites |
|---|---|
| Portrait 3/4 | `_framed` : la photo encadrée |
| Portrait 2/3 | `_with_sig` (ou `_framed` sans signature) : portrait 3/4 avec fond noir ou flouté |
| Paysage 3/2 | `_part1`, `_part2` : deux moitiés encadrées (panorama) ; `_part1_with_sig`, `_part2_with_sig` : la photo entière en portrait 3/4, droite puis pivotée |
| Autre ratio | ignorée (signalée dans le récapitulatif) |

## Utiliser l'appli (Windows)

Téléchargez `PhotoSplitter.exe` depuis les *Releases* du dépôt, puis lancez-le.

- **Fichiers** : ajoutez des fichiers ou des dossiers (ou glissez-déposez-les), choisissez le dossier de destination.
- **Réglages** : épaisseur et couleur du cadre, fond uni (couleur au choix) ou flouté et intensité du flou, signature (position, taille),
  qualité JPEG. Les réglages sont enregistrés automatiquement à la fermeture.
- **Aperçu et ordre…** : affiche le rendu final de chaque image dans une grille façon Instagram. Glissez les images
  pour choisir leur ordre — les morceaux d'une même photo peuvent être séparés. Avec « Numéroter les fichiers »,
  les fichiers générés sont préfixés `01_`, `02_`… selon cet ordre.
  Cliquez une image pour la sélectionner : **Voir en grand** (ou double-clic) ouvre le rendu en pleine résolution avec
  zoom, déplacement et une règle (clic droit + glisser) qui mesure en pixels, par exemple l'épaisseur du cadre ;
  **Exclure** (ou touche Suppr) retire l'image : elle n'est ni générée ni numérotée, et on peut la réintégrer.
- **Réglages** : les types d'images produites pour les paysages se décochent aussi une fois pour toutes.
- **Langue** : français ou anglais (liste en haut à droite).
- En cas de problème, le journal `image_splitter.log` est créé à côté de l'exécutable.

La configuration `.image_splitter_config.json` est stockée à côté de l'exécutable.

## En ligne de commande

```bash
pip install -r requirements.txt
python main.py photos/ -d output --frame-ratio 0.04 --number --workers 3
python photo_splitter_gui.py        # interface graphique
python -m unittest discover -s tests
```

## Compiler l'exécutable

`build_windows.bat` (Windows, Python installé) produit `dist\PhotoSplitter.exe`.
Depuis WSL : voir `.claude/skills/imagesplitter-release/SKILL.md`.

## Publier une version

Le numéro de version est dans `version.py` (affiché dans le titre de la fenêtre et dans « À propos »).
Pousser un tag `vX.Y.Z` déclenche le workflow GitHub Actions `release.yml` qui exécute les tests, compile
l'exécutable Windows et l'ajoute à la release sous le nom `PhotoSplitter-vX.Y.Z.exe`.
