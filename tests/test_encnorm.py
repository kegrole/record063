import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from encnorm import bom, decode, httpheader, meta, mojibake, probe, report
from encnorm.cli import main as cli_main


P1 = '<html><head><meta charset="utf-8"></head><body>中文一</body></html>'
P2 = '<html><head><meta charset="utf-8"></head><body>中文二</body></html>'
P3 = '<html><body>无声明UTF-8</body></html>'
P4 = '<html><body>无声明GBK</body></html>'
P5 = '<html><body>cafÃ©</body></html>'
P6 = '<html><body>鏁版嵁</body></html>'
P7 = '<html><body>café</body></html>'
P8 = (
    '<html><head><meta charset="utf-8"></head><body>\n'
    '<p>这一行是GBK编码的中文</p>\n'
    '</body></html>'
)
P9 = '<html><body>BOM文件</body></html>'

EXPECTED_MANIFEST = """{
  "pages": [
    {"file": "p1_meta_utf8.html", "http_charset": ""},
    {"file": "p2_header_gbk.html", "http_charset": "GBK"},
    {"file": "p3_probe_utf8.html", "http_charset": ""},
    {"file": "p4_probe_gbk.html", "http_charset": ""},
    {"file": "p5_mojibake_latin1.html", "http_charset": ""},
    {"file": "p6_mojibake_gbk.html", "http_charset": ""},
    {"file": "p7_header_latin1.html", "http_charset": "latin-1"},
    {"file": "p8_bad_declaration.html", "http_charset": ""},
    {"file": "p9_bom_utf8.html", "http_charset": ""}
  ]
}
"""

EXPECTED_FIXTURES = {
    "p1_meta_utf8.html": ("utf-8", P1, b""),
    "p2_header_gbk.html": ("gbk", P2, b""),
    "p3_probe_utf8.html": ("utf-8", P3, b""),
    "p4_probe_gbk.html": ("gbk", P4, b""),
    "p5_mojibake_latin1.html": ("utf-8", P5, b""),
    "p6_mojibake_gbk.html": ("utf-8", P6, b""),
    "p7_header_latin1.html": ("latin-1", P7, b""),
    "p8_bad_declaration.html": ("gbk", P8, b""),
    "p9_bom_utf8.html": ("utf-8", P9, b"\xef\xbb\xbf"),
}


def write_fixtures(pages_dir, manifest_path, manifest_override=None, contents=None):
    pages_dir.mkdir(parents=True, exist_ok=True)
    overrides = contents or {}
    for name, (encoding, text, prefix) in EXPECTED_FIXTURES.items():
        data = overrides.get(name, prefix + text.encode(encoding))
        (pages_dir / name).write_bytes(data)

    manifest = json.loads(EXPECTED_MANIFEST)
    if manifest_override:
        manifest_override(manifest)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest


class EncnormTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.pages_dir = self.temp_dir / "pages"
        self.manifest_path = self.temp_dir / "manifest.json"
        self.out_path = self.temp_dir / "result" / "report.json"
        write_fixtures(self.pages_dir, self.manifest_path)

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def reset_workspace(self):
        shutil.rmtree(self.temp_dir)
        self.temp_dir = Path(tempfile.mkdtemp())
        self.pages_dir = self.temp_dir / "pages"
        self.manifest_path = self.temp_dir / "manifest.json"
        self.out_path = self.temp_dir / "result" / "report.json"

    def run_normalize(self):
        return report.run(self.pages_dir, self.manifest_path, self.out_path)

    def page_by_file(self, result, name):
        return next(page for page in result["pages"] if page["file"] == name)

    def normalized_text(self, normalized_dir, name):
        return (normalized_dir / (name + ".txt")).read_bytes()

    def assertPageFields(self, page):
        self.assertEqual(
            tuple(page.keys()),
            ("file", "declared_charset", "used_charset", "repaired", "issue"),
        )

    def test_criterion_01_fixture_and_manifest_bytes_match_contract(self):
        demo_manifest = (ROOT / "demo" / "manifest.json").read_bytes()
        self.assertEqual(demo_manifest, EXPECTED_MANIFEST.encode("utf-8"))

        for name, (encoding, text, prefix) in EXPECTED_FIXTURES.items():
            expected = prefix + text.encode(encoding)
            actual = (ROOT / "demo" / "pages" / name).read_bytes()
            self.assertEqual(actual, expected, name)

        p8_text = EXPECTED_FIXTURES["p8_bad_declaration.html"][1]
        self.assertEqual(len(p8_text.splitlines()), 3)

    def test_criterion_02_summary_and_repair_issue_counts(self):
        result, _ = self.run_normalize()
        self.assertEqual(
            tuple(result["summary"].keys()),
            ("files", "ok", "repaired", "issues"),
        )
        self.assertEqual(
            result["summary"],
            {"files": 9, "ok": 8, "repaired": 2, "issues": 1},
        )
        repaired = [page["file"] for page in result["pages"] if page["repaired"]]
        issues = [page["file"] for page in result["pages"] if page["issue"]]
        self.assertEqual(
            sorted(repaired),
            ["p5_mojibake_latin1.html", "p6_mojibake_gbk.html"],
        )
        self.assertEqual(issues, ["p8_bad_declaration.html"])
        for page in result["pages"]:
            self.assertPageFields(page)

    def test_criterion_03_p1_meta_utf8(self):
        result, _ = self.run_normalize()
        page = self.page_by_file(result, "p1_meta_utf8.html")
        self.assertEqual(page["declared_charset"], "utf-8")
        self.assertEqual(page["used_charset"], "utf-8")
        self.assertFalse(page["repaired"])
        self.assertEqual(page["issue"], "")

    def test_criterion_04_p2_http_header_beats_meta(self):
        result, output_dir = self.run_normalize()
        page = self.page_by_file(result, "p2_header_gbk.html")
        self.assertEqual(page["declared_charset"], "gbk")
        self.assertEqual(page["used_charset"], "gbk")
        self.assertFalse(page["repaired"])
        self.assertEqual(
            self.normalized_text(output_dir, "p2_header_gbk.html"),
            P2.encode("utf-8"),
        )

    def test_criterion_05_p3_probe_utf8_without_declaration(self):
        result, _ = self.run_normalize()
        page = self.page_by_file(result, "p3_probe_utf8.html")
        self.assertEqual(page["declared_charset"], "")
        self.assertEqual(page["used_charset"], "utf-8")

    def test_criterion_06_p4_probe_gbk_without_declaration(self):
        result, _ = self.run_normalize()
        page = self.page_by_file(result, "p4_probe_gbk.html")
        self.assertEqual(page["declared_charset"], "")
        self.assertEqual(page["used_charset"], "gbk")

    def test_criterion_07_p5_latin1_mojibake_repair(self):
        result, output_dir = self.run_normalize()
        page = self.page_by_file(result, "p5_mojibake_latin1.html")
        self.assertTrue(page["repaired"])
        self.assertEqual(page["used_charset"], "utf-8")
        output = self.normalized_text(
            output_dir, "p5_mojibake_latin1.html"
        ).decode("utf-8")
        self.assertEqual(output, "<html><body>café</body></html>")
        word = output.removeprefix("<html><body>").removesuffix("</body></html>")
        self.assertEqual(word, "café")
        self.assertEqual(len(word), 4)
        self.assertNotIn("Ã", output)

    def test_criterion_08_p6_gbk_mojibake_repair(self):
        result, output_dir = self.run_normalize()
        page = self.page_by_file(result, "p6_mojibake_gbk.html")
        self.assertTrue(page["repaired"])
        self.assertEqual(page["used_charset"], "utf-8")
        output = self.normalized_text(
            output_dir, "p6_mojibake_gbk.html"
        ).decode("utf-8")
        self.assertEqual(output, "<html><body>数据</body></html>")
        word = output.removeprefix("<html><body>").removesuffix("</body></html>")
        self.assertEqual(word, "数据")
        self.assertEqual(len(word), 2)
        self.assertNotIn("鏁版嵁", output)

    def test_criterion_09_p7_real_latin1_is_not_modified(self):
        result, output_dir = self.run_normalize()
        page = self.page_by_file(result, "p7_header_latin1.html")
        self.assertEqual(page["declared_charset"], "latin-1")
        self.assertEqual(page["used_charset"], "latin-1")
        self.assertFalse(page["repaired"])
        self.assertEqual(
            self.normalized_text(output_dir, "p7_header_latin1.html"),
            P7.encode("utf-8"),
        )

    def test_criterion_10_p8_line_fallback_used_charset_and_issue(self):
        result, output_dir = self.run_normalize()
        page = self.page_by_file(result, "p8_bad_declaration.html")
        self.assertEqual(page["declared_charset"], "utf-8")
        self.assertEqual(page["used_charset"], "utf-8+gbk")
        self.assertIn("2", page["issue"])
        self.assertIn("gbk", page["issue"])
        output = self.normalized_text(
            output_dir, "p8_bad_declaration.html"
        ).decode("utf-8")
        self.assertEqual(
            output.splitlines()[1], "<p>这一行是GBK编码的中文</p>"
        )

    def test_criterion_11_p9_bom_is_removed_and_not_declared(self):
        result, output_dir = self.run_normalize()
        page = self.page_by_file(result, "p9_bom_utf8.html")
        self.assertEqual(page["declared_charset"], "")
        self.assertEqual(page["used_charset"], "utf-8")
        self.assertFalse(page["repaired"])
        output = self.normalized_text(output_dir, "p9_bom_utf8.html")
        self.assertFalse(output.startswith(b"\xef\xbb\xbf"))
        self.assertNotIn("\ufeff", output.decode("utf-8"))
        self.assertEqual(output, P9.encode("utf-8"))

    def test_criterion_12_normalized_directory_has_nine_txt_files(self):
        _, output_dir = self.run_normalize()
        txt_files = sorted(
            path.name for path in output_dir.iterdir() if path.is_file()
        )
        expected = sorted(name + ".txt" for name in EXPECTED_FIXTURES)
        self.assertEqual(txt_files, expected)
        self.assertEqual(len(txt_files), 9)
        for path in output_dir.iterdir():
            self.assertFalse(path.read_bytes().startswith(b"\xef\xbb\xbf"))

    def test_criterion_13_p2_without_http_header_uses_meta_and_full_fallback(self):
        def remove_p2_header(manifest):
            next(
                item
                for item in manifest["pages"]
                if item["file"] == "p2_header_gbk.html"
            )["http_charset"] = ""

        self.reset_workspace()
        write_fixtures(
            self.pages_dir,
            self.manifest_path,
            manifest_override=remove_p2_header,
        )
        result, output_dir = self.run_normalize()
        page = self.page_by_file(result, "p2_header_gbk.html")
        self.assertEqual(page["declared_charset"], "utf-8")
        self.assertEqual(page["used_charset"], "gbk")
        self.assertIn("1", page["issue"])
        self.assertIn("gbk", page["issue"])
        self.assertEqual(
            self.normalized_text(output_dir, "p2_header_gbk.html"),
            P2.encode("utf-8"),
        )

    def test_criterion_14_p9_without_bom_still_probes_utf8(self):
        self.reset_workspace()
        write_fixtures(
            self.pages_dir,
            self.manifest_path,
            contents={"p9_bom_utf8.html": P9.encode("utf-8")},
        )
        result, output_dir = self.run_normalize()
        page = self.page_by_file(result, "p9_bom_utf8.html")
        self.assertEqual(page["declared_charset"], "")
        self.assertEqual(page["used_charset"], "utf-8")
        self.assertFalse(page["repaired"])
        self.assertEqual(
            self.normalized_text(output_dir, "p9_bom_utf8.html"),
            P9.encode("utf-8"),
        )

    def test_criterion_15_repairs_are_character_exact(self):
        result, output_dir = self.run_normalize()
        p5 = self.normalized_text(
            output_dir, "p5_mojibake_latin1.html"
        ).decode("utf-8")
        p6 = self.normalized_text(
            output_dir, "p6_mojibake_gbk.html"
        ).decode("utf-8")
        self.assertIn("café", p5)
        self.assertNotIn("cafÃ©", p5)
        self.assertIn("数据", p6)
        self.assertNotIn("鏁版嵁", p6)

    def test_repeated_runs_are_byte_for_byte_deterministic(self):
        first_report, first_dir = self.run_normalize()
        first_report_bytes = self.out_path.read_bytes()
        first_outputs = {
            path.name: path.read_bytes() for path in first_dir.iterdir()
        }

        second_report, second_dir = self.run_normalize()
        self.assertEqual(self.out_path.read_bytes(), first_report_bytes)
        self.assertEqual(second_report, first_report)
        second_outputs = {
            path.name: path.read_bytes() for path in second_dir.iterdir()
        }
        self.assertEqual(second_outputs, first_outputs)

    def test_cli_prints_one_summary_line_and_writes_utf8_report(self):
        stdout = StringIO()
        with redirect_stdout(stdout):
            exit_code = cli_main([
                "--dir", str(self.pages_dir),
                "--manifest", str(self.manifest_path),
                "--out", str(self.out_path),
            ])
        self.assertEqual(exit_code, 0)
        lines = stdout.getvalue().splitlines()
        self.assertEqual(len(lines), 1)
        self.assertIn("pages=9", lines[0])
        self.assertIn("repaired=2", lines[0])
        self.assertIn("issues=1", lines[0])
        self.assertIn("normalized", lines[0])
        report_bytes = self.out_path.read_bytes()
        self.assertFalse(report_bytes.startswith(b"\xef\xbb\xbf"))
        self.assertEqual(json.loads(report_bytes)["summary"]["files"], 9)

    def test_module_cli_entry_point_runs(self):
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "encnorm.cli",
                "--dir",
                str(self.pages_dir),
                "--manifest",
                str(self.manifest_path),
                "--out",
                str(self.out_path),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertEqual(len(completed.stdout.splitlines()), 1)
        self.assertTrue(self.out_path.exists())


