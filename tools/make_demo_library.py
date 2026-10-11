"""造一批带真实 ID3 标签的假 MP3，用于验证 file / scan 子命令。

运行：
    uv run python tools/make_demo_library.py [目标目录]
"""

from __future__ import annotations

import sys
from pathlib import Path

from mutagen.id3 import ID3, TALB, TIT2, TPE1

# 最小可解析的 MPEG-1 Layer III 帧（帧头 + 静音负载）
_FRAME = b"\xff\xfb\x90\x64" + b"\x00" * 413

DEMO_FILES = [
    ("晴天.mp3", "晴天", "周杰伦", "叶惠美"),
    ("稻香.mp3", "稻香", "周杰伦", "魔杰座"),
    ("夜空中最亮的星.mp3", "夜空中最亮的星", "逃跑计划", "世界"),
    ("周杰伦 - 七里香.mp3", "七里香", "周杰伦", "七里香"),
    ("不存在的歌名qqqzzz.mp3", "不存在的歌名qqqzzz", "未知歌手zzz", ""),
]


def make_fake_mp3(path: Path, title: str, artist: str, album: str = "") -> None:
    path.write_bytes(_FRAME * 4)
    tags = ID3()
    tags.add(TIT2(encoding=3, text=[title]))
    tags.add(TPE1(encoding=3, text=[artist]))
    if album:
        tags.add(TALB(encoding=3, text=[album]))
    tags.save(path)


def main() -> int:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("_demo_library")
    target.mkdir(parents=True, exist_ok=True)

    for name, title, artist, album in DEMO_FILES:
        make_fake_mp3(target / name, title, artist, album)

    print(f"已生成 {len(DEMO_FILES)} 个假音频文件于 {target.resolve()}")
    for name, *_ in DEMO_FILES:
        print(f"  {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
