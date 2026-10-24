# Changelog / Journal des modifications

Each `## vX.Y.Z` section becomes the GitHub release text and is shown in the app's update window, in the app's language
(see `tools/release_notes.py`). Write both languages before tagging: `### English` first, then `### Français`.
Chaque section `## vX.Y.Z` devient le texte de la release ; l'appli n'affiche que la langue choisie.

## v0.13.0

### English

- The app is now a four-step flow: Photos, Order, Adjust, Export. Use "Previous" and "Next" at the bottom (or click a step at the top); on the last step "Next" becomes "Start processing". The Files and Settings tabs are gone.
- Photos: add your photos, choose the destination folder and the image format.
- Order: the grid, with the "Images produced" column beside it. Select an image and click "Adjust this image" to move on to it.
- Adjust: the full-resolution viewer with the carousel, presets and all frame, colour, background and signature settings.
- Export: a summary of what will be produced, file quality and size, numbering and Google Drive.
- Language, theme and updates moved to a "Preferences" button at the top right.
- The order grid is now centred in the window, and it keeps the selected image when you go back and forth between steps.

### Français

- L'appli est maintenant un flux en quatre étapes : Photos, Ordre, Ajustements, Export. On avance avec « Précédent » et « Suivant » en bas (ou en cliquant une étape en haut) ; à la dernière étape, « Suivant » devient « Lancer le traitement ». Les onglets Fichiers et Réglages disparaissent.
- Photos : ajoutez vos photos, choisissez le dossier de destination et le format des images.
- Ordre : la grille, avec la colonne « Images produites » à côté. Sélectionnez une image et cliquez « Ajuster cette image » pour passer à l'étape suivante sur elle.
- Ajustements : la visionneuse en pleine résolution avec le carrousel, les préréglages et tous les réglages de cadre, de couleurs, de fond et de signature.
- Export : un récapitulatif de ce qui sera produit, la qualité et la taille des fichiers, la numérotation et Google Drive.
- La langue, le thème et les mises à jour passent dans un bouton « Préférences » en haut à droite.
- La grille d'ordre est maintenant centrée dans la fenêtre, et elle garde l'image sélectionnée quand on fait des allers-retours entre les étapes.

## v0.12.0

### English

- "View large" now has a settings panel: frame, colours, background and signature are adjusted live, without going back to the Settings tab. Settings the displayed image does not use are greyed out.
- Per-photo frame colour, with the resulting colour shown and a light fine-tune of hue, saturation and lightness (double-click a slider to reset it).
- New colours taken from the photo: complementary and contrasting. You can choose where the reference colour comes from: dominant colour, edges or average.
- Carousel preview: neighbouring images appear on either side, like an Instagram post. Swipe with the mouse, or use the arrows or the keys. Browsing is fast, and the Crop button is available on crop images.
- With a solid background, the frame now surrounds the whole image, as with a blurred background. This changes the look of images that use a solid (black or white) background.
- For landscapes, the whole photo now comes before the split by default. The two whole-photo images (upright and rotated) can be placed before or after the split, at the end of the carousel, or removed.
- The order grid adds columns when you enlarge the window, and warns beyond Instagram's 20-image limit (numbers turn red). Panoramas can now be cut into up to 20 slices.

### Français

- « Voir en grand » a maintenant un panneau de réglages : cadre, couleurs, fond et signature se règlent en direct, sans retourner dans l'onglet Réglages. Les réglages que l'image affichée n'utilise pas sont grisés.
- Couleur de cadre propre à chaque photo, avec la couleur obtenue affichée et une retouche légère de la teinte, de la saturation et de la clarté (double-clic sur un curseur pour le remettre à zéro).
- Nouvelles couleurs tirées de la photo : complémentaire et de contraste. On choisit d'où vient la couleur de référence : dominante, bords ou moyenne.
- Aperçu carrousel : les images voisines apparaissent de part et d'autre, comme un post Instagram. On les fait défiler à la souris, aux flèches ou au clavier. Le feuilletage est rapide, et le bouton Recadrer est disponible sur les images recadrées.
- Avec un fond uni, le cadre entoure maintenant toute l'image, comme avec un fond flouté. Cela change l'aspect des images à fond uni (noir ou blanc).
- Pour un paysage, la photo entière vient maintenant avant le découpage par défaut. Les deux photos entières (droite et pivotée) se placent avant ou après le découpage, à la fin du carrousel, ou se suppriment.
- La grille d'ordre ajoute des colonnes quand on agrandit la fenêtre, et avertit au-delà des 20 images d'Instagram (numéros en rouge). Un panorama peut être découpé en 20 tranches au maximum.

