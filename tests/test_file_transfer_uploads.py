import unittest
from types import SimpleNamespace

from src.services.file_transfer.uploads import (
    UploadAccess,
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


class UploadAccessTests(unittest.TestCase):
    def test_off_until_enabled(self) -> None:
        access = UploadAccess(lambda: "0427")
        self.assertFalse(access.enabled)
        self.assertIsNone(access.unlock("0427"))

    def test_correct_code_returns_a_session_token(self) -> None:
        access = UploadAccess(lambda: "0427")
        access.set_enabled(True)
        self.assertEqual(access.code, "0427")
        self.assertIsNone(access.unlock("1111"))
        token = access.unlock(" 0427 ")
        self.assertTrue(access.allows(token))
        self.assertFalse(access.allows("forged"))
        self.assertFalse(access.allows(None))

    def test_missing_code_leaves_uploads_off(self) -> None:
        def no_code() -> str:
            raise UploadCodeError("not set")

        access = UploadAccess(no_code)
        with self.assertRaises(UploadCodeError):
            access.set_enabled(True)
        self.assertFalse(access.enabled)
        self.assertEqual(access.code, "")

    def test_code_changes_apply_when_uploads_are_turned_on_again(self) -> None:
        codes = iter(["0427", "9051"])
        access = UploadAccess(lambda: next(codes))
        access.set_enabled(True)
        token = access.unlock("0427")
        access.set_enabled(True)
        self.assertEqual(access.code, "0427")
        access.set_enabled(False)
        self.assertFalse(access.allows(token))
        access.set_enabled(True)
        self.assertEqual(access.code, "9051")
        self.assertFalse(access.allows(token))


if __name__ == "__main__":
    unittest.main()
