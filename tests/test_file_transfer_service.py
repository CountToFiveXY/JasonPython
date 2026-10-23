import http.client
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from src.infrastructure.bonjour import HostNameInUseError
from src.services import FileTransferService
from src.services.file_transfer.files import list_shared_files
from src.services.file_transfer.access import UploadCodeError


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



class AccessServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.folder = Path(self._temp.name) / "FileTransfer"
        self.service = FileTransferService(
            self.folder,
            port=0,
            host="127.0.0.1",
            announcer=FakeAnnouncer(),
            load_upload_code=lambda: "0427",
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

    def cookie_for(self, code="0427"):
        return self.unlock(code).headers["Set-Cookie"].split(";")[0]

    def test_defaults_are_open_downloads_and_no_uploads(self) -> None:
        status = self.service.start()
        self.assertFalse(status["allow_uploads"])
        self.assertFalse(status["require_code"])
        self.assertIsNone(status["access_code"])
        (self.folder / "notes.txt").write_text("hi")
        response, data = self.request("GET", "/notes.txt")
        self.assertEqual((response.status, data), (200, b"hi"))
        response, _ = self.request("POST", "/upload?name=a.txt", b"hi")
        self.assertEqual(response.status, 403)
        self.assertEqual(list_shared_files(self.folder), [{"name": "notes.txt", "size": 2}])

    def test_uploads_without_the_code_need_no_unlock(self) -> None:
        self.service.start(allow_uploads=True)
        _, page = self.request("GET", "/")
        self.assertIn(b'id="upload"', page)
        self.assertNotIn(b"Unlock", page)
        response, data = self.request("POST", "/upload?name=notes%20one.txt", b"hello")
        self.assertEqual(response.status, 201, data)
        self.assertEqual((self.folder / "notes one.txt").read_bytes(), b"hello")
        response, _ = self.request("POST", "/upload?name=.hidden", b"x")
        self.assertEqual(response.status, 400)

    def test_requiring_the_code_makes_the_list_view_only(self) -> None:
        status = self.service.start(require_code=True)
        self.assertTrue(status["require_code"])
        self.assertEqual(status["access_code"], "0427")
        (self.folder / "notes.txt").write_text("hi")

        _, page = self.request("GET", "/")
        self.assertIn(b"notes.txt", page)
        self.assertNotIn(b'href="/notes.txt"', page)
        self.assertIn(b"Enter the code to download files.", page)
        response, _ = self.request("GET", "/notes.txt")
        self.assertEqual(response.status, 401)

        response = self.unlock("1111")
        self.assertEqual(response.headers["Location"], "/?wrong")
        self.assertIsNone(response.headers["Set-Cookie"])
        _, page = self.request("GET", "/?wrong")
        self.assertIn(b"That code is not right", page)

        response = self.unlock("0427")
        self.assertEqual(response.headers["Location"], "/")
        self.assertIn("HttpOnly", response.headers["Set-Cookie"])
        cookie = response.headers["Set-Cookie"].split(";")[0]
        _, page = self.request("GET", "/", cookie=cookie)
        self.assertIn(b'href="/notes.txt"', page)
        response, data = self.request("GET", "/notes.txt", cookie=cookie)
        self.assertEqual((response.status, data), (200, b"hi"))

    def test_with_the_code_required_uploads_need_it_too(self) -> None:
        self.service.start(allow_uploads=True, require_code=True)
        _, page = self.request("GET", "/")
        self.assertIn(b"Enter the code to download or upload files.", page)
        self.assertNotIn(b'id="upload"', page)
        response, _ = self.request("POST", "/upload?name=a.txt", b"hi")
        self.assertEqual(response.status, 401)

        cookie = self.cookie_for()
        _, page = self.request("GET", "/", cookie=cookie)
        self.assertIn(b'id="upload"', page)
        response, data = self.request("POST", "/upload?name=a.txt", b"hi", cookie=cookie)
        self.assertEqual(response.status, 201, data)

    def test_turning_the_code_off_signs_devices_out_and_reopens_downloads(self) -> None:
        self.service.start(require_code=True)
        cookie = self.cookie_for()
        self.service.start(require_code=False)
        self.service.start(require_code=True)
        (self.folder / "notes.txt").write_text("hi")
        response, _ = self.request("GET", "/notes.txt", cookie=cookie)
        self.assertEqual(response.status, 401)
        status = self.service.start(require_code=False)
        self.assertIsNone(status["access_code"])
        response, _ = self.request("GET", "/notes.txt")
        self.assertEqual(response.status, 200)

    def make_folders(self):
        (self.folder / "Photos" / "Trip").mkdir(parents=True)
        (self.folder / "Photos" / "Trip" / "beach.jpg").write_bytes(b"jpg")

    def test_devices_browse_into_folders_and_download_from_them(self) -> None:
        status = self.service.start()
        self.make_folders()
        self.assertEqual(self.service.status()["folders"], ["Photos"])
        _, page = self.request("GET", "/")
        self.assertIn(b'href="/Photos/"', page)
        _, page = self.request("GET", "/Photos/Trip/")
        self.assertIn(b"<h1>Trip</h1>", page)
        self.assertIn(b'href="/Photos/"', page)
        self.assertIn(b'href="/Photos/Trip/beach.jpg"', page)
        response, data = self.request("GET", "/Photos/Trip/beach.jpg")
        self.assertEqual((response.status, data), (200, b"jpg"))

        response, _ = self.request("GET", "/Photos/Trip")
        self.assertEqual((response.status, response.headers["Location"]), (301, "/Photos/Trip/"))
        for path in ["/Missing/", "/Photos/Trip/beach.jpg/", "/../", "/Photos/../../"]:
            response, _ = self.request("GET", path)
            self.assertEqual(response.status, 404, path)

    def test_uploads_go_into_the_folder_being_viewed(self) -> None:
        self.service.start(allow_uploads=True)
        self.make_folders()
        _, page = self.request("GET", "/Photos/Trip/")
        self.assertIn(b'data-folder="Photos/Trip"', page)
        response, data = self.request("POST", "/upload?folder=Photos%2FTrip&name=new.jpg", b"new")
        self.assertEqual(response.status, 201, data)
        self.assertEqual((self.folder / "Photos" / "Trip" / "new.jpg").read_bytes(), b"new")

    def test_devices_cannot_create_folders_or_upload_outside(self) -> None:
        self.service.start(allow_uploads=True)
        self.make_folders()
        for folder in ["Missing", "Photos%2FMissing", "..", "Photos%2F..%2F..", ".hidden"]:
            response, _ = self.request("POST", f"/upload?folder={folder}&name=x.txt", b"x")
            self.assertEqual(response.status, 404, folder)
        for name in ["Sub%2Fx.txt", "..%2Fx.txt"]:
            response, _ = self.request("POST", f"/upload?folder=Photos&name={name}", b"x")
            self.assertEqual(response.status, 400, name)
        self.assertFalse((self.folder / "Missing").exists())
        self.assertFalse((self.folder.parent / "x.txt").exists())

    def test_view_only_folders_can_be_browsed_and_unlock_returns_to_them(self) -> None:
        self.service.start(require_code=True)
        self.make_folders()
        _, page = self.request("GET", "/Photos/Trip/")
        self.assertIn(b"beach.jpg", page)
        self.assertNotIn(b'href="/Photos/Trip/beach.jpg"', page)
        response, _ = self.request("GET", "/Photos/Trip/beach.jpg")
        self.assertEqual(response.status, 401)
        form = {"Content-Type": "application/x-www-form-urlencoded"}
        response, _ = self.request("POST", "/unlock", b"code=1111&next=Photos%2FTrip", headers=form)
        self.assertEqual(response.headers["Location"], "/Photos/Trip/?wrong")
        response, _ = self.request("POST", "/unlock", b"code=0427&next=Photos%2FTrip", headers=form)
        self.assertEqual(response.headers["Location"], "/Photos/Trip/")
        response, _ = self.request("POST", "/unlock", b"code=0427&next=..%2F..", headers=form)
        self.assertEqual(response.headers["Location"], "/")

    def test_rejects_files_over_the_size_limit(self) -> None:
        self.service = FileTransferService(
            self.folder,
            port=0,
            host="127.0.0.1",
            announcer=FakeAnnouncer(),
            max_upload_bytes=4,
        )
        self.service.start(allow_uploads=True)
        response, data = self.request("POST", "/upload?name=big.bin", b"12345")
        self.assertEqual(response.status, 413, data)
        self.assertEqual(list_shared_files(self.folder), [])

    def test_without_a_code_in_firestore_the_code_cannot_be_required(self) -> None:
        self.service.stop()
        self.service = FileTransferService(
            self.folder, port=0, host="127.0.0.1", announcer=FakeAnnouncer()
        )
        with self.assertRaises(UploadCodeError):
            self.service.start(require_code=True)
        self.assertFalse(self.service.status()["running"])
        self.service.start(allow_uploads=True)
        with self.assertRaises(UploadCodeError):
            self.service.start(allow_uploads=False, require_code=True)
        status = self.service.status()
        # A failed change leaves the switches as they were.
        self.assertTrue(status["running"])
        self.assertTrue(status["allow_uploads"])
        self.assertFalse(status["require_code"])

    def test_stopping_resets_both_switches(self) -> None:
        self.service.start(allow_uploads=True, require_code=True)
        status = self.service.stop()
        self.assertFalse(status["allow_uploads"])
        self.assertFalse(status["require_code"])
        self.assertIsNone(status["access_code"])

if __name__ == "__main__":
    unittest.main()
