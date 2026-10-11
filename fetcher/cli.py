"""命令行入口。

四个子命令：
    search  <歌名> [-a 歌手] [--all] [-o 文件] [--format {lrc,srt,txt}]
    file    <音频路径> [-o 文件] [--overwrite] [--format {lrc,srt,txt}]
    scan    <目录> [--no-recursive] [--overwrite] [--format {lrc,srt,txt}]
    convert <.lrc 或目录> [-o 输出] [--no-recursive]

退出码约定：
    0 = 成功
    1 = 未命中或运行时错误
    2 = 参数错误 / 功能未实现
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from . import __version__
from .adapters import ALL_SOURCES
from .adapters.base import LyricSource
from .client import HttpClient
from .formats import lrc_to_srt
from .library import AudioFile, embed_directory, read_audio_file, write_lrc, write_srt
from .models import Candidate, TrackQuery
from .service import LyricService
from .textutil import strip_lrc_metadata

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_USAGE = 2

DEFAULT_SOURCES = "lrclib,netease,qqmusic"


def _build_common_parser() -> argparse.ArgumentParser:
    """全局选项。

    同时挂在顶层与每个子命令上（add_help=False 避免子命令吞掉 -h），
    这样 `fetcher --json search ...` 和 `fetcher search ... --json` 两种写法都能用。
    """
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="以 JSON 输出")
    common.add_argument("-q", "--quiet", action="store_true", help="只输出最终歌词")
    common.add_argument(
        "--sources",
        default=DEFAULT_SOURCES,
        help=f"启用的源，逗号分隔（默认 {DEFAULT_SOURCES}）",
    )
    common.add_argument("--show-errors", action="store_true", help="打印各源的失败信息")
    common.add_argument(
        "--min-score", type=float, default=0.75, help="匹配分数下限（默认 0.75）"
    )
    return common


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fetcher",
        description="多源歌词抓取工具：按歌名搜索、为本地音频批量配歌词。",
        parents=[_build_common_parser()],
    )
    parser.add_argument("--version", action="version", version=__version__)

    common = _build_common_parser()
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    _format_help = "输出格式：lrc（默认）、srt（VLC 字幕）、txt（纯文本）"

    p_search = sub.add_parser("search", parents=[common], help="按歌名搜索歌词")
    p_search.add_argument("title", nargs="?", default="", help="歌曲标题")
    p_search.add_argument("-a", "--artist", default="", help="歌手")
    p_search.add_argument("--all", action="store_true", help="列出全部达标候选")
    p_search.add_argument("-o", "--output", default="", help="歌词输出到指定文件")
    p_search.add_argument(
        "--format",
        dest="output_format",
        choices=["lrc", "srt", "txt"],
        default="lrc",
        help=_format_help,
    )
    p_search.add_argument("--plain", action="store_true", help="同 --format txt")

    p_file = sub.add_parser("file", parents=[common], help="为单个音频文件抓取歌词")
    p_file.add_argument("path", nargs="?", default="", help="音频文件路径")
    p_file.add_argument("-o", "--output", default="", help="歌词输出路径")
    p_file.add_argument("--overwrite", action="store_true", help="覆盖已存在的 .lrc")
    p_file.add_argument(
        "--format",
        dest="output_format",
        choices=["lrc", "srt", "txt"],
        default="lrc",
        help=_format_help,
    )
    p_file.add_argument("--plain", action="store_true", help="同 --format txt")

    p_scan = sub.add_parser("scan", parents=[common], help="扫描目录批量抓取")
    p_scan.add_argument("root", nargs="?", default="", help="目录路径")
    p_scan.add_argument("--no-recursive", action="store_true", help="不递归子目录")
    p_scan.add_argument("--overwrite", action="store_true", help="覆盖已存在的 .lrc")
    p_scan.add_argument(
        "--format",
        dest="output_format",
        choices=["lrc", "srt", "txt"],
        default="lrc",
        help=_format_help,
    )
    p_scan.add_argument("--plain", action="store_true", help="同 --format txt")

    p_convert = sub.add_parser("convert", help="把已有 .lrc 转成其他格式（支持目录）")
    p_convert.add_argument("path", nargs="?", default="", help=".lrc 文件或目录")
    p_convert.add_argument("-o", "--output", default="", help="输出文件或目录")
    p_convert.add_argument("--json", action="store_true", help="以 JSON 输出")
    p_convert.add_argument("-q", "--quiet", action="store_true", help="只输出最终路径")
    p_convert.add_argument(
        "--format",
        dest="output_format",
        choices=["srt"],
        default="srt",
        help="目标格式（默认 srt）",
    )
    p_convert.add_argument(
        "--default-duration", type=float, default=5.0, help="末句默认显示秒数"
    )
    p_convert.add_argument("--no-recursive", action="store_true", help="目录不递归")

    return parser


def main(argv: list[str] | None = None) -> int:
    # Windows 控制台默认用 GBK，中文歌词与 JSON 会乱码；统一切成 UTF-8
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            pass

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return EXIT_OK

    if args.command != "convert":
        try:
            sources = _parse_sources(args.sources)
        except ValueError as exc:
            print(f"参数错误: {exc}", file=sys.stderr)
            return EXIT_USAGE

    try:
        if args.command == "search":
            return _cmd_search(args, sources)
        if args.command == "file":
            return _cmd_file(args, sources)
        if args.command == "scan":
            return _cmd_scan(args, sources)
        if args.command == "convert":
            return _cmd_convert(args)
    except Exception as exc:  # noqa: BLE001 - 绝不把裸栈抛给用户
        print(f"运行失败: {exc}", file=sys.stderr)
        return EXIT_FAIL

    print(f"未实现的子命令: {args.command}", file=sys.stderr)
    return EXIT_USAGE


# ------------------------------------------------------------------ 子命令


def _output_format(args: argparse.Namespace) -> str:
    """--plain 是 --format txt 的兼容别名。"""
    if args.plain:
        return "txt"
    return args.output_format


def _cmd_search(args: argparse.Namespace, sources: list[str]) -> int:
    if not args.title.strip():
        print("参数错误: search 需要提供歌名", file=sys.stderr)
        return EXIT_USAGE

    query = TrackQuery(title=args.title.strip(), artist=(args.artist or "").strip())
    output_format = _output_format(args)

    with _build_service(sources) as service:
        # --all 与 --json 才需要完整候选表，否则只取最佳一条，省下大量 fetch
        candidates = (
            service.find_all(query, min_score=args.min_score)
            if (args.all or args.json)
            else []
        )
        best = service.find(query, min_score=args.min_score)

        if args.json:
            payload: dict[str, Any] = {
                "query": {"title": query.title, "artist": query.artist},
                "best": _cand_json(best) if best else None,
                "candidates": [_cand_json(cand) for cand in candidates],
                "errors": service.errors,
            }
            _print_json(payload)
            return EXIT_OK if best else EXIT_FAIL

        if args.all and not args.quiet and candidates:
            print("候选排名:")
            for cand in candidates:
                print("  " + cand.summary())
        elif not args.quiet and best is not None:
            print("最佳候选:")
            print("  " + best.summary())

        if best is None:
            print(f"未找到匹配结果: {query.describe()}", file=sys.stderr)
            _maybe_print_errors(service, args)
            return EXIT_FAIL

        text = _render_text(best, format=output_format)

        if args.output:
            target = _write_text(args.output, text)
            if not args.quiet:
                print(f"已写入: {target}")
        elif args.quiet:
            print(text)
        else:
            label = {"lrc": "歌词", "srt": "SRT 字幕", "txt": "歌词"}.get(
                output_format, "歌词"
            )
            print("")
            print(f"{label}:")
            print(text)

        _maybe_print_errors(service, args)

    return EXIT_OK


def _cmd_file(args: argparse.Namespace, sources: list[str]) -> int:
    if not args.path.strip():
        print("参数错误: file 需要提供音频路径", file=sys.stderr)
        return EXIT_USAGE

    output_format = _output_format(args)
    audio = read_audio_file(args.path)
    if audio is None:
        print(f"无法读取音频: {args.path}", file=sys.stderr)
        return EXIT_FAIL

    existing_ext = ".srt" if output_format == "srt" else ".lrc"
    existing_path = Path(args.path).with_suffix(existing_ext)
    if existing_path.exists() and not args.overwrite:
        print(
            f"已存在 {existing_ext}，跳过（加 --overwrite 覆盖）: {audio.path}",
            file=sys.stderr,
        )
        return EXIT_OK

    with _build_service(sources) as service:
        best = _find_for_audio(service, audio, args.min_score)

        if best is None:
            print(f"未找到匹配结果: {audio.name}", file=sys.stderr)
            if args.json:
                _print_json(
                    {
                        "type": "file",
                        "path": audio.path,
                        "matched": False,
                        "errors": service.errors,
                    }
                )
            _maybe_print_errors(service, args)
            return EXIT_FAIL

        text = _render_text(best, format=output_format)
        if args.output:
            target = args.output
            _write_text(target, text)
        elif output_format == "srt":
            target = write_srt(audio.path, best.best_text)
        else:
            target = write_lrc(audio.path, best.best_text)

        if args.json:
            _print_json(
                {
                    "type": "file",
                    "path": audio.path,
                    "matched": True,
                    "lyrics": target,
                    "format": output_format,
                    "candidate": _cand_json(best),
                    "errors": service.errors,
                }
            )
        elif args.quiet:
            print(target)
        else:
            print(f"[{best.score:.2f}] {best.source} → {target}")

        _maybe_print_errors(service, args)

    return EXIT_OK


def _cmd_scan(args: argparse.Namespace, sources: list[str]) -> int:
    if not args.root.strip():
        print("参数错误: scan 需要提供目录路径", file=sys.stderr)
        return EXIT_USAGE

    output_format = _output_format(args)
    root = Path(args.root)
    if not root.exists():
        print(f"路径不存在: {root}", file=sys.stderr)
        return EXIT_FAIL

    collected: list[str] = []

    def on_progress(done: int, total: int, audio: AudioFile, cand: Candidate | None) -> None:
        if cand is None:
            line = f"[{done}/{total}] {audio.name} → 未命中"
        else:
            line = f"[{done}/{total}] {audio.name} → 命中 ({cand.source}, {cand.score:.2f})"
        if not args.json and not args.quiet:
            print(line)

    with _build_service(sources) as service:
        report = embed_directory(
            root,
            service,
            recursive=not args.no_recursive,
            overwrite=args.overwrite,
            min_score=args.min_score,
            on_progress=on_progress,
            output_format=output_format,
        )
        errors = list(report["errors"]) + list(service.errors)

        if args.json:
            _print_json(
                {
                    "type": "scan",
                    "root": str(root),
                    "summary": {
                        "total": len(report["ok"])
                        + len(report["skipped"])
                        + len(report["failed"]),
                        "ok": len(report["ok"]),
                        "skipped": len(report["skipped"]),
                        "failed": len(report["failed"]),
                    },
                    "ok": list(report["ok"]),
                    "skipped": list(report["skipped"]),
                    "failed": list(report["failed"]),
                    "errors": errors,
                }
            )
            return EXIT_OK

        if not args.quiet:
            print("")
            print(
                f"汇总: 成功 {len(report['ok'])} / 跳过 {len(report['skipped'])} "
                f"/ 失败 {len(report['failed'])}"
            )

        failed = list(report["failed"])
        if failed:
            print("")
            print(f"未生成歌词 ({len(failed)}):")
            for item in failed:
                name = str(item["name"])
                collected.append(name)
                print(f"  {name}")
                if not args.quiet:
                    print(f"      {item['path']}")
        elif not args.quiet:
            print("")
            print("全部曲目都已生成歌词")

        _maybe_print_errors_with(service, args, errors)

    return EXIT_OK


def _cmd_convert(args: argparse.Namespace) -> int:
    if not args.path.strip():
        print("参数错误: convert 需要提供 .lrc 文件或目录路径", file=sys.stderr)
        return EXIT_USAGE

    input_path = Path(args.path)
    if not input_path.exists():
        print(f"路径不存在: {input_path}", file=sys.stderr)
        return EXIT_FAIL

    if input_path.is_file():
        return _convert_single(input_path, args)

    recursive = not args.no_recursive
    lrc_files = input_path.rglob("*.lrc") if recursive else input_path.glob("*.lrc")

    ok = 0
    failed = 0
    for lrc_file in sorted(lrc_files):
        code = _convert_single(lrc_file, args)
        if code == EXIT_OK:
            ok += 1
        else:
            failed += 1

    if not args.json and not args.quiet:
        print("")
        print(f"批量转换完成: 成功 {ok} / 失败 {failed}")

    return EXIT_OK if failed == 0 else EXIT_FAIL


def _convert_single(input_path: Path, args: argparse.Namespace) -> int:
    """转换单个 .lrc 文件。"""
    lrc_text = input_path.read_text(encoding="utf-8")
    total_duration: float | None = None

    # 若存在同名音频文件，可用其时长作为最后一句结束时间
    for ext in (".mp3", ".flac", ".m4a", ".ogg", ".wav"):
        audio_path = input_path.with_suffix(ext)
        if audio_path.exists():
            audio = read_audio_file(audio_path)
            if audio and audio.duration:
                total_duration = audio.duration
                break

    srt_text = lrc_to_srt(
        lrc_text, default_duration=args.default_duration, total_duration=total_duration
    )
    if not srt_text.strip():
        print(f"转换后为空，跳过: {input_path}", file=sys.stderr)
        return EXIT_FAIL

    output_path = Path(args.output) if args.output else input_path.with_suffix(".srt")
    _write_text(output_path, srt_text)

    if args.json:
        _print_json(
            {
                "type": "convert",
                "input": str(input_path),
                "output": str(output_path),
                "format": "srt",
            }
        )
    elif not args.quiet:
        print(f"已转换: {input_path} → {output_path}")

    return EXIT_OK


# ------------------------------------------------------------------ 辅助


def _parse_sources(raw: str) -> list[str]:
    names = [part.strip().lower() for part in (raw or "").split(",") if part.strip()]
    if not names:
        raise ValueError("--sources 不能为空")

    known = {source_cls.name for source_cls in ALL_SOURCES}
    unknown = [name for name in names if name not in known]
    if unknown:
        raise ValueError(f"未知源: {', '.join(unknown)}（可选: {', '.join(sorted(known))}）")

    return names


def _build_service(sources: list[str]) -> LyricService:
    http = HttpClient()
    chosen: list[LyricSource] = [
        source_cls(http) for source_cls in ALL_SOURCES if source_cls.name in sources
    ]
    return LyricService(sources=chosen, http=http)


def _find_for_audio(
    service: LyricService, audio: AudioFile, min_score: float
) -> Candidate | None:
    """标签优先，查不到再退到文件名的两种解释，取分高者。"""
    best: Candidate | None = None

    queries: list[TrackQuery] = []
    if audio.title:
        queries.append(
            TrackQuery(
                title=audio.title,
                artist=audio.artist,
                album=audio.album,
                duration=audio.duration,
            )
        )
    queries.extend(
        TrackQuery(title=title, artist=artist, duration=audio.duration)
        for title, artist in audio.candidates
    )

    for query in queries:
        if not query.title:
            continue
        cand = service.find(query, min_score=min_score)
        if cand is not None and (best is None or cand.score > best.score):
            best = cand

    return best


def _render_text(cand: Candidate, format: str) -> str:
    if format == "txt":
        return strip_lrc_metadata(cand.synced) if cand.has_synced else cand.plain
    if format == "srt":
        return lrc_to_srt(cand.best_text)
    return cand.best_text


def _write_text(path: str | Path, text: str) -> str:
    target = Path(path)
    with open(target, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
        if not text.endswith("\n"):
            handle.write("\n")
    return str(target)


def _cand_json(cand: Candidate) -> dict[str, Any]:
    return {
        "source": cand.source,
        "title": cand.title,
        "artist": cand.artist,
        "album": cand.album,
        "duration": cand.duration,
        "score": cand.score,
        "type": "LRC" if cand.has_synced else "TXT",
        "lyrics": cand.best_text,
    }


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _maybe_print_errors(service: LyricService, args: argparse.Namespace) -> None:
    _maybe_print_errors_with(service, args, service.errors)


def _maybe_print_errors_with(
    service: LyricService, args: argparse.Namespace, errors: list[str]
) -> None:
    if args.show_errors and errors:
        print("", file=sys.stderr)
        print("源错误信息:", file=sys.stderr)
        for err in errors:
            print(f"  {err}", file=sys.stderr)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
