"""
ID3 tagging for downloaded MP3s: text tags, front-cover artwork and lyrics.

Tags are written as ID3v2.3, which Apple Music, Finder, Windows Explorer and most
players read reliably.
"""

import io
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from mutagen.id3 import (
    APIC, COMM, ID3, TALB, TCON, TCMP, TCOP, TDRC, TIT2, TLEN, TPE1, TPE2, TPOS, TRCK, TSRC, TXXX,
    USLT, WOAS, ID3NoHeaderError,
)
from mutagen.mp3 import MP3

logger = logging.getLogger(__name__)

MAX_ARTWORK = 1400


@dataclass
class TagData:
    title: str
    artist: str
    album: str = ""
    album_artist: str = ""
    genre: str = ""
    date: str = ""  # YYYY or YYYY-MM-DD
    track_number: Optional[int] = None
    track_count: Optional[int] = None
    disc_number: Optional[int] = None
    disc_count: Optional[int] = None
    isrc: str = ""
    copyright: str = ""
    explicit: bool = False
    compilation: bool = False
    source_url: str = ""
    comment: str = ""


def prepare_artwork(data: bytes) -> Optional[bytes]:
    """Return a square JPEG (center-cropped, at most MAX_ARTWORK px), or the input if Pillow is missing."""
    if not data:
        return None
    try:
        from PIL import Image
    except ImportError:
        return data if data[:3] == b"\xff\xd8\xff" else None
    try:
        img = Image.open(io.BytesIO(data))
        img = img.convert("RGB")
        w, h = img.size
        if abs(w - h) > 2:  # video thumbnails are 16:9 — crop the middle square
            side = min(w, h)
            left, top = (w - side) // 2, (h - side) // 2
            img = img.crop((left, top, left + side, top + side))
        if img.width > MAX_ARTWORK:
            img = img.resize((MAX_ARTWORK, MAX_ARTWORK), Image.LANCZOS)
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=92)
        return out.getvalue()
    except Exception as exc:
        logger.debug("Could not process artwork: %s", exc)
        return None


def _num(n: Optional[int], total: Optional[int]) -> str:
    if not n:
        return ""
    return f"{n}/{total}" if total else str(n)


def write_tags(path: Path, tags: TagData, artwork: Optional[bytes] = None, lyrics: Optional[str] = None) -> None:
    """Replace all ID3 tags on `path` with the given metadata."""
    path = Path(path)
    try:
        id3 = ID3(str(path))
        id3.delete(str(path))
    except ID3NoHeaderError:
        pass
    id3 = ID3()

    id3.add(TIT2(encoding=3, text=tags.title))
    id3.add(TPE1(encoding=3, text=tags.artist))
    id3.add(TPE2(encoding=3, text=tags.album_artist or tags.artist))
    if tags.album:
        id3.add(TALB(encoding=3, text=tags.album))
    if tags.genre:
        id3.add(TCON(encoding=3, text=tags.genre))
    if tags.date:
        id3.add(TDRC(encoding=3, text=tags.date))
    if _num(tags.track_number, tags.track_count):
        id3.add(TRCK(encoding=3, text=_num(tags.track_number, tags.track_count)))
    if _num(tags.disc_number, tags.disc_count):
        id3.add(TPOS(encoding=3, text=_num(tags.disc_number, tags.disc_count)))
    if tags.isrc:
        id3.add(TSRC(encoding=3, text=tags.isrc))
    if tags.copyright:
        id3.add(TCOP(encoding=3, text=tags.copyright))
    if tags.compilation:
        id3.add(TCMP(encoding=3, text="1"))
    if tags.explicit:
        id3.add(TXXX(encoding=3, desc="ITUNESADVISORY", text="1"))
    if tags.source_url:
        id3.add(WOAS(url=tags.source_url))
    if tags.comment:
        id3.add(COMM(encoding=3, lang="eng", desc="", text=tags.comment))

    try:
        length_ms = int(MP3(str(path)).info.length * 1000)
        id3.add(TLEN(encoding=3, text=str(length_ms)))
    except Exception:
        pass

    if artwork:
        id3.add(APIC(encoding=3, mime="image/jpeg", type=3, desc="Cover", data=artwork))
    if lyrics:
        id3.add(USLT(encoding=3, lang="eng", desc="", text=lyrics))

    id3.save(str(path), v2_version=3)


def read_summary(path: Path) -> dict:
    """Small dict of the tags on a file (used by tests and the verify command)."""
    id3 = ID3(str(path))

    def text(key):
        frame = id3.get(key)
        return str(frame.text[0]) if frame and getattr(frame, "text", None) else ""

    return {
        "title": text("TIT2"),
        "artist": text("TPE1"),
        "album_artist": text("TPE2"),
        "album": text("TALB"),
        "genre": text("TCON"),
        "date": text("TDRC"),
        "track": text("TRCK"),
        "disc": text("TPOS"),
        "has_artwork": bool(id3.getall("APIC")),
        "has_lyrics": bool(id3.getall("USLT")),
        "length": round(MP3(str(path)).info.length),
    }
