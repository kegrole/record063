"""Command-line entry point for encnorm."""

import argparse

from .report import run


def build_parser():
    parser = argparse.ArgumentParser(
        description="Normalize HTML page encodings and emit a JSON report."
    )
    parser.add_argument("--dir", default="demo/pages", help="page input directory")
    parser.add_argument(
        "--manifest", default="demo/manifest.json", help="source manifest JSON"
    )
    parser.add_argument("--out", required=True, help="output report JSON path")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    report, output_dir = run(args.dir, args.manifest, args.out)
    summary = report["summary"]
    print(
        "pages={files} repaired={repaired} issues={issues} normalized_dir={path}".format(
            files=summary["files"],
            repaired=summary["repaired"],
            issues=summary["issues"],
            path=output_dir,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
