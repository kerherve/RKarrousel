"""Guide d'utilisation (français). Source unique : l'écran « Guide » de l'appli et `docs/guide-utilisateur.md`
(généré par `python tools/build_docs.py`) en sont tous deux tirés.

Chaque rubrique est un triplet (identifiant, titre, blocs). Blocs : ("p", texte), ("h", sous-titre),
("steps", [étapes]), ("bullets", [puces]), ("note", texte).
"""

INTRO = "Tout ce qu'il faut savoir pour préparer vos photos pour Instagram avec RKarrousel."

GUIDE = [
    ("start", "Premiers pas", [
        ("p", "RKarrousel prépare vos photos pour Instagram : cadre, fond, découpe des panoramas, recadrage, ordre et "
              "numérotation des images. L'appli se parcourt en quatre étapes, de gauche à droite :"),
        ("steps", [
            "« Photos » : ajoutez vos photos (ou glissez-déposez-les), choisissez le dossier de destination et le format des images.",
            "« Ordre » : la grille montre chaque image produite ; réordonnez-les, excluez celles dont vous ne voulez pas, recadrez.",
            "« Ajustements » : image par image, réglez cadre, couleurs, fond et signature, et jugez le rendu en carrousel.",
            "« Export » : qualité et taille des fichiers, numérotation, Google Drive, puis « Lancer le traitement ».",
        ]),
        ("note", "Les boutons « Précédent » et « Suivant » en bas font avancer ; vous pouvez aussi cliquer une étape déjà atteignable en haut. "
                 "Vos réglages sont enregistrés automatiquement à la fermeture, et la touche F1 ouvre ce guide à tout moment."),
    ]),
    ("photos", "Étape 1 : Photos", [
        ("bullets", [
            "Formats acceptés : JPEG, PNG, TIFF et BMP. Tous les formats de photo vont : portrait, paysage, carré, panorama…",
            "« Ajouter dossier » prend toutes les images du dossier (sans ses sous-dossiers).",
            "Le glisser-déposer de fichiers et de dossiers dans la liste fonctionne aussi.",
            "Cliquez une entrée de la liste : l'aperçu à droite montre la photo, ou la première photo d'un dossier. « Effacer la sélection » vide la liste.",
            "Format des images : 3:4 (grille Instagram, par défaut), 4:5 (feed), 1:1 (carré) ou 9:16 (stories, reels). Choisissez-le d'abord : le découpage des panoramas, le recadrage et les fonds s'adaptent.",
            "Le bouton « Suivant » s'active dès qu'il y a au moins une photo et un dossier de destination.",
        ]),
    ]),
    ("outputs", "Les images produites", [
        ("p", "Chaque photo donne une ou plusieurs images, au format de sortie choisi :"),
        ("bullets", [
            "Photo déjà au format de sortie : une image encadrée (`_framed`). Elle est rognée de moins de 1 % pour que, cadre compris, le format soit exact.",
            "Portrait 2:3, autre portrait ou carré : la photo entière sur un fond au format (`_with_sig`, ou `_framed` sans signature) et un recadrage réglable (`_crop34`).",
            "Paysage 3:2 : les deux moitiés encadrées d'un panorama (`_part1`, `_part2`), la photo entière (`_part1_with_sig`) et la même pivotée (`_part2_with_sig`).",
            "Autre paysage ou panorama : le panorama découpé en tranches contiguës (`_part1` à `_partN`, 20 au maximum), la photo entière droite et pivotée, et un recadrage.",
        ]),
        ("p", "Avec un fond uni (noir par défaut) comme avec un fond flouté, le cadre entoure toute l'image, au bord ; la photo entière est posée à l'intérieur."),
        ("note", "Les tranches d'un panorama se recomposent sans double bordure : le cadre n'entoure que le haut, le bas et les deux extrémités."),
        ("p", "Vous n'avez pas besoin de toutes les images : décochez un type dans la colonne « Images produites » de l'étape Ordre, "
              "ou excluez une image précise avec la croix de sa vignette."),
    ]),
    ("order", "Étape 2 : Ordre", [
        ("p", "La grille affiche le rendu final de chaque image, comme un profil Instagram. L'ordre se lit de gauche à droite, ligne après ligne."),
        ("bullets", [
            "Glissez une image pour la déplacer : les morceaux d'une même photo peuvent être séparés.",
            "Agrandissez la fenêtre pour voir plus d'images à la fois : la grille ajoute des colonnes (trois au minimum).",
            "Le numéro bleu est celui qui préfixera le fichier (voir « Numérotation des fichiers »).",
            "Instagram limite un carrousel à 20 images : au-delà, un avertissement orange apparaît en haut et les numéros des images 21 et suivantes passent en rouge. Excluez-en ou répartissez-les en plusieurs publications.",
            "La croix en haut à droite d'une image l'exclut (elle n'est ni générée ni numérotée) ; ↺ la réintègre.",
            "Cliquez une image pour la sélectionner : « Ajuster cette image » ouvre l'étape suivante sur elle, « Recadrer… » règle un recadrage, « Exclure » la retire. Un double-clic ouvre le recadrage, ou les ajustements pour les autres images. Le clic droit ouvre un menu.",
            "Colonne « Images produites » : cochez les types d'images voulus pour chaque photo. Pour un paysage, les deux photos entières (droite et pivotée) se placent avant ou après le découpage, à la fin du carrousel (dans l'ordre des photos), ou se suppriment. Par défaut, la photo entière vient avant les tranches.",
            "« Rafraîchir l'aperçu » prend en compte les réglages modifiés ailleurs ; « Ordre naturel » remet l'ordre d'origine.",
        ]),
    ]),
    ("adjust", "Étape 3 : Ajustements", [
        ("p", "L'image sélectionnée s'affiche en pleine résolution, avec ses voisines de part et d'autre, comme quand on fait défiler un post Instagram."),
        ("bullets", [
            "Molette : zoom ; glisser : déplacer l'image zoomée ; « Ajuster » et « 100 % » pour revenir.",
            "Flèches rondes sur les bords (ou touches ← →) : image précédente ou suivante de la grille. Les images exclues sont sautées ; le rang (3 / 12) est en haut.",
            "Glisser l'image à la souris la fait défiler : lâchée assez loin (ou d'un coup de pouce rapide), l'image voisine arrive en glissant ; sinon elle revient en place.",
            "Feuilleter est rapide : les voisines et l'aperçu de la nouvelle image s'affichent tout de suite, puis la pleine résolution se précise dès que vous vous arrêtez.",
            "La case « Carrousel » affiche ou masque les images voisines ; « Recadrer… » ouvre le réglage du cadrage quand l'image affichée est un recadrage.",
            "Clic droit + glisser : règle qui mesure en pixels, par exemple l'épaisseur du cadre, aussi mesurée automatiquement et affichée en haut.",
            "Panneau de droite : préréglages, cadre, fond, signature. L'image se recalcule après chaque changement ; ce que l'image affichée n'utilise pas est grisé (une tranche de panorama ou un recadrage n'a ni fond ni signature). Ces réglages valent pour toutes les photos.",
            "« Cadre de cette photo » : une couleur de cadre propre à la photo affichée (fixe, ou tirée de la photo), qui remplace le réglage général pour elle seule. « Comme les réglages généraux » l'annule. « Couleur obtenue » montre la couleur réellement calculée ; trois curseurs « Affiner » (teinte, saturation, clarté) la retouchent très légèrement, à l'œil. « Réinitialiser » les remet à zéro ; un double-clic sur une ligne remet ce seul curseur au milieu.",
        ]),
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
        ("note", "Pour une seule photo, l'étape Ajustements propose une couleur de cadre qui lui est propre, avec une retouche fine."),
    ]),
    ("presets", "Préréglages", [
        ("p", "Un préréglage mémorise le cadre, le fond, la signature, le format et la taille des images. Ils sont en haut du panneau de l'étape Ajustements :"),
        ("bullets", [
            "Choisissez un préréglage dans la liste : tous les réglages concernés changent d'un coup.",
            "Quatre sont fournis : Classique, Fond noir, Couleurs de la photo, Sans cadre. Ils ne changent que les réglages qu'ils citent.",
            "« Enregistrer sous… » garde vos réglages actuels sous le nom de votre choix (un nom déjà pris demande confirmation).",
            "« Supprimer » retire un de vos préréglages ; les préréglages fournis ne se suppriment pas.",
        ]),
        ("note", "Modifier un réglage ensuite ne change pas le préréglage : enregistrez-le de nouveau sous le même nom pour le mettre à jour."),
    ]),
    ("crop", "Recadrer une image", [
        ("p", "Sur une image « recadrage », « Recadrer… » (étape Ordre ou Ajustements) ouvre l'éditeur :"),
        ("bullets", [
            "Faites glisser le cadre orange sur la photo pour choisir la zone conservée ; l'aperçu à droite montre le résultat final.",
            "Molette ou flèches du clavier (Maj pour aller plus vite) ; boutons Haut / Centre / Bas.",
            "Le cadre se déplace verticalement pour une photo plus étroite que le format, horizontalement pour une photo plus large.",
            "« Valider » enregistre le choix pour cette photo : il est conservé d'une session à l'autre.",
        ]),
    ]),
    ("export", "Étape 4 : Export", [
        ("p", "Le récapitulatif annonce ce qui va être produit (nombre d'images, exclues, destination) et avertit au-delà de 20 images."),
        ("bullets", [
            "Largeur : taille d'origine, ou 1080 px (la taille idéale pour Instagram), 1440 ou 2048 px. Les fichiers sont beaucoup plus légers, et jamais agrandis.",
            "Qualité JPEG : 100 par défaut ; vers 90-95 les fichiers pèsent environ moitié moins, sans différence visible.",
            "« Numéroter les fichiers » préfixe chaque image de son numéro (voir « Numérotation des fichiers »).",
            "Google Drive : envoi automatique après le traitement (voir « Envoyer sur Google Drive »).",
            "« Lancer le traitement » (en bas) produit les fichiers ; « Annuler » l'arrête. Un récapitulatif s'affiche à la fin.",
        ]),
        ("note", "Les fichiers de recadrage portent le format dans leur nom : `_crop34` en 3:4, `_crop45` en 4:5, etc."),
    ]),
    ("numbering", "Numérotation des fichiers", [
        ("p", "Avec « Numéroter les fichiers » (étape Export), chaque image est préfixée par son numéro : 01_, 02_, 03_… "
              "(trois chiffres au-delà de 99). L'ordre est celui de l'étape Ordre."),
        ("p", "Vous copiez ensuite les fichiers sur votre drive ou votre téléphone sans rien renommer : l'ordre alphabétique est celui du carrousel."),
        ("note", "Relancer un traitement avec un autre ordre dans le même dossier ne supprime pas les anciens fichiers : videz le dossier avant si besoin."),
    ]),
    ("drive", "Envoyer sur Google Drive", [
        ("p", "Étape Export → « Google Drive » : cochez « Envoyer les images sur Google Drive après le traitement ». Les images partent dans l'ordre numéroté vers le dossier indiqué "
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
    ("preferences", "Préférences et mises à jour", [
        ("bullets", [
            "Le bouton « Préférences » (en haut à droite) règle la langue (français ou anglais), le thème (clair, sombre, ou « Auto » qui suit Windows) et les mises à jour.",
            "À chaque démarrage, l'appli cherche une version plus récente sur GitHub (désactivable dans les préférences) et affiche les nouveautés dans votre langue.",
            "« Mettre à jour maintenant » télécharge la nouvelle version, vérifie qu'elle est intacte et qu'elle démarre, remplace l'ancienne sur place et relance l'appli ; « Plus tard » ou « Ignorer cette version » la repoussent.",
            "Votre raccourci et vos réglages ne changent pas. « Rechercher maintenant » force la vérification.",
        ]),
    ]),
    ("shortcuts", "Raccourcis", [
        ("bullets", [
            "F1 : ouvrir ce guide.",
            "Grille d'ordre : Suppr exclut l'image sélectionnée ; Entrée l'ouvre dans les ajustements.",
            "Ajustements : ← → image précédente / suivante.",
            "Éditeur de recadrage : ↑ ↓ ← → déplacent le cadre (Maj : plus vite) ; Entrée valide ; Échap annule.",
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
