import ipaddress
import re
import socket
from typing import Optional

import aioimaplib

from app.core.config import settings
from app.core.crypto import decrypt_credential

# --- SSRF guard ---
_PRIVATE_NETS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("224.0.0.0/4"),
]


def _is_private_host(host: str) -> bool:
    """Return True if host resolves to a private/link-local/multicast address."""
    try:
        host_port = host.split(":")[0]
        try:
            ip = ipaddress.ip_address(host_port)
            return any(ip in net for net in _PRIVATE_NETS)
        except ValueError:
            pass
        infos = socket.getaddrinfo(host_port, None)
        for info in infos:
            addr = info[4][0]
            try:
                ip = ipaddress.ip_address(addr)
                if any(ip in net for net in _PRIVATE_NETS):
                    return True
            except ValueError:
                continue
        return False
    except Exception:
        return not settings.ALLOW_PRIVATE_MAIL_HOSTS


def validate_mail_host(host: str, port: int) -> None:
    """Raise ValueError if host is private and ALLOW_PRIVATE_MAIL_HOSTS is false."""
    if not settings.ALLOW_PRIVATE_MAIL_HOSTS and _is_private_host(host):
        raise ValueError(
            f"Private mail host '{host}' not allowed. Set ALLOW_PRIVATE_MAIL_HOSTS=true to enable (dev only)."
        )

# --- Capability detection ---
_CAPABILITY_KEYWORDS = (
    "IDLE", "CONDSTORE", "QRESYNC", "SORT", "THREAD", "MOVE", "SPECIAL-USE",
    "UTF8=ACCEPT", "IMAP4REV2", "LOGIN-REFERRALS",
)


def detect_capabilities(capabilities_line: str) -> list:
    """Parse IMAP CAPABILITY response and return known supported capabilities."""
    caps = capabilities_line.upper().split()
    found = [c for c in _CAPABILITY_KEYWORDS if c in caps]
    return sorted(set(found))


# --- IMAP client wrapper ---
class ImapClient:
    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        security: str = "ssl",
        timeout: int = 30,
    ):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.security = security
        self.timeout = timeout
        self._imap: Optional[aioimaplib.IMAP4_SSL] = None

    async def connect(self) -> None:
        validate_mail_host(self.host, self.port)
        if self.security == "ssl":
            self._imap = aioimaplib.IMAP4_SSL(
                host=self.host, port=self.port, timeout=self.timeout
            )
        elif self.security == "starttls":
            self._imap = aioimaplib.IMAP4(
                host=self.host, port=self.port, timeout=self.timeout
            )
            await self._imap.starttls()
        elif self.security == "none":
            self._imap = aioimaplib.IMAP4(
                host=self.host, port=self.port, timeout=self.timeout
            )
        else:
            raise ValueError(f"Unsupported IMAP security: {self.security}")
        await self._imap.login(self.username, self.password)

    async def capabilities(self) -> list:
        if not self._imap:
            raise RuntimeError("Not connected")
        typ, data = await self._imap.capability()
        line = " ".join(d.decode() if isinstance(d, bytes) else str(d) for d in data)
        return detect_capabilities(line)

    async def list_folders(self) -> list:
        """Return list of (delimiter, folder_name)."""
        if not self._imap:
            raise RuntimeError("Not connected")
        typ, data = await self._imap.list()
        folders: list = []
        if typ == "OK":
            for line in data:
                s = line.decode() if isinstance(line, bytes) else str(line)
                match = re.search(r'"([^"]*)"\s+"(.+)"$', s)
                if match:
                    delimiter = match.group(1)
                    name = match.group(2)
                    folders.append((delimiter, name))
        return folders

    async def select(self, folder: str = "INBOX") -> dict:
        if not self._imap:
            raise RuntimeError("Not connected")
        typ, data = await self._imap.select(folder)
        info: dict = {}
        if typ == "OK" and data:
            info["raw"] = data[0].decode() if isinstance(data[0], bytes) else str(data[0])
        return info

    async def status(self, folder: str, items: str = "(UIDNEXT UIDVALIDITY MESSAGES UNSEEN)") -> dict:
        if not self._imap:
            raise RuntimeError("Not connected")
        typ, data = await self._imap.status(folder, items)
        return {"typ": typ, "data": [d.decode() if isinstance(d, bytes) else str(d) for d in data]}

    async def idle(self, timeout: int = 29 * 60):
        """Begin IMAP IDLE on the currently selected folder. Yields untagged responses."""
        if not self._imap:
            raise RuntimeError("Not connected")
        await self._imap.idle_start()
        try:
            while True:
                line = await self._imap.idle_check(timeout=timeout)
                if line is None:
                    return
                yield line
        finally:
            await self._imap.idle_done()

    async def logout(self) -> None:
        if self._imap:
            try:
                await self._imap.logout()
            except Exception:
                pass
            self._imap = None


async def test_imap_connection(
    host: str,
    port: int,
    username: str,
    password: str,
    security: str = "ssl",
) -> dict:
    """Test an IMAP connection. Returns {ok, capabilities, message}."""
    client = ImapClient(host, port, username, password, security=security)
    try:
        await client.connect()
        caps = await client.capabilities()
        await client.logout()
        return {"ok": True, "imap_capabilities": caps, "message": "IMAP connection successful"}
    except Exception as exc:  # noqa: BLE001
        try:
            await client.logout()
        except Exception:
            pass
        return {"ok": False, "imap_capabilities": None, "message": str(exc)}
