# Fichier de réglages

`.image_splitter_config.json`, à côté de l'exécutable (ou à la racine du dépôt en lançant depuis les sources). Il est
écrit à la fermeture de l'appli ; la ligne de commande le lit aussi. Une valeur absente ou invalide retombe sur la valeur
par défaut (`config.py` valide chaque accès). Les chemins `/mnt/c/…` et `C:\…` sont convertis selon le système.

| Clé | Valeurs | Défaut | Rôle |
|---|---|---|---|
| `frame_enabled` | `true` / `false` | `true` | Cadre autour de l'image (`false` = « Sans cadre ») |
| `frame_ratio` | 0 à ~0,1 | `0.04` | Épaisseur du cadre, fraction du plus petit côté (l'appli l'affiche en %) |
| `border_color` | `"#RRGGBB"` | `#FFFFFF` | Couleur du cadre |
| `border_color_mode` | `fixed`, `dominant`, `light`, `dark`, `complement`, `contrast` | `fixed` | Cadre fixe, ou tiré de la photo : tel quel, version claire, sombre, complémentaire (teinte opposée adoucie) ou de contraste (clair sur photo sombre, foncé sur photo claire, à la teinte de la photo) |
| `color_source` | `dominant`, `edges`, `average` | `dominant` | D'où vient la couleur de référence des modes « tirée de la photo » : dominante, bords ou moyenne |
| `landscape_fill_mode` | `black`, `blur` | `black` | Fond quand la photo n'a pas le format : uni ou flouté |
| `background_color` | `"#RRGGBB"` | `#000000` | Couleur du fond uni |
| `background_color_mode` | comme `border_color_mode` | `fixed` | Fond uni fixe ou tiré de la photo |
| `blur_strength` | nombre | `1.0` | Intensité du flou du fond |
| `signature_path` | chemin | — | Image de signature (vide = aucune) |
| `signature_position` | `bottom-right`, `bottom-center`, `bottom-left` | `bottom-right` | Position de la signature |
| `signature_scale` | nombre | `1.0` | Taille de la signature |
| `output_format` | `3:4`, `4:5`, `1:1`, `9:16` | `3:4` | Format des images produites |
| `output_width` | `0`, `1080`, `1440`, `2048` | `0` | Largeur en pixels (0 = taille d'origine, jamais d'agrandissement) |
| `jpeg_quality` | 50 à 100 | `100` | Qualité d'enregistrement |
| `disabled_kinds` | liste de types | `[]` | Types d'images non produits (`part1` règle la première tranche, `part2` les suivantes) |
| `number_files` | `true` / `false` | `true` | Préfixer les fichiers `01_`, `02_`… |
| `crop_offsets` | `{chemin: 0..1}` | `{}` | Zone conservée des recadrages, par photo |
| `kind_placement` | `{part1_with_sig, part2_with_sig: before / inline / end}` | `before` pour la photo entière droite, `inline` pour la pivotée | Place des deux « photos entières » d'un paysage : avant le découpage, après (avec leur photo), ou à la fin du carrousel dans l'ordre des photos. « Aucune » = le type est dans `disabled_kinds` |
| `photo_overrides` | `{chemin: {border_color_mode, border_color, border_tweak}}` | `{}` | Couleur du cadre propre à une photo : remplace le réglage général pour elle seule. `border_tweak` = `[teinte °, saturation, clarté]` (limites ± 30, 0,3 et 0,2), retouche fine d'une couleur tirée de la photo ; seules ces trois clés sont lues |
| `presets` | `{nom: {clé: valeur}}` | `{}` | Préréglages de l'utilisateur (voir `presets.PRESET_KEYS` pour les clés mémorisées) |
| `last_source_dir`, `last_dest_dir` | chemin | — | Derniers dossiers utilisés |
| `language` | `fr`, `en` | `fr` | Langue de l'interface |
| `theme` | `auto`, `light`, `dark` | `auto` | Thème |
| `update_check` | `true` / `false` | `true` | Rechercher les mises à jour au démarrage |
| `skipped_version` | `"X.Y.Z"` | — | Version ignorée dans la fenêtre de mise à jour |
| `gdrive_enabled` | `true` / `false` | `false` | Envoyer sur Google Drive après le traitement |
| `gdrive_folder` | chemin Drive | — | Dossier de destination sur le Drive (`Instagram/2026`) |
| `gdrive_client_id`, `gdrive_client_secret` | texte | — | Identifiants OAuth « application de bureau » |

Le jeton de connexion Google n'est **pas** dans ce fichier : il est dans `gdrive_token.json`, à côté de l'exécutable.

L'installateur dépose des valeurs par défaut au premier lancement : voir `installer/default_config.json`.
