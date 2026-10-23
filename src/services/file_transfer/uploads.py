"""The upload code devices enter, and the cookie that remembers them."""

import hmac
import secrets
import threading

from src.services.file_transfer.config import MAX_CODE_FAILURES


class UploadAccess:
    """Whether uploads are on, and the code devices enter to unlock them.

    A device that enters the code gets a cookie holding a random session
    token, so it is asked only once per sharing session. Turning uploads
    off and on again issues a new code and signs every device out.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.enabled = False
        self.code = ""
        self.token = ""
        self._failures = 0

    def set_enabled(self, enabled: bool) -> None:
        with self._lock:
            if enabled and not self.enabled:
                self.code = _new_code()
                self.token = secrets.token_urlsafe(32)
                self._failures = 0
            elif not enabled:
                self.code = self.token = ""
            self.enabled = enabled

    def unlock(self, code: str) -> str | None:
        """The session token for a correct code; None otherwise."""

        with self._lock:
            if not self.enabled:
                return None
            if hmac.compare_digest(code.strip(), self.code):
                self._failures = 0
                return self.token
            self._failures += 1
            if self._failures >= MAX_CODE_FAILURES:
                # Too many guesses: replace the code the host shows.
                self.code = _new_code()
                self._failures = 0
            return None

    def allows(self, token: str | None) -> bool:
        with self._lock:
            return self.enabled and bool(token) and hmac.compare_digest(token, self.token)


def _new_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"
