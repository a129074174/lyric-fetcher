"""Step 5 验收脚本：逐个源验证 search + fetch。

运行：
    uv run python tools/check_all_sources.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fetcher.adapters import ALL_SOURCES
from fetcher.client import HttpClient
from fetcher.matcher import rank
from fetcher.models import TrackQuery


def main() -> int:
    query = TrackQuery("晴天", "周杰伦", duration=270.0)

    with HttpClient() as http:
        for source_cls in ALL_SOURCES:
            source = source_cls(http)

            try:
                candidates = source.search(query)
            except Exception as exc:  # noqa: BLE001 - 单源失败不得中断其他源
                print(f"源 {source.name} 失败: {exc}")
                continue

            ranked = rank(query, candidates)
            print(f"--- {source.name} ({len(ranked)} 条) ---")
            for cand in ranked[:3]:
                print(cand.summary())

            if not ranked:
                continue

            try:
                fetched = source.fetch(ranked[0])
            except Exception as exc:  # noqa: BLE001
                print(f"源 {source.name} fetch 失败: {exc}")
                continue

            print(f"{source.name} synced 前 3 行: {fetched.synced.splitlines()[:3]}")
            if not fetched.synced:
                print(f"{source.name} plain 前 3 行: {fetched.plain.splitlines()[:3]}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
