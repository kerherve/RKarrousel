#!/usr/bin/env python3
import argparse
from pathlib import Path

from utils import (
    CONFIG_PATH,
    DEFAULT_FRAME_RATIO,
    gather_input_files,
    load_config,
    process_image,
    save_config,
)


def main() -> int:
    config_path = CONFIG_PATH
    config = load_config(config_path)

    parser = argparse.ArgumentParser(
        description=(
            "Traitement de photos LR pour Instagram : encadrement portrait 3/4 "
            "et découpe paysage 2/3 → 2x portrait 3/4"
        )
    )
    parser.add_argument("paths", nargs="*", help="Fichiers ou dossiers source à traiter")
    parser.add_argument("-d", "--dest", help="Dossier de destination")
    parser.add_argument(
        "--frame-ratio",
        type=float,
        help="Épaisseur du cadre en fraction de la plus petite dimension (par défaut 0.04)",
    )
    parser.add_argument(
        "--config-file",
        default=str(CONFIG_PATH),
        help="Chemin du fichier de configuration (par défaut ~/.image_splitter_config.json)",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Utiliser automatiquement les dernières préférences enregistrées si aucun chemin n'est fourni",
    )
    parser.add_argument(
        "--save-preferences",
        action="store_true",
        help="Enregistrer les chemins source/destination et le ratio de cadre dans la configuration",
    )

    args = parser.parse_args()
    config_path = Path(args.config_file).expanduser()
    if config_path != CONFIG_PATH:
        config = load_config(config_path)

    inputs = args.paths or []
    if not inputs and config.get("last_source_dir"):
        if args.yes:
            inputs = [config["last_source_dir"]]
        else:
            print(f"Utilisation du dernier dossier source : {config['last_source_dir']}")
            inputs = [config["last_source_dir"]]

    if not inputs:
        parser.print_help()
        return 1

    output_dir = Path(args.dest or config.get("last_dest_dir", "output")).expanduser()
    frame_ratio = args.frame_ratio if args.frame_ratio is not None else config.get("frame_ratio", DEFAULT_FRAME_RATIO)

    config["frame_ratio"] = frame_ratio
    if args.save_preferences:
        config["last_source_dir"] = str(Path(inputs[0]).expanduser())
        config["last_dest_dir"] = str(output_dir)
        save_config(config_path, config)

    output_dir.mkdir(parents=True, exist_ok=True)

    files = gather_input_files(inputs)
    if not files:
        print("Aucun fichier image trouvé à traiter.")
        return 1

    print(f"{len(files)} fichier(s) trouvé(s). Destination : {output_dir}")
    successful = 0
    for path in files:
        try:
            output_files = process_image(path, output_dir, config)
            if output_files:
                successful += 1
                for out in output_files:
                    print(f"   ✅ {out}")
        except Exception as exc:
            print(f"❌ Erreur pour {path.name} : {exc}")

    print(f"Terminé : {successful}/{len(files)} fichier(s) traités")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
