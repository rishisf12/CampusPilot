"""Phase 9 — Downloads library skeleton verified."""
from features.mail.downloads.library import DownloadItem


def test_download_item_exists():
    item = DownloadItem(filename="circular.pdf", source_section="academics")
    assert item.filename == "circular.pdf"
