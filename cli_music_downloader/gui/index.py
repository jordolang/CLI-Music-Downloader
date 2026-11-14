"""
The music library as the GUI sees it: every audio file under the library folder with
its tags, plus artwork, lyrics, tag editing and file organizing (<Artist>/<Title>.mp3).
"""

import hashlib
import io
import logging
import os
import shutil
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from ..library import UNKNOWN_ARTIST, track_path

logger = logging.getLogger(__name__)

AUDIO_EXTS = {".mp3", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".wav", ".aiff", ".aif"}
SKIP_DIRS = {".Trash", "__MACOSX"}
# Folders other apps manage (Apple Music / iTunes media, Logic and GarageBand content):
# never index or reorganize them.
SKIP_TOP_DIRS = {"Music", "iTunes", "Audio Music Apps", "GarageBand", "Logic", "Apple Loops"}
SKIP_SUFFIXES = (".bundle", ".logicx", ".band", ".app", ".musiclibrary", ".photoslibrary", ".tvlibrary",
                 ".localized")
EDITABLE = ("title", "artist", "album", "album_artist", "genre", "year", "track", "disc")


@dataclass
class Song:
    id: str
    path: str  # relative to the library folder
    title: str
    artist: str
    album: str = ""
    album_artist: str = ""
    genre: str = ""
    year: str = ""
    track: int = 0
    disc: int = 0
    duration: float = 0.0
    bitrate: int = 0
    size: int = 0
    added: float = 0.0
    modified: float = 0.0
    has_art: bool = False
    has_lyrics: bool = False
    source_url: str = ""
    ext: str = ".mp3"
    extra: Dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("extra", None)
        return d


def song_id(rel_path: str) -> str:
    return hashlib.sha1(rel_path.casefold().encode("utf-8")).hexdigest()[:16]


def _num(text) -> int:
    try:
        return int(str(text).split("/")[0].strip() or 0)
    except (ValueError, TypeError):
        return 0


def _first(tags, key) -> str:
    try:
        value = tags.get(key)
    except Exception:
        return ""
    if not value:
        return ""
    if isinstance(value, (list, tuple)):
        value = value[0] if value else ""
    return str(value).strip()


def read_song(path: Path, root: Path) -> Song:
    """Read one file's tags (falls back to the <Artist>/<Title> folder layout)."""
    import mutagen

    rel = str(path.relative_to(root))
    st = path.stat()
    parent = path.parent.name if path.parent != root else ""
    song = Song(id=song_id(rel), path=rel, title=path.stem, artist=parent or UNKNOWN_ARTIST,
                size=st.st_size, added=getattr(st, "st_birthtime", st.st_ctime), modified=st.st_mtime,
                ext=path.suffix.lower())
    try:
        audio = mutagen.File(str(path))
    except Exception as exc:
        logger.debug("Could not read %s: %s", path, exc)
        audio = None
    if audio is None:
        return song
    info = getattr(audio, "info", None)
    song.duration = round(float(getattr(info, "length", 0) or 0), 2)
    song.bitrate = int((getattr(info, "bitrate", 0) or 0) / 1000)
    tags = audio.tags
    if tags is None:
        return song
    if path.suffix.lower() == ".mp3" or tags.__class__.__name__ == "ID3":
        def t(key):
            frame = tags.get(key)
            return str(frame.text[0]).strip() if frame is not None and getattr(frame, "text", None) else ""
        song.title = t("TIT2") or song.title
        song.artist = t("TPE1") or song.artist
        song.album = t("TALB")
        song.album_artist = t("TPE2")
        song.genre = t("TCON")
        song.year = t("TDRC")[:4]
        song.track = _num(t("TRCK"))
        song.disc = _num(t("TPOS"))
        song.has_art = bool(tags.getall("APIC"))
        song.has_lyrics = bool(tags.getall("USLT"))
        wxxx = tags.getall("WXXX")
        song.source_url = str(wxxx[0].url) if wxxx else ""
    elif path.suffix.lower() in (".m4a", ".aac"):
        song.title = _first(tags, "\xa9nam") or song.title
        song.artist = _first(tags, "\xa9ART") or song.artist
        song.album = _first(tags, "\xa9alb")
        song.album_artist = _first(tags, "aART")
        song.genre = _first(tags, "\xa9gen")
        song.year = _first(tags, "\xa9day")[:4]
        trkn = tags.get("trkn")
        song.track = trkn[0][0] if trkn else 0
        song.has_art = bool(tags.get("covr"))
        song.has_lyrics = bool(tags.get("\xa9lyr"))
    else:  # Vorbis comments (FLAC / Ogg / Opus)
        song.title = _first(tags, "title") or song.title
        song.artist = _first(tags, "artist") or song.artist
        song.album = _first(tags, "album")
        song.album_artist = _first(tags, "albumartist")
        song.genre = _first(tags, "genre")
        song.year = _first(tags, "date")[:4]
        song.track = _num(_first(tags, "tracknumber"))
        song.disc = _num(_first(tags, "discnumber"))
        song.has_art = bool(getattr(audio, "pictures", None)) or bool(tags.get("metadata_block_picture"))
        song.has_lyrics = bool(_first(tags, "lyrics") or _first(tags, "unsyncedlyrics"))
    return song


