# RKarrousel

Prépare des photos exportées de Lightroom pour Instagram : cadre blanc, découpe des paysages 2/3 en
deux portraits 3/4, fond flouté ou noir, signature, et numérotation des fichiers selon l'ordre voulu.

## Ce que fait l'appli

| Photo source | Images produites |
|---|---|
| Portrait 3/4 | `_framed` : la photo encadrée |
| Portrait 2/3 | `_with_sig` (ou `_framed` sans signature) : portrait 3/4 avec fond uni ou flouté ; `_crop34` : recadrage 3/4 de la photo (cadre blanc, sans signature), dont vous réglez la zone conservée |
| Paysage 3/2 | `_part1`, `_part2` : deux moitiés encadrées (panorama) ; `_part1_with_sig`, `_part2_with_sig` : la photo entière en portrait 3/4, droite puis pivotée |
| Autre ratio | ignorée (signalée dans le récapitulatif) |

## Utiliser l'appli (Windows)

Téléchargez depuis les *Releases* du dépôt :

- **`RKarrousel-Setup-vX.Y.Z.exe`** (recommandé) : installateur Windows, sans droits administrateur. Il installe
  l'appli dans `%LOCALAPPDATA%\Programs\RKarrousel`, crée l'entrée du menu Démarrer (et un raccourci bureau en option)
  et dépose des **réglages par défaut** (cadre 1 %, fond flouté, numérotation, sortie dans *Documents\RKarrousel*, langue
  de l'installateur) modifiables dans `installer/default_config.json`. Une mise à jour **conserve vos réglages** ;
  la désinstallation propose de les supprimer.
- **`RKarrousel-vX.Y.Z.exe`** : version portable, un seul fichier, à lancer où vous voulez.

- **Fichiers** : ajoutez des fichiers ou des dossiers (ou glissez-déposez-les), choisissez le dossier de destination.
- **Réglages** : épaisseur et couleur du cadre, fond uni (couleur au choix) ou flouté et intensité du flou, signature (position, taille),
  qualité JPEG. Les réglages sont enregistrés automatiquement à la fermeture.
- **Aperçu et ordre…** : affiche le rendu final de chaque image dans une grille façon Instagram. Glissez les images
  pour choisir leur ordre — les morceaux d'une même photo peuvent être séparés. Avec « Numéroter les fichiers »,
  les fichiers générés sont préfixés `01_`, `02_`… selon cet ordre.
  Cliquez une image pour la sélectionner : **Voir en grand** (ou double-clic) ouvre le rendu en pleine résolution avec
  zoom, déplacement et une règle (clic droit + glisser) qui mesure en pixels, par exemple l'épaisseur du cadre ;
  **Recadrer…** (ou double-clic sur un « recadrage 3/4 ») ouvre l'éditeur : on fait glisser le cadre 3/4 sur la photo
  avec un aperçu du résultat, et le choix est mémorisé par photo ;
  **Exclure** (ou touche Suppr, ou la croix de la vignette) retire l'image : elle n'est ni générée ni numérotée, et on peut la réintégrer.
- **Réglages** : les types d'images produites pour les paysages se décochent aussi une fois pour toutes.
- **Langue** : français ou anglais (liste en haut à droite).
- En cas de problème, le journal `image_splitter.log` est créé à côté de l'exécutable.

La configuration `.image_splitter_config.json` est stockée à côté de l'exécutable.

## Envoi sur Google Drive (optionnel)

Dans **Réglages → Google Drive**, cochez « Envoyer les images sur Google Drive après le traitement » : les images
générées sont envoyées, dans l'ordre numéroté, vers le dossier Drive indiqué (créé au besoin, `Instagram/2026` crée un
sous-dossier ; un fichier du même nom est mis à jour au lieu d'être dupliqué).

Configuration, une seule fois (le bouton « Comment faire ? » de l'appli résume ces étapes) :

1. Sur [console.cloud.google.com](https://console.cloud.google.com), créez un projet et activez **Google Drive API**.
2. « Écran de consentement OAuth » : type *Externe*, nom et e-mail, puis **Publier l'application** (sinon l'accès expire
   au bout de 7 jours).
3. « Identifiants » → *ID client OAuth* → type **Application de bureau** ; téléchargez le fichier JSON.
4. Dans l'appli : **Charger les identifiants (JSON)…**, puis **Se connecter** (autorisation dans le navigateur ;
   Google peut afficher « application non vérifiée » : *Paramètres avancés* → *Continuer*).

L'appli utilise la portée `drive.file` : elle ne voit que les fichiers qu'elle envoie, jamais le reste du Drive.
Le jeton de connexion est enregistré dans `gdrive_token.json`, à côté de l'exécutable (à ne pas partager).

## En ligne de commande

```bash
pip install -r requirements.txt
python main.py photos/ -d output --frame-ratio 0.04 --number --workers 3
python photo_splitter_gui.py        # interface graphique
python -m unittest discover -s tests
```

## Compiler l'exécutable et l'installateur

`build_windows.bat` (Windows, Python installé) produit `dist\RKarrousel.exe`.
L'installateur se compile ensuite avec [Inno Setup 6](https://jrsoftware.org/isinfo.php) :
`ISCC.exe /DAppVersion=X.Y.Z installer\RKarrousel.iss` produit `dist\RKarrousel-Setup-vX.Y.Z.exe`.
Depuis WSL : voir `.claude/skills/imagesplitter-release/SKILL.md`.

## Publier une version

Le numéro de version est dans `version.py` (affiché dans le titre de la fenêtre et dans « À propos »).
Pousser un tag `vX.Y.Z` déclenche le workflow GitHub Actions `release.yml` qui exécute les tests, compile
l'exécutable Windows, fabrique l'installateur, teste une installation silencieuse, puis ajoute
`RKarrousel-vX.Y.Z.exe` et `RKarrousel-Setup-vX.Y.Z.exe` à la release. Le tag doit correspondre à `version.py`.
