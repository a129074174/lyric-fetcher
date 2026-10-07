"""命令行入口。

Step 1 阶段只保证：--version 可用、子命令骨架存在、未实现的功能给出明确退出码。
后续步骤逐步把 search / file / scan 填上。

退出码约定：
    0 = 成功
    1 = 未命中或运行时错误
    2 = 参数错误 / 功能未实现
"""

from __future__ import annotations

import argparse
import sys

from . import __version__

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_USAGE = 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fetcher",
        description="多源歌词抓取工具：按歌名搜索、为本地音频批量配歌词。",
    )
    parser.add_argument("--version", action="version", version=__version__)

    sub = parser.add_subparsers(dest="command", metavar="<command>")

    p_search = sub.add_parser("search", help="按歌名搜索歌词")
    p_search.add_argument("title", nargs="?", default="", help="歌曲标题")
    p_search.add_argument("-a", "--artist", default="", help="歌手")
    p_search.add_argument("--all", action="store_true", help="列出全部达标候选")
    p_search.add_argument("-o", "--output", default="", help="歌词输出到指定文件")
    p_search.add_argument("--plain", action="store_true", help="输出无时间轴的纯文本")

    p_file = sub.add_parser("file", help="为单个音频文件抓取歌词")
    p_file.add_argument("path", nargs="?", default="", help="音频文件路径")
    p_file.add_argument("-o", "--output", default="", help="歌词输出路径")
    p_file.add_argument("--overwrite", action="store_true", help="覆盖已存在的 .lrc")

    p_scan = sub.add_parser("scan", help="扫描目录批量抓取")
    p_scan.add_argument("root", nargs="?", default="", help="目录路径")
    p_scan.add_argument("--no-recursive", action="store_true", help="不递归子目录")
    p_scan.add_argument("--overwrite", action="store_true", help="覆盖已存在的 .lrc")
    p_scan.add_argument("--min-score", type=float, default=0.75, help="匹配分数下限")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return EXIT_OK

    print("not implemented yet", file=sys.stderr)
    return EXIT_USAGE


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
