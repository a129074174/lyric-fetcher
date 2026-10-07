"""Step 4 验收脚本：验证 HttpClient 与 LrclibSource。

运行：
    uv run python tools/check_lrclib.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fetcher.adapters.lrclib import LrclibSource
from fetcher.client import HttpClient, HttpError
from fetcher.matcher import rank
from fetcher.models import TrackQuery


def main() -> int:
    query = TrackQuery("晴天", "周杰伦", duration=270.0)

    with HttpClient() as http:
        # 1) HttpClient 基本可用性
        try:
            resp = http.get("https://lrclib.net/api/search", params={"q": "晴天"})
            print(f"(HttpClient) OK, status={resp.status_code}")
        except HttpError as exc:
            print(f"(HttpClient) 失败: {exc}")
            return 1

        # 2) LrclibSource 搜索
        source = LrclibSource(http)
        try:
            candidates = source.search(query)
        except HttpError as exc:
            print(f"LrclibSource.search 失败: {exc}")
            return 1

        ranked = rank(query, candidates)
        print(f"候选数: {len(ranked)}")

        # 3) 前 3 条排名
        for cand in ranked[:3]:
            print(cand.summary())

        # 4) 第一条的同步歌词前 5 行
        if ranked:
            synced_lines = ranked[0].synced.splitlines()[:5]
            print("synced 前 5 行:")
            print(synced_lines)
            if not synced_lines:
                print("（第一条没有同步歌词，plain 前 5 行:）")
                print(ranked[0].plain.splitlines()[:5])
        else:
            print("没有候选")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
