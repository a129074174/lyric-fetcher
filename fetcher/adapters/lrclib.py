"""LRCLIB 适配器（Step 4 实现）。

接口要点（已实测）：
    精确匹配  GET https://lrclib.net/api/get?track_name=&artist_name=&duration=
    模糊搜索  GET https://lrclib.net/api/search?q=  或  ?track_name=&artist_name=
    响应字段  id / trackName / artistName / albumName / duration(秒)
              / instrumental / plainLyrics / syncedLyrics / hasWordSync
"""

from __future__ import annotations
