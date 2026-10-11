"""网易云音乐适配器（Step 5 实现）。

接口要点（已实测）：
    搜索  GET https://music.163.com/api/search/get/web
          params: s="标题 歌手", type=1, offset=0, limit=N
          headers: Referer: https://music.163.com/
          取 result.songs[]：id / name / artists[].name / album.name / duration(毫秒!)
          ⚠️ duration 是毫秒，必须 /1000 转成秒
    歌词  GET https://music.163.com/api/song/lyric?id=<id>&lv=-1&kv=-1&tv=-1
          lrc.lyric → synced；tlyric.lyric → 翻译；klyric.lyric → 无时间轴纯文本
"""

from __future__ import annotations

from typing import Any

from ..models import Candidate, TrackQuery
from .base import LyricSource

# /api/search/get/web 现已返回加密串（result 是 hex 而非对象），这里用仍返回明文的 /get
_SEARCH_URL = "https://music.163.com/api/search/get"
_LYRIC_URL = "https://music.163.com/api/song/lyric"
_REFERER = {"Referer": "https://music.163.com/"}


class NeteaseSource(LyricSource):
    """网易云音乐：中文歌覆盖最好的源之一，但时长单位是毫秒。"""

    name = "netease"
    display_name = "网易云音乐"
    priority = 20

    def search(self, query: TrackQuery, limit: int = 8) -> list[Candidate]:
        keyword = " ".join(part for part in (query.title.strip(), query.artist.strip()) if part)
        if not keyword:
            return []

        params = {"s": keyword, "type": 1, "offset": 0, "limit": max(limit, 5)}
        data = self.http.get_json(_SEARCH_URL, params=params, headers=_REFERER)

        songs: list[Any] = []
        result = data.get("result") if isinstance(data, dict) else None
        if isinstance(result, dict):
            raw_songs = result.get("songs")
            if isinstance(raw_songs, list):
                songs = [song for song in raw_songs if isinstance(song, dict)]

        return [self._to_candidate(song) for song in songs[: max(limit, 5)]]

    def fetch(self, cand: Candidate) -> Candidate:
        """按 remote_id（歌曲 id）取歌词；搜索时不带正文，必须到这里才拉。"""
        if not cand.remote_id:
            return cand

        params = {"id": cand.remote_id, "lv": -1, "kv": -1, "tv": -1}
        data = self.http.get_json(_LYRIC_URL, params=params, headers=_REFERER)
        if not isinstance(data, dict):
            return cand

        cand.synced = self._pick(data, "lrc")
        translation = self._pick(data, "tlyric")
        if translation:
            cand.extra["translation"] = translation
        if not cand.synced:
            # 没有时间轴版本时，退而用逐字/纯文本版本
            cand.plain = self._pick(data, "klyric")

        return cand

    @staticmethod
    def _pick(data: dict[str, Any], key: str) -> str:
        """取 data[key].lyric，任何结构缺失都返回空串。"""
        section = data.get(key)
        if isinstance(section, dict):
            return (section.get("lyric") or "").strip()
        return ""

    def _to_candidate(self, song: dict[str, Any]) -> Candidate:
        artists = song.get("artists")
        artist = ""
        if isinstance(artists, list):
            names = [
                item.get("name", "")
                for item in artists
                if isinstance(item, dict) and item.get("name")
            ]
            artist = " / ".join(names)

        album = ""
        album_info = song.get("album")
        if isinstance(album_info, dict):
            album = album_info.get("name") or ""

        duration = song.get("duration")
        aliases = song.get("alias")

        return Candidate(
            source=self.name,
            title=song.get("name") or "",
            artist=artist,
            album=album,
            # 网易云返回毫秒，必须转成秒
            duration=float(duration) / 1000.0 if duration else None,
            remote_id=str(song.get("id") or ""),
            extra={"alias": aliases if isinstance(aliases, list) else []},
        )


__all__ = ["NeteaseSource"]
