"""Point d'entrée : `python -m rkarrousel` lance l'interface graphique (la ligne de commande est `python -m rkarrousel.cli`)."""
from rkarrousel.gui.launcher import main

if __name__ == "__main__":
    raise SystemExit(main())
