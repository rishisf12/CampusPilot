"""Downloads library: indexed attachments, admin uploads, previews.
Phase 9 skeleton — full indexing and preview deferred."""
from typing import Optional

from pydantic import BaseModel


class DownloadItem(BaseModel):
    filename: str
    source_section: Optional[str] = None
    hash_digest: Optional[str] = None
