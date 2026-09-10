import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
from google.auth.exceptions import DefaultCredentialsError

from src.infrastructure.clients import get_firestore


class ClientDependencyTests(unittest.TestCase):
    def test_missing_firestore_credentials_returns_service_unavailable(self) -> None:
        request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))

        with (
            patch("src.infrastructure.clients.firebase_admin.get_app", return_value=object()),
            patch(
                "src.infrastructure.clients.firestore.client",
                side_effect=DefaultCredentialsError("credentials missing"),
            ),
            self.assertRaises(HTTPException) as raised,
        ):
            get_firestore(request)

        self.assertEqual(raised.exception.status_code, 503)
        self.assertIn("GOOGLE_APPLICATION_CREDENTIALS", raised.exception.detail)


if __name__ == "__main__":
    unittest.main()
