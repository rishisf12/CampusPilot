"""Phase 6 — Search & filters: query parser skeleton verified."""
from features.mail.search import SearchParser


def test_parser_reads_operators():
    p = SearchParser("from:tnp is:unread has:attachment internship")
    assert p.unread_filter() is True
    assert p.has_attachment_filter() is True
    assert "internship" in p.text_keywords()


def test_parser_empty():
    p = SearchParser("")
    assert p.text_keywords() == []
    assert p.unread_filter() is False
