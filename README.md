<p align="center"><img src="docs/logo.png" alt="Logo RKarrousel" width="128"></p>

# RKarrousel

Prépare vos photos pour Instagram : cadre, fond flouté ou uni, découpe des panoramas en carrousel, recadrage, signature,
ordre et numérotation des fichiers. Application Windows (Python, Tkinter, Pillow), en français et en anglais.

*Prepares your photos for Instagram: frame, background, panorama slicing, cropping, signature, ordering and numbering. Windows app, French and English.*

## Installer

Téléchargez depuis les [Releases](https://github.com/kerherve/RKarrousel/releases/latest) :

- **`RKarrousel-Setup-vX.Y.Z.exe`** (recommandé) : installateur sans droits administrateur (menu Démarrer, raccourci
  bureau en option, réglages par défaut). Une mise à jour conserve vos réglages.
- **`RKarrousel-vX.Y.Z.exe`** : version portable, un seul fichier.

L'appli recherche ensuite elle-même les nouvelles versions au démarrage et se met à jour en un clic.

## Comment ça marche

Un flux en quatre étapes : **Photos** (ajout, dossier de destination, format) → **Ordre** (la grille façon profil
Instagram : réordonner, exclure, recadrer) → **Ajustements** (image par image, avec un carrousel qui montre les
voisines) → **Export** (qualité, taille, numérotation, Google Drive, « Lancer le traitement »).

## Ce qu'elle fait

| Photo source | Images produites |
|---|---|
| Déjà au format de sortie (3:4 par défaut) | Une image encadrée, au format exact |
| Portrait 2:3, autre portrait, carré | La photo entière sur un fond au format, et un recadrage réglable |
| Paysage 3:2 | Deux moitiés encadrées d'un panorama, plus la photo entière droite et pivotée |
| Autre paysage, panorama | Le panorama découpé en tranches contiguës (20 au maximum), la photo entière et un recadrage |

Formats 3:4, 4:5, 1:1 et 9:16 ; largeur d'origine ou 1080/1440/2048 px ; **préréglages** nommés ; cadre et fond dont la
**couleur est tirée de chaque photo** ; grille d'aperçu façon Instagram pour choisir l'ordre ; numérotation `01_`, `02_`… ;
envoi optionnel sur Google Drive.

## Documentation

- **Guide d'utilisation** : bouton « Guide » (ou touche F1) dans l'appli ; [en français](docs/guide-utilisateur.md), [in English](docs/user-guide.md)
- [Architecture](docs/architecture.md) : modules, flux de données, interface
- [Développement](docs/development.md) : installation, tests, compilation, publication d'une version
- [Fichier de réglages](docs/config.md) : toutes les clés de configuration

## Depuis les sources

```bash
python -m pip install -r requirements.txt
python -m rkarrousel                                    # interface graphique
python -m rkarrousel.cli photos/ -d sortie --number     # ligne de commande (--help)
python -m unittest discover -s tests -t .               # tests
```
