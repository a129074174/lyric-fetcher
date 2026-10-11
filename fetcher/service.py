"""多源聚合调度（Step 6 实现）。

计划对外接口见项目《开发指令.md》的「接口契约」一节，签名已冻结：
    class LyricService(sources=None, http=None)
        .search(query, limit=8) / .fetch_lyrics(cand)
        .find(query, min_score=0.75, prefer_synced=True) / .find_all(query, min_score=0.75)
        .close()

两条核心策略：
    并发：三个源同时查，单源超时或异常只记录、不拖垮整次查询。
    两阶段拉取：先全源 search 汇总打分，再只对排前面的候选按需 fetch 歌词正文，
                把请求数从 N×M 降到 N+M。
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Iterable, Sequence

from .adapters import ALL_SOURCES
from .adapters.base import LyricSource
from .client import HttpClient
from .matcher import rank
from .models import Candidate, TrackQuery
from .textutil import normalize_lrc, to_simplified


class LyricService:
    """把多个歌词源聚合成「一次查询，直接给最佳答案」。"""

    def __init__(
        self,
        sources: Sequence[LyricSource] | None = None,
        http: HttpClient | None = None,
    ):
        self.http = http or HttpClient()
        self._owns_http = http is None
        self.errors: list[str] = []

        if sources is None:
            sources = [source_cls(self.http) for source_cls in ALL_SOURCES]
        self.sources: list[LyricSource] = list(sources)

    # ------------------------------------------------------------------ 查询

    def search(self, query: TrackQuery, limit: int = 8) -> list[Candidate]:
        """全源并发搜索，统一打分去重后降序返回。"""
        candidates: list[Candidate] = []

        if self.sources:
            workers = min(4, len(self.sources))
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = [
                    pool.submit(self._search_one, source, query, limit)
                    for source in self.sources
                ]
                for future in futures:
                    candidates.extend(future.result())

        ranked = rank(query, candidates)
        return self._dedupe(ranked)

    def _search_one(
        self, source: LyricSource, query: TrackQuery, limit: int
    ) -> list[Candidate]:
        """单源搜索；异常只记录，不影响其他源。"""
        try:
            return source.search(query, limit=limit)
        except Exception as exc:  # noqa: BLE001 - 单源故障不得拖垮整次查询
            self.errors.append(f"{source.name}: {exc}")
            return []

    @staticmethod
    def _dedupe(candidates: Iterable[Candidate]) -> list[Candidate]:
        """同一 (标题, 歌手, 时长) 只保留打分最高的那条。"""
        deduped: list[Candidate] = []
        index: dict[tuple[str, str, float], Candidate] = {}

        for cand in candidates:
            key = (cand.title, cand.artist, round(cand.duration or 0.0, 1))
            existing = index.get(key)
            if existing is None:
                index[key] = cand
                deduped.append(cand)
            elif cand.score > existing.score:
                # 保留首次出现的槽位（同分时维持原顺序），但换成分更高的候选
                deduped[deduped.index(existing)] = cand
                index[key] = cand

        return deduped

    # ------------------------------------------------------------------ 歌词

    def fetch_lyrics(self, cand: Candidate) -> Candidate:
        """按候选来源取歌词正文，并统一繁转简。"""
        source = self._source_for(cand)
        if source is None:
            return cand

        try:
            cand = source.fetch(cand)
        except Exception as exc:  # noqa: BLE001 - 取歌词失败不中断，返回原候选
            self.errors.append(f"{source.name}: {exc}")
            return cand

        # LRCLIB 常返回繁体，这里统一转简体
        if cand.synced:
            cand.synced = normalize_lrc(cand.synced, simplify=True)
        if cand.plain:
            cand.plain = _plain_to_text(cand.plain, simplify=True)

        return cand

    def _source_for(self, cand: Candidate) -> LyricSource | None:
        for source in self.sources:
            if source.name == cand.source:
                return source
        return None

    # ------------------------------------------------------------------ 择优

    def find(
        self,
        query: TrackQuery,
        min_score: float = 0.75,
        prefer_synced: bool = True,
    ) -> Candidate | None:
        """返回最佳候选；都不达标时返回 None，绝不返回低分垃圾结果。"""
        accepted = self._collect(query, min_score)
        if not accepted:
            return None
        return self._best(accepted, prefer_synced)

    def find_all(
        self, query: TrackQuery, min_score: float = 0.75
    ) -> list[Candidate]:
        """返回所有达标且确有歌词的候选，按择优规则排序。"""
        return self._collect(query, min_score)

    def _collect(self, query: TrackQuery, min_score: float) -> list[Candidate]:
        """打分 → 只取达标候选 → 按需 fetch → 过滤掉没歌词的，最后按择优规则排序。"""
        ranked = self.search(query)
        targets = [cand for cand in ranked if cand.score >= min_score]

        accepted: list[Candidate] = []
        for cand in targets:
            fetched = self.fetch_lyrics(cand)
            if fetched.has_lyrics and fetched.score >= min_score:
                accepted.append(fetched)

        # 同分时按源 priority 升序（qqmusic 10 < netease 20 < lrclib 30）
        return sorted(accepted, key=_sort_key(prefer_synced=True), reverse=True)

    @staticmethod
    def _best(candidates: list[Candidate], prefer_synced: bool) -> Candidate | None:
        if not candidates:
            return None
        return max(candidates, key=_sort_key(prefer_synced))

    # ------------------------------------------------------------------ 资源

    def close(self) -> None:
        if self._owns_http:
            self.http.close()

    def __enter__(self) -> LyricService:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()


def _sort_key(prefer_synced: bool) -> Callable[[Candidate], tuple]:
    def key(cand: Candidate) -> tuple:
        synced_flag = 1 if (prefer_synced and cand.has_synced) else 0
        return (synced_flag, cand.score, -_priority_of(cand))

    return key


def _priority_of(cand: Candidate) -> int:
    for source_cls in ALL_SOURCES:
        if source_cls.name == cand.source:
            return source_cls.priority
    return 999


def _plain_to_text(plain: str, simplify: bool = True) -> str:
    """纯文本歌词：统一换行并可选繁转简。"""
    text = plain.replace("\r\n", "\n").strip("\n")
    return to_simplified(text) if simplify else text
