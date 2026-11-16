"""Build deterministic reports and normalized UTF-8 text files."""

import json
import shutil
from pathlib import Path

from .decode import decode_page

PAGE_FIELDS = ("file", "declared_charset", "used_charset", "repaired", "issue")
SUMMARY_FIELDS = ("files", "ok", "repaired", "issues")


def load_manifest(manifest_path):
    """Load the page list from a manifest JSON file."""
    with open(manifest_path, "r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    return manifest["pages"]


def normalize_pages(pages_dir, manifest_pages):
    """Decode every manifest page and return report page records."""
    directory = Path(pages_dir)
    records = []
    for entry in manifest_pages:
        file_name = entry["file"]
        with open(directory / file_name, "rb") as handle:
            raw = handle.read()
        result = decode_page(raw, entry.get("http_charset", ""))
        records.append(
            {
                "file": file_name,
                "declared_charset": result["declared_charset"],
                "used_charset": result["used_charset"],
                "repaired": result["repaired"],
                "issue": result["issue"],
                "_text": result["text"],
            }
        )
    return records


def write_report(records, out_path):
    """Write normalized text files and the JSON report; return the report."""
    out_path = Path(out_path)
    output_dir = out_path.parent / "normalized"
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    pages = []
    for record in records:
        target = output_dir / (record["file"] + ".txt")
        with open(target, "wb") as handle:
            handle.write(record["_text"].encode("utf-8", errors="strict"))
        pages.append({field: record[field] for field in PAGE_FIELDS})

    summary = {
        "files": len(pages),
        "ok": sum(1 for page in pages if not page["issue"]),
        "repaired": sum(1 for page in pages if page["repaired"]),
        "issues": sum(1 for page in pages if page["issue"]),
    }
    report = {"pages": pages, "summary": {field: summary[field] for field in SUMMARY_FIELDS}}

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2, sort_keys=False)
        handle.write("\n")

    return report, output_dir


def run(pages_dir, manifest_path, out_path):
    """Execute the full pipeline and return ``(report, normalized_dir)``."""
    manifest_pages = load_manifest(manifest_path)
    records = normalize_pages(pages_dir, manifest_pages)
    return write_report(records, out_path)
