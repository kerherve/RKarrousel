#!/usr/bin/env python3
"""Envoi des images vers Google Drive, sans dépendance externe (bibliothèque standard uniquement).

- Connexion OAuth 2.0 « application de bureau » : le navigateur s'ouvre, l'utilisateur autorise, Google
  redirige vers un petit serveur local (127.0.0.1) qui récupère le code (PKCE).
- Portée `drive.file` : l'appli ne voit que les fichiers qu'elle crée elle-même, jamais le reste du Drive.
- Envoi « reprenable » (resumable) des fichiers ; un fichier du même nom dans le même dossier est mis à jour
  plutôt que dupliqué.
"""
import base64
import hashlib
import http.server
import json
import logging
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
API_URL = "https://www.googleapis.com/drive/v3"
UPLOAD_URL = "https://www.googleapis.com/upload/drive/v3"
SCOPE = "https://www.googleapis.com/auth/drive.file"
FOLDER_MIME = "application/vnd.google-apps.folder"
RETRY_STATUS = {429, 500, 502, 503, 504}
RETRY_DELAY = 1.0  # secondes, doublé à chaque essai
HTTP_TIMEOUT = 120

MIME_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
    ".bmp": "image/bmp",
}

logger = logging.getLogger("imagesplitter")


class DriveError(Exception):
    """Erreur lisible (réseau, autorisation, quota…) remontée à l'utilisateur."""


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


# ---------------------------------------------------------------------- HTTP
def _error_message(body: bytes) -> str:
    try:
        data = json.loads(body.decode("utf-8", "replace"))
    except ValueError:
        return body.decode("utf-8", "replace")[:200]
    error = data.get("error")
    if isinstance(error, dict):
        return error.get("message") or str(error)
    description = data.get("error_description")
    return f"{error}: {description}" if description else str(error or data)[:200]


def _http(method: str, url: str, headers: Optional[dict] = None, data: Optional[bytes] = None, retries: int = 3):
    """Requête HTTP avec nouvel essai sur les erreurs temporaires. Renvoie (en-têtes, corps)."""
    last: Optional[Exception] = None
    for attempt in range(retries):
        request = urllib.request.Request(url, data=data, method=method, headers=headers or {})
        try:
            with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response:
                return response.headers, response.read()
        except urllib.error.HTTPError as exc:
            body = exc.read()
            if exc.code in RETRY_STATUS and attempt < retries - 1:
                time.sleep(RETRY_DELAY * (2 ** attempt))
                last = exc
                continue
            raise DriveError(f"Google ({exc.code}) : {_error_message(body)}") from exc
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            last = exc
            if attempt < retries - 1:
                time.sleep(RETRY_DELAY * (2 ** attempt))
                continue
            raise DriveError(f"Connexion impossible : {getattr(exc, 'reason', exc)}") from exc
    raise DriveError(f"Échec de la requête : {last}")


