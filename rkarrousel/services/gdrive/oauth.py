"""Connexion OAuth 2.0 « application de bureau » (navigateur + serveur local, PKCE) et stockage du jeton."""

import base64
import hashlib
import http.server
import json
import secrets
import threading
import time
import urllib.parse
import webbrowser
from pathlib import Path
from typing import Callable, Optional, Tuple

from rkarrousel.services.gdrive.transport import DriveError, post_form


AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPE = "https://www.googleapis.com/auth/drive.file"


# ---------------------------------------------------------------------- identifiants / jeton
def load_client_secrets(path) -> Tuple[str, str]:
    """Lit le JSON téléchargé depuis la console Google Cloud (client OAuth « application de bureau »)."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise DriveError(f"Fichier d'identifiants illisible : {exc}") from exc
    section = data.get("installed") or data.get("web") or data
    client_id, client_secret = section.get("client_id"), section.get("client_secret")
    if not client_id or not client_secret:
        raise DriveError("Ce fichier ne contient pas de client_id / client_secret.")
    return str(client_id), str(client_secret)


def load_token(path) -> Optional[dict]:
    try:
        token = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return token if isinstance(token, dict) and token.get("refresh_token") else None


def save_token(path, token: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(token, indent=2), encoding="utf-8")


def clear_token(path) -> None:
    try:
        Path(path).unlink()
    except OSError:
        pass


# ---------------------------------------------------------------------- connexion OAuth
def authorize(
    client_id: str,
    client_secret: str,
    *,
    open_browser: Callable[[str], object] = webbrowser.open,
    auth_url: str = AUTH_URL,
    token_url: str = TOKEN_URL,
    scope: str = SCOPE,
    timeout: float = 180,
    cancel: Optional[threading.Event] = None,
) -> dict:
    """Ouvre le navigateur pour autoriser l'accès et renvoie le jeton (avec refresh_token)."""
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    state = secrets.token_urlsafe(16)
    received: dict = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 (nom imposé par http.server)
            query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if "code" not in query and "error" not in query:
                self.send_response(404)
                self.end_headers()
                return
            received.update({key: values[0] for key, values in query.items()})
            ok = "code" in query
            page = (
                "<html><body style='font-family:sans-serif;text-align:center;margin-top:4em'>"
                + ("<h2>Connexion réussie</h2><p>Vous pouvez fermer cet onglet et revenir à RKarrousel.</p>"
                   if ok else "<h2>Connexion refusée</h2><p>Vous pouvez fermer cet onglet.</p>")
                + "</body></html>"
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(page)))
            self.end_headers()
            self.wfile.write(page)

        def log_message(self, *args):  # silence
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    server.timeout = 0.5
    redirect_uri = f"http://127.0.0.1:{server.server_address[1]}"
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": scope,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "access_type": "offline",
        "prompt": "consent",
    }
    try:
        open_browser(f"{auth_url}?{urllib.parse.urlencode(params)}")
        deadline = time.time() + timeout
        while not received and time.time() < deadline:
            if cancel is not None and cancel.is_set():
                raise DriveError("Connexion annulée.")
            server.handle_request()
    finally:
        server.server_close()

    if not received:
        raise DriveError("Aucune réponse du navigateur (délai dépassé).")
    if "error" in received:
        raise DriveError(f"Autorisation refusée : {received['error']}")
    if received.get("state") != state:
        raise DriveError("Réponse inattendue (état invalide).")

    token = post_form(
        token_url,
        {
            "code": received["code"],
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
            "code_verifier": verifier,
        },
    )
    if not token.get("refresh_token"):
        raise DriveError("Google n'a pas renvoyé de jeton de renouvellement. Réessayez la connexion.")
    return {
        "access_token": token["access_token"],
        "refresh_token": token["refresh_token"],
        "expires_at": time.time() + int(token.get("expires_in", 3600)) - 60,
    }
