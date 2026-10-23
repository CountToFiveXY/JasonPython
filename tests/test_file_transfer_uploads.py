import unittest

from src.services.file_transfer.config import MAX_CODE_FAILURES
from src.services.file_transfer.uploads import UploadAccess


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


if __name__ == "__main__":
    unittest.main()
