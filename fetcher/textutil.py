"""文本归一化与 LRC 解析工具（Step 2 实现）。

计划对外接口见项目《开发指令.md》的「接口契约」一节，签名已冻结：
    to_simplified / strip_brackets / normalize / split_artists
    parse_lrc_lines / is_valid_lrc / lrc_metadata
    build_lrc / strip_lrc_metadata / normalize_lrc
"""

from __future__ import annotations

import re
import unicodedata

try:
    from zhconv import convert as _zh_convert
except ImportError:
    # zhconv 是可选能力；缺失时保持原文，避免整个工具无法启动。
    _zh_convert = None


# 只匹配成对括号，避免误伤 "AC/DC" 这类无括号标题
_BRACKET_RE = re.compile(r"[（(\[【][^）)\]】]*[）)\]】]")

# feat./ft./featuring 及其之后的内容都要去掉；用前后边界避免命中单词内部的字母
_FEAT_RE = re.compile(
    r"(?<![A-Za-z0-9_])(?:feat(?:uring)?|ft)\.?(?![A-Za-z0-9_]).*$",
    re.IGNORECASE,
)

_ARTIST_SPLIT_RE = re.compile(r"[/、,，;；&+]|\b(?:feat|ft)\b\.?", re.IGNORECASE)

# 时间戳：同时支持 [00:29.30] 与 [00:29:30] 两种分隔符，小数位 1~3 位
LRC_TIME_RE = re.compile(r"\[(\d{1,3}):(\d{1,2})(?:[.:](\d{1,3}))?\]")

# 元信息行：parse_lrc_lines 必须跳过
LRC_TAG_RE = re.compile(
    r"^\[(ti|ar|al|by|offset|re|ve|length|kana):.*\]\s*$",
    re.IGNORECASE,
)


def to_simplified(text: str) -> str:
    """将文本转换为简体中文；zhconv 不可用或文本为空时原样返回。"""
    if not text or _zh_convert is None:
        return text
    return _zh_convert(text, "zh-cn")


def strip_brackets(text: str) -> str:
    """移除成对括号及其内容，不影响 "AC/DC" 等无括号文本。"""
    return _BRACKET_RE.sub(" ", text or "")


def _replace_separators(text: str) -> str:
    """把标点、符号与空白统一替换为空格。"""
    return "".join(
        " "
        if char.isspace() or unicodedata.category(char).startswith(("P", "S", "Z"))
        else char
        for char in text
    )


def normalize(text: str, drop_brackets: bool = False) -> str:
    """把标题/歌手名归一化为可比形式：全角转半角、小写、去 feat、去标点。"""
    if not text:
        return ""

    # NFKC 必须最先做：全角英数与标点要先折成半角，再走后续规则
    normalized = unicodedata.normalize("NFKC", text).lower()
    normalized = _FEAT_RE.sub(" ", normalized)
    if drop_brackets:
        normalized = strip_brackets(normalized)
    normalized = _replace_separators(normalized)
    return " ".join(normalized.split())


def split_artists(raw: str) -> list[str]:
    """按 / 、 , ， ; ； & + 和独立单词 feat/ft 拆分歌手名。"""
    if not raw:
        return []

    raw = unicodedata.normalize("NFKC", raw)
    parts = (normalize(part) for part in _ARTIST_SPLIT_RE.split(raw))
    return [part for part in parts if part]


def parse_lrc_lines(lrc: str) -> list[tuple[float, str]]:
    """解析 LRC 为 [(秒, 正文)]，跳过空行与元信息行，最后按时间升序。"""
    lines: list[tuple[float, str]] = []

    for raw_line in (lrc or "").splitlines():
        line = raw_line.strip()
        if not line or LRC_TAG_RE.match(line):
            continue

        timestamps = LRC_TIME_RE.findall(line)
        if not timestamps:
            continue

        text = LRC_TIME_RE.sub("", line).strip()
        if not text:
            continue

        # 一行可能有多个时间戳（如 "[00:01.00][00:35.00]副歌"），必须全部展开
        for minutes, seconds, fraction in timestamps:
            hundredths = int(fraction[:2].ljust(2, "0")) if fraction else 0
            timestamp = int(minutes) * 60 + int(seconds) + hundredths / 100
            lines.append((timestamp, text))

    lines.sort(key=lambda item: item[0])
    return lines


def is_valid_lrc(lrc: str, min_lines: int = 3) -> bool:
    """至少有 min_lines 条带时间戳的歌词，才认为是可用的同步歌词。"""
    return len(parse_lrc_lines(lrc)) >= min_lines


def lrc_metadata(lrc: str) -> dict[str, str]:
    """抽取 [ti:][ar:][al:][by:][offset:] 等元信息，key 统一小写。"""
    metadata: dict[str, str] = {}

    for raw_line in (lrc or "").splitlines():
        line = raw_line.strip()
        match = LRC_TAG_RE.match(line)
        if match is None:
            continue
        key = match.group(1).lower()
        value = line[1:-1].partition(":")[2].strip()
        metadata[key] = value

    return metadata


def _format_timestamp(seconds: float) -> str:
    """把秒数格式化为统一的 [mm:ss.xx]（分钟两位、秒两位、小数两位）。"""
    total_hundredths = int(max(0.0, seconds) * 100 + 0.5)
    minutes, remainder = divmod(total_hundredths, 6000)
    whole_seconds, hundredths = divmod(remainder, 100)
    return f"[{minutes:02d}:{whole_seconds:02d}.{hundredths:02d}]"


def build_lrc(
    lines: list[tuple[float, str]], metadata: dict[str, str] | None = None
) -> str:
    """把 [(秒, 正文)] 拼回 LRC 文本，可选写入元信息头。"""
    output: list[str] = []

    for key in ("ti", "ar", "al", "by", "offset"):
        value = metadata.get(key) if metadata else None
        if value:
            output.append(f"[{key}:{value}]")

    output.extend(f"{_format_timestamp(seconds)}{text}" for seconds, text in lines)
    return "\n".join(output)


def strip_lrc_metadata(lrc: str) -> str:
    """只保留歌词正文行，丢弃元信息与时间戳，用 \n 连接。"""
    return "\n".join(text for _, text in parse_lrc_lines(lrc))


def normalize_lrc(lrc: str, simplify: bool = True) -> str:
    """解析后按统一排版重建 LRC，可选对元信息与正文做繁转简。"""
    metadata = lrc_metadata(lrc)
    lines = parse_lrc_lines(lrc)

    if simplify:
        metadata = {key: to_simplified(value) for key, value in metadata.items()}
        lines = [(seconds, to_simplified(text)) for seconds, text in lines]

    return build_lrc(lines, metadata)
