"""UTF-8 byte-order-mark handling."""

UTF8_BOM = b"\xef\xbb\xbf"


def has_utf8_bom(raw):
    """Return whether ``raw`` begins with the UTF-8 BOM."""
    return raw.startswith(UTF8_BOM)


def strip_utf8_bom(raw):
    """Remove a leading UTF-8 BOM when present; otherwise return ``raw``."""
    return raw[len(UTF8_BOM):] if has_utf8_bom(raw) else raw
