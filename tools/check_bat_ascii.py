"""Step 8 自检：确认 .bat 全是 ASCII 字节。

cmd.exe 按当前代码页（936/GBK）解码 .bat，文件里若有 UTF-8 中文，
多字节序列会被吞掉换行，导致 "xxx 不是内部或外部命令" 这类诡异报错。
所以 .bat 里一个非 ASCII 字节都不能有，中文提示一律交给 Python 输出。

运行：
    uv run python tools/check_bat_ascii.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "fetch-lyrics.bat"


def main() -> int:
    if not TARGET.exists():
        print(f"找不到文件: {TARGET}", file=sys.stderr)
        return 1

    raw = TARGET.read_bytes()
    offenders: list[tuple[int, str]] = []

    for lineno, line in enumerate(raw.split(b"\n"), start=1):
        for byte in line:
            if byte > 0x7F:
                offenders.append((lineno, line.decode("utf-8", errors="replace")))
                break

    if offenders:
        print(f"{TARGET.name}: 发现非 ASCII 字节，违规行如下:", file=sys.stderr)
        for lineno, text in offenders:
            print(f"  第 {lineno} 行: {text}", file=sys.stderr)
        return 1

    print(f"{TARGET.name}: 纯 ASCII 检查通过 (0 个非 ASCII 字节)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
