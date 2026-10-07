"""textutil 单元测试（标准库 unittest）。"""

from __future__ import annotations

import unittest

from fetcher.textutil import (
    build_lrc,
    is_valid_lrc,
    lrc_metadata,
    normalize,
    normalize_lrc,
    parse_lrc_lines,
    split_artists,
    strip_brackets,
    strip_lrc_metadata,
    to_simplified,
)


class TextUtilTest(unittest.TestCase):
    def test_to_simplified(self):
        """繁体歌词要能转成简体。"""
        self.assertEqual(to_simplified("故事的小黃花"), "故事的小黄花")

    def test_parse_lrc_single_timestamp(self):
        """[00:29.30] 的小数部分按百分秒处理。"""
        self.assertEqual(
            parse_lrc_lines("[00:29.30] 故事的小黃花"),
            [(29.3, "故事的小黃花")],
        )

    def test_parse_lrc_multi_timestamp(self):
        """一行多个时间戳要展开成多条。"""
        self.assertEqual(
            parse_lrc_lines("[00:01.00][00:35.00]副歌"),
            [(1.0, "副歌"), (35.0, "副歌")],
        )

    def test_parse_lrc_skips_metadata(self):
        """元信息行不算歌词。"""
        lrc = "[ti:晴天]\n[ar:周杰伦]\n[00:01.00]故事的小黄花"
        self.assertEqual(parse_lrc_lines(lrc), [(1.0, "故事的小黄花")])

    def test_is_valid_lrc_false(self):
        """少于 min_lines 条视为无效。"""
        self.assertFalse(is_valid_lrc("[00:01.00]a\n[00:02.00]b"))

    def test_is_valid_lrc_true(self):
        """达到 min_lines 条视为有效。"""
        self.assertTrue(is_valid_lrc("[00:01.00]a\n[00:02.00]b\n[00:03.00]c"))

    def test_normalize_drop_brackets(self):
        """两种模式结果必须不同，去括号后不含版本标记。"""
        strict = normalize("晴天 (Live版)")
        loose = normalize("晴天 (Live版)", drop_brackets=True)

        self.assertNotEqual(strict, loose)
        self.assertIn("live", strict)
        self.assertNotIn("live", loose)

    def test_normalize_nfkc(self):
        """全角与半角归一化结果必须一致。"""
        self.assertEqual(normalize("ＡＣ/ＤＣ"), normalize("AC/DC"))

    def test_split_artists(self):
        """多个歌手要拆成独立条目。"""
        self.assertEqual(split_artists("周杰伦 / 费玉清"), ["周杰伦", "费玉清"])

    def test_build_lrc_timestamp_format(self):
        """输出时间戳统一为 [mm:ss.xx]。"""
        self.assertEqual(build_lrc([(29.3, "故事的小黄花")]), "[00:29.30]故事的小黄花")

    def test_strip_brackets_keeps_bracketless_text(self):
        """无括号文本不得被误伤。"""
        self.assertEqual(strip_brackets("AC/DC"), "AC/DC")

    def test_build_lrc_with_metadata(self):
        """元信息按 ti/ar/al/by/offset 顺序输出，且只写有值的。"""
        lrc = build_lrc([(1.0, "a")], {"ar": "周杰伦", "ti": "晴天"})
        self.assertEqual(lrc, "[ti:晴天]\n[ar:周杰伦]\n[00:01.00]a")

    def test_lrc_metadata(self):
        """元信息 key 统一小写。"""
        meta = lrc_metadata("[ti:晴天]\n[AR:周杰伦]")
        self.assertEqual(meta, {"ti": "晴天", "ar": "周杰伦"})

    def test_strip_lrc_metadata(self):
        """只返回正文行。"""
        self.assertEqual(
            strip_lrc_metadata("[ti:晴天]\n[00:01.00]故事的小黄花"),
            "故事的小黄花",
        )

    def test_normalize_lrc_simplifies_and_reformats(self):
        """重建后排版统一，且正文转简体。"""
        lrc = "[00:29.300]故事的小黃花"
        self.assertEqual(normalize_lrc(lrc), "[00:29.30]故事的小黄花")


if __name__ == "__main__":
    unittest.main()