def read_artwork(path: Path) -> Optional[bytes]:
    import mutagen

    try:
        audio = mutagen.File(str(path))
    except Exception:
        return None
    if audio is None or audio.tags is None:
        return getattr(audio, "pictures", [None])[0].data if getattr(audio, "pictures", None) else None
    tags = audio.tags
    if hasattr(tags, "getall"):
        pics = tags.getall("APIC")
        if pics:
            front = [p for p in pics if p.type == 3]
            return (front or pics)[0].data
    if "covr" in tags:
        return bytes(tags["covr"][0])
    pictures = getattr(audio, "pictures", None)
    if pictures:
        return pictures[0].data
    return None


def read_lyrics(path: Path) -> str:
    import mutagen

    try:
        audio = mutagen.File(str(path))
    except Exception:
        return ""
    if audio is None or audio.tags is None:
        return ""
    tags = audio.tags
    if hasattr(tags, "getall"):
        frames = tags.getall("USLT")
        return str(frames[0].text) if frames else ""
    return _first(tags, "\xa9lyr") or _first(tags, "lyrics") or _first(tags, "unsyncedlyrics")


def thumbnail(data: bytes, size: int) -> bytes:
    from PIL import Image

    img = Image.open(io.BytesIO(data))
    img = img.convert("RGB")
    img.thumbnail((size, size), Image.LANCZOS)
    out = io.BytesIO()
    img.save(out, "JPEG", quality=86)
    return out.getvalue()


def _remove_empty_dirs(start: Path, root: Path) -> None:
    d = start
    while d != root and root in d.parents:
        try:
            leftovers = [p for p in d.iterdir() if p.name not in (".DS_Store", "Icon\r")]
            if leftovers:
                return
            for p in d.iterdir():
                p.unlink()
            d.rmdir()
        except OSError:
            return
        d = d.parent


def move_to_trash(path: Path) -> Path:
    trash = Path.home() / ".Trash"
    trash.mkdir(exist_ok=True)
    target = trash / path.name
    n = 1
    while target.exists():
        target = trash / f"{path.stem} {n}{path.suffix}"
        n += 1
    shutil.move(str(path), str(target))
    return target


