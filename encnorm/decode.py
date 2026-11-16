"""Decode one page using declarations, BOM, probing and line fallbacks."""

from .bom import has_utf8_bom, strip_utf8_bom
from .httpheader import normalize_charset
from .meta import find_meta_charset
from .mojibake import repair_mojibake
from .probe import PROBE_CHARSETS, probe_bytes


def determine_declared_charset(raw, http_charset):
    """Resolve a declared charset with HTTP header priority over meta."""
    header_charset = normalize_charset(http_charset)
    if header_charset:
        return header_charset
    return find_meta_charset(raw)


def decode_page(raw, http_charset=""):
    """Decode raw page bytes and return all facts needed by the report.

    The result contains the canonical declaration, the actually used
    charset expression, repaired text, repair flag and a deterministic issue
    description.
    """
    declared = determine_declared_charset(raw, http_charset)

    if declared:
        selected = declared
        payload = raw
    elif has_utf8_bom(raw):
        selected = "utf-8"
        payload = strip_utf8_bom(raw)
    else:
        selected = probe_bytes(raw)
        payload = raw

    text, fallback_charsets, fallback_line_count, issue_parts = _decode_payload(
        payload, selected
    )
    repaired_text, repaired = repair_mojibake(text)
    total_lines = len(payload.splitlines(keepends=True))
    used_charset = _build_used_charset(
        selected, fallback_charsets, fallback_line_count, total_lines
    )

    return {
        "declared_charset": declared,
        "used_charset": used_charset,
        "text": repaired_text,
        "repaired": repaired,
        "issue": "; ".join(issue_parts),
    }


def _decode_payload(payload, selected):
    try:
        return payload.decode(selected, errors="strict"), [], 0, []
    except UnicodeDecodeError:
        return _decode_line_by_line(payload, selected)


def _decode_line_by_line(payload, selected):
    parts = []
    fallback_charsets = []
    fallback_line_count = 0
    issue_parts = []

    for line_number, line in enumerate(payload.splitlines(keepends=True), start=1):
        try:
            parts.append(line.decode(selected, errors="strict"))
            continue
        except UnicodeDecodeError:
            pass

        decoded_line, fallback = _decode_with_fallback(line)
        if fallback is None:
            parts.append(line.decode("latin-1", errors="replace"))
            issue_parts.append(
                "line {} could not be decoded; raw bytes retained".format(line_number)
            )
            continue

        parts.append(decoded_line)
        fallback_line_count += 1
        if fallback not in fallback_charsets:
            fallback_charsets.append(fallback)
        issue_parts.append(
            "line {} decoded with fallback charset {}".format(line_number, fallback)
        )

    return "".join(parts), fallback_charsets, fallback_line_count, issue_parts


def _decode_with_fallback(line):
    for charset in PROBE_CHARSETS:
        try:
            return line.decode(charset, errors="strict"), charset
        except UnicodeDecodeError:
            continue
    return None, None


def _build_used_charset(
    selected, fallback_charsets, fallback_line_count, total_lines
):
    if not fallback_charsets:
        return selected
    if total_lines > 0 and fallback_line_count == total_lines:
        return "+".join(fallback_charsets)
    return "{}+{}".format(selected, "+".join(fallback_charsets))
