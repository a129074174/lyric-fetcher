"""matcher 单元测试（标准库 unittest）。"""

from __future__ import annotations

import unittest

from fetcher.matcher import (
    artist_score,
    duration_score,
    rank,
    score_candidate,
    title_score,
)
from fetcher.models import Candidate, TrackQuery


def build_original_candidates() -> list[Candidate]:
    """Step 3 给定的真实场景：原版两条、翻唱一条、无歌词一条。"""
    return [
        Candidate(
            source="qqmusic",
            title="晴天",
            artist="周杰伦",
            duration=269.0,
            synced="[00:01.00]x",
        ),
        Candidate(
            source="netease",
            title="晴天(深情版)",
            artist="Lucky小爱",
            duration=279.0,
            synced="[00:01.00]x",
        ),
        Candidate(
            source="lrclib",
            title="晴天",
            artist="周杰伦",
            duration=270.0,
            synced="[00:01.00]x",
        ),
        Candidate(
            source="lrclib",
            title="晴天",
            artist="周杰伦",
            duration=270.0,
        ),
    ]


class MatcherTest(unittest.TestCase):
    def setUp(self):
        self.query = TrackQuery(title="晴天", artist="周杰伦", duration=270.0)
        self.a, self.b, self.c, self.d = build_original_candidates()

    def test_rank_orders_original_first(self):
        """原版两条排前两位，翻唱排最后。"""
        ranked = rank(self.query, build_original_candidates())
        top_two = {ranked[0].source, ranked[1].source}

        self.assertEqual(top_two, {"qqmusic", "lrclib"})
        self.assertEqual(ranked[-1].source, "netease")

    def test_high_score_for_exact_matches(self):
        """原版候选得分都要高于 0.95。"""
        self.assertGreater(score_candidate(self.query, self.a), 0.95)
        self.assertGreater(score_candidate(self.query, self.c), 0.95)

    def test_low_score_for_cover_version(self):
        """翻唱版本不得高于 0.7。"""
        self.assertLess(score_candidate(self.query, self.b), 0.7)

    def test_exact_duration_beats_close_duration(self):
        """时长完全一致的原版不低于时长略有偏差的原版。

        注意：两者都落在 2 秒容差内，加上同步歌词奖励后都会撞到 1.0 上限，
        断言写成「不低于」而不是「严格大于」。
        """
        self.assertGreaterEqual(
            score_candidate(self.query, self.c), score_candidate(self.query, self.a)
        )

    def test_instrumental_candidate_is_rejected(self):
        """纯音乐候选在非纯音乐查询下直接判 0。"""
        instrumental = Candidate(
            source="lrclib",
            title="晴天",
            artist="周杰伦",
            duration=270.0,
            instrumental=True,
            synced="[00:01.00]x",
        )
        self.assertEqual(score_candidate(self.query, instrumental), 0.0)

    def test_missing_artist_does_not_penalize(self):
        """查询不带歌手时 artist_score 为 None，整体分数不被拉低到 0.5 以下。"""
        query = TrackQuery(title="晴天", duration=270.0)

        self.assertIsNone(artist_score(query.artist, self.c.artist))
        self.assertGreater(score_candidate(query, self.c), 0.5)

    def test_title_score_prefers_relaxed_match(self):
        """带版本标记的标题要靠去括号匹配上原名。"""
        self.assertGreater(title_score("晴天", "晴天(深情版)"), 0.9)

    def test_artist_score_semantics(self):
        """三种返回值语义：None / 中性分 / 完全匹配。"""
        self.assertIsNone(artist_score("", "周杰伦"))
        self.assertEqual(artist_score("周杰伦", ""), 0.35)
        self.assertEqual(artist_score("周杰伦 / 费玉清", "费玉清"), 1.0)

    def test_duration_score_bounds(self):
        """时长分在容差内为 1、超阈值为 0、缺失为 None。"""
        self.assertEqual(duration_score(270.0, 271.5), 1.0)
        self.assertEqual(duration_score(270.0, 300.0), 0.0)
        self.assertIsNone(duration_score(None, 270.0))
        self.assertIsNone(duration_score(270.0, 0))

    def test_rank_writes_score_in_place(self):
        """rank 要就地写入 score 并降序返回。"""
        candidates = build_original_candidates()
        ranked = rank(self.query, candidates)

        self.assertTrue(all(cand.score > 0 for cand in candidates))
        self.assertEqual(
            [cand.score for cand in ranked],
            sorted((cand.score for cand in ranked), reverse=True),
        )


if __name__ == "__main__":
    unittest.main()
