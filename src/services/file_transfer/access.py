"""Who may download and upload: the host's two switches and the code."""

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


class AccessControl:
    """The host's two switches, and the code that unlocks the share.

    With the code off, anyone on the network can download, and upload too
    when uploads are allowed. With it on, devices only see the file list
    until they enter the code; then they can download, and upload when
    allowed. The code is read from Firestore when the switch is turned on, so
    a changed code applies the next time it is. A device that enters it gets
    a cookie for the rest of the session; turning the switch off signs every
    device out.
    """

    def __init__(self, load_code: Callable[[], str]) -> None:
        self._load_code = load_code
        self._lock = threading.Lock()
        self.uploads_enabled = False
        self.code_required = False
        self.code = ""
        self.token = ""

    def configure(self, allow_uploads: bool, require_code: bool) -> None:
        with self._lock:
            if require_code and not self.code_required:
                # Raises UploadCodeError, changing nothing, when no code is set.
                self.code = self._load_code()
                self.token = secrets.token_urlsafe(32)
            elif not require_code:
                self.code = self.token = ""
            self.code_required = require_code
            self.uploads_enabled = allow_uploads

    def unlock(self, code: str) -> str | None:
        """The session token for a correct code; None otherwise."""

        with self._lock:
            if self.code_required and hmac.compare_digest(code.strip(), self.code):
                return self.token
            return None

    def unlocked(self, token: str | None) -> bool:
        """Whether a device may download, and upload when uploads are on."""

        with self._lock:
            if not self.code_required:
                return True
            return bool(token) and hmac.compare_digest(token, self.token)
