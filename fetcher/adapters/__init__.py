"""歌词源适配器集合。

Step 4 先导出 LRCLIB；Step 5 补齐网易云与 QQ 音乐后再给出
ALL_SOURCES = [LrclibSource, NeteaseSource, QQMusicSource]（顺序即默认优先级）。
"""

from __future__ import annotations

from .base import LyricSource
from .lrclib import LrclibSource

__all__ = ["LyricSource", "LrclibSource"]
