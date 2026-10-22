#!/usr/bin/env python3
"""Mise à jour automatique depuis les releases GitHub (bibliothèque standard uniquement).

Principe : on récupère la dernière release, on télécharge `RKarrousel-vX.Y.Z.exe`, on vérifie qu'il est intact
(taille, empreinte SHA-256 si GitHub la fournit) et qu'il démarre (--smoke-test), puis on remplace l'exécutable
en cours **en place** : sous Windows un exécutable en cours d'exécution peut être renommé mais pas écrasé, donc
l'ancien devient `RKarrousel.exe.old` et le nouveau prend son nom. Le raccourci et la configuration (fichier
voisin) ne bougent pas. L'ancien exécutable est supprimé au démarrage suivant.
"""
import hashlib
import json
import logging
import os
import re
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Tuple

REPO = "kerherve/RKarrousel"
API_URL = "https://api.github.com"
ASSET_RE = re.compile(r"^RKarrousel-v(\d+\.\d+\.\d+)\.exe$")  # l'exécutable portable (pas l'installateur)
USER_AGENT = "RKarrousel-updater"
CHECK_INTERVAL = 6 * 3600  # secondes entre deux vérifications automatiques
CHUNK = 256 * 1024

logger = logging.getLogger("imagesplitter")


class UpdateError(Exception):
    """Erreur lisible ; `code` distingue les cas à traiter à part (not_found, rate_limit, permission…)."""

    def __init__(self, message: str, code: str = "error"):
        super().__init__(message)
        self.code = code


# ---------------------------------------------------------------------- versions
def parse_version(text: str) -> Tuple[int, ...]:
    match = re.match(r"^\s*v?(\d+(?:\.\d+)*)", text or "")
    return tuple(int(part) for part in match.group(1).split(".")) if match else ()


def is_newer(candidate: str, current: str) -> bool:
    new, old = parse_version(candidate), parse_version(current)
    return bool(new) and new > old


def check_due(last_check: float, now: Optional[float] = None, interval: float = CHECK_INTERVAL) -> bool:
    return (time.time() if now is None else now) - float(last_check or 0) >= interval


@dataclass
class ReleaseInfo:
    version: str
    tag: str
    notes: str
    asset_name: str
    asset_url: str
    size: int
    digest: Optional[str]
    page_url: str


# ---------------------------------------------------------------------- GitHub
def fetch_latest_release(repo: str = REPO, api: str = API_URL, timeout: float = 20) -> ReleaseInfo:
    """Dernière release publiée (hors brouillons et pré-versions) avec son exécutable portable."""
    url = f"{api}/repos/{repo}/releases/latest"
    headers = {"Accept": "application/vnd.github+json", "User-Agent": USER_AGENT, "X-GitHub-Api-Version": "2022-11-28"}
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise UpdateError("Aucune release trouvée.", "not_found") from exc
        if exc.code in (403, 429):
            raise UpdateError("Limite de requêtes GitHub atteinte, réessayez plus tard.", "rate_limit") from exc
        raise UpdateError(f"GitHub a répondu {exc.code}.", "http") from exc
    except (urllib.error.URLError, TimeoutError, ConnectionError, ValueError) as exc:
        raise UpdateError(f"Connexion impossible : {getattr(exc, 'reason', exc)}", "network") from exc

    tag = str(data.get("tag_name", ""))
    version = ".".join(str(n) for n in parse_version(tag))
    if not version:
        raise UpdateError("Numéro de version illisible dans la release.", "bad_release")
    for asset in data.get("assets", []):
        match = ASSET_RE.match(str(asset.get("name", "")))
        if match and match.group(1) == version:
            return ReleaseInfo(
                version=version,
                tag=tag,
                notes=str(data.get("body") or "").strip(),
                asset_name=asset["name"],
                asset_url=str(asset.get("browser_download_url", "")),
                size=int(asset.get("size") or 0),
                digest=asset.get("digest"),
                page_url=str(data.get("html_url", "")),
            )
    raise UpdateError(f"La release {tag} ne contient pas d'exécutable portable.", "no_asset")


def download(
    info: ReleaseInfo,
    dest: Path,
    progress: Optional[Callable[[int, int], None]] = None,
    cancel: Optional[threading.Event] = None,
    timeout: float = 60,
) -> Path:
    """Télécharge l'exécutable dans `dest` (via un fichier .part) et en vérifie l'intégrité."""
    dest = Path(dest)
    part = dest.with_name(dest.name + ".part")
    sha = hashlib.sha256()
    try:
        request = urllib.request.Request(info.asset_url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=timeout) as response, open(part, "wb") as out:
            total = int(response.headers.get("Content-Length") or info.size or 0)
            done = 0
            while True:
                if cancel is not None and cancel.is_set():
                    raise UpdateError("Téléchargement annulé.", "cancelled")
                chunk = response.read(CHUNK)
                if not chunk:
                    break
                out.write(chunk)
                sha.update(chunk)
                done += len(chunk)
                if progress is not None:
                    progress(done, total)
    except urllib.error.HTTPError as exc:
        part.unlink(missing_ok=True)
        raise UpdateError(f"Téléchargement refusé ({exc.code}).", "http") from exc
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
        part.unlink(missing_ok=True)
        raise UpdateError(f"Téléchargement interrompu : {getattr(exc, 'reason', exc)}", "network") from exc
    except UpdateError:
        part.unlink(missing_ok=True)
        raise

    problem = None
    if info.size and part.stat().st_size != info.size:
        problem = f"taille inattendue ({part.stat().st_size} au lieu de {info.size} octets)"
    elif info.digest and info.digest.startswith("sha256:") and info.digest[7:].lower() != sha.hexdigest():
        problem = "empreinte SHA-256 incorrecte"
    elif not looks_like_exe(part):
        problem = "ce n'est pas un exécutable Windows"
    if problem:
        part.unlink(missing_ok=True)
        raise UpdateError(f"Fichier téléchargé corrompu : {problem}.", "corrupt")
    os.replace(part, dest)
    return dest