class PrimitiveTestCase(unittest.TestCase):
    def test_http_header_name_normalization(self):
        self.assertEqual(httpheader.normalize_charset("utf8"), "utf-8")
        self.assertEqual(httpheader.normalize_charset("GB2312"), "gbk")
        self.assertEqual(httpheader.normalize_charset("gb18030"), "gbk")
        self.assertEqual(httpheader.normalize_charset("ISO-8859-1"), "latin-1")
        self.assertEqual(httpheader.normalize_charset("unknown-9"), "")
        self.assertEqual(httpheader.normalize_charset(""), "")
        self.assertEqual(httpheader.normalize_charset(None), "")

    def test_meta_supports_both_forms_and_header_prefix_limit(self):
        attr = b'<html><meta charset="GBK"><body>'
        self.assertEqual(meta.find_meta_charset(attr), "gbk")
        http_equiv = (
            b'<meta http-equiv="Content-Type" '
            b"content='text/html; charset=big5'>"
        )
        self.assertEqual(meta.find_meta_charset(http_equiv), "big5")
        unknown = b'<meta charset="x-mystery">'
        self.assertEqual(meta.find_meta_charset(unknown), "")
        late = b"<html>" + b" " * 1100 + b'<meta charset="gbk">'
        self.assertEqual(meta.find_meta_charset(late), "")

    def test_bom_detection_and_stripping(self):
        self.assertTrue(bom.has_utf8_bom(b"\xef\xbb\xbfabc"))
        self.assertEqual(bom.strip_utf8_bom(b"\xef\xbb\xbfabc"), b"abc")
        self.assertEqual(bom.strip_utf8_bom(b"abc"), b"abc")

    def test_probe_order_utf8_gbk_big5_latin1(self):
        self.assertEqual(probe.probe_bytes("中文".encode("utf-8")), "utf-8")
        self.assertEqual(probe.probe_bytes("中文".encode("gbk")), "gbk")
        big5_only = b"\xa1\x40\xaa\xf9"
        big5_only.decode("big5")
        with self.assertRaises(UnicodeDecodeError):
            big5_only.decode("gbk")
        with self.assertRaises(UnicodeDecodeError):
            big5_only.decode("utf-8")
        self.assertEqual(probe.probe_bytes(big5_only), "big5")
        self.assertEqual(probe.probe_bytes(b"\xff\xfe"), "latin-1")

    def test_mojibake_requires_all_three_conditions(self):
        latin_repaired, latin_changed = mojibake.repair_mojibake("cafÃ©")
        self.assertTrue(latin_changed)
        self.assertEqual(latin_repaired, "café")

        gbk_repaired, gbk_changed = mojibake.repair_mojibake("鏁版嵁")
        self.assertTrue(gbk_changed)
        self.assertEqual(gbk_repaired, "数据")

        normal, changed = mojibake.repair_mojibake("café")
        self.assertFalse(changed)
        self.assertEqual(normal, "café")

        plain_ascii, ascii_changed = mojibake.repair_mojibake("plain ascii")
        self.assertFalse(ascii_changed)
        self.assertEqual(plain_ascii, "plain ascii")

    def test_latin1_first_then_gbk_candidate_order(self):
        self.assertEqual(mojibake.try_reverse("cafÃ©", "latin-1"), "café")
        self.assertIsNone(mojibake.try_reverse("café", "latin-1"))
        self.assertEqual(mojibake.try_reverse("鏁版嵁", "gbk"), "数据")

    def test_all_line_fallback_reports_only_fallback_charset(self):
        raw = "中文".encode("gbk")
        result = decode.decode_page(raw, "utf-8")
        self.assertEqual(result["declared_charset"], "utf-8")
        self.assertEqual(result["used_charset"], "gbk")
        self.assertIn("1", result["issue"])
        self.assertIn("gbk", result["issue"])
        self.assertEqual(result["text"], "中文")

    def test_mixed_line_fallback_keeps_selected_charset_first(self):
        raw = ("good line\n").encode("utf-8") + "中文\n".encode("gbk")
        result = decode.decode_page(raw, "utf-8")
        self.assertEqual(result["used_charset"], "utf-8+gbk")
        self.assertIn("2", result["issue"])
        self.assertEqual(result["text"].splitlines()[1], "中文")

    def test_bom_is_not_recorded_as_declaration(self):
        result = decode.decode_page(b"\xef\xbb\xbf" + "中文".encode("utf-8"))
        self.assertEqual(result["declared_charset"], "")
        self.assertEqual(result["used_charset"], "utf-8")
        self.assertNotIn("\ufeff", result["text"])


if __name__ == "__main__":
    unittest.main()
