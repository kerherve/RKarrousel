"""Envoi des images vers Google Drive, sans dépendance externe (bibliothèque standard uniquement).

- `oauth` : connexion OAuth 2.0 « application de bureau » (navigateur + serveur local, PKCE) et stockage du jeton.
  Portée `drive.file` : l'appli ne voit que les fichiers qu'elle crée elle-même, jamais le reste du Drive.
- `client` : dossiers et envoi « reprenable » des fichiers ; un fichier du même nom dans le même dossier est mis à
  jour plutôt que dupliqué.
- `transport` : requêtes HTTP avec nouvel essai sur les erreurs temporaires.
"""
from rkarrousel.services.gdrive.client import FOLDER_MIME, DriveClient
from rkarrousel.services.gdrive.oauth import authorize, clear_token, load_client_secrets, load_token, save_token
from rkarrousel.services.gdrive.transport import DriveError

__all__ = [
    "FOLDER_MIME", "DriveClient", "DriveError", "authorize", "clear_token", "load_client_secrets", "load_token",
    "save_token",
]
