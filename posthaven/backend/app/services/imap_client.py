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
            await self._imap.wait_hello_from_server()
        elif self.security == "starttls":
            self._imap = aioimaplib.IMAP4(
                host=self.host, port=self.port, timeout=self.timeout
            )
            await self._imap.wait_hello_from_server()
            await self._imap.starttls()
        elif self.security == "none":
            self._imap = aioimaplib.IMAP4(
                host=self.host, port=self.port, timeout=self.timeout
            )
            await self._imap.wait_hello_from_server()
        else:
            raise ValueError(f"Unsupported IMAP security: {self.security}")
        await self._imap.login(self.username, self.password)

    async def capabilities(self) -> list:
        if not self._imap:
            raise RuntimeError("Not connected")
        return [c for c in _CAPABILITY_KEYWORDS if self._imap.has_capability(c)]

    async def list_folders(self) -> list:
        """Return list of (delimiter, folder_name)."""
        if not self._imap:
            raise RuntimeError("Not connected")
        typ, data = await self._imap.list("\"\"", "*")
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
        """Yield untagged server responses while in IMAP IDLE."""
        if not self._imap:
            raise RuntimeError("Not connected")
        await self._imap.idle_start(timeout=float(timeout))
        try:
            while True:
                resp = await self._imap.wait_server_push(timeout=float(timeout))
                if resp is None:
                    return
                yield str(resp)
        finally:
            try:
                await self._imap.idle_done()
            except Exception:
                pass

    async def create_folder(self, name: str) -> None:
        if not self._imap:
            raise RuntimeError("Not connected")
        await self._imap.create(name)

    async def copy_uids(self, uid_set: str, destination: str) -> bool:
        if not self._imap:
            raise RuntimeError("Not connected")
        typ, _ = await self._imap.uid("copy", uid_set, destination)
        return typ == "OK"

    async def store_uids(self, uid_set: str, add_flags: list[str] | None = None,
                         remove_flags: list[str] | None = None) -> bool:
        if not self._imap:
            raise RuntimeError("Not connected")
        if add_flags:
            typ, _ = await self._imap.uid("store", uid_set, "+FLAGS", f"({' '.join(add_flags)})")
            if typ != "OK":
                return False
        if remove_flags:
            typ, _ = await self._imap.uid("store", uid_set, "-FLAGS", f"({' '.join(remove_flags)})")
            if typ != "OK":
                return False
        return True

    async def move_uids(self, uid_set: str, destination: str) -> bool:
        """Move UIDs to destination. Tries MOVE extension, falls back to COPY+STORE+EXPUNGE."""
        if not self._imap:
            raise RuntimeError("Not connected")
        try:
            typ, _ = await self._imap.uid("move", uid_set, destination)
            if typ == "OK":
                return True
        except Exception:
            pass
        if not await self.copy_uids(uid_set, destination):
            return False
        if not await self.store_uids(uid_set, add_flags=["\\Deleted"]):
            return False
        await self._imap.expunge()
        return True

    async def expunge(self) -> None:
        if not self._imap:
            raise RuntimeError("Not connected")
        await self._imap.expunge()

    async def append(self, mailbox: str, raw: bytes, flags: list[str] | None = None) -> bool:
        if not self._imap:
            raise RuntimeError("Not connected")
        typ, _ = await self._imap.append(raw, mailbox, " ".join(flags) if flags else None)
        return typ == "OK"

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
