#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

from utils import (
    CONFIG_PATH,
    DEFAULT_FRAME_RATIO,
    gather_input_files,
    load_config,
    process_batch,
    save_config,
)


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        # Les consoles Windows (cp1252) ne savent pas encoder → ✅ ⚠️ : on remplace plutôt que planter.
        if stream is not None and hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
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
        "--number",
        action="store_true",
        default=None,
        help="Préfixer les fichiers générés par un numéro d'ordre (01_, 02_…) ; sinon utilise la préférence enregistrée",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Nombre de photos traitées en parallèle (par défaut 1)",
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
    number_files = args.number if args.number is not None else bool(config.get("number_files", False))
    results = process_batch(files, output_dir, config, number_files=number_files, workers=args.workers)

    successful = 0
    for result in results:
        if result.status == "ok":
            successful += 1
            for out in result.outputs:
                print(f"   ✅ {out}")
        elif result.status == "error":
            print(f"❌ Erreur pour {result.path.name} : {result.message}")

    print(f"Terminé : {successful}/{len(files)} fichier(s) traités")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
