"""Strict raw-byte charset probing.

The probe order is part of the public contract: UTF-8 first, then GBK, then
Big5, and only as a last resort Latin-1 (which always succeeds because every
byte maps to one code point).
"""

PROBE_CHARSETS = ("utf-8", "gbk", "big5", "latin-1")


def probe_bytes(raw):
    """Return the first charset that strictly decodes all of ``raw``."""
    for charset in PROBE_CHARSETS:
        try:
            raw.decode(charset, errors="strict")
        except UnicodeDecodeError:
            continue
        return charset
    raise RuntimeError("latin-1 fallback must always decode successfully")


def decode_with_probe(raw):
    """Probe ``raw`` and return a ``(text, charset)`` tuple."""
    charset = probe_bytes(raw)
    return raw.decode(charset, errors="strict"), charset