## v0.11.3

### English

- The update window shows the release notes in the app's language (English or French) instead of both.
- Release notes are written in English and French.

### Français

- La fenêtre de mise à jour affiche les nouveautés dans la langue de l'appli (français ou anglais), et non plus les deux.
- Les notes de version sont écrites en anglais et en français.

## v0.11.2

### English

- The update window now shows what's new as readable plain text, in the app's language.
- Release notes are now written by hand, in English and French.

If you are updating from an older version, the 0.11 highlights also apply:

- Presets: one click sets frame, background, signature, format and size. Four are provided, and "Save as..." keeps your own.
- Colours taken from the photo: the frame and the solid background can use each photo's dominant colour, light or dark.
- Built-in user guide: "Guide" button (or F1), in English and French.
- "Number files" now lives in Settings -> "Generated files".

### Français

- Les nouveautés s'affichent lisiblement dans la fenêtre de mise à jour, dans la langue de l'appli.
- Les notes de chaque version sont désormais écrites à la main, en anglais et en français.

Pour passer d'une version plus ancienne, voir aussi les nouveautés de la 0.11 :

- Préréglages : un clic règle cadre, fond, signature, format et taille. Quatre sont fournis, et « Enregistrer sous… » garde les vôtres.
- Couleurs tirées de la photo : le cadre et le fond uni peuvent prendre la couleur dominante de chaque photo, en version claire ou sombre.
- Guide d'utilisation intégré : bouton « Guide » (ou touche F1), en français et en anglais.
- L'option « Numéroter les fichiers » est maintenant dans Réglages → « Fichiers générés ».

## v0.11.1

### English

- "Number files" moved to Settings -> "Generated files".
- Includes everything from 0.11: presets, colours taken from the photo, built-in guide, reorganised code (same look, same images).

### Français

- « Numéroter les fichiers » passe dans Réglages → « Fichiers générés ».
- Inclut tout ce que la 0.11 apporte : préréglages, couleurs tirées de la photo, guide intégré, code réorganisé (même aspect, mêmes images).

## v0.11.0

### English

- Named presets, frame and background colours taken from the photo, built-in user guide ("Guide" button, F1).
- Code reorganised and project documentation added; the look and the produced images are unchanged.

### Français

- Préréglages nommés, couleurs de cadre et de fond tirées de la photo, guide d'utilisation intégré (bouton « Guide », touche F1).
- Code réorganisé en profondeur et documentation du projet ; l'aspect et les images produites restent identiques.

## v0.10.2

### English

- The app checks for updates at every start.

### Français

- Recherche de mise à jour à chaque démarrage de l'appli.

## v0.10.1

### English

- Code and update-settings cleanup; background settings are greyed out when they do not apply.

### Français

- Nettoyage du code et des réglages de mise à jour ; les réglages de fond sont grisés quand ils ne servent pas.

## v0.10.0

### English

- Output formats 3:4, 4:5, 1:1 and 9:16; width 1080, 1440 or 2048 px.
- A photo already in the output format gets exact dimensions, frame included.

### Français

- Formats de sortie 3:4, 4:5, 1:1 et 9:16, largeur 1080, 1440 ou 2048 px.
- Une photo déjà au format de sortie donne des dimensions exactes, cadre compris.
