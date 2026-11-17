import socket
from typing import Optional

import aiosmtplib

from app.core.config import settings
from app.core.crypto import decrypt_credential


def validate_smtp_host(host: str, port: int) -> None:
    """Raise ValueError if host is private and ALLOW_PRIVATE_MAIL_HOSTS is false."""
    if not settings.ALLOW_PRIVATE_MAIL_HOSTS:
        try:
            ip = socket.gethostbyname(host)
            import ipaddress

            addr = ipaddress.ip_address(ip)
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
            if any(addr in net for net in _PRIVATE_NETS):
                raise ValueError(
                    f"Private SMTP host '{host}' not allowed. Set ALLOW_PRIVATE_MAIL_HOSTS=true to enable (dev only)."
                )
        except ValueError:
            raise
        except Exception:
            pass


async def test_smtp_connection(
    host: str,
    port: int,
    username: str,
    password: str,
    security: str = "ssl",
) -> dict:
    """Test an SMTP connection. Returns {ok, message}."""
    validate_smtp_host(host, port)
    try:
        if security == "ssl":
            smtp = aiosmtplib.SMTP(hostname=host, port=port, use_tls=True, timeout=30)
        elif security == "starttls":
            smtp = aiosmtplib.SMTP(hostname=host, port=port, use_tls=False, timeout=30)
        elif security == "none":
            smtp = aiosmtplib.SMTP(hostname=host, port=port, use_tls=False, timeout=30)
        else:
            return {"ok": False, "message": f"Unsupported SMTP security: {security}"}

        await smtp.connect()
        if security == "starttls":
            await smtp.starttls()
        if username and password:
            await smtp.login(username, password)
        await smtp.quit()
        return {"ok": True, "message": "SMTP connection successful"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "message": str(exc)}
