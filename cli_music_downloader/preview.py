"""
Play the first 30 seconds of a song.

The audio is streamed from YouTube (the same search and matching the downloader uses)
and played with ffplay, or with ffmpeg + afplay on a Mac without ffplay. When YouTube
is unavailable (rate limiting, sign-in walls) Deezer's free 30-second preview is used.
"""

import logging
import os
import shutil
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, Optional

from . import catalog
from .recommend import DEEZER, Suggestion

logger = logging.getLogger(__name__)

PREVIEW_SECONDS = 30
PREVIEW_SOURCES = ("youtube", "ytmusic")
YOUTUBE_COOLDOWN = 300  # after YouTube rate-limits us, use Deezer previews for this long
YOUTUBE_WAIT = 8.0  # seconds to wait for YouTube before playing the Deezer preview instead


class PreviewError(Exception):
    pass


@dataclass
class PreviewSource:
    label: str  # shown to the user, e.g. "YouTube: Song (Official Audio) — Artist"
    url: str
    headers: Dict[str, str] = field(default_factory=dict)


def find_player() -> Optional[str]:
    if shutil.which("ffplay"):
        return "ffplay"
    if shutil.which("afplay") and shutil.which("ffmpeg"):
        return "afplay"
    return None


class Previewer:
    def __init__(self, finder=None, seconds: int = PREVIEW_SECONDS, player: Optional[str] = None,
                 youtube_wait: float = YOUTUBE_WAIT):
        self.finder = finder
        self.youtube_wait = youtube_wait
        self.seconds = seconds
        self.player = player or find_player()
        self._sources: Dict[str, PreviewSource] = {}
        self._lock = threading.Lock()
        self._procs = []
        self._token = 0
        self._tmp: Optional[str] = None
        self._youtube_down_until = 0.0

    @property
    def available(self) -> bool:
        return self.player is not None

    # ------------------------------------------------------------- finding audio

    def resolve(self, song: Suggestion) -> PreviewSource:
        cached = self._sources.get(song.key)
        if cached:
            return cached
        # Look on YouTube in the background; if it is slow (rate limiting), play Deezer's
        # preview now and keep the YouTube result for the next time this song is played.
        found: Dict[str, PreviewSource] = {}

        def lookup():
            source = self._from_youtube(song)
            if source:
                found["youtube"] = self._sources[song.key] = source

        worker = threading.Thread(target=lookup, daemon=True)
        worker.start()
        worker.join(self.youtube_wait)
        source = found.get("youtube") or self._from_deezer(song)
        if not source:
            worker.join()  # no Deezer preview either: YouTube is the only option left
            source = found.get("youtube")
        if not source:
            raise PreviewError("No preview found on YouTube or Deezer")
        return source

    def _from_youtube(self, song: Suggestion) -> Optional[PreviewSource]:
        if not self.finder or time.monotonic() < self._youtube_down_until:
            return None
        throttled_before = self.finder.throttled
        source = self._search_youtube(song)
        if not source and self.finder.throttled > throttled_before:
            # Rate limited: keep previews instant by skipping YouTube for a while.
            self._youtube_down_until = time.monotonic() + YOUTUBE_COOLDOWN
        return source

    def _search_youtube(self, song: Suggestion) -> Optional[PreviewSource]:
        track = song.to_track()
        for name in PREVIEW_SOURCES:
            if name not in self.finder.sources:
                continue
            for cand in self.finder.search(name, track)[:2]:
                try:
                    url, headers = self.finder.stream_url(cand.url)
                except Exception as exc:
                    self.finder._note_error(exc)
                    logger.debug("No stream for %s: %s", cand.url, exc)
                    continue
                label = "YouTube Music" if name == "ytmusic" else "YouTube"
                return PreviewSource(f"{label}: {cand.title} — {cand.uploader}", url, headers)
        return None

    def _from_deezer(self, song: Suggestion) -> Optional[PreviewSource]:
        if not song.deezer_id:
            return None
        # Preview links expire after a few minutes, so always ask for a fresh one.
        data = catalog._get_json(f"{DEEZER}/track/{song.deezer_id}", host_key="deezer", min_interval=0.11) or {}
        url = data.get("preview")
        return PreviewSource("Deezer 30-second preview (YouTube unavailable)", url) if url else None

    # ------------------------------------------------------------- playback

    def play(self, song: Suggestion) -> Optional[PreviewSource]:
        """Start playing a song (stopping any current preview). Returns None if superseded."""
        if not self.available:
            raise PreviewError("No audio player found: install ffmpeg (brew install ffmpeg)")
        with self._lock:
            self._token += 1
            token = self._token
        self.stop(keep_token=True)
        source = self.resolve(song)
        with self._lock:
            if token != self._token:  # another preview was requested while searching
                return None
        if self.player == "ffplay":
            self._spawn(["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", "-t", str(self.seconds),
                         *self._header_args(source), source.url])
        else:
            self._play_with_afplay(source, token)
        return source

    def _header_args(self, source: PreviewSource):
        if not source.headers:
            return []
        return ["-headers", "".join(f"{k}: {v}\r\n" for k, v in source.headers.items())]

    def _play_with_afplay(self, source: PreviewSource, token: int) -> None:
        fd, path = tempfile.mkstemp(suffix=".m4a", prefix="preview-")
        os.close(fd)
        self._tmp = path
        grab = self._spawn(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", *self._header_args(source),
                            "-i", source.url, "-t", str(self.seconds), "-vn", "-c:a", "aac", path])
        grab.wait()
        with self._lock:
            if token != self._token or grab.returncode != 0:
                return
        self._spawn(["afplay", path])

    def _spawn(self, cmd) -> subprocess.Popen:
        proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, start_new_session=True)
        with self._lock:
            self._procs.append(proc)
        return proc

    def is_playing(self) -> bool:
        with self._lock:
            return any(p.poll() is None for p in self._procs)

    def stop(self, keep_token: bool = False) -> None:
        with self._lock:
            if not keep_token:
                self._token += 1
            procs, self._procs = self._procs, []
        for p in procs:
            if p.poll() is None:
                p.terminate()
                try:
                    p.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    p.kill()
        if self._tmp:
            try:
                os.unlink(self._tmp)
            except OSError:
                pass
            self._tmp = None
