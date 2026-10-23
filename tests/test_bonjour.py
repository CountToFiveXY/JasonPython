import shutil
import time
import unittest
import uuid

from src.infrastructure.bonjour import BonjourAnnouncer, HostNameInUseError


@unittest.skipUnless(shutil.which("dns-sd"), "needs macOS Bonjour")
class BonjourAnnouncerTests(unittest.TestCase):
    def test_second_claim_on_the_same_name_is_refused(self) -> None:
        name = f"jasonapp-test-{uuid.uuid4().hex[:8]}.local"
        first, second = BonjourAnnouncer(name), BonjourAnnouncer(name)
        try:
            self.assertTrue(first.claim("192.0.2.10", 80))
            self.assertTrue(first.is_active)
            # Bonjour on one Mac can miss a clash started the same instant
            # the first name goes live; a person pressing Start is never that fast.
            time.sleep(1)
            with self.assertRaises(HostNameInUseError):
                second.claim("192.0.2.11", 80)
            self.assertFalse(second.is_active)
        finally:
            first.release()
            second.release()
        self.assertFalse(first.is_active)


if __name__ == "__main__":
    unittest.main()
