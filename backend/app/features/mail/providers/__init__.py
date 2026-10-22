"""Mail providers package."""
from features.mail.providers.base import (
    InboundProvider,
    OutboundProvider,
    RawMessage,
    SendResult,
    get_provider,
    list_providers,
    register_provider,
    register_providers,
)

__all__ = [
    "InboundProvider",
    "OutboundProvider",
    "RawMessage",
    "SendResult",
    "get_provider",
    "list_providers",
    "register_provider",
    "register_providers",
]