"""QQ 音乐适配器（Step 5 实现）。

接口要点（已实测）：
    搜索  GET https://c.y.qq.com/soso/fcgi-bin/client_search_cp?w=&format=json
          headers: Referer: https://y.qq.com/
    歌词  GET https://c.y.qq.com/lyric/fcgi-bin/fcg_query_lyric_new.fcg?songmid=&nobase64=1
          headers: Referer: https://y.qq.com/portal/player.html
    注意  歌词接口 content-type 谎报为 text/html，body 其实是 JSON，
          依赖 HttpClient.get_json 的降级解析分支兜住
"""

from __future__ import annotations
