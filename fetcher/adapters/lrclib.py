"""LRCLIB 适配器（Step 4 实现）。

接口要点（已实测）：
    精确匹配  GET https://lrclib.net/api/get?track_name=&artist_name=&duration=
    模糊搜索  GET https://lrclib.net/api/search?q=  或  ?track_name=&artist_name=
    响应字段  id / trackName / artistName / albumName / duration(秒)
              / instrumental / plainLyrics / syncedLyrics / hasWordSync

降级链：/get 精确匹配 → /search 按字段搜 → /search 用 q 泛搜。
"""

from __future__ import annotations

from typing import Any

from ..models import Candidate, TrackQuery
from .base import LyricSource


class LrclibSource(LyricSource):
    """LRCLIB：无需认证，一次请求就带同步歌词，最适合作为首个联调源。"""

    name = "lrclib"
    display_name = "LRCLIB"
    priority = 10

    BASE = "https://lrclib.net/api"

    def search(self, query: TrackQuery, limit: int = 8) -> list[Candidate]:
        headers = {"Accept": "application/json"}
        candidates: list[Candidate] = []
        seen_ids: set[str] = set()

        exact = self._try_exact(query, headers)
        if exact is not None:
            candidates.append(exact)
            seen_ids.add(exact.remote_id)

        for item in self._search_items(query, headers):
            cand = self._to_candidate(item)
            if cand.remote_id in seen_ids:
                continue
            seen_ids.add(cand.remote_id)
            candidates.append(cand)
            if len(candidates) >= limit * 2:
                break

        return candidates

    def _try_exact(self, query: TrackQuery, headers: dict[str, str]) -> Candidate | None:
        """/get 精确匹配；404 等任何失败都属正常，静默降级返回 None。"""
        if not (query.duration and query.artist and query.title):
            return None

        params = {
            "track_name": query.title,
            "artist_name": query.artist,
            "duration": int(query.duration),
        }

        try:
            data = self.http.get_json(f"{self.BASE}/get", params=params, headers=headers)
        except Exception:  # noqa: BLE001 - 精确匹配失败必须降级，不能抛给用户
            return None

        if not isinstance(data, dict):
            return None

        cand = self._to_candidate(data)
        # 没歌词的精确命中没有意义，继续走搜索链
        return cand if cand.has_lyrics else None

    def _search_items(self, query: TrackQuery, headers: dict[str, str]) -> list[dict[str, Any]]:
        """/search 两段降级：先按字段搜，拿不到再退化为 q 泛搜。"""
        title = query.title.strip()
        artist = query.artist.strip()

        if title and artist:
            params: dict[str, Any] = {"track_name": title, "artist_name": artist}
        else:
            params = {"q": title or artist}

        items = self._request_search(params, headers)
        if items or not (title and artist):
            return items

        # 按字段太严格时，改用 "标题 歌手" 整串泛搜
        return self._request_search({"q": f"{title} {artist}"}, headers)

    def _request_search(
        self, params: dict[str, Any], headers: dict[str, str]
    ) -> list[dict[str, Any]]:
        data = self.http.get_json(f"{self.BASE}/search", params=params, headers=headers)
        if not isinstance(data, list):
            return []
        return [item for item in data if isinstance(item, dict)]

    def _to_candidate(self, item: dict[str, Any]) -> Candidate:
        """把 LRCLIB 的一条记录映射为统一 Candidate。"""
        duration = item.get("duration")
        return Candidate(
            source=self.name,
            title=item.get("trackName") or item.get("name") or "",
            artist=item.get("artistName") or "",
            album=item.get("albumName") or "",
            duration=float(duration) if duration else None,
            instrumental=bool(item.get("instrumental")),
            synced=item.get("syncedLyrics") or "",
            plain=item.get("plainLyrics") or "",
            remote_id=str(item.get("id") or ""),
            extra={"hasWordSync": bool(item.get("hasWordSync"))},
        )


__all__ = ["LrclibSource"]
