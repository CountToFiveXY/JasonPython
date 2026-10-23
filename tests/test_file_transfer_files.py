import io
import os
import tempfile
import unittest
from pathlib import Path

from src.services.file_transfer.files import (
    list_folder,
    list_shared_files,
    path_parts,
    save_upload,
    shared_file,
    shared_folder,
    valid_name,
)


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



class SubfolderTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.outside = Path(self._temp.name)
        self.root = self.outside / "FileTransfer"
        (self.root / "Photos" / "Trip").mkdir(parents=True)
        (self.root / "Photos" / "Trip" / "beach.jpg").write_bytes(b"jpg")
        (self.root / "Photos" / "cover.png").write_bytes(b"png")
        (self.root / ".private").mkdir()
        (self.root / ".private" / "notes.txt").write_text("hidden")
        (self.outside / "secret.txt").write_text("outside")
        (self.outside / "Elsewhere").mkdir()
        (self.outside / "Elsewhere" / "data.txt").write_text("outside")
        # A folder shortcut pointing outside the shared folder.
        os.symlink(self.outside / "Elsewhere", self.root / "Shortcut")

    def tearDown(self) -> None:
        self._temp.cleanup()

    def test_lists_visible_real_folders_only(self) -> None:
        folders, files = list_folder(self.root)
        self.assertEqual((folders, files), (["Photos"], []))
        folders, files = list_folder(self.root / "Photos")
        self.assertEqual(folders, ["Trip"])
        self.assertEqual(files, [{"name": "cover.png", "size": 3}])

    def test_finds_files_and_folders_at_any_depth(self) -> None:
        self.assertEqual(shared_folder(self.root, ""), self.root)
        self.assertEqual(shared_folder(self.root, "/Photos/Trip/"), self.root / "Photos" / "Trip")
        self.assertEqual(
            shared_file(self.root, "/Photos/Trip/beach.jpg"),
            self.root / "Photos" / "Trip" / "beach.jpg",
        )

    def test_refuses_every_way_out_of_the_shared_folder(self) -> None:
        escapes = [
            "../secret.txt",
            "Photos/../../secret.txt",
            "Photos/Trip/../../../secret.txt",
            "..",
            "Shortcut/data.txt",
            ".private/notes.txt",
            "Photos//Trip/beach.jpg",
            "Photos\\Trip\\beach.jpg",
            "Photos/./Trip/beach.jpg",
        ]
        for path in escapes:
            self.assertIsNone(shared_file(self.root, path), path)
        for path in ["..", "../Elsewhere", "Shortcut", ".private", "Photos/../..", "Missing"]:
            self.assertIsNone(shared_folder(self.root, path), path)

    def test_a_folder_is_not_a_file_and_a_file_is_not_a_folder(self) -> None:
        self.assertIsNone(shared_file(self.root, "Photos/Trip"))
        self.assertIsNone(shared_folder(self.root, "Photos/cover.png"))

    def test_path_parts(self) -> None:
        self.assertEqual(path_parts("/"), [])
        self.assertEqual(path_parts("/Photos/Trip/"), ["Photos", "Trip"])
        self.assertIsNone(path_parts("Photos/../Trip"))


class ValidNameTests(unittest.TestCase):
    def test_accepts_ordinary_phone_file_names(self) -> None:
        for name in ["IMG_1234.HEIC", "report (final).pdf", "照片.jpg"]:
            self.assertTrue(valid_name(name), name)

    def test_rejects_paths_hidden_and_control_characters(self) -> None:
        for name in ["", ".env", "../x", "a/b", "a\\b", "bad\nname", "x" * 256]:
            self.assertFalse(valid_name(name), repr(name))



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


if __name__ == "__main__":
    unittest.main()
