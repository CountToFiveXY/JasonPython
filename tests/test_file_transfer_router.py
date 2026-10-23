import unittest
from types import SimpleNamespace

from fastapi import HTTPException

from src.routers.file_transfer import require_local_client


class LocalClientTests(unittest.TestCase):
    def test_allows_this_computer(self) -> None:
        for host in ["127.0.0.1", "::1"]:
            require_local_client(SimpleNamespace(client=SimpleNamespace(host=host)))

    def test_rejects_other_devices(self) -> None:
        for client in [SimpleNamespace(host="192.168.1.20"), None]:
            with self.assertRaises(HTTPException) as error:
                require_local_client(SimpleNamespace(client=client))
            self.assertEqual(error.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
