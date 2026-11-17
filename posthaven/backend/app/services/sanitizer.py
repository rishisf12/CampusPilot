"""HTML sanitizer: nh3 allow-list + remote-content classifier."""
import re
import nh3


ALLOWED_TAGS = {
    "a", "abbr", "acronym", "address", "area", "article", "aside", "audio",
    "b", "bdi", "bdo", "big", "blockquote", "br", "button", "caption", "center",
    "cite", "code", "col", "colgroup", "data", "datalist", "dd", "del", "details",
    "dfn", "div", "dl", "dt", "em", "embed", "fieldset", "figcaption", "figure",
    "font", "footer", "form", "h1", "h2", "h3", "h4", "h5", "h6", "header", "hgroup",
    "hr", "i", "img", "input", "ins", "kbd", "label", "legend", "li", "map", "mark",
    "menu", "meter", "nav", "object", "ol", "optgroup", "option", "output", "p",
    "picture", "pre", "progress", "q", "rp", "rt", "ruby", "s", "samp", "slot",
    "small", "source", "span", "strike", "strong", "style", "sub", "summary",
    "sup", "table", "tbody", "td", "textarea", "tfoot", "th", "thead", "time",
    "tr", "track", "tt", "u", "ul", "var", "video", "wbr",
}

ALLOWED_ATTRIBUTES = {
    "a": ["href", "title", "target", "rel"],
    "img": ["src", "alt", "title", "width", "height"],
    "div": ["class", "id", "style"],
    "span": ["class", "id", "style"],
    "td": ["colspan", "rowspan", "align", "valign"],
    "th": ["colspan", "rowspan", "align", "valign"],
    "table": ["border", "cellpadding", "cellspacing", "width"],
    "*": ["class", "id", "style", "title"],
}

ALLOWED_URL_SCHEMES = {"http", "https", "mailto", "cid"}


def sanitize_html(html_content: str) -> str:
    """Sanitize HTML email content: strip scripts/forms/event handlers, allow-list tags."""
    return nh3.clean(
        html_content or "",
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        url_schemes=ALLOWED_URL_SCHEMES,
    )


def classify_remote_content(html_content: str) -> bool:
    """Return True if HTML contains remote content (external images, etc.) that should be blocked."""
    if not html_content:
        return False
    # Look for <img src="http..."> not cid:
    return bool(re.search(r'<img[^>]+src=["\'](?!(cid:|data:))[^"\']+', html_content, re.IGNORECASE))
