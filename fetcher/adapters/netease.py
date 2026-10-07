"""网易云音乐适配器（Step 5 实现）。

接口要点（已实测）：
    搜索  GET https://music.163.com/api/search/get/web?s=&type=1
          headers: Referer: https://music.163.com/
    歌词  GET https://music.163.com/api/song/lyric?id=&lv=-1&kv=-1&tv=-1
          lrc.lyric -> synced；tlyric.lyric -> 翻译；klyric.lyric -> 无时间轴文本
    注意  duration 返回值是「毫秒」，必须 /1000 转成秒
"""

from __future__ import annotations
