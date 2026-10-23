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
from src.services.file_transfer import (
    BonjourAnnouncer,
    HostNameInUseError,
    list_shared_files,
    shared_file,
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
