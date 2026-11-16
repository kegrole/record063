"""Normalize externally declared charset names.

Only the four canonical names used by the project are emitted: ``utf-8``,
``gbk``, ``big5`` and ``latin-1``.  Anything that cannot be recognized is
treated as no declaration at all, so callers receive an empty string.
"""

_CANONICAL = {
    "utf-8": "utf-8",
    "utf8": "utf-8",
    "u8": "utf-8",
    "gbk": "gbk",
    "gb2312": "gbk",
    "gb18030": "gbk",
    "gb-2312": "gbk",
    "gb-18030": "gbk",
    "big5": "big5",
    "big-5": "big5",
    "latin-1": "latin-1",
    "iso-8859-1": "latin-1",
    "iso8859-1": "latin-1",
    "latin1": "latin-1",
}


def normalize_charset(name):
    """Return the canonical lowercase charset name, or ``""`` if unknown."""
    if name is None:
        return ""
    key = str(name).strip().lower().replace("_", "-")
    return _CANONICAL.get(key, "")