class LibraryIndex:
    """All songs in the library folder, kept up to date with cheap rescans."""

    def __init__(self, root):
        self.root = Path(root).expanduser()
        self._songs: Dict[str, Song] = {}
        self._lock = threading.RLock()
        self.version = 0
        self.scanned_at = 0.0
        self.scanning = False
        self._art_cache: Dict[str, bytes] = {}

    # ------------------------------------------------------------- scanning

    def set_root(self, root) -> None:
        with self._lock:
            self.root = Path(root).expanduser()
            self._songs = {}
            self._art_cache.clear()
            self.version += 1
        self.scan()

    def _files(self) -> Iterable[Path]:
        if not self.root.is_dir():
            return []
        out = []
        for dirpath, dirnames, filenames in os.walk(self.root):
            top = Path(dirpath) == self.root
            dirnames[:] = [d for d in dirnames
                           if not d.startswith(".") and d not in SKIP_DIRS and not d.endswith(SKIP_SUFFIXES)
                           and not (top and d in SKIP_TOP_DIRS)]
            for name in filenames:
                if name.startswith("._") or name.endswith(".part"):
                    continue
                if os.path.splitext(name)[1].lower() in AUDIO_EXTS:
                    out.append(Path(dirpath) / name)
        return out

    def scan(self) -> bool:
        """Re-read new or changed files. Returns True when anything changed."""
        with self._lock:
            if self.scanning:
                return False
            self.scanning = True
        try:
            old = dict(self._songs)
            fresh: Dict[str, Song] = {}
            changed = False
            for path in self._files():
                rel = str(path.relative_to(self.root))
                sid = song_id(rel)
                prev = old.get(sid)
                try:
                    mtime = path.stat().st_mtime
                except OSError:
                    continue
                if prev and prev.modified == mtime and prev.path == rel:
                    fresh[sid] = prev
                    continue
                try:
                    fresh[sid] = read_song(path, self.root)
                    self._art_cache = {k: v for k, v in self._art_cache.items() if not k.startswith(sid)}
                    changed = True
                except Exception as exc:
                    logger.debug("Skipping %s: %s", path, exc)
            if set(fresh) != set(old):
                changed = True
            with self._lock:
                self._songs = fresh
                if changed:
                    self.version += 1
                self.scanned_at = time.time()
            return changed
        finally:
            self.scanning = False

    # ------------------------------------------------------------- queries

    def songs(self) -> List[Song]:
        with self._lock:
            return list(self._songs.values())

    def get(self, sid: str) -> Optional[Song]:
        with self._lock:
            return self._songs.get(sid)

    def abspath(self, song: Song) -> Path:
        return self.root / song.path

    def find(self, artist: str, title: str) -> Optional[Song]:
        from ..recommend import song_key

        want = song_key(artist, title)
        with self._lock:
            for s in self._songs.values():
                if song_key(s.artist, s.title) == want:
                    return s
        return None

    def owned_keys(self) -> set:
        from ..recommend import song_key

        with self._lock:
            return {song_key(s.artist, s.title) for s in self._songs.values()}

    def artwork(self, sid: str, size: int = 300) -> Optional[bytes]:
        key = f"{sid}:{size}"
        cached = self._art_cache.get(key)
        if cached is not None:
            return cached or None
        song = self.get(sid)
        data = read_artwork(self.abspath(song)) if song and song.has_art else None
        if data and size:
            try:
                data = thumbnail(data, size)
            except Exception as exc:
                logger.debug("Bad artwork in %s: %s", song.path if song else sid, exc)
                data = None
        if len(self._art_cache) > 1500:
            self._art_cache.clear()
        self._art_cache[key] = data or b""
        return data

    def lyrics(self, sid: str) -> str:
        song = self.get(sid)
        return read_lyrics(self.abspath(song)) if song else ""

    # ------------------------------------------------------------- editing

    def update_tags(self, sid: str, changes: Dict, organize: bool = True,
                    artwork: Optional[bytes] = None, lyrics: Optional[str] = None) -> Song:
        song = self.get(sid)
        if not song:
            raise KeyError(sid)
        path = self.abspath(song)
        values = {k: str(v).strip() for k, v in changes.items() if k in EDITABLE and v is not None}
        if path.suffix.lower() == ".mp3":
            self._write_id3(path, values, artwork, lyrics)
        else:
            self._write_generic(path, values)
        if organize:
            path = self._organize(path, values.get("artist", song.artist), values.get("title", song.title))
        rel = str(path.relative_to(self.root))
        with self._lock:
            self._songs.pop(sid, None)
            new = read_song(path, self.root)
            self._songs[new.id] = new
            self._art_cache = {k: v for k, v in self._art_cache.items() if not k.startswith(sid)}
            self.version += 1
        return self._songs[song_id(rel)]

    @staticmethod
    def _write_id3(path: Path, values: Dict, artwork: Optional[bytes], lyrics: Optional[str]) -> None:
        from mutagen.id3 import APIC, ID3, TALB, TCON, TDRC, TIT2, TPE1, TPE2, TPOS, TRCK, USLT, ID3NoHeaderError

        try:
            id3 = ID3(str(path))
        except ID3NoHeaderError:
            id3 = ID3()
        frames = {"title": TIT2, "artist": TPE1, "album": TALB, "album_artist": TPE2, "genre": TCON,
                  "year": TDRC, "track": TRCK, "disc": TPOS}
        for key, cls in frames.items():
            if key not in values:
                continue
            id3.delall(cls.__name__)
            if values[key] and values[key] != "0":
                id3.add(cls(encoding=3, text=values[key]))
        if artwork:
            id3.delall("APIC")
            id3.add(APIC(encoding=3, mime="image/jpeg", type=3, desc="Cover", data=artwork))
        if lyrics:
            id3.delall("USLT")
            id3.add(USLT(encoding=3, lang="eng", desc="", text=lyrics))
        id3.save(str(path), v2_version=3)

    @staticmethod
    def _write_generic(path: Path, values: Dict) -> None:
        import mutagen

        audio = mutagen.File(str(path), easy=True)
        if audio is None:
            raise ValueError(f"Cannot write tags to {path.name}")
        if audio.tags is None:
            audio.add_tags()
        names = {"title": "title", "artist": "artist", "album": "album", "album_artist": "albumartist",
                 "genre": "genre", "year": "date", "track": "tracknumber", "disc": "discnumber"}
        for key, name in names.items():
            if key in values:
                try:
                    if values[key] and values[key] != "0":
                        audio[name] = values[key]
                    elif name in audio:
                        del audio[name]
                except Exception as exc:  # not every format supports every tag
                    logger.debug("Cannot set %s on %s: %s", name, path, exc)
        audio.save()

    def _organize(self, path: Path, artist: str, title: str) -> Path:
        """Move a file to <library>/<Artist>/<Title><ext> (keeps it if that name is taken)."""
        target = track_path(self.root, artist or UNKNOWN_ARTIST, title).with_suffix(path.suffix.lower())
        if target == path or str(target).casefold() == str(path).casefold() and target.name == path.name:
            return path
        if target.exists() and not os.path.samefile(target, path):
            return path
        target.parent.mkdir(parents=True, exist_ok=True)
        old_dir = path.parent
        if str(target).casefold() == str(path).casefold():  # case-only rename on a case-insensitive disk
            tmp = path.with_name(path.name + ".renaming")
            os.rename(path, tmp)
            os.rename(tmp, target)
        else:
            shutil.move(str(path), str(target))
        _remove_empty_dirs(old_dir, self.root)
        return target

    def misplaced(self) -> List[Dict]:
        """Songs whose file is not at <Artist>/<Title>.<ext>."""
        out = []
        for s in self.songs():
            want = track_path(self.root, s.artist or UNKNOWN_ARTIST, s.title).with_suffix(s.ext)
            have = self.abspath(s)
            if str(want) != str(have):
                out.append({"id": s.id, "from": s.path, "to": str(want.relative_to(self.root))})
        return out

    def organize_all(self) -> Dict[str, str]:
        """Move every misplaced file; returns {old song id: new song id}."""
        moved: Dict[str, str] = {}
        for item in self.misplaced():
            song = self.get(item["id"])
            if not song:
                continue
            path = self.abspath(song)
            try:
                new = self._organize(path, song.artist, song.title)
            except OSError as exc:
                logger.warning("Could not move %s: %s", path, exc)
                continue
            if new != path:
                moved[song.id] = song_id(str(new.relative_to(self.root)))
        if moved:
            self.scan()
        return moved

    def delete(self, sid: str) -> None:
        song = self.get(sid)
        if not song:
            raise KeyError(sid)
        path = self.abspath(song)
        move_to_trash(path)
        _remove_empty_dirs(path.parent, self.root)
        with self._lock:
            self._songs.pop(sid, None)
            self.version += 1

    def import_files(self, paths: Iterable[str]) -> int:
        """Copy outside audio files into the library as <Artist>/<Title>.<ext>."""
        count = 0
        for p in paths:
            src = Path(p).expanduser()
            if not src.is_file() or src.suffix.lower() not in AUDIO_EXTS:
                continue
            try:
                s = read_song(src, src.parent)
            except Exception:
                continue
            target = track_path(self.root, s.artist or UNKNOWN_ARTIST, s.title).with_suffix(src.suffix.lower())
            if target.exists():
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(src), str(target))
            count += 1
        if count:
            self.scan()
        return count
