"""Find an HTML ``meta`` charset declaration inside the first 1024 bytes."""

import re

from .httpheader import normalize_charset

_META_RE = re.compile(rb"<meta[^>]*>", re.IGNORECASE | re.DOTALL)
_CHARSET_ATTR_RE = re.compile(
    rb'''charset\s*=\s*["']?\s*([^"'\s/>]+)''', re.IGNORECASE
)
_HTTP_EQUIV_RE = re.compile(
    rb'''http-equiv\s*=\s*["']?\s*content-type["']?''', re.IGNORECASE
)
_CONTENT_RE = re.compile(
    rb'''content\s*=\s*(["'])(.*?)\1''', re.IGNORECASE | re.DOTALL
)
_CONTENT_CHARSET_RE = re.compile(
    rb'''charset\s*=\s*([^"'\s;]+)''', re.IGNORECASE
)


def find_meta_charset(raw, limit=1024):
    """Return the canonical charset declared by a meta tag, else ``""``.

    Both ``<meta charset="...">`` and
    ``<meta http-equiv="Content-Type" content="text/html; charset=...">``
    are supported.  The search is intentionally byte-based and ASCII-only so
    it works before the page has been decoded.  The first recognizable
    declaration wins; an unrecognizable name is ignored and scanning
    continues, mirroring the rule for an absent declaration.
    """
    prefix = raw[:limit]
    for tag in _META_RE.findall(prefix):
        charset = _attr_charset(tag)
        if charset:
            return charset
        if _HTTP_EQUIV_RE.search(tag):
            content_match = _CONTENT_RE.search(tag)
            if content_match:
                charset_match = _CONTENT_CHARSET_RE.search(content_match.group(2))
                if charset_match:
                    charset = normalize_charset(charset_match.group(1).decode("ascii", "ignore"))
                    if charset:
                        return charset
    return ""


def _attr_charset(tag):
    match = _CHARSET_ATTR_RE.search(tag)
    if not match:
        return ""
    return normalize_charset(match.group(1).decode("ascii", "ignore"))
