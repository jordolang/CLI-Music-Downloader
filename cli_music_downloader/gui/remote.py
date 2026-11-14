"""
Online lookups for the GUI: catalog songs (iTunes, with 30-second previews), YouTube
videos, and direct audio/video streams that the local server proxies to the player.
"""

import logging
import re
import secrets
import threading
import time
from typing import Dict, List, Optional, Tuple

from .. import catalog
from ..recommend import DEEZER, song_key
from ..sources import DEFAULT_SOURCES, SourceError, SourceFinder

logger = logging.getLogger(__name__)

STREAM_TTL = 3 * 3600  # YouTube stream links last ~6 hours
HLS_MIME = "application/vnd.apple.mpegurl"
AUDIO_FORMAT = "bestaudio[ext=m4a]/bestaudio[acodec^=mp4a]/bestaudio/best"

_NOISE = re.compile(
    r"\s*[\(\[\{][^\)\]\}]*(official|video|audio|lyric|lyrics|visuali[sz]er|hd|hq|4k|mv|m/v|music video|"
    r"explicit|clean|remaster(ed)?|full song|color coded)[^\)\]\}]*[\)\]\}]",
    re.I,
)
_TAIL = re.compile(r"\s*(\||//).*$")
_CHANNEL_SUFFIX = re.compile(r"\s*(- Topic|VEVO|Official|Music)$", re.I)


def clean_video_title(title: str, channel: str = "") -> Tuple[str, str]:
    """Guess (artist, title) from a YouTube video title like 'Artist - Song (Official Video)'."""
    text = _TAIL.sub("", title or "")
    text = _NOISE.sub("", text).strip()
    text = re.sub(r"\s+", " ", text)
    m = re.match(r"^(.+?)\s+[-–—]\s+(.+)$", text)
    if m:
        artist, song = m.group(1).strip(), m.group(2).strip()
    else:
        artist = _CHANNEL_SUFFIX.sub("", channel or "").strip()
        song = text
    song = re.sub(r"^[\"'“]+|[\"'”]+$", "", song).strip()
    return artist, song


class StreamRegistry:
    """Short tokens for remote media URLs, so the player only ever talks to localhost."""

    def __init__(self):
        self._items: Dict[str, Dict] = {}
        self._lock = threading.Lock()

    def add(self, url: str, headers: Optional[Dict[str, str]] = None, mime: str = "") -> str:
        token = secrets.token_urlsafe(12)
        with self._lock:
            now = time.time()
            if len(self._items) > 20000:  # HLS playlists add one token per segment
                self._items = {k: v for k, v in self._items.items() if now - v["t"] < STREAM_TTL}
            self._items[token] = {"url": url, "headers": headers or {}, "mime": mime, "t": now}
        return token

    def get(self, token: str) -> Optional[Dict]:
        with self._lock:
            return self._items.get(token)


