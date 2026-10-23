import http.client
import io
import os
import shutil
import tempfile
import time
import uuid
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from types import SimpleNamespace

from fastapi import HTTPException

from src.routers.file_transfer import require_local_client
from src.services import FileTransferService
from src.services import file_transfer
from src.services.file_transfer import (
    MAX_CODE_FAILURES,
    BonjourAnnouncer,
    HostNameInUseError,
    UploadAccess,
    list_shared_files,
    save_upload,
    shared_file,
    valid_name,
)


class FakeAnnouncer:
    host_name = "jason.local"

    def __init__(self, in_use: bool = False) -> None:
        self.in_use = in_use
        self.is_active = False
        self.claimed_port: int | None = None

    def claim(self, address: str, port: int) -> bool:
        if self.in_use:
            raise HostNameInUseError(self.host_name, "192.168.88.20")
        self.is_active, self.claimed_port = True, port
        return True

    def release(self) -> None:
        self.is_active = False


class SharedFileTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.root = Path(self._temp.name)
        self.folder = self.root / "FileTransfer"
        self.folder.mkdir()
        (self.folder / "report.pdf").write_bytes(b"pdf")
        (self.folder / ".DS_Store").write_bytes(b"hidden")
        (self.folder / "nested").mkdir()
        (self.root / "secret.txt").write_text("outside")
        os.symlink(self.root / "secret.txt", self.folder / "link.txt")

    def tearDown(self) -> None:
        self._temp.cleanup()

    def test_lists_only_visible_plain_files(self) -> None:
        self.assertEqual(list_shared_files(self.folder), [{"name": "report.pdf", "size": 3}])

    def test_missing_folder_lists_nothing(self) -> None:
        self.assertEqual(list_shared_files(self.root / "missing"), [])

    def test_refuses_paths_outside_the_folder(self) -> None:
        self.assertEqual(shared_file(self.folder, "report.pdf"), self.folder / "report.pdf")
        for name in ["", "../secret.txt", "..", ".DS_Store", "nested", "link.txt", "a/b", "a\\b"]:
            self.assertIsNone(shared_file(self.folder, name), name)


class FileTransferServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.folder = Path(self._temp.name) / "FileTransfer"
        self.announcer = FakeAnnouncer()
        self.service = FileTransferService(
            self.folder, port=0, host="127.0.0.1", announcer=self.announcer
        )

    def tearDown(self) -> None:
        self.service.stop()
        self._temp.cleanup()

    def test_serves_downloads_until_stopped(self) -> None:
        status = self.service.start()
        self.assertTrue(status["running"])
        self.assertTrue(self.folder.is_dir())
        (self.folder / "hello world.txt").write_text("hi")
        base = f"http://127.0.0.1:{status['port']}"

        with urllib.request.urlopen(f"{base}/hello%20world.txt", timeout=5) as response:
            self.assertEqual(response.read(), b"hi")
            self.assertIn("attachment", response.headers["Content-Disposition"])
        with urllib.request.urlopen(f"{base}/", timeout=5) as response:
            self.assertIn(b"hello%20world.txt", response.read())
        with self.assertRaises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(f"{base}/..%2Fsecret.txt", timeout=5)
        self.assertEqual(error.exception.code, 404)
        with self.assertRaises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(
                urllib.request.Request(f"{base}/upload.txt", data=b"x", method="PUT"),
                timeout=5,
            )
        self.assertEqual(error.exception.code, 501)

        status = self.service.stop()
        self.assertFalse(status["running"])
        self.assertIsNone(status["port"])
        with self.assertRaises(urllib.error.URLError):
            urllib.request.urlopen(f"{base}/", timeout=2)

    def test_announces_the_shared_name_while_running(self) -> None:
        status = self.service.start()
        self.assertEqual(self.announcer.claimed_port, status["port"])
        self.assertEqual(status["host_name"], "jason.local")
        self.assertEqual(status["url"], f"http://jason.local:{status['port']}")

        status = self.service.stop()
        self.assertFalse(self.announcer.is_active)
        self.assertIsNone(status["host_name"])
        self.assertIsNone(status["url"])

    def test_refuses_to_start_when_another_mac_owns_the_name(self) -> None:
        self.announcer.in_use = True
        with self.assertRaises(HostNameInUseError) as error:
            self.service.start()
        self.assertIn("192.168.88.20", str(error.exception))
        self.assertFalse(self.service.status()["running"])

    def test_start_is_idempotent(self) -> None:
        first = self.service.start()
        self.assertEqual(self.service.start()["port"], first["port"])


