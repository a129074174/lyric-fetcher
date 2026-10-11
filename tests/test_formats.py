"""歌词格式转换单元测试（对应 VLC 字幕转换需求）。"""

from __future__ import annotations

import unittest

from fetcher.formats import lrc_to_srt, srt_timestamp


class TestSrtTimestamp(unittest.TestCase):
    def test_zero(self):
        self.assertEqual(srt_timestamp(0), "00:00:00,000")

    def test_less_than_one_second(self):
        self.assertEqual(srt_timestamp(0.5), "00:00:00,500")

    def test_minutes_and_seconds(self):
        self.assertEqual(srt_timestamp(62.345), "00:01:02,345")

    def test_over_one_hour(self):
        self.assertEqual(srt_timestamp(3661.001), "01:01:01,001")


class TestLrcToSrt(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(lrc_to_srt(""), "")

    def test_basic_two_lines(self):
        lrc = "[00:01.00]第一行\n[00:03.00]第二行"
        srt = lrc_to_srt(lrc)
        expected = (
            "1\n00:00:01,000 --> 00:00:03,000\n第一行\n"
            "\n"
            "2\n00:00:03,000 --> 00:00:08,000\n第二行\n"
        )
        self.assertEqual(srt, expected)

    def test_skips_metadata(self):
        lrc = "[ti:晴天]\n[ar:周杰伦]\n[00:01.00]歌词\n"
        srt = lrc_to_srt(lrc)
        expected = "1\n00:00:01,000 --> 00:00:06,000\n歌词\n"
        self.assertEqual(srt, expected)

    def test_multi_timestamp_expansion(self):
        lrc = "[00:01.00][00:03.00]重复句\n[00:05.00]下一句"
        srt = lrc_to_srt(lrc)
        # parse_lrc_lines 会展开为 (1.0, "重复句") (3.0, "重复句") (5.0, "下一句")
        lines = srt.strip().split("\n\n")
        self.assertEqual(len(lines), 3)
        self.assertIn("00:00:01,000 --> 00:00:03,000", lines[0])
        self.assertIn("00:00:03,000 --> 00:00:05,000", lines[1])
        self.assertIn("00:00:05,000 --> 00:00:10,000", lines[2])

    def test_total_duration_for_last_line(self):
        lrc = "[00:01.00]第一行\n[00:03.00]第二行"
        srt = lrc_to_srt(lrc, total_duration=10.0)
        # 第二行结束应为总时长 10 秒
        self.assertIn("00:00:03,000 --> 00:00:10,000", srt)

    def test_default_duration_when_no_total(self):
        lrc = "[00:01.00]仅一行"
        srt = lrc_to_srt(lrc, default_duration=7.0)
        self.assertIn("00:00:01,000 --> 00:00:08,000", srt)

    def test_zero_or_negative_interval(self):
        lrc = "[00:01.00]第一行\n[00:01.00]第二行"
        srt = lrc_to_srt(lrc)
        # 两个相同时间戳，第二行至少要显示 0.5 秒
        self.assertIn("00:00:01,000 --> 00:00:01,500", srt)


if __name__ == "__main__":
    unittest.main()
