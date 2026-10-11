"""Step 6 验收脚本：验证 LyricService 的聚合、繁简统一与降级。

运行：
    uv run python tools/check_service.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fetcher.models import Candidate, TrackQuery
from fetcher.service import LyricService

OUTPUT = Path(__file__).resolve().parent / "_service_out.txt"


def dump(cand: Candidate | None, label: str) -> list[str]:
    lines = [f"--- {label} ---"]
    if cand is None:
        lines.append("未命中")
        return lines

    kind = "LRC" if cand.has_synced else "TXT"
    lines.append(cand.summary())
    lines.append(f"来源={cand.source} 类型={kind}")

    text = cand.best_text
    body = text.splitlines() if cand.has_synced else text.splitlines()
    lines.append("歌词前 5 行:")
    lines.extend(f"  {line}" for line in body[:5])
    return lines


def main() -> int:
    out: list[str] = []

    with LyricService() as service:
        query = TrackQuery("晴天", "周杰伦", duration=270.0)

        best = service.find(query)
        out.append("=== find ===")
        out.extend(dump(best, "最佳候选")[1:])

        all_cands = service.find_all(query)
        out.append("")
        out.append("=== find_all ===")
        if all_cands:
            for cand in all_cands:
                out.append(cand.summary())
        else:
            out.append("（无达标候选）")

        # 不带时长也要能找到
        no_duration = TrackQuery("晴天", "周杰伦")
        found = service.find(no_duration)
        out.append("")
        out.append("=== 不带 duration ===")
        out.extend(dump(found, "结果")[1:])

        if service.errors:
            out.append("")
            out.append("=== 源错误 ===")
            out.extend(f"  {err}" for err in service.errors)

    OUTPUT.write_text("\n".join(out), encoding="utf-8")
    print("written to", OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
