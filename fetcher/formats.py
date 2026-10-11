"""歌词格式转换器。

VLC Media Player 不支持原生 LRC 作为外挂字幕，但支持 SRT/SSA/ASS/VTT/SMI 等。
这里提供从 LRC 到这些格式的可复用转换函数，核心输出为 SRT（最通用）。

对外接口：
    lrc_to_srt(lrc_text, default_duration=5.0, total_duration=None) -> str
    srt_timestamp(seconds) -> str
"""

from __future__ import annotations

from .textutil import parse_lrc_lines


def srt_timestamp(seconds: float) -> str:
    """秒数 → SRT 时间戳 ``HH:MM:SS,mmm``（逗号分隔毫秒）。"""
    if seconds < 0:
        seconds = 0.0

    total_millis = round(seconds * 1000)
    hours, remainder = divmod(total_millis // 1000, 3600)
    minutes, secs = divmod(remainder, 60)
    millis = total_millis % 1000
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def lrc_to_srt(
    lrc_text: str,
    default_duration: float = 5.0,
    total_duration: float | None = None,
) -> str:
    """把 LRC 转换为 SRT。

    转换规则：
        - LRC 元信息行（[ti:]/[ar:]/[al:] 等）跳过，只保留带时间戳的歌词。
        - 每一句的结束时间取下一句的开始时间；最后一句若提供总时长则到结尾，
          否则使用 default_duration。
        - 多时间戳行会按 parse_lrc_lines 展开为独立 SRT 条目。
    """
    lines = parse_lrc_lines(lrc_text)
    if not lines:
        return ""

    entries: list[str] = []
    for index, (start, text) in enumerate(lines, start=1):
        # 结束时间：下一条开始时间，或总时长，或默认延续时长
        if index < len(lines):
            end = lines[index][0]
        elif total_duration is not None and total_duration > start:
            end = total_duration
        else:
            end = start + default_duration

        # 避免 0 长度或负数区间（至少 0.5 秒可见）
        if end <= start:
            end = start + 0.5

        entries.append(
            f"{index}\n{srt_timestamp(start)} --> {srt_timestamp(end)}\n{text}\n"
        )

    return "\n".join(entries)
