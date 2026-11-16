"""Reverse text that was already misread through a single-byte codec.

A candidate is accepted only when all three conditions hold:

1. the current text can be encoded with the candidate codec;
2. the resulting bytes decode strictly as UTF-8;
3. the decoded text differs from the current text.

Candidates are tried in the fixed order Latin-1 then GBK, and the first
successful candidate is used.  Normal text fails at least one condition and is
therefore left untouched.
"""

REVERSAL_CANDIDATES = ("latin-1", "gbk")


def try_reverse(text, charset):
    """Attempt one reversal candidate; return repaired text or ``None``."""
    try:
        encoded = text.encode(charset, errors="strict")
        repaired = encoded.decode("utf-8", errors="strict")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return None
    if repaired == text:
        return None
    return repaired


def repair_mojibake(text):
    """Repair reversible mojibake, returning ``(repaired_text, changed)``."""
    for charset in REVERSAL_CANDIDATES:
        repaired = try_reverse(text, charset)
        if repaired is not None:
            return repaired, True
    return text, False
