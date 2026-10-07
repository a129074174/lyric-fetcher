"""多源聚合调度（Step 6 实现）。

计划对外接口见项目《开发指令.md》的「接口契约」一节，签名已冻结：
    class LyricService(sources=None, http=None)
        .search(query, limit=8) / .fetch_lyrics(cand)
        .find(query, min_score=0.75, prefer_synced=True) / .find_all(query, min_score=0.75)
        .close() / .errors
"""

from __future__ import annotations
