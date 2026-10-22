import base64
import hashlib
import http.server
import json
import re
import sys
import tempfile
import threading
import time
import unittest
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import gdrive


class FakeGoogle(http.server.ThreadingHTTPServer):
    """Mini-serveur imitant juste ce qu'utilise gdrive.py : jeton OAuth, recherche/création de dossiers,
    envoi reprenable de fichiers."""

    def __init__(self):
        super().__init__(("127.0.0.1", 0), FakeHandler)
        self.files = {}  # id -> {name, parents, mime, content}
        self.sessions = {}
        self.counter = 0
        self.challenge = None
        self.refresh_calls = 0
        self.fail_put_once = False
        self.thread = threading.Thread(target=self.serve_forever, daemon=True)
        self.thread.start()

    @property
    def base(self):
        return f"http://127.0.0.1:{self.server_address[1]}"

    def next_id(self):
        self.counter += 1
        return f"id{self.counter}"

    def stop(self):
        self.shutdown()
        self.server_close()


class FakeHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, status=200, body=None, headers=None):
        payload = json.dumps(body).encode() if body is not None else b""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(payload)

    def _body(self):
        return self.rfile.read(int(self.headers.get("Content-Length") or 0))

    def _authorized(self):
        if self.headers.get("Authorization") not in ("Bearer AT1", "Bearer AT2"):
            self._send(401, {"error": {"message": "bad token"}})
            return False
        return True

    def do_POST(self):
        server = self.server
        path = urllib.parse.urlparse(self.path).path
        if path == "/token":
            form = {k: v[0] for k, v in urllib.parse.parse_qs(self._body().decode()).items()}
            if form["grant_type"] == "authorization_code":
                digest = base64.urlsafe_b64encode(hashlib.sha256(form["code_verifier"].encode()).digest()).rstrip(b"=").decode()
                if form["code"] != "CODE123" or digest != server.challenge:
                    return self._send(400, {"error": "invalid_grant", "error_description": "bad code or verifier"})
                return self._send(200, {"access_token": "AT1", "refresh_token": "RT1", "expires_in": 3600})
            if form["grant_type"] == "refresh_token" and form["refresh_token"] == "RT1":
                server.refresh_calls += 1
                return self._send(200, {"access_token": "AT2", "expires_in": 3600})
            return self._send(400, {"error": "invalid_grant"})
        if not self._authorized():
            return
        if path == "/drive/v3/files":
            meta = json.loads(self._body())
            file_id = server.next_id()
            server.files[file_id] = {"name": meta["name"], "parents": meta["parents"], "mime": meta["mimeType"], "content": b""}
            return self._send(200, {"id": file_id})
        if path == "/upload/drive/v3/files":
            meta = json.loads(self._body())
            session = server.next_id()
            server.sessions[session] = ("create", meta)
            return self._send(200, {}, {"Location": f"{server.base}/session/{session}"})
        self._send(404, {"error": {"message": "unknown"}})

    def do_PATCH(self):
        if not self._authorized():
            return
        match = re.match(r"/upload/drive/v3/files/(\w+)", urllib.parse.urlparse(self.path).path)
        self._body()
        session = self.server.next_id()
        self.server.sessions[session] = ("update", match.group(1))
        self._send(200, {}, {"Location": f"{self.server.base}/session/{session}"})

    def do_PUT(self):
        server = self.server
        content = self._body()
        if server.fail_put_once:
            server.fail_put_once = False
            return self._send(503, {"error": {"message": "try again"}})
        kind, data = server.sessions[self.path.rsplit("/", 1)[1]]
        if kind == "create":
            file_id = server.next_id()
            server.files[file_id] = {"name": data["name"], "parents": data["parents"], "mime": self.headers["Content-Type"], "content": content}
        else:
            file_id = data
            server.files[file_id]["content"] = content
        self._send(200, {"id": file_id, "name": server.files[file_id]["name"]})

    def do_GET(self):
        if not self._authorized():
            return
        query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)["q"][0]
        name = re.search(r"name = '((?:[^'\\]|\\.)*)'", query).group(1).replace("\\'", "'").replace("\\\\", "\\")
        parent = re.search(r"'(\w+)' in parents", query).group(1)
        folder = "mimeType" in query
        hits = [
            {"id": fid, "name": f["name"]}
            for fid, f in self.server.files.items()
            if f["name"] == name and parent in f["parents"] and (f["mime"] == gdrive.FOLDER_MIME) == folder
        ]
        self._send(200, {"files": hits[:1]})


def authorize_with_fake_browser(fake, deny=False, bad_state=False):
    def open_browser(url):
        params = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))
        fake.challenge = params["code_challenge"]
        callback = {"error": "access_denied"} if deny else {"code": "CODE123"}
        callback["state"] = "wrong" if bad_state else params["state"]
        target = f"{params['redirect_uri']}/?{urllib.parse.urlencode(callback)}"
        threading.Thread(target=lambda: urllib.request.urlopen(target).read(), daemon=True).start()

    return gdrive.authorize(
        "cid", "secret", open_browser=open_browser, auth_url=f"{fake.base}/auth", token_url=f"{fake.base}/token", timeout=10
    )


