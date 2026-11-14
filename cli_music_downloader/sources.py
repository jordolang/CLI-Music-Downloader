"""
Audio sources: find the right recording for a track and download it as MP3.

Sources are tried in order until one yields a confident match:
  1. YouTube Music  - official "song" uploads (studio versions with exact durations)
  2. YouTube        - general search, scored to avoid live/cover/remix uploads
  3. SoundCloud     - free streams, many independent artists
  4. Audius         - free, artist-uploaded catalog (open API)

Every candidate is scored against the listed title, artist and duration, so a wrong
version (live, acoustic, cover, sped up, ...) is rejected unless the listed title asks
for it.
"""

import glob
import logging
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
from urllib.parse import quote_plus

import requests

from .catalog import USER_AGENT, base_title, normalize, split_artists
from .songlist import Track

logger = logging.getLogger(__name__)

DEFAULT_SOURCES = ("ytmusic", "youtube", "soundcloud", "audius")
ACCEPT_SCORE = 70.0

# Words that mark a different version of a song. A candidate containing one is
# rejected unless the listed title or album contains it too.
VERSION_WORDS = [
    "live", "acoustic", "cover", "covers", "remix", "rmx", "karaoke", "instrumental",
    "sped up", "speed up", "slowed", "reverb", "nightcore", "8d", "reaction", "tutorial",
    "lesson", "piano version", "guitar cover", "drum cover", "bass boosted", "1 hour", "10 hours",
    "extended", "radio edit", "demo", "stripped", "unplugged",
    "mashup", "medley", "tribute", "parody", "chipmunk", "female version", "male version",
    "a cappella", "acapella", "lyrics translation", "traduzione", "letra", "legendado",
    "clean", "censored", "clean version", "type beat", "beat", "prod", "freestyle", "rework",
    "bootleg", "flip", "vip", "mix", "cover version", "piano", "violin", "cello", "sax", "ukulele",
    "one take", "fan made", "ai", "ai cover", "snippet", "preview", "unreleased", "leak",
]

# Sources where anyone can upload: only the artist's own account is trusted.
ARTIST_ACCOUNT_ONLY = {"soundcloud", "audius"}


@dataclass
class Candidate:
    source: str
    url: str
    title: str
    uploader: str = ""
    duration: Optional[float] = None
    score: float = 0.0
    extra: Dict = field(default_factory=dict)

    def describe(self) -> str:
        dur = f"{int(self.duration) // 60}:{int(self.duration) % 60:02d}" if self.duration else "?:??"
        return f"[{self.source}] {self.title} — {self.uploader} ({dur}, score {self.score:.0f})"


class SourceError(Exception):
    pass


