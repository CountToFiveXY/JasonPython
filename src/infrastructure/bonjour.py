"""This Mac's LAN address, and announcing a .local name for it with Bonjour."""

import os
import selectors
import shutil
import socket
import subprocess
import threading
import time


class HostNameInUseError(RuntimeError):
    """Another device on the network is already sharing under the name."""

    def __init__(self, host_name: str, owner: str | None) -> None:
        self.host_name = host_name
        self.owner = owner
        where = f" from {owner}" if owner else " from another device"
        super().__init__(
            f"{host_name} is already being shared{where}. Stop sharing there first."
        )


def lan_address() -> str | None:
    """The IPv4 address other devices on the LAN use to reach this computer.

    Prefers the Wi-Fi or Ethernet interface (en*, bridge*) so a VPN tunnel,
    which other devices cannot reach, is never chosen.
    """

    for _, name in sorted(socket.if_nameindex(), key=lambda interface: interface[1]):
        if not name.startswith(("en", "bridge")):
            continue
        try:
            result = subprocess.run(
                ["ipconfig", "getifaddr", name],
                capture_output=True,
                text=True,
                timeout=2,
            )
        except (OSError, subprocess.TimeoutExpired):
            break
        address = result.stdout.strip()
        # 169.254.x.x is a self-assigned address with no working network.
        if address and not address.startswith("169.254."):
            return address
    return _default_route_address()


def _default_route_address() -> str | None:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        try:
            # Connecting a UDP socket only picks the outgoing interface;
            # no packet is sent.
            probe.connect(("192.0.2.1", 9))
            address = probe.getsockname()[0]
        except OSError:
            return None
    return None if address.startswith(("127.", "0.")) else address


# Runs dns-sd and kills it once the pipe from this process closes, which
# also happens if the API crashes or is force-quit. Without it an orphaned
# dns-sd would keep claiming the name and lock out every other Mac.
_TIED_TO_PARENT = (
    'exec 3<&0; dns-sd "$@" </dev/null & child=$!; '
    '{ read -r _ <&3; kill "$child" 2>/dev/null; } & '
    'wait "$child"'
)


class BonjourAnnouncer:
    """Announces a .local name for this Mac through macOS's own Bonjour service.

    Bonjour lets only one device own a name, so a second Mac that tries to
    share is refused instead of silently taking over the address.
    """

    def __init__(self, host_name: str, timeout: float = 5) -> None:
        self.host_name = host_name
        self._timeout = timeout
        self._process: subprocess.Popen[bytes] | None = None

    @property
    def is_active(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def claim(self, address: str, port: int) -> bool:
        """Announce the name; False when Bonjour is unavailable on this system."""

        self.release()
        if shutil.which("dns-sd") is None:
            return False
        try:
            process = subprocess.Popen(
                [
                    "/bin/sh", "-c", _TIED_TO_PARENT, "dns-sd",
                    "-P", "JasonApp Files", "_http._tcp", "local",
                    str(port), self.host_name, address,
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        except OSError:
            return False
        assert process.stdout is not None
        record = f"record {self.host_name}:"
        output = ""
        in_use = False
        deadline = time.monotonic() + self._timeout
        with selectors.DefaultSelector() as selector:
            # Read the raw pipe: a buffered readline() can hold the reply in
            # Python's buffer while select() waits for data that already came.
            selector.register(process.stdout, selectors.EVENT_READ)
            while (remaining := deadline - time.monotonic()) > 0:
                if not selector.select(remaining):
                    continue
                chunk = os.read(process.stdout.fileno(), 4096)
                if not chunk:
                    break
                output += chunk.decode("utf-8", "replace")
                replies = [line for line in output.splitlines() if record in line]
                if any("Name now registered" in line for line in replies):
                    self._process = process
                    # Keep draining output so dns-sd never blocks on a full pipe.
                    threading.Thread(
                        target=process.stdout.read,
                        name="file-transfer-bonjour",
                        daemon=True,
                    ).start()
                    return True
                if any("Name in use" in line for line in replies):
                    in_use = True
                    break
        self._end(process)
        if in_use:
            raise HostNameInUseError(self.host_name, self._current_owner())
        # Bonjour did not answer in time; devices can still use the IP address.
        return False

    def release(self) -> None:
        process, self._process = self._process, None
        if process is not None:
            self._end(process)

    @staticmethod
    def _end(process: subprocess.Popen[bytes]) -> None:
        """Withdraw the name: closing the pipe makes the wrapper stop dns-sd."""

        if process.stdin is not None:
            process.stdin.close()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            # The wrapper and dns-sd share a session of their own.
            try:
                os.killpg(process.pid, 9)
            except ProcessLookupError:
                pass
            process.wait()

    def _current_owner(self) -> str | None:
        try:
            return socket.gethostbyname(self.host_name)
        except OSError:
            return None
