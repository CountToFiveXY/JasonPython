"""The upload code devices enter, and the cookie that remembers them."""

import hmac
import re
import secrets
import threading
from collections.abc import Callable

from google.cloud.firestore_v1 import Client as FirestoreClient

from src.services.file_transfer.config import (
    UPLOAD_CODE_COLLECTION,
    UPLOAD_CODE_DOCUMENT,
    UPLOAD_CODE_FIELD,
)

UPLOAD_CODE_PATH = f"{UPLOAD_CODE_COLLECTION}/{UPLOAD_CODE_DOCUMENT}"


class UploadCodeError(RuntimeError):
    """The upload code could not be read, so uploads cannot be turned on."""


def read_upload_code(firestore: FirestoreClient) -> str:
    """The fixed 4-digit code kept in Firestore, which the owner edits by hand."""

    try:
        snapshot = (
            firestore.collection(UPLOAD_CODE_COLLECTION)
            .document(UPLOAD_CODE_DOCUMENT)
            .get()
        )
    except Exception as exc:
        raise UploadCodeError(
            f"Could not read the upload code from Firestore ({UPLOAD_CODE_PATH}): {exc}"
        ) from exc
    code = (snapshot.to_dict() or {}).get(UPLOAD_CODE_FIELD)
    # A number field would drop leading zeros, so the code must be text.
    if not isinstance(code, str) or not re.fullmatch(r"\d{4}", code):
        raise UploadCodeError(
            f"Set {UPLOAD_CODE_FIELD} in Firestore {UPLOAD_CODE_PATH} to a "
            "4-digit string, such as \"0427\", to allow uploads."
        )
    return code


class UploadAccess:
    """Whether uploads are on, and the code devices enter to unlock them.

    The code is read when uploads are turned on, so a code changed in
    Firestore applies the next time they are. A device that enters it gets a
    cookie holding a random token, so it is asked only once per sharing
    session; turning uploads off signs every device out.
    """

    def __init__(self, load_code: Callable[[], str]) -> None:
        self._load_code = load_code
        self._lock = threading.Lock()
        self.enabled = False
        self.code = ""
        self.token = ""

    def set_enabled(self, enabled: bool) -> None:
        with self._lock:
            if enabled and not self.enabled:
                # Raises UploadCodeError, leaving uploads off, when no code is set.
                self.code = self._load_code()
                self.token = secrets.token_urlsafe(32)
            elif not enabled:
                self.code = self.token = ""
            self.enabled = enabled

    def unlock(self, code: str) -> str | None:
        """The session token for a correct code; None otherwise."""

        with self._lock:
            if self.enabled and hmac.compare_digest(code.strip(), self.code):
                return self.token
            return None

    def allows(self, token: str | None) -> bool:
        with self._lock:
            return self.enabled and bool(token) and hmac.compare_digest(token, self.token)
