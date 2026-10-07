"""歌词源抽象基类（Step 4 实现）。

计划接口：
    class LyricSource(ABC):
        name: str; display_name: str; priority: int
        __init__(self, http: HttpClient)
        search(self, query: TrackQuery, limit: int = 8) -> list[Candidate]  # 抽象
        fetch(self, cand: Candidate) -> Candidate                           # 默认原样返回
"""

from __future__ import annotations
