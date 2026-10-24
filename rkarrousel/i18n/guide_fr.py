"""Guide d'utilisation (français). Source unique : l'écran « Guide » de l'appli et `docs/guide-utilisateur.md`
(généré par `python tools/build_docs.py`) en sont tous deux tirés.

Chaque rubrique est un triplet (identifiant, titre, blocs). Blocs : ("p", texte), ("h", sous-titre),
("steps", [étapes]), ("bullets", [puces]), ("note", texte).
"""

INTRO = "Tout ce qu'il faut savoir pour préparer vos photos pour Instagram avec RKarrousel."

GUIDE = [
    ("start", "Premiers pas", [
        ("p", "RKarrousel prépare vos photos pour Instagram : cadre, fond, découpe des panoramas, recadrage, ordre et "
              "numérotation des images. En quatre étapes :"),
        ("steps", [
            "Onglet « Fichiers » : ajoutez vos photos avec « Ajouter fichiers » ou « Ajouter dossier » (ou glissez-déposez-les).",
            "Choisissez le dossier de destination.",
            "Onglet « Réglages » : réglez le look, ou choisissez un préréglage.",
            "Cliquez sur « Aperçu et ordre… » pour vérifier et ordonner les images, puis sur « Lancer le traitement ».",
        ]),
        ("note", "Vos réglages sont enregistrés automatiquement à la fermeture de l'appli. La touche F1 ouvre ce guide à tout moment."),
    ]),
    ("photos", "Ajouter des photos", [
        ("bullets", [
            "Formats acceptés : JPEG, PNG, TIFF et BMP.",
            "« Ajouter dossier » prend toutes les images du dossier (sans ses sous-dossiers).",
            "Le glisser-déposer de fichiers et de dossiers dans la liste fonctionne aussi.",
            "Cliquez une entrée de la liste : l'aperçu à droite montre la photo, ou la première photo d'un dossier.",
            "« Effacer la sélection » vide la liste.",
        ]),
        ("p", "Tous les formats de photo sont acceptés : portrait, paysage, carré, panorama… Le traitement s'adapte (voir « Les images produites »)."),
    ]),
    ("outputs", "Les images produites", [
        ("p", "Chaque photo donne une ou plusieurs images, au format de sortie choisi (3:4 par défaut, la grille Instagram) :"),
        ("bullets", [
            "Photo déjà au format de sortie : une image encadrée (`_framed`). Elle est rognée de moins de 1 % pour que, cadre compris, le format soit exact.",
            "Portrait 2:3, autre portrait ou carré : la photo entière sur un fond au format (`_with_sig`, ou `_framed` sans signature) et un recadrage réglable (`_crop34`).",
            "Paysage 3:2 : les deux moitiés encadrées d'un panorama (`_part1`, `_part2`), la photo entière (`_part1_with_sig`) et la même pivotée (`_part2_with_sig`).",
            "Autre paysage ou panorama : le panorama découpé en tranches contiguës (`_part1` à `_partN`, 20 au maximum), la photo entière droite et pivotée, et un recadrage.",
        ]),
        ("p", "Avec un fond uni (noir par défaut) comme avec un fond flouté, le cadre entoure toute l'image, au bord ; la photo entière est posée à l'intérieur."),
        ("p", "Ordre dans le carrousel : pour un paysage, la photo entière vient par défaut avant les tranches. Réglages → « Images produites pour chaque photo » permet de placer chacune des deux photos entières (droite et pivotée) avant ou après le découpage, à la fin du carrousel (dans l'ordre des photos), ou de la supprimer."),
        ("note", "Les tranches d'un panorama se recomposent sans double bordure : le cadre n'entoure que le haut, le bas et les deux extrémités."),
        ("p", "Vous n'avez pas besoin de toutes les images : décochez un type dans Réglages → « Images produites pour chaque photo », "
              "ou excluez une image précise dans la grille « Aperçu et ordre »."),
    ]),
    ("look", "Cadre, fond et signature", [
        ("h", "Cadre"),
        ("bullets", [
            "Épaisseur : en pourcentage du plus petit côté de la photo (1 = cadre fin, 3 = cadre épais).",
            "Couleur : fixe, ou tirée de la photo (voir « Couleurs tirées de la photo »).",
            "« Sans cadre » supprime tout cadre ; les images restent exactement au format de sortie.",
        ]),
        ("h", "Fond"),
        ("p", "Quand la photo n'a pas le format de sortie, le reste de l'image est rempli par un fond :"),
        ("bullets", [
            "Fond uni : couleur fixe (noir par défaut) ou tirée de la photo.",
            "Fond flouté : une version agrandie et floutée de la photo ; l'intensité du flou se règle.",
        ]),
        ("h", "Signature"),
        ("bullets", [
            "Choisissez une image (un PNG à fond transparent donne le meilleur résultat), sa position (bas à droite, au centre ou à gauche) et sa taille (×).",
            "Elle est posée sur les images « entières » (portraits 2:3, paysages), pas sur les recadrages ni sur les photos déjà au bon format.",
        ]),
    ]),
    ("colors", "Couleurs tirées de la photo", [
        ("p", "La couleur du cadre et celle du fond uni peuvent être calculées pour chaque photo :"),
        ("bullets", [
            "Couleur de la photo : la couleur dominante.",
            "Photo, version claire : la dominante éclaircie (élégant pour un cadre).",
            "Photo, version sombre : la dominante assombrie (idéal pour un fond uni).",
            "Photo, couleur complémentaire : la teinte opposée, adoucie (un ciel bleu donne un cadre chaud, sans orange criard).",
            "Photo, couleur de contraste : un ton clair sur une photo sombre, foncé sur une photo claire, à la teinte de la photo (un pastel ou un brun profond, jamais un blanc ou un noir pur).",
        ]),
        ("p", "« Couleur prise sur » choisit la couleur de référence : la couleur dominante, les bords de la photo (ce que le cadre touche vraiment) ou la moyenne de toute la photo."),
        ("p", "Un lot de photos de teintes différentes donne ainsi des cadres assortis à chacune. Toutes les images d'une même photo partagent ses couleurs."),
        ("note", "Pour une seule photo, la visionneuse (« Voir en grand ») propose une couleur de cadre qui lui est propre : voir « Voir en grand et mesurer »."),
    ]),
    ("presets", "Préréglages", [
        ("p", "Un préréglage mémorise le cadre, le fond, la signature, le format et la taille des images. En haut de l'onglet Réglages :"),
        ("bullets", [
            "Choisissez un préréglage dans la liste : tous les réglages concernés changent d'un coup.",
            "Quatre sont fournis : Classique, Fond noir, Couleurs de la photo, Sans cadre. Ils ne changent que les réglages qu'ils citent.",
            "« Enregistrer sous… » garde vos réglages actuels sous le nom de votre choix (un nom déjà pris demande confirmation).",
            "« Supprimer » retire un de vos préréglages ; les préréglages fournis ne se suppriment pas.",
        ]),
        ("note", "Modifier un réglage ensuite ne change pas le préréglage : enregistrez-le de nouveau sous le même nom pour le mettre à jour."),
    ]),
    ("format", "Format et taille des images", [
        ("p", "Réglages → « Fichiers générés » :"),
        ("bullets", [
            "Format : 3:4 (grille Instagram, par défaut), 4:5 (feed), 1:1 (carré) ou 9:16 (stories, reels). Le découpage des panoramas, le recadrage et les fonds s'adaptent.",
            "Largeur : taille d'origine, ou 1080 px (la taille idéale pour Instagram), 1440 ou 2048 px. Les fichiers sont beaucoup plus légers, et jamais agrandis.",
            "Qualité JPEG : 100 par défaut ; vers 90-95 les fichiers pèsent environ moitié moins, sans différence visible.",
        ]),
        ("note", "Les fichiers de recadrage portent le format dans leur nom : `_crop34` en 3:4, `_crop45` en 4:5, etc."),
    ]),
    ("order", "Aperçu et ordre", [
        ("p", "Le bouton « Aperçu et ordre… » affiche le rendu final de chaque image dans une grille de trois colonnes, comme un profil Instagram."),
        ("bullets", [
            "Agrandissez la fenêtre pour voir plus d'images à la fois : la grille ajoute des colonnes (trois au minimum, comme un profil Instagram) et l'ordre se lit de gauche à droite, ligne après ligne.",
            "Instagram limite un carrousel à 20 images : au-delà, un avertissement orange apparaît en haut et les numéros des images 21 et suivantes passent en rouge. Excluez-en ou répartissez-les en plusieurs publications.",
            "Glissez une image pour la déplacer : les morceaux d'une même photo peuvent être séparés.",
            "Le numéro bleu est celui qui préfixera le fichier (voir « Numérotation des fichiers »).",
            "La croix en haut à droite d'une image l'exclut (elle n'est ni générée ni numérotée) ; ↺ la réintègre.",
            "Cliquez une image pour la sélectionner : « Voir en grand », « Recadrer… » (pour un recadrage) et « Exclure » agissent sur elle. Un double-clic ouvre le recadrage, ou la vue en grand pour les autres images. Le clic droit ouvre un menu.",
            "« Rafraîchir l'aperçu » prend en compte les réglages modifiés depuis l'ouverture ; « Ordre naturel » remet l'ordre d'origine.",
        ]),
    ]),
    ("crop", "Recadrer une image", [
        ("p", "Sur une image « recadrage », « Recadrer… » ouvre l'éditeur :"),
        ("bullets", [
            "Faites glisser le cadre orange sur la photo pour choisir la zone conservée ; l'aperçu à droite montre le résultat final.",
            "Molette ou flèches du clavier (Maj pour aller plus vite) ; boutons Haut / Centre / Bas.",
            "Le cadre se déplace verticalement pour une photo plus étroite que le format, horizontalement pour une photo plus large.",
            "« Valider » enregistre le choix pour cette photo : il est conservé d'une session à l'autre.",
        ]),
    ]),
    ("viewer", "Voir en grand et mesurer", [
        ("p", "« Voir en grand » ouvre le rendu en pleine résolution :"),
        ("bullets", [
            "Molette : zoom ; glisser : déplacer l'image ; « Ajuster » et « 100 % » pour revenir.",
            "Flèches rondes sur les bords (ou touches ← →) : image précédente ou suivante de la grille, sans fermer la fenêtre. Les images exclues sont sautées ; le rang (3 / 12) est en haut.",
            "Feuilleter est rapide : les images voisines et l'aperçu de la nouvelle image s'affichent tout de suite (ils viennent de la grille), puis la pleine résolution se précise dès que vous vous arrêtez.",
            "Glisser l'image à la souris la fait défiler : lâchée assez loin (ou d'un coup de pouce rapide), l'image voisine arrive en glissant ; sinon elle revient en place. Zoomée, le glisser déplace l'image.",
            "Le bouton « Recadrer… » ouvre le réglage du cadrage quand l'image affichée est un recadrage ; l'image se recalcule une fois validé.",
            "Aperçu carrousel : les images précédente et suivante apparaissent de part et d'autre, comme quand on fait défiler un post Instagram, pour juger le rendu d'ensemble (tranches d'un panorama qui se raccordent, cadres voisins…). La case « Aperçu carrousel » le désactive.",
            "Clic droit + glisser : règle qui mesure en pixels, par exemple l'épaisseur du cadre.",
            "L'épaisseur du cadre est aussi mesurée automatiquement et affichée en haut.",
            "Panneau « Réglages » à droite : épaisseur et couleur du cadre, fond (uni ou flou), signature, couleurs tirées de la photo. Ce que l'image affichée n'utilise pas est grisé : une tranche de panorama ou un recadrage n'a ni fond ni signature. L'image se recalcule après chaque changement, sans retourner dans l'onglet Réglages ; le bouton « Réglages » masque ou affiche le panneau.",
            "« Cadre de cette photo » : une couleur de cadre propre à la photo affichée (fixe, ou tirée de la photo), qui remplace le réglage général pour elle seule. « Comme les réglages généraux » l'annule. « Couleur obtenue » montre la couleur réellement calculée pour cette photo ; trois curseurs « Affiner » (teinte, saturation, clarté) la retouchent très légèrement, à l'œil, pour cette photo seulement. « Réinitialiser » les remet à zéro ; un double-clic sur une ligne remet ce seul curseur au milieu. Le choix est conservé d'une session à l'autre.",
            "Le reste du panneau reprend les réglages de l'onglet Réglages : ils s'appliquent à toutes les photos, et la grille se met à jour à la fermeture.",
        ]),
    ]),
    ("numbering", "Numérotation des fichiers", [
        ("p", "Avec « Numéroter les fichiers » (Réglages → « Fichiers générés »), chaque image est préfixée par son numéro : 01_, 02_, 03_… "
              "(trois chiffres au-delà de 99). L'ordre est celui de la grille."),
        ("p", "Vous copiez ensuite les fichiers sur votre drive ou votre téléphone sans rien renommer : l'ordre alphabétique est celui du carrousel."),
        ("note", "Relancer un traitement avec un autre ordre dans le même dossier ne supprime pas les anciens fichiers : videz le dossier avant si besoin."),
    ]),
    ("drive", "Envoyer sur Google Drive", [
        ("p", "Réglages → « Google Drive » : cochez « Envoyer les images sur Google Drive après le traitement ». Les images partent dans l'ordre numéroté vers le dossier indiqué "
              "(« Instagram/2026 » crée un sous-dossier ; un fichier du même nom est mis à jour au lieu d'être dupliqué)."),
        ("h", "À faire une seule fois"),
        ("steps", [
            "Sur console.cloud.google.com, créez un projet et activez « Google Drive API ».",
            "« Écran de consentement OAuth » : type Externe, nom et e-mail, puis « Publier l'application » (sinon l'accès expire au bout de 7 jours).",
            "« Identifiants » → « ID client OAuth » → type « Application de bureau », puis téléchargez le fichier JSON.",
            "Dans l'appli : « Charger les identifiants (JSON)… », puis « Se connecter » (autorisation dans le navigateur ; « application non vérifiée » : Paramètres avancés → Continuer).",
        ]),
        ("note", "L'appli ne voit que les fichiers qu'elle envoie elle-même, jamais le reste de votre Drive. Le bouton « Comment faire ? » rappelle ces étapes."),
    ]),
    ("updates", "Mises à jour", [
        ("bullets", [
            "À chaque démarrage, l'appli cherche une version plus récente sur GitHub (désactivable dans Réglages → Mises à jour).",
            "Si elle en trouve une, elle affiche les nouveautés : « Mettre à jour maintenant », « Plus tard » ou « Ignorer cette version ».",
            "La mise à jour télécharge la nouvelle version, vérifie qu'elle est intacte et qu'elle démarre, remplace l'ancienne sur place et relance l'appli.",
            "Votre raccourci et vos réglages ne changent pas. « Rechercher maintenant » force la vérification.",
        ]),
    ]),
    ("appearance", "Langue et thème", [
        ("bullets", [
            "Langue : français ou anglais (Réglages → Apparence).",
            "Thème : clair, sombre, ou « Auto » qui suit Windows.",
        ]),
    ]),
    ("shortcuts", "Raccourcis", [
        ("bullets", [
            "F1 : ouvrir ce guide.",
            "Grille d'ordre : Suppr exclut l'image sélectionnée ; Entrée l'ouvre en grand.",
            "Éditeur de recadrage : ↑ ↓ ← → déplacent le cadre (Maj : plus vite) ; Entrée valide ; Échap annule.",
            "Vue en grand : ← → image précédente / suivante ; Échap ferme la fenêtre.",
        ]),
    ]),
    ("help", "En cas de problème", [
        ("bullets", [
            "Un récapitulatif s'affiche à la fin du traitement : il liste les photos en erreur ou ignorées, avec la raison.",
            "Le journal `image_splitter.log` est à côté de l'exécutable (son emplacement est indiqué dans « À propos »).",
            "« Format trop panoramique » : une photo très large donnerait plus de 20 images (la limite d'un carrousel Instagram) ; recadrez-la dans votre logiciel photo.",
            "Pour repartir de zéro, fermez l'appli et supprimez le fichier `.image_splitter_config.json` à côté de l'exécutable.",
            "Pour traiter des photos sans l'interface : `python -m rkarrousel.cli` (voir la documentation du projet).",
        ]),
    ]),
]