def _contains_phrase(haystack: str, phrase: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", haystack) is not None


def title_patterns(title: str) -> List[str]:
    """Regex per word of a title; censored words ("F**k") match any spelling ("Fuck", "F##k")."""
    patterns = []
    for token in base_title(title).split():
        if re.search(r"\w[*#]+", token):
            letters = re.sub(r"[^\w]", "", token)
            if letters:
                patterns.append(re.escape(normalize(letters[0])) + r"\w*(?:\s\w+)?")
            continue
        patterns.extend(re.escape(w) for w in normalize(token).split())
    return patterns


def _matches(haystack: str, pattern: str) -> bool:
    return re.search(rf"(?<!\w){pattern}(?!\w)", haystack) is not None


def score_candidate(track: Track, title: str, uploader: str, duration: Optional[float],
                    artists: Iterable[str] = (), source: str = "") -> float:
    """How likely a search result is the listed recording (higher is better, <0 = reject)."""
    cand_title = normalize(title)
    cand_all = normalize(" ".join([title, uploader, *artists]))
    listed_context = normalize(f"{track.title} {track.album}")

    # Title: every word of the listed title should appear in the candidate's title.
    words = title_patterns(track.title)
    if not words:
        return -1
    if _matches(cand_title, r"\s".join(words)):
        score = 40.0
    else:
        found = sum(1 for w in words if _matches(cand_all, w))
        ratio = found / len(words)
        if ratio < 0.75:
            return -1
        score = 30.0 * ratio

    # Artist: at least one listed artist should be credited somewhere.
    listed_artists = [normalize(a) for a in split_artists(track.artist)] if track.artist else []
    if listed_artists:
        hits = [a for a in listed_artists if a and _contains_phrase(cand_all, a)]
        if source in ARTIST_ACCOUNT_ONLY:
            up = normalize(uploader)
            if not up or not any(a in up or up in a for a in listed_artists if a):
                return -1  # fan upload: usually a cover, remix or rip
        if hits:
            score += 25.0 + 5.0 * (len(hits) - 1)
            if normalize(uploader).endswith(" topic") or any(
                    normalize(a) == listed_artists[0] for a in artists):
                score += 15.0  # official auto-generated / credited upload
        else:
            score -= 30.0

    # Different version of the song?
    for w in VERSION_WORDS:
        if _contains_phrase(cand_title, w) and not _contains_phrase(listed_context, w):
            return -1

    if re.search(r"official (audio|music video|video|lyric video)", title, re.I):
        score += 6.0
    elif re.search(r"\b(audio|lyrics?)\b", title, re.I):
        score += 3.0

    # Duration: the song list gives the exact length of the wanted recording.
    if track.duration and duration:
        diff = abs(track.duration - duration)
        tolerance = max(8.0, track.duration * 0.04)
        if diff <= 2:
            score += 35.0
        elif diff <= 5:
            score += 28.0
        elif diff <= tolerance:
            score += 15.0
        elif diff <= tolerance * 2.5:
            score -= 10.0  # e.g. music video with an intro/outro
        else:
            return -1
    elif track.duration:
        score -= 5.0
    return score


# ------------------------------------------------------------------------ yt-dlp


def _find_js_runtime() -> Dict:
    """yt-dlp needs a JS runtime for YouTube; use deno or node if one is installed."""
    if shutil.which("deno"):
        return {"deno": {}}
    node = shutil.which("node")
    if not node:
        candidates = sorted(glob.glob(os.path.expanduser("~/.nvm/versions/node/*/bin/node")))
        candidates += [p for p in ("/opt/homebrew/bin/node", "/usr/local/bin/node") if os.path.exists(p)]
        node = candidates[-1] if candidates else None
    return {"node": {"path": node}} if node else {}


class _QuietLogger:
    def debug(self, msg):
        logger.debug(msg)

    def info(self, msg):
        logger.debug(msg)

    def warning(self, msg):
        logger.debug(msg)

    def error(self, msg):
        logger.debug(msg)


class SourceFinder:
    """Searches the configured sources and downloads the best match."""

    def __init__(self, sources: Iterable[str] = DEFAULT_SOURCES, cookies_from_browser: Optional[str] = None,
                 cookies_file: Optional[str] = None, audio_quality: str = "0"):
        try:
            import yt_dlp  # noqa: F401
        except ImportError as exc:
            raise SourceError("yt-dlp is not installed: pip install yt-dlp") from exc
        if not shutil.which("ffmpeg"):
            raise SourceError("ffmpeg is required to convert audio to MP3 (brew install ffmpeg)")
        unknown = set(sources) - set(DEFAULT_SOURCES)
        if unknown:
            raise SourceError(f"Unknown source(s): {', '.join(sorted(unknown))}")
        self.sources = list(sources)
        self.audio_quality = audio_quality
        self.base_opts = {
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "logger": _QuietLogger(),
            "socket_timeout": 30,
            "retries": 5,
            "fragment_retries": 5,
            "noplaylist": True,
            "extractor_retries": 3,
            # Pace requests; YouTube answers bursts with HTTP 403 for a while.
            "sleep_interval_requests": 1,
            "js_runtimes": _find_js_runtime(),
        }
        if cookies_from_browser:
            self.base_opts["cookiesfrombrowser"] = (cookies_from_browser,)
        if cookies_file:
            self.base_opts["cookiefile"] = cookies_file
        self._http = requests.Session()
        self._http.headers["User-Agent"] = USER_AGENT
        self._audius_host: Optional[str] = None
        self.age_restricted = 0  # results YouTube refused without sign-in
        self.throttled = 0  # requests YouTube rejected, usually from rate limiting

    def _note_error(self, exc: Exception) -> None:
        msg = str(exc)
        if "confirm your age" in msg or "Sign in" in msg:
            self.age_restricted += 1
        if "403" in msg or "not a bot" in msg or "Requested format is not available" in msg:
            self.throttled += 1
        logger.debug("Skipping result: %s", msg)

    # ------------------------------------------------------------- searching

    def _ydl(self, **extra):
        import yt_dlp
        return yt_dlp.YoutubeDL({**self.base_opts, **extra})

    def _flat_search(self, query: str) -> List[Dict]:
        with self._ydl(extract_flat="in_playlist", skip_download=True) as ydl:
            info = ydl.extract_info(query, download=False)
        return [e for e in (info or {}).get("entries") or [] if e]

    def _full_info(self, url: str) -> Optional[Dict]:
        with self._ydl(skip_download=True) as ydl:
            return ydl.extract_info(url, download=False)

    def stream_url(self, url: str) -> Tuple[str, Dict[str, str]]:
        """Direct audio stream URL (and the HTTP headers it needs) for a result, without downloading."""
        with self._ydl(skip_download=True, format="bestaudio/best") as ydl:
            info = ydl.extract_info(url, download=False) or {}
        media = info.get("url") or next((f.get("url") for f in info.get("requested_formats") or [] if f.get("url")), "")
        if not media:
            raise SourceError(f"No audio stream for {url}")
        return media, dict(info.get("http_headers") or {})

    def search(self, source: str, track: Track) -> List[Candidate]:
        """Scored candidates from one source, best first (only acceptable ones)."""
        artist = track.artist
        title = base_title(track.title)
        query = f"{artist} {title}".strip()
        try:
            if source == "ytmusic":
                found = self._search_ytmusic(track, query)
            elif source == "youtube":
                found = self._search_flat(track, f"ytsearch10:{artist} - {title} audio".strip(), "youtube")
            elif source == "soundcloud":
                found = self._search_flat(track, f"scsearch10:{query}", "soundcloud")
            elif source == "audius":
                found = self._search_audius(track, query)
            else:
                found = []
        except Exception as exc:
            self._note_error(exc)
            logger.debug("%s search failed for %s: %s", source, track, exc)
            found = []
        found = [c for c in found if c.score >= ACCEPT_SCORE]
        return sorted(found, key=lambda c: c.score, reverse=True)

    def _search_ytmusic(self, track: Track, query: str) -> List[Candidate]:
        # Flat YouTube Music results only carry titles; fetch details for the plausible ones.
        url = f"https://music.youtube.com/search?q={quote_plus(query)}#songs"
        entries = self._flat_search(url)[:6]
        want = title_patterns(track.title)
        out = []
        for e in entries:
            if len(out) >= 3:
                break
            t = normalize(e.get("title", ""))
            if want and sum(1 for w in want if _matches(t, w)) / len(want) < 0.75:
                continue
            try:
                info = self._full_info(e.get("url") or f"https://music.youtube.com/watch?v={e['id']}")
            except Exception as exc:  # one unavailable result must not hide the others
                self._note_error(exc)
                continue
            if not info:
                continue
            artists = info.get("artists") or ([info["artist"]] if info.get("artist") else [])
            cand = Candidate(
                source="ytmusic",
                url=info.get("webpage_url") or e.get("url"),
                title=info.get("track") or info.get("title", ""),
                uploader=info.get("channel") or info.get("uploader") or "",
                duration=info.get("duration"),
                extra={"thumbnail": info.get("thumbnail"), "artists": artists},
            )
            cand.score = score_candidate(track, cand.title, cand.uploader, cand.duration, artists)
            out.append(cand)
            if cand.score >= 95:
                break
        return out

    def _search_flat(self, track: Track, query: str, source: str) -> List[Candidate]:
        out = []
        for e in self._flat_search(query):
            cand = Candidate(
                source=source,
                url=e.get("url") or e.get("webpage_url") or "",
                title=e.get("title") or e.get("track") or "",
                uploader=e.get("channel") or e.get("uploader") or "",
                duration=e.get("duration"),
                extra={"thumbnail": (e.get("thumbnails") or [{}])[-1].get("url")},
            )
            if not cand.url:
                continue
            if source == "youtube" and "/shorts/" in cand.url:
                continue
            cand.score = score_candidate(track, cand.title, cand.uploader, cand.duration, source=source)
            out.append(cand)
        return out

    def _audius(self) -> Optional[str]:
        if self._audius_host is None:
            try:
                hosts = self._http.get("https://api.audius.co", timeout=15).json().get("data") or []
                self._audius_host = hosts[0] if hosts else ""
            except Exception:
                self._audius_host = ""
        return self._audius_host or None

    def _search_audius(self, track: Track, query: str) -> List[Candidate]:
        host = self._audius()
        if not host:
            return []
        resp = self._http.get(f"{host}/v1/tracks/search",
                              params={"query": query, "app_name": "cli-music-downloader"}, timeout=20)
        out = []
        for item in (resp.json().get("data") or [])[:10]:
            if not item.get("is_streamable", True):
                continue
            cand = Candidate(
                source="audius",
                url=f"{host}/v1/tracks/{item['id']}/stream?app_name=cli-music-downloader",
                title=item.get("title", ""),
                uploader=(item.get("user") or {}).get("name", ""),
                duration=item.get("duration"),
                extra={"thumbnail": (item.get("artwork") or {}).get("1000x1000")},
            )
            cand.score = score_candidate(track, cand.title, cand.uploader, cand.duration, source="audius")
            out.append(cand)
        return out

    # ----------------------------------------------------------- downloading

    def download(self, cand: Candidate, dest: Path, expected_duration: Optional[int] = None,
                 on_progress=None) -> Path:
        """Download a candidate and convert it to MP3 at `dest`.

        When the listed duration is known the real audio length is checked, which catches
        30-second previews and wrong cuts that search metadata does not reveal.
        """
        dest.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="cmd-dl-") as tmp:
            if cand.source == "audius":
                raw = Path(tmp) / "audio.src"
                with self._http.get(cand.url, stream=True, timeout=60) as resp:
                    resp.raise_for_status()
                    total = int(resp.headers.get("Content-Length") or 0)
                    got = 0
                    with open(raw, "wb") as fh:
                        for chunk in resp.iter_content(1 << 16):
                            fh.write(chunk)
                            got += len(chunk)
                            if on_progress and total:
                                on_progress(min(1.0, got / total))
                out = Path(tmp) / "audio.mp3"
                cmd = ["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", str(raw),
                       "-vn", "-codec:a", "libmp3lame", "-q:a", self.audio_quality, str(out)]
                subprocess.run(cmd, check=True, capture_output=True)
            else:
                opts = {
                    "format": "bestaudio/best",
                    "outtmpl": str(Path(tmp) / "audio.%(ext)s"),
                    "postprocessors": [{
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": self.audio_quality,
                    }],
                }
                if on_progress:
                    def hook(d):
                        if d.get("status") == "downloading":
                            total = d.get("total_bytes") or d.get("total_bytes_estimate")
                            if total:
                                on_progress(min(1.0, d.get("downloaded_bytes", 0) / total))
                    opts["progress_hooks"] = [hook]
                with self._ydl(**opts) as ydl:
                    ydl.download([cand.url])
                out = Path(tmp) / "audio.mp3"
            if not out.exists() or out.stat().st_size < 50_000:
                raise SourceError("download produced no usable audio")
            if expected_duration:
                from mutagen.mp3 import MP3
                length = MP3(str(out)).info.length
                if abs(length - expected_duration) > max(15.0, expected_duration * 0.08):
                    raise SourceError(f"audio is {length:.0f}s but the song is {expected_duration}s")
            # Write to a temp name next to the destination, then rename atomically.
            partial = dest.with_name(dest.name + ".part")
            shutil.move(str(out), partial)
            os.replace(partial, dest)
        return dest

    def fetch_thumbnail(self, cand: Candidate) -> Optional[bytes]:
        url = cand.extra.get("thumbnail")
        if not url:
            return None
        try:
            resp = self._http.get(url, timeout=20)
            return resp.content if resp.ok else None
        except requests.RequestException:
            return None
