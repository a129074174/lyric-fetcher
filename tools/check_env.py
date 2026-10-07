"""环境自检：确认 Python 版本、依赖与包结构就绪。

用法：
    .venv\\Scripts\\python.exe tools\\check_env.py
    或  uv run python tools/check_env.py
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

# 允许以脚本方式直接运行（sys.path[0] 会是 tools/，导致 import fetcher 失败）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

TARGET_PY = (3, 12)
PACKAGES = ("httpx", "zhconv", "mutagen")


def main() -> int:
    print("=" * 52)
    print(" lyric-fetcher  -  environment self-check")
    print("=" * 52)

    problems: list[str] = []

    version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    is_target = sys.version_info[:2] == TARGET_PY
    print(f"[1/3] Python       : {version}")
    if is_target:
        print("      -> OK")
    else:
        print(f"      -> WARN: project targets {TARGET_PY[0]}.{TARGET_PY[1]}.x"
              " (needed by later stages)")

    print("[2/3] dependencies :")
    for name in PACKAGES:
        try:
            mod = importlib.import_module(name)
        except ImportError:
            print(f"      {name:<10} MISSING")
            problems.append(name)
            continue
        shown = getattr(mod, "__version__", None) or getattr(mod, "version_string", None)
        print(f"      {name:<10} {shown or 'installed'}")

    print("[3/3] package      :")
    try:
        pkg = importlib.import_module("fetcher")
        print(f"      fetcher    {getattr(pkg, '__version__', '?')}")
        importlib.import_module("fetcher.cli")
        importlib.import_module("fetcher.models")
        print("      fetcher.cli / fetcher.models importable")
    except Exception as exc:  # noqa: BLE001 - 自检要报告一切失败
        print(f"      fetcher    FAILED -> {type(exc).__name__}: {exc}")
        problems.append("fetcher")

    print()
    if problems:
        print(f"FAILED: {len(problems)} problem(s) -> {', '.join(problems)}")
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
