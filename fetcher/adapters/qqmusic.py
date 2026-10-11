"""QQ 音乐适配器（Step 5 实现）。

接口要点（实测修正版，与《开发指令.md》的差异见文件末尾说明）：
    搜索  GET https://u.y.qq.com/cgi-bin/musicu.fcg
          data={"comm":{...},"req":{"method":"DoSearchForQQMusicDesktop",
                "module":"music.search.SearchCgiService",
                "param":{"query":"标题 歌手","page_num":1,"num_per_page":N,"search_type":0}}}
          headers: Referer: https://y.qq.com/
          取 req.data.body.song.list[]：mid / title / singer[].name / album.name / interval(秒)
    歌词  GET https://c.y.qq.com/lyric/fcgi-bin/fcg_query_lyric_new.fcg
          params: songmid / format=json / nobase64=1 / g_tk=5381 / ...
          headers: Referer: https://y.qq.com/portal/player.html
          lyric → synced；trans → 翻译

⚠️ 实测与文档的两处不一致（已确认，勿改回）：
    1. 文档里的 https://c.y.qq.com/soso/fcgi-bin/client_search_cp 现已稳定返回 500，
       改用新版 musicu.fcg 的 DoSearchForQQMusicDesktop。
    2. musicu.fcg 的 content-type 声称 UTF-8、实际返回 GBK 字节，
       由 HttpClient 的 _decode_json 做 UTF-8 → GBK 二级解码兜住。
"""

from __future__ import annotations

import json
from typing import Any

from ..models import Candidate, TrackQuery
from .base import LyricSource

_SEARCH_URL = "https://u.y.qq.com/cgi-bin/musicu.fcg"
_LYRIC_URL = "https://c.y.qq.com/lyric/fcgi-bin/fcg_query_lyric_new.fcg"
_SEARCH_REFERER = {"Referer": "https://y.qq.com/"}
_LYRIC_REFERER = {"Referer": "https://y.qq.com/portal/player.html"}

_SEARCH_METHOD = "DoSearchForQQMusicDesktop"
_SEARCH_MODULE = "music.search.SearchCgiService"

_LYRIC_PARAMS = {
    "format": "json",
    "nobase64": 1,
    "g_tk": 5381,
    "loginUin": 0,
    "hostUin": 0,
    "inCharset": "utf8",
    "outCharset": "utf-8",
    "notice": 0,
    "platform": "yqq",
    "needNewCode": 0,
}


class QQMusicSource(LyricSource):
    """QQ 音乐：interval 已是秒，但搜索接口发的字节是 GBK。"""

    name = "qqmusic"
    display_name = "QQ音乐"
    # 官方歌词：元信息完整、简体、排版规范，作为首选源
    priority = 10

    def search(self, query: TrackQuery, limit: int = 8) -> list[Candidate]:
        keyword = " ".join(part for part in (query.title.strip(), query.artist.strip()) if part)
        if not keyword:
            return []

        payload = {
            "comm": {"ct": "19", "cv": "1859", "uin": "0", "platform": "yqq"},
            "req": {
                "method": _SEARCH_METHOD,
                "module": _SEARCH_MODULE,
                "param": {
                    "query": keyword,
                    "page_num": 1,
                    "num_per_page": max(limit, 5),
                    "search_type": 0,
                },
            },
        }
        params = {"format": "json", "data": json.dumps(payload, ensure_ascii=False)}
        data = self.http.get_json(_SEARCH_URL, params=params, headers=_SEARCH_REFERER)

        songs = self._extract_songs(data)
        return [self._to_candidate(song) for song in songs[: max(limit, 5)]]

    def fetch(self, cand: Candidate) -> Candidate:
        if not cand.remote_id:
            return cand

        params = dict(_LYRIC_PARAMS, songmid=cand.remote_id)
        data = self.http.get_json(_LYRIC_URL, params=params, headers=_LYRIC_REFERER)
        if not isinstance(data, dict):
            return cand

        cand.synced = (data.get("lyric") or "").strip()
        translation = (data.get("trans") or "").strip()
        if translation:
            cand.extra["translation"] = translation

        return cand

    @staticmethod
    def _extract_songs(data: Any) -> list[dict[str, Any]]:
        """从 req.data.body.song.list[] 取歌曲，任何结构缺失都返回空列表。"""
        if not isinstance(data, dict):
            return []

        req = data.get("req")
        if not isinstance(req, dict):
            return []

        body = req.get("data", {}).get("body") if isinstance(req.get("data"), dict) else None
        if not isinstance(body, dict):
            return []

        song_section = body.get("song")
        if not isinstance(song_section, dict):
            return []

        raw_songs = song_section.get("list")
        if not isinstance(raw_songs, list):
            return []

        return [song for song in raw_songs if isinstance(song, dict)]

    def _to_candidate(self, song: dict[str, Any]) -> Candidate:
        singers = song.get("singer")
        artist = ""
        if isinstance(singers, list):
            names = [
                item.get("name", "")
                for item in singers
                if isinstance(item, dict) and item.get("name")
            ]
            artist = " / ".join(names)

        album_info = song.get("album")
        album = album_info.get("name") if isinstance(album_info, dict) else ""
        interval = song.get("interval")

        return Candidate(
            source=self.name,
            title=song.get("title") or song.get("name") or "",
            artist=artist,
            album=album or "",
            # QQ 音乐的 interval 已经是秒
            duration=float(interval) if interval else None,
            remote_id=str(song.get("mid") or ""),
        )


__all__ = ["QQMusicSource"]
