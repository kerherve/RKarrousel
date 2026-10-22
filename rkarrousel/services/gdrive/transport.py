"""Requêtes HTTP vers Google (avec nouvel essai sur les erreurs temporaires) et erreur lisible `DriveError`."""

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional


RETRY_STATUS = {429, 500, 502, 503, 504}
RETRY_DELAY = 1.0  # secondes, doublé à chaque essai
HTTP_TIMEOUT = 120


class DriveError(Exception):
    """Erreur lisible (réseau, autorisation, quota…) remontée à l'utilisateur."""


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


def http_request(method: str, url: str, headers: Optional[dict] = None, data: Optional[bytes] = None, retries: int = 3):
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


def post_form(url: str, form: dict) -> dict:
    _, body = http_request(
        "POST", url, {"Content-Type": "application/x-www-form-urlencoded"}, urllib.parse.urlencode(form).encode()
    )
    return json.loads(body.decode("utf-8"))
