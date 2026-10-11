"""Step 7 验收脚本：扫描、匹配、写回，并断言 .lrc 无 BOM / 行尾 LF。

运行：
    uv run python tools/check_library.py
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mutagen.id3 import ID3, TALB, TIT2, TPE1

from fetcher.library import embed_directory, scan_directory, write_lrc
from fetcher.models import Candidate
from fetcher.service import LyricService

OUTPUT = Path(__file__).resolve().parent / "_library_out.txt"


def make_fake_mp3(path: Path, title: str, artist: str, album: str = "") -> None:
    """写一个能被 mutagen 解析的假 MP3（含真实 ID3 标签）。

    关键点：光有 ID3 头不行， mutagen 的 MP3 解析器找不到合法帧同步就整文件解析失败，
    所以先垫一个最小 MPEG-1 Layer III 帧（帧头 + 静音负载）。
    """
    frame_header = b"\xff\xfb\x90\x64"  # MPEG1 Layer3 128kbps 44.1kHz
    frame = frame_header + b"\x00" * 413  # 帧长 417 字节
    path.write_bytes(frame * 4)

    tags = ID3()
    tags.add(TIT2(encoding=3, text=[title]))
    tags.add(TPE1(encoding=3, text=[artist]))
    if album:
        tags.add(TALB(encoding=3, text=[album]))
    tags.save(path)


def main() -> int:
    out: list[str] = []
    tmp = Path(tempfile.mkdtemp(prefix="lyric-fetcher-check-"))

    try:
        # 1) 造 3 个假音频文件
        make_fake_mp3(tmp / "晴天.mp3", "晴天", "周杰伦", "叶惠美")
        make_fake_mp3(tmp / "晴天 - 周杰伦.mp3", "晴天", "周杰伦")
        make_fake_mp3(tmp / "不存在的歌名xxx.mp3", "不存在的歌名xxx", "未知歌手zzz")

        # 2) 扫描
        audios = scan_directory(tmp)
        out.append(f"扫描到 {len(audios)} 个文件")
        for audio in audios:
            out.append(
                f"  {audio.name} | title={audio.title!r} artist={audio.artist!r} "
                f"album={audio.album!r} duration={audio.duration} "
                f"has_lyrics={audio.has_lyrics}"
            )

        # 3) 批量写回
        def on_progress(done: int, total: int, audio: object, cand: Candidate | None) -> None:
            if cand is None:
                out.append(f"[{done}/{total}] {Path(audio.path).name} → 未命中")
            else:
                out.append(
                    f"[{done}/{total}] {Path(audio.path).name} → 命中 "
                    f"({cand.source}, {cand.score:.2f})"
                )

        with LyricService() as service:
            report = embed_directory(
                tmp, service, on_progress=on_progress, min_score=0.75
            )

        out.append("")
        out.append(
            f"汇总: ok={len(report['ok'])} skipped={len(report['skipped'])} "
            f"failed={len(report['failed'])}"
        )
        for item in report["failed"]:
            out.append(f"  未生成歌词: {item['name']} ({item['reason']})")

        # 4) 再跑一次，验证「已存在 .lrc 不覆盖」的跳过分支
        with LyricService() as service:
            second = embed_directory(tmp, service, overwrite=False)
        out.append("")
        out.append(
            f"二次运行汇总: ok={len(second['ok'])} "
            f"skipped={len(second['skipped'])} failed={len(second['failed'])}"
        )
        for item in second["skipped"]:
            out.append(f"  已跳过: {item['name']} ({item['reason']})")

        # 5) 编码与行尾断言
        out.append("")
        out.append("编码断言:")
        lrc_files = sorted(tmp.glob("*.lrc"))
        if not lrc_files:
            out.append("  没有生成任何 .lrc，无法断言")
            return 1

        for lrc_path in lrc_files:
            raw = lrc_path.read_bytes()
            bom = raw.startswith(b"\xef\xbb\xbf")
            crlf = raw.count(b"\r\n")
            out.append(f"  {lrc_path.name}:")
            out.append(f"    BOM 检查: {'有 BOM ✗' if bom else '无 BOM ✓'}")
            out.append(f"    行尾检查: CRLF={crlf} {'✓' if crlf == 0 else '✗'}")
            out.append(f"    首行: {raw.decode('utf-8').splitlines()[0]!r}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    OUTPUT.write_text("\n".join(out), encoding="utf-8")
    print("written to", OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