def looks_like_exe(path: Path) -> bool:
    try:
        with open(path, "rb") as handle:
            return handle.read(2) == b"MZ"
    except OSError:
        return False


# ---------------------------------------------------------------------- vérification / remplacement
def smoke_test(exe: Path, timeout: float = 90) -> bool:
    """Le nouvel exécutable doit démarrer et construire son interface (mode --smoke-test)."""
    with tempfile.TemporaryDirectory() as tmp:
        result = Path(tmp) / "smoke.txt"
        try:
            process = subprocess.Popen([str(exe), "--smoke-test", str(result)], cwd=str(Path(exe).parent))
        except OSError:
            return False
        deadline = time.time() + timeout
        while time.time() < deadline and not result.exists():
            if process.poll() is not None and not result.exists():
                break
            time.sleep(0.3)
        ok = result.exists() and result.read_text(encoding="utf-8", errors="replace").startswith("ok")
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
        return ok


def old_path(current: Path) -> Path:
    return Path(current).with_name(Path(current).name + ".old")


def new_path(current: Path) -> Path:
    """Emplacement du téléchargement : même dossier (remplacement atomique), extension .exe conservée."""
    current = Path(current)
    return current.with_name(f"{current.stem}.new{current.suffix}")


def apply_update(new_exe: Path, current: Path) -> Path:
    """Remplace `current` par `new_exe` en gardant l'ancien en `.old` (annulé si le remplacement échoue)."""
    current, new_exe = Path(current), Path(new_exe)
    backup = old_path(current)
    try:
        backup.unlink(missing_ok=True)
        os.replace(current, backup)
    except PermissionError as exc:
        raise UpdateError("Droits insuffisants pour remplacer l'application.", "permission") from exc
    except OSError as exc:
        raise UpdateError(f"Remplacement impossible : {exc}", "replace") from exc
    try:
        os.replace(new_exe, current)
    except OSError as exc:
        try:
            os.replace(backup, current)  # retour arrière : l'ancienne version reste en place
        except OSError:
            logger.exception("Retour arrière impossible")
        raise UpdateError(f"Remplacement impossible : {exc}", "replace") from exc
    return backup


def cleanup_leftovers(current: Path) -> None:
    """Supprime les restes d'une mise à jour précédente (ancien exécutable, téléchargement interrompu)."""
    current = Path(current)
    new = new_path(current)
    for leftover in (old_path(current), new, new.with_name(new.name + ".part")):
        try:
            leftover.unlink(missing_ok=True)
        except OSError:
            pass  # encore utilisé : on réessaiera au prochain démarrage


def perform_update(
    info: ReleaseInfo,
    current: Path,
    progress: Optional[Callable[[int, int], None]] = None,
    cancel: Optional[threading.Event] = None,
    status: Optional[Callable[[str], None]] = None,
    verify: Callable[[Path], bool] = smoke_test,
) -> Path:
    """Télécharge, vérifie puis installe la nouvelle version à la place de `current`. Renvoie le chemin de
    l'ancienne version conservée (.old). `status` reçoit « downloading », « verifying » puis « installing »."""
    current = Path(current)
    new = new_path(current)
    note = status or (lambda _: None)
    note("downloading")
    download(info, new, progress, cancel)
    note("verifying")
    if not verify(new):
        new.unlink(missing_ok=True)
        raise UpdateError("La nouvelle version ne démarre pas : mise à jour annulée, rien n'a été modifié.", "verify")
    note("installing")
    try:
        return apply_update(new, current)
    except UpdateError:
        new.unlink(missing_ok=True)
        raise


def relaunch(exe: Path) -> None:
    """Relance l'exécutable dans un processus indépendant (PyInstaller : environnement réinitialisé pour que
    la nouvelle instance extrait ses propres fichiers au lieu de réutiliser ceux du processus qui va se fermer)."""
    env = {k: v for k, v in os.environ.items() if not k.startswith(("_PYI", "_MEI"))}
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    flags = 0
    if os.name == "nt":
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen([str(exe)], cwd=str(Path(exe).parent), env=env, close_fds=True, creationflags=flags)
