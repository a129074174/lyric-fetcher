"""歌词源适配器集合。

ALL_SOURCES 的顺序即默认优先级：
    qqmusic(10) < netease(20) < lrclib(30)

选序依据（实测）：QQ 音乐与网易云是官方歌词，元信息完整、简体、排版规范；
LRCLIB 是社区上传，同一首歌常有多条质量参差的重复条目，因此降为兜底源。
"""

from __future__ import annotations

from .base import LyricSource
from .lrclib import LrclibSource
from .netease import NeteaseSource
from .qqmusic import QQMusicSource

# 顺序即默认优先级：官方源在前，社区源兜底
ALL_SOURCES = [QQMusicSource, NeteaseSource, LrclibSource]

__all__ = [
    "ALL_SOURCES",
    "LyricSource",
    "LrclibSource",
    "NeteaseSource",
    "QQMusicSource",
]
