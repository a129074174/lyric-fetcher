"""歌词源抽象基类（Step 4 实现）。

计划接口：
    class LyricSource(ABC):
        name: str; display_name: str; priority: int
        __init__(self, http: HttpClient)
        search(self, query: TrackQuery, limit: int = 8) -> list[Candidate]  # 抽象
        fetch(self, cand: Candidate) -> Candidate                           # 默认原样返回

设计意图：
    search 只负责「列出候选」，歌词正文允许延后到 fetch 再取。
    这样聚合层可以只对最可能命中的两三条真正拉歌词，
    把请求数从 N×M 降到 N+M——对有速率限制的接口尤其重要。
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..client import HttpClient
from ..models import Candidate, TrackQuery


class LyricSource(ABC):
    """一个歌词源的最小契约。"""

    name: str = ""
    display_name: str = ""
    priority: int = 100

    def __init__(self, http: HttpClient):
        self.http = http

    @abstractmethod
    def search(self, query: TrackQuery, limit: int = 8) -> list[Candidate]:
        """列出候选，不取歌词正文。"""

    def fetch(self, cand: Candidate) -> Candidate:
        """按需取歌词正文；默认源在 search 时已带全，直接返回。"""
        return cand

    def __repr__(self) -> str:
        return f"<{type(self).__name__} name={self.name!r} priority={self.priority}>"
