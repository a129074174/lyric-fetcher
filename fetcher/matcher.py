"""候选打分与排序（Step 3 实现）。

计划对外接口见项目《开发指令.md》的「接口契约」一节，签名已冻结：
    title_score / artist_score / duration_score / score_candidate / rank

打分的核心难点不是「算得多准」，而是「某个信号缺失时该怎么办」——
直接按 0 分加权会把大量正常结果误杀，所以这里用 None 表示「无法判断」，
由 score_candidate 动态重新分配权重。
"""

from __future__ import annotations

from difflib import SequenceMatcher

from .models import Candidate, TrackQuery
from .textutil import normalize, split_artists

# 时长容差：2 秒内视为完全一致，20 秒以上视为完全不匹配
_DURATION_EXACT = 2.0
_DURATION_MAX = 20.0

# 有同步歌词是正向信号：说明这个源给的是可用的时间轴
_SYNCED_BONUS = 0.03

# 查询与候选都声明为纯音乐时的一致性奖励
_INSTRUMENTAL_BONUS = 0.05

# 源没有提供歌手信息时的中性分：不确定，但不直接淘汰
_UNKNOWN_ARTIST_SCORE = 0.35


def _ratio(a: str, b: str) -> float:
    """两个归一化字符串的相似度，空串一律记为 0。"""
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


def title_score(query_title: str, cand_title: str) -> float:
    """标题相似度：严格版与宽松版（去括号）取较大值。

    这样 "晴天" 才能匹配上 "晴天(深情版)"，但严格匹配仍然优先。
    """
    strict = _ratio(normalize(query_title), normalize(cand_title))
    loose = _ratio(
        normalize(query_title, drop_brackets=True),
        normalize(cand_title, drop_brackets=True),
    )
    return max(strict, loose)


def artist_score(query_artist: str, cand_artist: str) -> float | None:
    """歌手相似度。

    返回值语义（两者完全不同，调用方必须区分处理）：
    - None：查询侧没给歌手，属于「无法判断」，不应参与加权，更不是 0 分。
    - 0.35：查询给了歌手但候选侧缺失，中性偏低，保留竞争资格。
    - 其他：真实比对结果，1.0 表示集合有交集。
    """
    query_artists = split_artists(query_artist)
    if not query_artists:
        return None

    cand_artists = split_artists(cand_artist)
    if not cand_artists:
        return _UNKNOWN_ARTIST_SCORE

    if set(query_artists) & set(cand_artists):
        return 1.0

    return max(_ratio(q, c) for q in query_artists for c in cand_artists)


def duration_score(q_sec: float | None, c_sec: float | None) -> float | None:
    """时长相似度：任一侧缺失返回 None（无法判断），否则线性插值。"""
    if q_sec is None or c_sec is None or q_sec == 0 or c_sec == 0:
        return None

    delta = abs(q_sec - c_sec)
    if delta <= _DURATION_EXACT:
        return 1.0
    if delta >= _DURATION_MAX:
        return 0.0

    return 1.0 - (delta - _DURATION_EXACT) / (_DURATION_MAX - _DURATION_EXACT)


def score_candidate(query: TrackQuery, cand: Candidate) -> float:
    """综合打分，权重按可用信号动态分配（总和恒为 1）。"""
    # 候选是纯音乐而我要的是带唱的，直接淘汰
    if cand.instrumental and not query.instrumental:
        return 0.0

    title = title_score(query.title, cand.title)
    artist = artist_score(query.artist, cand.artist)
    duration = duration_score(query.duration, cand.duration)

    if artist is None and duration is None:
        weights = (1.00, 0.00, 0.00)
    elif artist is None:
        weights = (0.75, 0.00, 0.25)
    elif duration is None:
        weights = (0.60, 0.40, 0.00)
    else:
        weights = (0.50, 0.32, 0.18)

    # None 表示不参与加权，按 0 计入乘积（对应权重本就是 0）
    score = (
        title * weights[0]
        + (artist or 0.0) * weights[1]
        + (duration or 0.0) * weights[2]
    )

    if cand.has_synced:
        score += _SYNCED_BONUS
    if query.instrumental and cand.instrumental:
        score += _INSTRUMENTAL_BONUS

    return round(min(1.0, max(0.0, score)), 4)


def rank(query: TrackQuery, candidates: list[Candidate]) -> list[Candidate]:
    """就地给每个候选打分，按分数降序返回。"""
    for cand in candidates:
        cand.score = score_candidate(query, cand)
    return sorted(candidates, key=lambda item: item.score, reverse=True)
