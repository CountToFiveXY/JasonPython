import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from src.services.file_transfer.thumbnails import THUMBNAIL_SIZE, is_image, thumbnail

SAMPLE_PHOTO = Path(__file__).resolve().parent.parent / "assets" / "metroidzm_map.jpg"


def pixel_size(path: Path) -> tuple[int, int]:
    output = subprocess.run(
        ["sips", "-g", "pixelWidth", "-g", "pixelHeight", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout
    values = [int(line.split(":")[1]) for line in output.splitlines() if "pixel" in line]
    return values[0], values[1]


class IsImageTests(unittest.TestCase):
    def test_recognises_photo_types_case_insensitively(self) -> None:
        for name in ["a.jpg", "b.JPEG", "IMG_0140.HEIC", "c.png", "d.webp"]:
            self.assertTrue(is_image(name), name)
        for name in ["data.csv", "notes.txt", "movie.mov", "jpg"]:
            self.assertFalse(is_image(name), name)


@unittest.skipUnless(shutil.which("sips"), "needs macOS sips")
class ThumbnailTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.root = Path(self._temp.name)
        self.cache = self.root / "cache"
        self.photo = self.root / "photo.jpg"
        shutil.copy(SAMPLE_PHOTO, self.photo)

    def tearDown(self) -> None:
        self._temp.cleanup()

    def test_makes_a_small_jpeg_and_reuses_it(self) -> None:
        preview = thumbnail(self.photo, self.cache)
        self.assertIsNotNone(preview)
        self.assertLessEqual(max(pixel_size(preview)), THUMBNAIL_SIZE)
        self.assertLess(preview.stat().st_size, self.photo.stat().st_size)
        made_at = preview.stat().st_mtime_ns
        self.assertEqual(thumbnail(self.photo, self.cache), preview)
        self.assertEqual(preview.stat().st_mtime_ns, made_at)
        self.assertEqual([p.name for p in self.cache.iterdir()], [preview.name])

    def test_a_replaced_photo_gets_a_new_preview(self) -> None:
        first = thumbnail(self.photo, self.cache)
        subprocess.run(
            ["sips", "-r", "90", str(self.photo)], capture_output=True, check=True
        )
        second = thumbnail(self.photo, self.cache)
        self.assertNotEqual(first, second)

    def test_heic_photos_get_jpeg_previews(self) -> None:
        heic = self.root / "IMG_0001.HEIC"
        subprocess.run(
            ["sips", "-s", "format", "heic", str(self.photo), "--out", str(heic)],
            capture_output=True, check=True,
        )
        preview = thumbnail(heic, self.cache)
        self.assertIsNotNone(preview)
        self.assertEqual(preview.read_bytes()[:2], b"\xff\xd8")

    def test_unreadable_images_get_no_preview_and_leave_nothing(self) -> None:
        broken = self.root / "broken.jpg"
        broken.write_text("not an image")
        self.assertIsNone(thumbnail(broken, self.cache))
        self.assertEqual(list(self.cache.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
