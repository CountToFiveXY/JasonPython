import unittest
from types import SimpleNamespace

from src.services.file_transfer.access import (
    AccessControl,
    UploadCodeError,
    read_upload_code,
)


def fake_firestore(fields: dict | None = None, error: Exception | None = None):
    """A Firestore stand-in holding config/file_transfer."""

    def get():
        if error is not None:
            raise error
        return SimpleNamespace(to_dict=lambda: fields)

    def document(name):
        assert name == "file_transfer"
        return SimpleNamespace(get=get)

    def collection(name):
        assert name == "config"
        return SimpleNamespace(document=document)

    return SimpleNamespace(collection=collection)


class ReadUploadCodeTests(unittest.TestCase):
    def test_reads_a_four_digit_string(self) -> None:
        self.assertEqual(read_upload_code(fake_firestore({"upload_code": "0427"})), "0427")

    def test_rejects_codes_that_are_not_four_digit_text(self) -> None:
        # A number field loses leading zeros, so it is refused rather than guessed.
        for fields in [None, {}, {"upload_code": 427}, {"upload_code": "12345"}, {"upload_code": "12a4"}]:
            with self.assertRaises(UploadCodeError, msg=repr(fields)) as error:
                read_upload_code(fake_firestore(fields))
            self.assertIn("config/file_transfer", str(error.exception))

    def test_reports_firestore_failures(self) -> None:
        with self.assertRaises(UploadCodeError) as error:
            read_upload_code(fake_firestore(error=RuntimeError("offline")))
        self.assertIn("offline", str(error.exception))


class AccessControlTests(unittest.TestCase):
    def test_open_by_default(self) -> None:
        access = AccessControl(lambda: "0427")
        self.assertFalse(access.uploads_enabled)
        self.assertFalse(access.code_required)
        self.assertTrue(access.unlocked(None))
        self.assertIsNone(access.unlock("0427"))

    def test_required_code_returns_a_session_token(self) -> None:
        access = AccessControl(lambda: "0427")
        access.configure(allow_uploads=False, require_code=True)
        self.assertEqual(access.code, "0427")
        self.assertFalse(access.unlocked(None))
        self.assertIsNone(access.unlock("1111"))
        token = access.unlock(" 0427 ")
        self.assertTrue(access.unlocked(token))
        self.assertFalse(access.unlocked("forged"))

    def test_uploads_switch_does_not_touch_the_code(self) -> None:
        access = AccessControl(lambda: "0427")
        access.configure(allow_uploads=False, require_code=True)
        token = access.unlock("0427")
        access.configure(allow_uploads=True, require_code=True)
        self.assertTrue(access.uploads_enabled)
        self.assertTrue(access.unlocked(token))

    def test_missing_code_changes_nothing(self) -> None:
        def no_code() -> str:
            raise UploadCodeError("not set")

        access = AccessControl(no_code)
        access.configure(allow_uploads=True, require_code=False)
        with self.assertRaises(UploadCodeError):
            access.configure(allow_uploads=False, require_code=True)
        self.assertTrue(access.uploads_enabled)
        self.assertFalse(access.code_required)
        self.assertEqual(access.code, "")

    def test_code_changes_apply_when_the_code_is_required_again(self) -> None:
        codes = iter(["0427", "9051"])
        access = AccessControl(lambda: next(codes))
        access.configure(False, True)
        token = access.unlock("0427")
        access.configure(False, True)
        self.assertEqual(access.code, "0427")
        access.configure(False, False)
        self.assertTrue(access.unlocked(None))
        access.configure(False, True)
        self.assertEqual(access.code, "9051")
        self.assertFalse(access.unlocked(token))

if __name__ == "__main__":
    unittest.main()
