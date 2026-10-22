"""Client Google Drive : dossiers et envoi des fichiers (reprenable, mise à jour plutôt que doublon)."""

import json
import logging
import threading
import time
import urllib.parse
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence

from rkarrousel.services.gdrive.oauth import TOKEN_URL, load_token, save_token
from rkarrousel.services.gdrive.transport import DriveError, http_request, post_form

logger = logging.getLogger("imagesplitter")


API_URL = "https://www.googleapis.com/drive/v3"
UPLOAD_URL = "https://www.googleapis.com/upload/drive/v3"
FOLDER_MIME = "application/vnd.google-apps.folder"
MIME_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
    ".bmp": "image/bmp",
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
        fresh = post_form(
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
        _, response = http_request(method, url, headers, data)
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
        headers, _ = http_request(
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
        _, body = http_request("PUT", session, {"Content-Type": mime}, content)
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
