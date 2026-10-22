import hashlib
import http.server
import json
import os
import stat
import sys
import tempfile
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import updater

EXE_BYTES = b"MZ" + b"\x00" * 5000


class FakeGitHub(http.server.ThreadingHTTPServer):
    def __init__(self, tag="v9.9.9", payload=EXE_BYTES, with_digest=True, setup_only=False):
        super().__init__(("127.0.0.1", 0), FakeGitHubHandler)
        self.tag, self.payload = tag, payload
        self.with_digest, self.setup_only = with_digest, setup_only
        self.thread = threading.Thread(target=self.serve_forever, daemon=True)
        self.thread.start()

    @property
    def base(self):
        return f"http://127.0.0.1:{self.server_address[1]}"

    def stop(self):
        self.shutdown()
        self.server_close()


class FakeGitHubHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, status, body=b"", headers=None):
        self.send_response(status)
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        s = self.server
        version = s.tag.lstrip("v")
        if self.path == "/repos/o/r/releases/latest":
            assets = [{"name": f"RKarrousel-Setup-v{version}.exe", "browser_download_url": f"{s.base}/download/setup", "size": 10}]
            if not s.setup_only:
                asset = {
                    "name": f"RKarrousel-v{version}.exe",
                                        "browser_download_url": f"{s.base}/download/portable",
                    "size": len(s.payload),
                }
                if s.with_digest:
                    asset["digest"] = "sha256:" + hashlib.sha256(s.payload).hexdigest()
                assets.append(asset)
            body = {"tag_name": s.tag, "body": "- nouveautés", "html_url": f"{s.base}/release", "assets": assets}
            return self._send(200, json.dumps(body).encode(), {"Content-Type": "application/json"})
        if self.path == "/download/portable":
            return self._send(200, s.payload)
        self._send(404)


class VersionTests(unittest.TestCase):
    def test_parse_and_compare(self):
        self.assertEqual(updater.parse_version("v0.10.2"), (0, 10, 2))
        self.assertEqual(updater.parse_version("nonsense"), ())
        self.assertTrue(updater.is_newer("v0.10.0", "0.9.9"))  # comparaison numérique, pas alphabétique
        self.assertTrue(updater.is_newer("1.0.0", "0.99.99"))
        self.assertFalse(updater.is_newer("0.7.0", "0.7.0"))
        self.assertFalse(updater.is_newer("0.6.9", "0.7.0"))
        self.assertFalse(updater.is_newer("garbage", "0.7.0"))

    def test_check_due(self):
        self.assertTrue(updater.check_due(0, now=100000))
        self.assertFalse(updater.check_due(100000, now=100100))
        self.assertTrue(updater.check_due(100000, now=100000 + updater.CHECK_INTERVAL + 1))


class GitHubTests(unittest.TestCase):
    def tearDown(self):
        self.fake.stop()

    def fetch(self, **kwargs):
        return updater.fetch_latest_release("o/r", api=self.fake.base, **kwargs)

    def test_picks_the_portable_exe_not_the_installer(self):
        self.fake = FakeGitHub()
        info = self.fetch()
        self.assertEqual(info.version, "9.9.9")
        self.assertEqual(info.asset_name, "RKarrousel-v9.9.9.exe")
        self.assertEqual(info.notes, "- nouveautés")
        self.assertEqual(info.size, len(EXE_BYTES))

    def test_release_without_portable_exe(self):
        self.fake = FakeGitHub(setup_only=True)
        with self.assertRaises(updater.UpdateError) as ctx:
            self.fetch()
        self.assertEqual(ctx.exception.code, "no_asset")

    def test_network_error(self):
        self.fake = FakeGitHub()
        with self.assertRaises(updater.UpdateError) as ctx:
            updater.fetch_latest_release("o/r", api="http://127.0.0.1:1", timeout=2)
        self.assertEqual(ctx.exception.code, "network")


class DownloadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.fake.stop()
        self.tmp.cleanup()

    def test_public_download_with_progress_and_digest(self):
        self.fake = FakeGitHub()
        info = updater.fetch_latest_release("o/r", api=self.fake.base)
        seen = []
        target = updater.download(info, self.dir / "new.exe", progress=lambda d, t: seen.append((d, t)))
        self.assertEqual(target.read_bytes(), EXE_BYTES)
        self.assertEqual(seen[-1][0], len(EXE_BYTES))
        self.assertFalse((self.dir / "new.exe.part").exists())

    def test_corrupted_download_is_rejected(self):
        self.fake = FakeGitHub()
        info = updater.fetch_latest_release("o/r", api=self.fake.base)
        info.digest = "sha256:" + "0" * 64
        with self.assertRaises(updater.UpdateError) as ctx:
            updater.download(info, self.dir / "new.exe")
        self.assertEqual(ctx.exception.code, "corrupt")
        self.assertFalse((self.dir / "new.exe").exists())
        self.assertFalse((self.dir / "new.exe.part").exists())

    def test_wrong_size_and_non_exe_are_rejected(self):
        self.fake = FakeGitHub(payload=b"<html>not an exe</html>", with_digest=False)
        info = updater.fetch_latest_release("o/r", api=self.fake.base)
        with self.assertRaises(updater.UpdateError):
            updater.download(info, self.dir / "new.exe")  # pas de MZ
        info.size += 1
        with self.assertRaises(updater.UpdateError):
            updater.download(info, self.dir / "new.exe")  # mauvaise taille

    def test_cancel(self):
        self.fake = FakeGitHub()
        info = updater.fetch_latest_release("o/r", api=self.fake.base)
        cancel = threading.Event()
        cancel.set()
        with self.assertRaises(updater.UpdateError) as ctx:
            updater.download(info, self.dir / "new.exe", cancel=cancel)
        self.assertEqual(ctx.exception.code, "cancelled")
        self.assertFalse(list(self.dir.glob("new.exe*")))


class ApplyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.current = self.dir / "RKarrousel.exe"
        self.current.write_bytes(b"MZ-old")
        self.config = self.dir / ".image_splitter_config.json"
        self.config.write_text('{"frame_ratio": 0.05}')

    def tearDown(self):
        self.tmp.cleanup()

    def test_swap_keeps_a_backup_and_leaves_the_config_alone(self):
        new = updater.new_path(self.current)
        self.assertEqual(new.name, "RKarrousel.new.exe")
        new.write_bytes(b"MZ-new")
        backup = updater.apply_update(new, self.current)
        self.assertEqual(self.current.read_bytes(), b"MZ-new")
        self.assertEqual(backup.read_bytes(), b"MZ-old")
        self.assertFalse(new.exists())
        self.assertEqual(json.loads(self.config.read_text())["frame_ratio"], 0.05)

    def test_failed_swap_rolls_back(self):
        with self.assertRaises(updater.UpdateError):
            updater.apply_update(self.dir / "does-not-exist.exe", self.current)
        self.assertEqual(self.current.read_bytes(), b"MZ-old")  # l'ancienne version est restée en place

    def test_cleanup_removes_leftovers(self):
        updater.old_path(self.current).write_bytes(b"x")
        (self.dir / "RKarrousel.new.exe.part").write_bytes(b"x")
        updater.cleanup_leftovers(self.current)
        self.assertEqual(sorted(p.name for p in self.dir.iterdir()), [".image_splitter_config.json", "RKarrousel.exe"])

    def test_perform_update_end_to_end(self):
        fake = FakeGitHub()
        try:
            info = updater.fetch_latest_release("o/r", api=fake.base)
            steps = []
            backup = updater.perform_update(info, self.current, status=steps.append, verify=lambda p: True)
        finally:
            fake.stop()
        self.assertEqual(steps, ["downloading", "verifying", "installing"])
        self.assertEqual(self.current.read_bytes(), EXE_BYTES)
        self.assertEqual(backup.read_bytes(), b"MZ-old")
        self.assertEqual(json.loads(self.config.read_text())["frame_ratio"], 0.05)

    def test_perform_update_aborts_when_the_new_exe_does_not_start(self):
        fake = FakeGitHub()
        try:
            info = updater.fetch_latest_release("o/r", api=fake.base)
            with self.assertRaises(updater.UpdateError) as ctx:
                updater.perform_update(info, self.current, verify=lambda p: False)
        finally:
            fake.stop()
        self.assertEqual(ctx.exception.code, "verify")
        self.assertEqual(self.current.read_bytes(), b"MZ-old")  # rien n'a changé
        self.assertFalse(updater.new_path(self.current).exists())

    @unittest.skipIf(os.name == "nt", "script shell")
    def test_smoke_test_reads_the_result_file(self):
        good = self.dir / "good.sh"
        good.write_text('#!/bin/sh\necho "ok v9" > "$2"\n')
        bad = self.dir / "bad.sh"
        bad.write_text('#!/bin/sh\nexit 1\n')
        for script in (good, bad):
            script.chmod(script.stat().st_mode | stat.S_IEXEC)
        self.assertTrue(updater.smoke_test(good, timeout=10))
        self.assertFalse(updater.smoke_test(bad, timeout=10))


if __name__ == "__main__":
    unittest.main()
