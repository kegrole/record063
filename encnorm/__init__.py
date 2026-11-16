"""encnorm: normalize the encoding of collected HTML pages.

The package only relies on the Python standard library.  Each module owns one
stage of the pipeline: HTTP header normalization, meta discovery, BOM handling,
raw-byte probing, mojibake reversal, line-by-line decoding and reporting.
"""

__all__ = [
    "httpheader",
    "meta",
    "bom",
    "probe",
    "mojibake",
    "decode",
    "report",
    "cli",
]
