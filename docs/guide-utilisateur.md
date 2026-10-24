<!-- Généré par tools/build_docs.py à partir de rkarrousel/i18n/guide_fr.py : ne pas modifier à la main. -->
# Guide d'utilisation de RKarrousel

Tout ce qu'il faut savoir pour préparer vos photos pour Instagram avec RKarrousel.

## Sommaire

1. [Premiers pas](#premiers-pas)
2. [Ajouter des photos](#ajouter-des-photos)
3. [Les images produites](#les-images-produites)
4. [Cadre, fond et signature](#cadre-fond-et-signature)
5. [Couleurs tirées de la photo](#couleurs-tirées-de-la-photo)
6. [Préréglages](#préréglages)
7. [Format et taille des images](#format-et-taille-des-images)
8. [Aperçu et ordre](#aperçu-et-ordre)
9. [Recadrer une image](#recadrer-une-image)
10. [Voir en grand et mesurer](#voir-en-grand-et-mesurer)
11. [Numérotation des fichiers](#numérotation-des-fichiers)
12. [Envoyer sur Google Drive](#envoyer-sur-google-drive)
13. [Mises à jour](#mises-à-jour)
14. [Langue et thème](#langue-et-thème)
15. [Raccourcis](#raccourcis)
16. [En cas de problème](#en-cas-de-problème)

## Premiers pas

RKarrousel prépare vos photos pour Instagram : cadre, fond, découpe des panoramas, recadrage, ordre et numérotation des images. En quatre étapes :

1. Onglet « Fichiers » : ajoutez vos photos avec « Ajouter fichiers » ou « Ajouter dossier » (ou glissez-déposez-les).
2. Choisissez le dossier de destination.
3. Onglet « Réglages » : réglez le look, ou choisissez un préréglage.
4. Cliquez sur « Aperçu et ordre… » pour vérifier et ordonner les images, puis sur « Lancer le traitement ».

> **Remarque** — Vos réglages sont enregistrés automatiquement à la fermeture de l'appli. La touche F1 ouvre ce guide à tout moment.


## Ajouter des photos

- Formats acceptés : JPEG, PNG, TIFF et BMP.
- « Ajouter dossier » prend toutes les images du dossier (sans ses sous-dossiers).
- Le glisser-déposer de fichiers et de dossiers dans la liste fonctionne aussi.
- Cliquez une entrée de la liste : l'aperçu à droite montre la photo, ou la première photo d'un dossier.
- « Effacer la sélection » vide la liste.

Tous les formats de photo sont acceptés : portrait, paysage, carré, panorama… Le traitement s'adapte (voir « Les images produites »).


## Les images produites

Chaque photo donne une ou plusieurs images, au format de sortie choisi (3:4 par défaut, la grille Instagram) :

- Photo déjà au format de sortie : une image encadrée (`_framed`). Elle est rognée de moins de 1 % pour que, cadre compris, le format soit exact.
- Portrait 2:3, autre portrait ou carré : la photo entière sur un fond au format (`_with_sig`, ou `_framed` sans signature) et un recadrage réglable (`_crop34`).
- Paysage 3:2 : les deux moitiés encadrées d'un panorama (`_part1`, `_part2`), la photo entière (`_part1_with_sig`) et la même pivotée (`_part2_with_sig`).
- Autre paysage ou panorama : le panorama découpé en tranches contiguës (`_part1` à `_partN`, 10 au maximum), la photo entière droite et pivotée, et un recadrage.

> **Remarque** — Les tranches d'un panorama se recomposent sans double bordure : le cadre n'entoure que le haut, le bas et les deux extrémités.

Vous n'avez pas besoin de toutes les images : décochez un type dans Réglages → « Images produites pour chaque photo », ou excluez une image précise dans la grille « Aperçu et ordre ».


## Cadre, fond et signature

### Cadre

- Épaisseur : en pourcentage du plus petit côté de la photo (1 = cadre fin, 3 = cadre épais).
- Couleur : fixe, ou tirée de la photo (voir « Couleurs tirées de la photo »).
- « Sans cadre » supprime tout cadre ; les images restent exactement au format de sortie.

### Fond

Quand la photo n'a pas le format de sortie, le reste de l'image est rempli par un fond :

- Fond uni : couleur fixe (noir par défaut) ou tirée de la photo.
- Fond flouté : une version agrandie et floutée de la photo ; l'intensité du flou se règle.

### Signature

- Choisissez une image (un PNG à fond transparent donne le meilleur résultat), sa position (bas à droite, au centre ou à gauche) et sa taille (×).
- Elle est posée sur les images « entières » (portraits 2:3, paysages), pas sur les recadrages ni sur les photos déjà au bon format.


## Couleurs tirées de la photo

La couleur du cadre et celle du fond uni peuvent être calculées pour chaque photo :

- Couleur de la photo : la couleur dominante.
- Photo, version claire : la dominante éclaircie (élégant pour un cadre).
- Photo, version sombre : la dominante assombrie (idéal pour un fond uni).

Un lot de photos de teintes différentes donne ainsi des cadres assortis à chacune. Toutes les images d'une même photo partagent ses couleurs.


## Préréglages

Un préréglage mémorise le cadre, le fond, la signature, le format et la taille des images. En haut de l'onglet Réglages :

- Choisissez un préréglage dans la liste : tous les réglages concernés changent d'un coup.
- Quatre sont fournis : Classique, Fond noir, Couleurs de la photo, Sans cadre. Ils ne changent que les réglages qu'ils citent.
- « Enregistrer sous… » garde vos réglages actuels sous le nom de votre choix (un nom déjà pris demande confirmation).
- « Supprimer » retire un de vos préréglages ; les préréglages fournis ne se suppriment pas.

> **Remarque** — Modifier un réglage ensuite ne change pas le préréglage : enregistrez-le de nouveau sous le même nom pour le mettre à jour.


## Format et taille des images

Réglages → « Fichiers générés » :

- Format : 3:4 (grille Instagram, par défaut), 4:5 (feed), 1:1 (carré) ou 9:16 (stories, reels). Le découpage des panoramas, le recadrage et les fonds s'adaptent.
- Largeur : taille d'origine, ou 1080 px (la taille idéale pour Instagram), 1440 ou 2048 px. Les fichiers sont beaucoup plus légers, et jamais agrandis.
- Qualité JPEG : 100 par défaut ; vers 90-95 les fichiers pèsent environ moitié moins, sans différence visible.

> **Remarque** — Les fichiers de recadrage portent le format dans leur nom : `_crop34` en 3:4, `_crop45` en 4:5, etc.


## Aperçu et ordre

Le bouton « Aperçu et ordre… » affiche le rendu final de chaque image dans une grille de trois colonnes, comme un profil Instagram.

- Glissez une image pour la déplacer : les morceaux d'une même photo peuvent être séparés.
- Le numéro bleu est celui qui préfixera le fichier (voir « Numérotation des fichiers »).
- La croix en haut à droite d'une image l'exclut (elle n'est ni générée ni numérotée) ; ↺ la réintègre.
- Cliquez une image pour la sélectionner : « Voir en grand », « Recadrer… » (pour un recadrage) et « Exclure » agissent sur elle. Un double-clic ouvre le recadrage, ou la vue en grand pour les autres images. Le clic droit ouvre un menu.
- « Rafraîchir l'aperçu » prend en compte les réglages modifiés depuis l'ouverture ; « Ordre naturel » remet l'ordre d'origine.


## Recadrer une image

Sur une image « recadrage », « Recadrer… » ouvre l'éditeur :

- Faites glisser le cadre orange sur la photo pour choisir la zone conservée ; l'aperçu à droite montre le résultat final.
- Molette ou flèches du clavier (Maj pour aller plus vite) ; boutons Haut / Centre / Bas.
- Le cadre se déplace verticalement pour une photo plus étroite que le format, horizontalement pour une photo plus large.
- « Valider » enregistre le choix pour cette photo : il est conservé d'une session à l'autre.


## Voir en grand et mesurer

« Voir en grand » ouvre le rendu en pleine résolution :

- Molette : zoom ; glisser : déplacer l'image ; « Ajuster » et « 100 % » pour revenir.
- Clic droit + glisser : règle qui mesure en pixels, par exemple l'épaisseur du cadre.
- L'épaisseur du cadre est aussi mesurée automatiquement et affichée en haut.
- Panneau « Réglages » à droite : épaisseur et couleur du cadre, fond (uni ou flou), couleurs tirées de la photo. L'image se recalcule après chaque changement, sans retourner dans l'onglet Réglages ; le bouton « Réglages » masque ou affiche le panneau.
- Ce sont les réglages de l'onglet Réglages : ils s'appliquent à toutes les photos, et la grille se met à jour à la fermeture.


## Numérotation des fichiers

Avec « Numéroter les fichiers » (Réglages → « Fichiers générés »), chaque image est préfixée par son numéro : 01_, 02_, 03_… (trois chiffres au-delà de 99). L'ordre est celui de la grille.

Vous copiez ensuite les fichiers sur votre drive ou votre téléphone sans rien renommer : l'ordre alphabétique est celui du carrousel.

> **Remarque** — Relancer un traitement avec un autre ordre dans le même dossier ne supprime pas les anciens fichiers : videz le dossier avant si besoin.


## Envoyer sur Google Drive

Réglages → « Google Drive » : cochez « Envoyer les images sur Google Drive après le traitement ». Les images partent dans l'ordre numéroté vers le dossier indiqué (« Instagram/2026 » crée un sous-dossier ; un fichier du même nom est mis à jour au lieu d'être dupliqué).

### À faire une seule fois

1. Sur console.cloud.google.com, créez un projet et activez « Google Drive API ».
2. « Écran de consentement OAuth » : type Externe, nom et e-mail, puis « Publier l'application » (sinon l'accès expire au bout de 7 jours).
3. « Identifiants » → « ID client OAuth » → type « Application de bureau », puis téléchargez le fichier JSON.
4. Dans l'appli : « Charger les identifiants (JSON)… », puis « Se connecter » (autorisation dans le navigateur ; « application non vérifiée » : Paramètres avancés → Continuer).

> **Remarque** — L'appli ne voit que les fichiers qu'elle envoie elle-même, jamais le reste de votre Drive. Le bouton « Comment faire ? » rappelle ces étapes.


## Mises à jour

- À chaque démarrage, l'appli cherche une version plus récente sur GitHub (désactivable dans Réglages → Mises à jour).
- Si elle en trouve une, elle affiche les nouveautés : « Mettre à jour maintenant », « Plus tard » ou « Ignorer cette version ».
- La mise à jour télécharge la nouvelle version, vérifie qu'elle est intacte et qu'elle démarre, remplace l'ancienne sur place et relance l'appli.
- Votre raccourci et vos réglages ne changent pas. « Rechercher maintenant » force la vérification.


## Langue et thème

- Langue : français ou anglais (Réglages → Apparence).
- Thème : clair, sombre, ou « Auto » qui suit Windows.


## Raccourcis

- F1 : ouvrir ce guide.
- Grille d'ordre : Suppr exclut l'image sélectionnée ; Entrée l'ouvre en grand.
- Éditeur de recadrage : ↑ ↓ ← → déplacent le cadre (Maj : plus vite) ; Entrée valide ; Échap annule.
- Vue en grand : Échap ferme la fenêtre.


## En cas de problème

- Un récapitulatif s'affiche à la fin du traitement : il liste les photos en erreur ou ignorées, avec la raison.
- Le journal `image_splitter.log` est à côté de l'exécutable (son emplacement est indiqué dans « À propos »).
- « Format trop panoramique » : une photo très large donnerait plus de 10 images ; recadrez-la dans votre logiciel photo.
- Pour repartir de zéro, fermez l'appli et supprimez le fichier `.image_splitter_config.json` à côté de l'exécutable.
- Pour traiter des photos sans l'interface : `python -m rkarrousel.cli` (voir la documentation du projet).