class Remote:
    def __init__(self, settings_getter):
        self._settings = settings_getter
        self._finder: Optional[SourceFinder] = None
        self._finder_key = None
        self._lock = threading.Lock()
        self.streams = StreamRegistry()
        self._resolved: Dict[Tuple[str, str], Tuple[float, Dict]] = {}
        self._deezer_art: Dict[int, str] = {}

    @property
    def finder(self) -> SourceFinder:
        s = self._settings()
        key = (tuple(s.get("sources") or ()), s.get("cookies_from_browser") or "")
        with self._lock:
            if self._finder is None or self._finder_key != key:
                self._finder = SourceFinder(s.get("sources") or DEFAULT_SOURCES,
                                            cookies_from_browser=s.get("cookies_from_browser") or None)
                self._finder_key = key
            return self._finder

    # ------------------------------------------------------------- catalog

    def search_songs(self, term: str, owned: set, limit: int = 30) -> List[Dict]:
        out = []
        for r in catalog._itunes_search(term, limit=limit):
            if r.get("kind") not in (None, "song"):
                continue
            art = r.get("artworkUrl100") or ""
            info = catalog._itunes_info(r, 100.0)
            out.append({
                "kind": "song",
                "title": info.title,
                "artist": info.artist,
                "album": info.album,
                "genre": info.genre,
                "year": info.year,
                "duration": info.duration,
                "explicit": info.explicit,
                "artwork": re.sub(r"/\d+x\d+bb\.(jpg|png)$", "/300x300bb.jpg", art) if art else "",
                "preview": r.get("previewUrl") or "",
                "url": info.url,
                "owned": song_key(info.artist, info.title) in owned,
            })
        return out

    # ------------------------------------------------------------- YouTube

    def search_videos(self, term: str, owned: set, limit: int = 20) -> List[Dict]:
        finder = self.finder
        try:
            entries = finder._flat_search(f"ytsearch{limit}:{term}")
        except Exception as exc:
            finder._note_error(exc)
            raise SourceError(f"YouTube search failed: {exc}") from exc
        out = []
        for e in entries:
            vid = e.get("id")
            if not vid or "/shorts/" in (e.get("url") or ""):
                continue
            artist, title = clean_video_title(e.get("title", ""), e.get("channel") or e.get("uploader") or "")
            out.append({
                "kind": "video",
                "id": vid,
                "url": f"https://www.youtube.com/watch?v={vid}",
                "video_title": e.get("title", ""),
                "channel": e.get("channel") or e.get("uploader") or "",
                "duration": e.get("duration"),
                "views": e.get("view_count"),
                "thumbnail": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
                "artist": artist,
                "title": title,
                "owned": song_key(artist, title) in owned if artist else False,
            })
        return out

    def resolve_stream(self, video_id: str, kind: str = "audio") -> Dict:
        """Playable stream for a YouTube video.

        audio -> a proxy token for the best M4A/AAC audio (plays in any browser engine)
        video -> YouTube's HLS master playlist (audio + video; WebKit plays it natively)
        """
        key = (video_id, kind)
        hit = self._resolved.get(key)
        if hit and time.time() - hit[0] < STREAM_TTL:
            return hit[1]
        finder = self.finder
        opts = {"skip_download": True}
        if kind == "audio":
            opts["format"] = AUDIO_FORMAT
        try:
            with finder._ydl(**opts) as ydl:
                info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False) or {}
        except Exception as exc:
            finder._note_error(exc)
            raise SourceError(str(exc).replace("ERROR: ", "")) from exc
        result = {
            "id": video_id,
            "title": info.get("title", ""),
            "channel": info.get("channel") or info.get("uploader") or "",
            "duration": info.get("duration"),
            "thumbnail": info.get("thumbnail") or f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
        }
        if kind == "video":
            hls = next((f.get("manifest_url") for f in info.get("formats") or []
                        if f.get("protocol", "").startswith("m3u8") and f.get("manifest_url")), "")
            if not hls:
                raise SourceError("No video stream for this upload")
            # Served through the local /api/hls proxy: same-origin, so every engine can play it.
            result["hls_token"] = self.streams.add(hls, {}, HLS_MIME)
        else:
            url = info.get("url")
            headers = dict(info.get("http_headers") or {})
            ext = info.get("ext") or ""
            if not url:
                raise SourceError("No audio stream for this upload")
            mime = {"m4a": "audio/mp4", "mp4": "audio/mp4", "webm": "audio/webm", "mp3": "audio/mpeg"}.get(ext, "")
            result["token"] = self.streams.add(url, headers, mime)
        self._resolved[key] = (time.time(), result)
        return result

    # ------------------------------------------------------------- Deezer

    def deezer_track(self, deezer_id: int) -> Dict:
        data = catalog._get_json(f"{DEEZER}/track/{int(deezer_id)}", host_key="deezer", min_interval=0.11) or {}
        album = data.get("album") or {}
        if album.get("cover_medium"):
            self._deezer_art[int(deezer_id)] = album["cover_medium"]
        return {"preview": data.get("preview") or "", "artwork": album.get("cover_medium") or ""}

    def deezer_artwork(self, deezer_id: int) -> str:
        cached = self._deezer_art.get(int(deezer_id))
        if cached is not None:
            return cached
        art = self.deezer_track(deezer_id).get("artwork", "")
        self._deezer_art[int(deezer_id)] = art
        return art
