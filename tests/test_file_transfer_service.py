import http.client
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from src.infrastructure.bonjour import HostNameInUseError
from src.services import FileTransferService
from src.services.file_transfer.files import list_shared_files


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
        self.service = FileTransferService(
            self.folder, port=0, host="127.0.0.1", announcer=FakeAnnouncer(), max_upload_bytes=4
        )
        status = self.service.start(allow_uploads=True)
        cookie = self.unlock(status["upload_code"]).headers["Set-Cookie"].split(";")[0]
        response, data = self.request("POST", "/upload?name=big.bin", b"12345", cookie=cookie)
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


if __name__ == "__main__":
    unittest.main()