class GDriveTests(unittest.TestCase):
    def setUp(self):
        gdrive.RETRY_DELAY = 0.01
        self.fake = FakeGoogle()
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.token_path = self.dir / "token.json"

    def tearDown(self):
        self.fake.stop()
        self.tmp.cleanup()

    def client(self):
        return gdrive.DriveClient(
            "cid", "secret", self.token_path,
            api_url=f"{self.fake.base}/drive/v3", upload_url=f"{self.fake.base}/upload/drive/v3", token_url=f"{self.fake.base}/token",
        )

    def connect(self):
        token = authorize_with_fake_browser(self.fake)
        gdrive.save_token(self.token_path, token)
        return self.client()

    def make_file(self, name, content=b"jpegdata"):
        path = self.dir / name
        path.write_bytes(content)
        return path

    # ---- identifiants
    def test_client_secrets_formats(self):
        for section in ("installed", "web"):
            path = self.dir / f"{section}.json"
            path.write_text(json.dumps({section: {"client_id": "a", "client_secret": "b"}}))
            self.assertEqual(gdrive.load_client_secrets(path), ("a", "b"))
        bad = self.dir / "bad.json"
        bad.write_text("{}")
        with self.assertRaises(gdrive.DriveError):
            gdrive.load_client_secrets(bad)
        with self.assertRaises(gdrive.DriveError):
            gdrive.load_client_secrets(self.dir / "missing.json")

    # ---- connexion
    def test_authorize_returns_a_refreshable_token_using_pkce(self):
        token = authorize_with_fake_browser(self.fake)
        self.assertEqual(token["refresh_token"], "RT1")
        self.assertEqual(token["access_token"], "AT1")
        self.assertGreater(token["expires_at"], time.time())

    def test_authorize_denied_and_bad_state(self):
        with self.assertRaises(gdrive.DriveError):
            authorize_with_fake_browser(self.fake, deny=True)
        with self.assertRaises(gdrive.DriveError):
            authorize_with_fake_browser(self.fake, bad_state=True)

    def test_not_connected(self):
        client = self.client()
        self.assertFalse(client.is_connected())
        with self.assertRaises(gdrive.DriveError):
            client.ensure_folder("A")

    def test_token_roundtrip_and_clear(self):
        gdrive.save_token(self.token_path, {"refresh_token": "x"})
        self.assertIsNotNone(gdrive.load_token(self.token_path))
        gdrive.clear_token(self.token_path)
        self.assertIsNone(gdrive.load_token(self.token_path))

    # ---- dossiers / envois
    def test_nested_folders_are_created_once_and_reused(self):
        client = self.connect()
        first = client.ensure_folder("Instagram/2026/Meneham")
        before = len(self.fake.files)
        self.assertEqual(before, 3)
        self.assertEqual(self.client().ensure_folder("Instagram/2026/Meneham"), first)  # retrouvés côté serveur
        self.assertEqual(len(self.fake.files), 3)

    def test_upload_creates_then_updates_without_duplicating(self):
        client = self.connect()
        folder = client.ensure_folder("RKarrousel")
        first = client.upload(self.make_file("01_a_framed.jpg", b"v1"), folder)
        self.assertFalse(first["updated"])
        second = client.upload(self.make_file("01_a_framed.jpg", b"v2-longer"), folder)
        self.assertTrue(second["updated"])
        self.assertEqual(first["id"], second["id"])
        files = [f for f in self.fake.files.values() if f["name"] == "01_a_framed.jpg"]
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0]["content"], b"v2-longer")
        self.assertEqual(files[0]["mime"], "image/jpeg")

    def test_names_with_quotes_are_searched_safely(self):
        client = self.connect()
        folder = client.ensure_folder("RKarrousel")
        client.upload(self.make_file("l'été.jpg"), folder)
        self.assertTrue(client.upload(self.make_file("l'été.jpg", b"x"), folder)["updated"])

    def test_expired_token_is_refreshed_and_saved(self):
        token = authorize_with_fake_browser(self.fake)
        token["expires_at"] = time.time() - 10
        gdrive.save_token(self.token_path, token)
        client = self.client()
        client.ensure_folder("A")
        self.assertEqual(self.fake.refresh_calls, 1)
        self.assertEqual(gdrive.load_token(self.token_path)["access_token"], "AT2")
        self.assertEqual(gdrive.load_token(self.token_path)["refresh_token"], "RT1")

    def test_temporary_server_error_is_retried(self):
        client = self.connect()
        folder = client.ensure_folder("RKarrousel")
        self.fake.fail_put_once = True
        info = client.upload(self.make_file("a.jpg"), folder)
        self.assertTrue(info["id"])

    def test_upload_files_reports_progress_errors_and_cancel(self):
        client = self.connect()
        good = self.make_file("01_a.jpg")
        missing = self.dir / "02_missing.jpg"
        seen = []
        results = client.upload_files([good, missing], "RKarrousel", progress=lambda d, t, p: seen.append((d, t)))
        self.assertEqual([r["status"] for r in results], ["ok", "error"])
        self.assertEqual(seen, [(1, 2), (2, 2)])
        cancel = threading.Event()
        cancel.set()
        results = client.upload_files([good], "RKarrousel", cancel=cancel)
        self.assertEqual(results[0]["status"], "cancelled")

    def test_upload_files_when_not_connected_reports_every_file_as_error(self):
        results = self.client().upload_files([self.make_file("a.jpg")], "RKarrousel")
        self.assertEqual(results[0]["status"], "error")


if __name__ == "__main__":
    unittest.main()