@unittest.skipUnless(shutil.which("dns-sd"), "needs macOS Bonjour")
class BonjourAnnouncerTests(unittest.TestCase):
    def test_second_claim_on_the_same_name_is_refused(self) -> None:
        name = f"jasonapp-test-{uuid.uuid4().hex[:8]}.local"
        first, second = BonjourAnnouncer(name), BonjourAnnouncer(name)
        try:
            self.assertTrue(first.claim("192.0.2.10", 80))
            self.assertTrue(first.is_active)
            # Bonjour on one Mac can miss a clash started the same instant
            # the first name goes live; a person pressing Start is never that fast.
            time.sleep(1)
            with self.assertRaises(HostNameInUseError):
                second.claim("192.0.2.11", 80)
            self.assertFalse(second.is_active)
        finally:
            first.release()
            second.release()
        self.assertFalse(first.is_active)


class ValidNameTests(unittest.TestCase):
    def test_accepts_ordinary_phone_file_names(self) -> None:
        for name in ["IMG_1234.HEIC", "report (final).pdf", "照片.jpg"]:
            self.assertTrue(valid_name(name), name)

    def test_rejects_paths_hidden_and_control_characters(self) -> None:
        for name in ["", ".env", "../x", "a/b", "a\\b", "bad\nname", "x" * 256]:
            self.assertFalse(valid_name(name), repr(name))


class UploadAccessTests(unittest.TestCase):
    def test_off_until_enabled(self) -> None:
        access = UploadAccess()
        self.assertFalse(access.enabled)
        self.assertIsNone(access.unlock(""))

    def test_correct_code_returns_a_session_token(self) -> None:
        access = UploadAccess()
        access.set_enabled(True)
        self.assertRegex(access.code, r"^\d{6}$")
        self.assertIsNone(access.unlock("not it"))
        token = access.unlock(access.code)
        self.assertTrue(access.allows(token))
        self.assertFalse(access.allows("forged"))
        self.assertFalse(access.allows(None))

    def test_repeated_wrong_codes_replace_the_code(self) -> None:
        access = UploadAccess()
        access.set_enabled(True)
        token = access.unlock(access.code)
        old_code = access.code
        for _ in range(MAX_CODE_FAILURES):
            access.unlock("wrong")
        self.assertNotEqual(access.code, old_code)
        self.assertIsNone(access.unlock(old_code))
        # Devices that already unlocked keep working.
        self.assertTrue(access.allows(token))

    def test_turning_uploads_off_signs_every_device_out(self) -> None:
        access = UploadAccess()
        access.set_enabled(True)
        token = access.unlock(access.code)
        access.set_enabled(False)
        self.assertFalse(access.allows(token))
        access.set_enabled(True)
        self.assertFalse(access.allows(token))

    def test_staying_enabled_keeps_the_code(self) -> None:
        access = UploadAccess()
        access.set_enabled(True)
        code = access.code
        access.set_enabled(True)
        self.assertEqual(access.code, code)


class SaveUploadTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.folder = Path(self._temp.name)

    def tearDown(self) -> None:
        self._temp.cleanup()

    def test_saves_without_replacing_existing_files(self) -> None:
        (self.folder / "photo.jpg").write_bytes(b"old")
        self.assertEqual(save_upload(self.folder, "photo.jpg", io.BytesIO(b"new"), 3), "photo (1).jpg")
        self.assertEqual(save_upload(self.folder, "photo.jpg", io.BytesIO(b"3rd"), 3), "photo (2).jpg")
        self.assertEqual((self.folder / "photo.jpg").read_bytes(), b"old")
        self.assertEqual((self.folder / "photo (1).jpg").read_bytes(), b"new")

    def test_interrupted_upload_leaves_nothing_behind(self) -> None:
        with self.assertRaises(ConnectionError):
            save_upload(self.folder, "video.mov", io.BytesIO(b"half"), 100)
        self.assertEqual(list(self.folder.iterdir()), [])


class UploadServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.folder = Path(self._temp.name) / "FileTransfer"
        self.service = FileTransferService(
            self.folder, port=0, host="127.0.0.1", announcer=FakeAnnouncer()
        )

    def tearDown(self) -> None:
        self.service.stop()
        self._temp.cleanup()

    def request(self, method, path, body=b"", cookie=None, headers=None):
        port = self.service.status()["port"]
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        all_headers = dict(headers or {})
        if cookie:
            all_headers["Cookie"] = cookie
        connection.request(method, path, body=body, headers=all_headers)
        response = connection.getresponse()
        data = response.read()
        connection.close()
        return response, data

    def unlock(self, code):
        response, _ = self.request(
            "POST", "/unlock", f"code={code}".encode(),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        return response

    def test_uploads_are_refused_while_turned_off(self) -> None:
        status = self.service.start()
        self.assertFalse(status["allow_uploads"])
        self.assertIsNone(status["upload_code"])
        response, _ = self.request("POST", "/upload?name=a.txt", b"hi")
        self.assertEqual(response.status, 403)
        self.assertEqual(list_shared_files(self.folder), [])

    def test_device_uploads_after_entering_the_code(self) -> None:
        status = self.service.start(allow_uploads=True)
        self.assertTrue(status["allow_uploads"])

        response, _ = self.request("POST", "/upload?name=a.txt", b"hi")
        self.assertEqual(response.status, 401)
        _, page = self.request("GET", "/")
        self.assertIn(b"Unlock uploads", page)

        response = self.unlock("000000" if status["upload_code"] != "000000" else "111111")
        self.assertEqual(response.headers["Location"], "/?wrong")
        self.assertIsNone(response.headers["Set-Cookie"])
        _, page = self.request("GET", "/?wrong")
        self.assertIn(b"That code is not right", page)

        response = self.unlock(status["upload_code"])
        self.assertEqual(response.headers["Location"], "/")
        cookie = response.headers["Set-Cookie"].split(";")[0]
        self.assertIn("HttpOnly", response.headers["Set-Cookie"])

        _, page = self.request("GET", "/", cookie=cookie)
        self.assertIn(b'id="upload"', page)
        response, data = self.request("POST", "/upload?name=notes%20one.txt", b"hello", cookie=cookie)
        self.assertEqual(response.status, 201, data)
        self.assertEqual((self.folder / "notes one.txt").read_bytes(), b"hello")

        response, _ = self.request("POST", "/upload?name=.hidden", b"x", cookie=cookie)
        self.assertEqual(response.status, 400)

    def test_rejects_files_over_the_size_limit(self) -> None:
        status = self.service.start(allow_uploads=True)
        cookie = self.unlock(status["upload_code"]).headers["Set-Cookie"].split(";")[0]
        limit = file_transfer.MAX_UPLOAD_BYTES
        file_transfer.MAX_UPLOAD_BYTES = 4
        try:
            response, data = self.request("POST", "/upload?name=big.bin", b"12345", cookie=cookie)
        finally:
            file_transfer.MAX_UPLOAD_BYTES = limit
        self.assertEqual(response.status, 413, data)
        self.assertEqual(list_shared_files(self.folder), [])

    def test_turning_uploads_off_while_sharing_keeps_downloads(self) -> None:
        status = self.service.start(allow_uploads=True)
        cookie = self.unlock(status["upload_code"]).headers["Set-Cookie"].split(";")[0]
        status = self.service.start(allow_uploads=False)
        self.assertTrue(status["running"])
        self.assertIsNone(status["upload_code"])
        response, _ = self.request("POST", "/upload?name=a.txt", b"hi", cookie=cookie)
        self.assertEqual(response.status, 403)

    def test_stopping_clears_the_upload_code(self) -> None:
        self.service.start(allow_uploads=True)
        status = self.service.stop()
        self.assertFalse(status["allow_uploads"])
        self.assertIsNone(status["upload_code"])


class LocalClientTests(unittest.TestCase):
    def test_allows_this_computer(self) -> None:
        for host in ["127.0.0.1", "::1"]:
            require_local_client(SimpleNamespace(client=SimpleNamespace(host=host)))

    def test_rejects_other_devices(self) -> None:
        for client in [SimpleNamespace(host="192.168.1.20"), None]:
            with self.assertRaises(HTTPException) as error:
                require_local_client(SimpleNamespace(client=client))
            self.assertEqual(error.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