def _post_form(url: str, form: dict) -> dict:
    _, body = _http(
        "POST", url, {"Content-Type": "application/x-www-form-urlencoded"}, urllib.parse.urlencode(form).encode()
    )
    return json.loads(body.decode("utf-8"))


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

    token = _post_form(
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


# ---------------------------------------------------------------------- client Drive
def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


class DriveClient:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        token_path,
        *,
        api_url: str = API_URL,
        upload_url: str = UPLOAD_URL,
        token_url: str = TOKEN_URL,
    ):
        self.client_id, self.client_secret = client_id, client_secret
        self.token_path = Path(token_path)
        self.api_url, self.upload_url, self.token_url = api_url, upload_url, token_url
        self._folders: Dict[str, str] = {}

    def is_connected(self) -> bool:
        return load_token(self.token_path) is not None

    def _access_token(self) -> str:
        token = load_token(self.token_path)
        if token is None:
            raise DriveError("Non connecté à Google Drive.")
        if token.get("access_token") and token.get("expires_at", 0) > time.time():
            return token["access_token"]
        fresh = _post_form(
            self.token_url,
            {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": token["refresh_token"],
                "grant_type": "refresh_token",
            },
        )
        token["access_token"] = fresh["access_token"]
        token["expires_at"] = time.time() + int(fresh.get("expires_in", 3600)) - 60
        save_token(self.token_path, token)
        return token["access_token"]

    def _auth(self, extra: Optional[dict] = None) -> dict:
        headers = {"Authorization": f"Bearer {self._access_token()}"}
        headers.update(extra or {})
        return headers

    def _json(self, method: str, url: str, params: Optional[dict] = None, body: Optional[dict] = None) -> dict:
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        data = json.dumps(body).encode("utf-8") if body is not None else None
        headers = self._auth({"Content-Type": "application/json; charset=UTF-8"} if body is not None else None)
        _, response = _http(method, url, headers, data)
        return json.loads(response.decode("utf-8") or "{}")

    def _find(self, name: str, parent_id: str, folder: bool = False) -> Optional[str]:
        query = f"name = '{_escape(name)}' and '{parent_id}' in parents and trashed = false"
        if folder:
            query += f" and mimeType = '{FOLDER_MIME}'"
        found = self._json("GET", f"{self.api_url}/files", {"q": query, "fields": "files(id,name)", "pageSize": 1})
        files = found.get("files") or []
        return files[0]["id"] if files else None

    def ensure_folder(self, path: str) -> str:
        """Identifiant du dossier `a/b/c` (créé au besoin, depuis « Mon Drive »)."""
        parent = "root"
        built = ""
        for name in [part.strip() for part in path.replace("\\", "/").split("/") if part.strip()]:
            built = f"{built}/{name}"
            if built not in self._folders:
                folder_id = self._find(name, parent, folder=True)
                if folder_id is None:
                    folder_id = self._json(
                        "POST", f"{self.api_url}/files", body={"name": name, "mimeType": FOLDER_MIME, "parents": [parent]}
                    )["id"]
                self._folders[built] = folder_id
            parent = self._folders[built]
        return parent

    def upload(self, file: Path, folder_id: str) -> dict:
        """Envoie un fichier (le met à jour s'il existe déjà dans ce dossier). Renvoie {id, name, updated}."""
        file = Path(file)
        content = file.read_bytes()
        mime = MIME_TYPES.get(file.suffix.lower(), "application/octet-stream")
        existing = self._find(file.name, folder_id)
        if existing:
            method, url, meta = "PATCH", f"{self.upload_url}/files/{existing}", {"name": file.name}
        else:
            method, url, meta = "POST", f"{self.upload_url}/files", {"name": file.name, "parents": [folder_id]}
        headers, _ = _http(
            method,
            f"{url}?uploadType=resumable",
            self._auth(
                {
                    "Content-Type": "application/json; charset=UTF-8",
                    "X-Upload-Content-Type": mime,
                    "X-Upload-Content-Length": str(len(content)),
                }
            ),
            json.dumps(meta).encode("utf-8"),
        )
        session = headers.get("Location")
        if not session:
            raise DriveError("Google n'a pas ouvert de session d'envoi.")
        _, body = _http("PUT", session, {"Content-Type": mime}, content)
        result = json.loads(body.decode("utf-8") or "{}")
        return {"id": result.get("id"), "name": file.name, "updated": bool(existing)}

    def upload_files(
        self,
        files: Sequence[Path],
        folder_path: str,
        progress: Optional[Callable[[int, int, Path], None]] = None,
        cancel: Optional[threading.Event] = None,
    ) -> List[dict]:
        """Envoie tous les fichiers dans `folder_path`. Chaque résultat : {path, status, message}."""
        results: List[dict] = []
        total = len(files)
        try:
            folder_id = self.ensure_folder(folder_path or "RKarrousel")
        except DriveError as exc:
            return [{"path": Path(f), "status": "error", "message": str(exc)} for f in files]
        for index, file in enumerate(files, start=1):
            file = Path(file)
            if cancel is not None and cancel.is_set():
                results.append({"path": file, "status": "cancelled", "message": ""})
                continue
            try:
                info = self.upload(file, folder_id)
                results.append({"path": file, "status": "ok", "message": "updated" if info["updated"] else "created"})
            except (DriveError, OSError) as exc:
                logger.exception("Envoi Drive échoué : %s", file)
                results.append({"path": file, "status": "error", "message": str(exc)})
            if progress is not None:
                progress(index, total, file)
        return results
