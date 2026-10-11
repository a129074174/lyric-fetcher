"""本地音乐库扫描与歌词写回（Step 7 实现）。

计划接口见项目《开发指令.md》的「接口契约」一节：
    AudioFile(path, title, artist, album, duration, has_lyrics)
    read_audio_file(path) / scan_directory(root, recursive=True)
    write_lrc(audio_path, lrc_text)
    embed_directory(root, service, recursive=True, overwrite=False,
                    min_score=0.75, on_progress=None) -> dict

两条最容易踩的坑：
    1. 写 .lrc 必须 UTF-8 无 BOM、行尾 LF。用 Path.write_text() 在 Windows 上会把
       \\n 变成 \\r\\n，部分播放器不认，所以显式 open(..., newline="\\n")。
    2. 标签缺失很常见，要从文件名 "歌手 - 歌名.mp3" 反推，且两种解释都要试。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import mutagen

from .models import Candidate, TrackQuery
from .textutil import strip_lrc_metadata

AUDIO_EXTENSIONS = {
    ".mp3",
    ".flac",
    ".m4a",
    ".wav",
    ".ogg",
    ".ape",
    ".wma",
    ".mp4",
    ".mkv",
}

# ID3 / MP4 的标签键与 Vorbis Comments 不同，各容器分别映射
_ID3_KEYS = {"title": "TIT2", "artist": "TPE1", "album": "TALB"}
_MP4_KEYS = {"title": "\xa9nam", "artist": "\xa9ART", "album": "\xa9alb"}
_VORBIS_KEYS = {"title": "title", "artist": "artist", "album": "album"}


@dataclass
class AudioFile:
    """一个本地音频文件及其可供匹配的标签信息。"""

    path: str
    title: str = ""
    artist: str = ""
    album: str = ""
    duration: float | None = None
    has_lyrics: bool = False
    # 标签缺失时从文件名反推出的 (title, artist) 候选解释，交给上层两种都试
    candidates: list[tuple[str, str]] = field(default_factory=list)

    @property
    def name(self) -> str:
        return os.path.basename(self.path)


def read_audio_file(path: str | os.PathLike[str]) -> AudioFile | None:
    """读取音频标签与时长；不是音频或读取失败时返回 None（不抛异常）。"""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix not in AUDIO_EXTENSIONS:
        return None

    info = AudioFile(path=str(path), has_lyrics=_has_lrc(path))

    try:
        title, artist, album, duration = _read_tags(path, suffix)
    except Exception:  # noqa: BLE001 - 坏文件不该中断整批扫描
        title, artist, album, duration = "", "", "", None

    info.title = title
    info.artist = artist
    info.album = album
    info.duration = duration
    info.candidates = _filename_candidates(path)

    return info


def scan_directory(root: str | os.PathLike[str], recursive: bool = True) -> list[AudioFile]:
    """扫描目录下的音频文件，按扩展名白名单筛选并跳过隐藏文件。"""
    root_path = Path(root)
    files: list[AudioFile] = []

    if root_path.is_file():
        audio = read_audio_file(root_path)
        return [audio] if audio else []

    if not root_path.is_dir():
        return files

    walker = root_path.rglob("*") if recursive else root_path.glob("*")
    for entry in walker:
        if entry.name.startswith("."):
            continue
        try:
            if not entry.is_file():
                continue
        except OSError:
            # 权限问题等，跳过该条目
            continue

        if entry.suffix.lower() not in AUDIO_EXTENSIONS:
            continue

        audio = read_audio_file(entry)
        if audio is not None:
            files.append(audio)

    return files


def write_lrc(audio_path: str | os.PathLike[str], lrc_text: str) -> str:
    """把歌词写到音频同目录的同名 .lrc，UTF-8 无 BOM、行尾 LF。"""
    return write_lyrics_file(audio_path, lrc_text, format="lrc")


def write_srt(audio_path: str | os.PathLike[str], lrc_text: str) -> str:
    """把 LRC 歌词转成 SRT 后写到音频同目录的同名 .srt，UTF-8 无 BOM、行尾 LF。"""
    from .formats import lrc_to_srt

    srt_text = lrc_to_srt(lrc_text)
    return write_lyrics_file(audio_path, srt_text, format="srt")


def write_lyrics_file(
    audio_path: str | os.PathLike[str], text: str, format: str = "lrc"
) -> str:
    """把歌词文本写到音频同目录的同名指定格式文件，UTF-8 无 BOM、行尾 LF。"""
    target = Path(audio_path).with_suffix(f".{format}")
    with open(target, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
        if not text.endswith("\n"):
            handle.write("\n")
    return str(target)


def embed_directory(
    root: str | os.PathLike[str],
    service: object,
    recursive: bool = True,
    overwrite: bool = False,
    min_score: float = 0.75,
    on_progress: Callable[[int, int, AudioFile, Candidate | None], None] | None = None,
    output_format: str = "lrc",
) -> dict:
    """批量为目录下的音频文件匹配并写回歌词，返回汇总报告。"""
    audios = scan_directory(root, recursive=recursive)
    total = len(audios)

    ok: list[dict[str, object]] = []
    skipped: list[dict[str, object]] = []
    failed: list[dict[str, object]] = []
    errors: list[str] = []

    ext = f".{output_format}"
    for index, audio in enumerate(audios, start=1):
        try:
            existing = Path(audio.path).with_suffix(ext).exists()
            if existing and not overwrite:
                skipped.append(_record(audio, f"已存在 {ext}"))
                _report(on_progress, index, total, audio, None)
                continue

            cand = _find_best(service, audio, min_score)
            if cand is None:
                failed.append(_record(audio, "未命中"))
                _report(on_progress, index, total, audio, None)
                continue

            if output_format == "srt":
                target = write_srt(audio.path, cand.best_text)
            elif output_format == "txt":
                target = write_lyrics_file(
                    audio.path, strip_lrc_metadata(cand.best_text), format="txt"
                )
            else:
                target = write_lrc(audio.path, cand.best_text)
            ok.append(_record(audio, "已写入", target=target, score=cand.score, source=cand.source))
            _report(on_progress, index, total, audio, cand)
        except Exception as exc:  # noqa: BLE001 - 单首失败必须继续处理下一首
            failed.append(_record(audio, f"处理失败: {exc}"))
            errors.append(f"{audio.path}: {exc}")
            _report(on_progress, index, total, audio, None)

    return {"ok": ok, "skipped": skipped, "failed": failed, "errors": errors}


# ------------------------------------------------------------------ 内部实现


def _has_lrc(path: Path) -> bool:
    return path.with_suffix(".lrc").exists()


def _report(
    on_progress: Callable[[int, int, AudioFile, Candidate | None], None] | None,
    done: int,
    total: int,
    audio: AudioFile,
    cand: Candidate | None,
) -> None:
    if on_progress is not None:
        on_progress(done, total, audio, cand)


def _record(
    audio: AudioFile,
    reason: str,
    target: str | None = None,
    score: float | None = None,
    source: str | None = None,
) -> dict[str, object]:
    item: dict[str, object] = {
        "path": audio.path,
        "name": audio.name,
        "title": audio.title,
        "artist": audio.artist,
        "reason": reason,
    }
    if target:
        item["lrc"] = target
    if score is not None:
        item["score"] = score
    if source:
        item["source"] = source
    return item


def _find_best(service: object, audio: AudioFile, min_score: float) -> Candidate | None:
    """先用标签查；标签没有或查不到时，再试文件名的两种解释，取分高者。"""
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
        try:
            cand = service.find(query, min_score=min_score)  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001 - 单首查询失败继续尝试下一种解释
            continue
        if cand is None:
            continue
        if best is None or cand.score > best.score:
            best = cand

    return best


def _read_tags(path: Path, suffix: str) -> tuple[str, str, str, float | None]:
    """按容器类型分派 mutagen 读取器，返回 (title, artist, album, duration)。"""
    audio = None
    try:
        if suffix == ".mp3":
            from mutagen.mp3 import MP3

            audio = MP3(path)
        elif suffix == ".flac":
            from mutagen.flac import FLAC

            audio = FLAC(path)
        elif suffix in (".m4a", ".mp4"):
            from mutagen.mp4 import MP4

            audio = MP4(path)
        elif suffix == ".wav":
            from mutagen.wave import WAVE

            audio = WAVE(path)
        elif suffix == ".ogg":
            from mutagen.oggvorbis import OggVorbis

            audio = OggVorbis(path)
        else:
            audio = mutagen.File(path, easy=True)
    except Exception:
        # 具体解析器失败时，退回通用解析
        try:
            audio = mutagen.File(path, easy=True)
        except Exception:
            return "", "", "", None

    if audio is None:
        return "", "", "", None

    if suffix == ".mp3":
        tags = _read_id3(audio)
    elif suffix in (".m4a", ".mp4"):
        tags = _read_mapping(audio, _MP4_KEYS)
    else:
        tags = _read_mapping(audio, _VORBIS_KEYS)

    duration = getattr(getattr(audio, "info", None), "length", None)
    return tags[0], tags[1], tags[2], float(duration) if duration else None


def _read_mapping(audio: object, keys: dict[str, str]) -> tuple[str, str, str]:
    tags = getattr(audio, "tags", None)
    values: list[str] = []
    for key in (keys["title"], keys["artist"], keys["album"]):
        values.append(_first_value(tags.get(key)) if tags else "")
    return values[0], values[1], values[2]


def _read_id3(audio: object) -> tuple[str, str, str]:
    """ID3 标签：帧对象的 text 可能是列表，多值用 " / " 连接。"""
    from mutagen.id3 import ID3

    tags = getattr(audio, "tags", None)
    if tags is None:
        try:
            tags = ID3(audio.filename)  # type: ignore[attr-defined]
        except Exception:
            return "", "", ""

    values = [
        _first_value(tags.get(key)) if hasattr(tags, "get") else ""
        for key in (_ID3_KEYS["title"], _ID3_KEYS["artist"], _ID3_KEYS["album"])
    ]
    return values[0], values[1], values[2]


def _first_value(raw: object) -> str:
    """把 mutagen 的标签值统一成字符串，多值用 " / " 连接。"""
    if raw is None:
        return ""

    if isinstance(raw, (list, tuple)):
        parts = [_first_value(item) for item in raw]
        return " / ".join(part for part in parts if part)

    text = getattr(raw, "text", None)
    if text is not None:
        return _first_value(text)

    return str(raw).strip()


def _filename_candidates(path: Path) -> list[tuple[str, str]]:
    """从 "歌手 - 歌名.mp3" 反推，两种解释都返回，交给打分决定哪个对。"""
    stem = path.stem.strip()
    if not stem:
        return []

    if " - " not in stem:
        return [(stem, "")]

    first, _, second = stem.partition(" - ")
    first, second = first.strip(), second.strip()
    if not first or not second:
        return [(stem, "")]

    return [(first, second), (second, first)]
