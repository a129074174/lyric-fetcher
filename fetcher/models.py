"""统一数据模型。

设计要点：
- TrackQuery 是「我要找什么」，Candidate 是「某个源给出的答案」。
- Candidate 同时承载打分所需的元信息（时长、是否纯音乐）和歌词正文。
- synced 存 LRC 原始文本，plain 存无时间轴纯文本；两者至少有一个。
- duration 单位统一为「秒」（float）—— 网易云返回毫秒，必须在适配器里除 1000。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class TrackQuery:
    """一次检索请求。artist / album / duration 可选，但给得越多匹配越准。"""

    title: str
    artist: str = ""
    album: str = ""
    duration: float | None = None
    instrumental: bool = False

    def describe(self) -> str:
        parts = [self.title]
        if self.artist:
            parts.append(f"- {self.artist}")
        if self.duration:
            parts.append(f"({int(self.duration // 60)}:{int(self.duration % 60):02d})")
        return " ".join(parts)


@dataclass(slots=True)
class Candidate:
    """某个源返回的一条候选歌词。"""

    source: str
    title: str = ""
    artist: str = ""
    album: str = ""
    duration: float | None = None
    instrumental: bool = False
    synced: str = ""  # LRC 文本（带时间戳）
    plain: str = ""  # 纯文本歌词
    remote_id: str = ""
    extra: dict[str, Any] = field(default_factory=dict)
    score: float = 0.0

    @property
    def has_synced(self) -> bool:
        return bool(self.synced.strip())

    @property
    def has_lyrics(self) -> bool:
        return self.has_synced or bool(self.plain.strip())

    @property
    def best_text(self) -> str:
        """优先返回带时间轴的版本。"""
        return self.synced if self.has_synced else self.plain

    def summary(self) -> str:
        flag = "LRC" if self.has_synced else ("TXT" if self.plain.strip() else "---")
        if self.duration:
            dur = f"{int(self.duration // 60)}:{int(self.duration % 60):02d}"
        else:
            dur = "--:--"
        return f"[{self.score:.3f}] {self.source:<8} {flag}  {self.title} - {self.artist} ({dur})"
