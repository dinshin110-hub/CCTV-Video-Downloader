import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import cctv_downloader as app


class CoreTests(unittest.TestCase):
    def test_display_title(self) -> None:
        self.assertEqual(
            app.DISPLAY_TITLE,
            "CCTV视频下载工具 v1.0.0 by:YaoYao",
        )

    def test_extract_guid(self) -> None:
        html = 'var guid = "a64699b8abf24fa7a8f7f73753c06e85";'
        self.assertEqual(
            app.extract_guid(html),
            "a64699b8abf24fa7a8f7f73753c06e85",
        )

    def test_parse_plain_urls_and_deduplicate(self) -> None:
        raw = (
            "https://tv.cctv.com/2024/03/28/example.shtml\n"
            "https://tv.cctv.com/2024/03/28/example.shtml\n"
        )
        self.assertEqual(
            app.parse_urls(raw),
            ["https://tv.cctv.com/2024/03/28/example.shtml"],
        )

    def test_parse_markdown_link(self) -> None:
        raw = "[video](https://tv.cctv.com/2024/03/28/example.shtml)"
        self.assertEqual(
            app.parse_urls(raw),
            ["https://tv.cctv.com/2024/03/28/example.shtml"],
        )

    def test_safe_filename_removes_windows_reserved_characters(self) -> None:
        result = app.safe_filename('a<b>c:d"e/f\\g|h?i*j')
        self.assertNotIn("<", result)
        self.assertNotIn(">", result)
        self.assertNotIn(":", result)
        self.assertNotIn('"', result)
        self.assertNotIn("/", result)
        self.assertNotIn("\\", result)
        self.assertNotIn("|", result)
        self.assertNotIn("?", result)
        self.assertNotIn("*", result)


if __name__ == "__main__":
    unittest.main()
