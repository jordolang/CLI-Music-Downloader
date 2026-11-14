"""Background download queue for the GUI, built on the regular LibraryDownloader."""

import itertools
import logging
import queue
import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Callable, Dict, List, Optional

from .. import catalog
from ..library import LibraryDownloader
from ..songlist import Track
from ..sources import DEFAULT_SOURCES, Candidate
from ..tagger import prepare_artwork

logger = logging.getLogger(__name__)

FINISHED = ("done", "exists", "failed", "cancelled")


class Cancelled(Exception):
    pass


@dataclass
class Job:
    id: int
    kind: str  # song (find the best source) | video (this exact YouTube upload) | fix (metadata only)
    title: str
    artist: str
    album: str = ""
    duration: Optional[int] = None
    video_url: str = ""
    video_title: str = ""
    song_id: str = ""  # library song (fix jobs, and the result of downloads)
    artwork: str = ""  # image shown in the downloads list
    status: str = "queued"
    stage: str = "Waiting"
    progress: Optional[float] = None
    message: str = ""
    source: str = ""
    created: float = field(default_factory=time.time)
    finished: float = 0.0
    cancel: bool = False

    def to_dict(self) -> Dict:
        d = asdict(self)
        d.pop("cancel", None)
        return d


class DownloadManager:
    def __init__(self, index, settings_getter: Callable[[], Dict], on_change: Callable[[], None] = lambda: None):
        self.index = index
        self._settings = settings_getter
        self._on_change = on_change
        self._jobs: Dict[int, Job] = {}
        self._queue: "queue.Queue[int]" = queue.Queue()
        self._ids = itertools.count(1)
        self._lock = threading.Lock()
        self._workers: List[threading.Thread] = []
        self.version = 0

    def _bump(self) -> None:
        self.version += 1

    def _ensure_workers(self) -> None:
        wanted = max(1, min(4, int(self._settings().get("workers") or 2)))
        self._workers = [t for t in self._workers if t.is_alive()]
        while len(self._workers) < wanted:
            t = threading.Thread(target=self._work, daemon=True, name=f"download-{len(self._workers) + 1}")
            t.start()
            self._workers.append(t)

    # ------------------------------------------------------------- queueing

    def add(self, kind: str, title: str, artist: str, **extra) -> Job:
        if not title.strip():
            raise ValueError("A title is required")
        with self._lock:
            # Do not queue the same song twice while it is still waiting or downloading.
            for job in self._jobs.values():
                if (job.status not in FINISHED and job.kind == kind and job.title.casefold() == title.casefold()
                        and job.artist.casefold() == artist.casefold() and job.song_id == extra.get("song_id", "")):
                    return job
            job = Job(id=next(self._ids), kind=kind, title=title.strip(), artist=artist.strip(), **extra)
            self._jobs[job.id] = job
            self._bump()
        self._queue.put(job.id)
        self._ensure_workers()
        return job

    def add_tracks(self, tracks: List[Track]) -> List[Job]:
        return [self.add("song", t.title, t.artist, album=t.album, duration=t.duration) for t in tracks]

    def jobs(self) -> List[Dict]:
        with self._lock:
            return [j.to_dict() for j in sorted(self._jobs.values(), key=lambda j: j.id, reverse=True)]

    def active_count(self) -> int:
        with self._lock:
            return sum(1 for j in self._jobs.values() if j.status not in FINISHED)

    def cancel(self, jid: int) -> None:
        with self._lock:
            job = self._jobs.get(jid)
            if job and job.status not in FINISHED:
                job.cancel = True
                if job.status == "queued":
                    job.status, job.stage, job.finished = "cancelled", "Cancelled", time.time()
                self._bump()

    def retry(self, jid: int) -> Optional[Job]:
        with self._lock:
            job = self._jobs.get(jid)
        if not job or job.status not in ("failed", "cancelled"):
            return None
        fields = {k: getattr(job, k) for k in ("album", "duration", "video_url", "video_title", "song_id", "artwork")}
        with self._lock:
            self._jobs.pop(jid, None)
        return self.add(job.kind, job.title, job.artist, **fields)

    def clear_finished(self) -> None:
        with self._lock:
            self._jobs = {k: j for k, j in self._jobs.items() if j.status not in FINISHED}
            self._bump()

    # ------------------------------------------------------------- working

    def _work(self) -> None:
        while True:
            jid = self._queue.get()
            with self._lock:
                job = self._jobs.get(jid)
                if not job or job.status != "queued":
                    continue
                job.status, job.stage = "running", "Starting"
                self._bump()
            try:
                if job.kind == "fix":
                    self._fix(job)
                else:
                    self._download(job)
            except Cancelled:
                job.status, job.stage, job.progress = "cancelled", "Cancelled", None
            except Exception as exc:
                logger.debug("Job %s failed", job.id, exc_info=True)
                job.status, job.stage, job.message = "failed", "Failed", str(exc)[:300]
            job.finished = time.time()
            if job.status in ("done", "exists"):
                try:
                    self.index.scan()
                    if job.kind != "fix":
                        found = self.index.find(job.artist, job.title)
                        job.song_id = found.id if found else job.song_id
                except Exception:
                    logger.debug("Rescan failed", exc_info=True)
                self._on_change()
            self._bump()

    def _status(self, job: Job):
        def update(stage: str, fraction: Optional[float] = None) -> None:
            if job.cancel:
                raise Cancelled()
            job.stage = stage
            job.progress = fraction
            self._bump()
        return update

    def _downloader(self) -> LibraryDownloader:
        s = self._settings()
        return LibraryDownloader(
            self.index.root, sources=s.get("sources") or DEFAULT_SOURCES, workers=1, lyrics=bool(s.get("lyrics", True)),
            cookies_from_browser=s.get("cookies_from_browser") or None, audio_quality=str(s.get("quality") or "0"),
            on_result=lambda *a: None, retry_passes=0, report=False)

    def _download(self, job: Job) -> None:
        dl = self._downloader()
        track = Track(number=job.id, title=job.title, artist=job.artist, album=job.album, duration=job.duration)
        candidate = None
        if job.kind == "video":
            candidate = Candidate(source="youtube", url=job.video_url, title=job.video_title or job.title,
                                  uploader="", duration=job.duration, score=100.0,
                                  extra={"thumbnail": job.artwork})
        result = dl.process(track, candidate=candidate, status=self._status(job))
        if job.cancel:
            raise Cancelled()
        job.progress = None
        job.source = result.source
        if result.status == "downloaded":
            job.status, job.stage = "done", "Added to library"
            job.message = f"{result.source} · match {result.match_score:.0f}" + ("" if result.artwork else " · no artwork")
        elif result.status in ("exists", "duplicate"):
            job.status, job.stage, job.message = "exists", "Already in library", result.message
        else:
            job.status, job.stage, job.message = "failed", "Failed", result.message
        # The catalog may have completed a truncated name; show what was actually saved.
        job.title, job.artist = result.title or job.title, result.artist or job.artist

    def _fix(self, job: Job) -> None:
        """Fill in missing artwork, lyrics, album, genre and year from the catalog."""
        song = self.index.get(job.song_id)
        if not song:
            raise ValueError("Song is no longer in the library")
        status = self._status(job)
        status("Looking up metadata")
        track = Track(number=job.id, title=song.title, artist=song.artist, album=song.album,
                      duration=int(song.duration) or None)
        info = catalog.lookup(track)
        changes: Dict[str, str] = {}
        artwork = lyrics = None
        if info:
            if not song.album and info.album:
                changes["album"] = info.album
            if not song.genre and info.genre:
                changes["genre"] = info.genre
            if not song.year and info.year:
                changes["year"] = info.year
            if not song.album_artist:
                changes["album_artist"] = song.artist
            if not song.has_art and info.artwork_url:
                status("Fetching artwork")
                artwork = prepare_artwork(catalog.fetch_artwork(info.artwork_url))
        if not song.has_lyrics and self._settings().get("lyrics", True):
            status("Fetching lyrics")
            lyrics = catalog.fetch_lyrics(song.title, song.artist, song.album, int(song.duration) or None)
        if not (changes or artwork or lyrics):
            job.status, job.stage = "done", "Nothing to add"
            job.message = "no catalog match" if not info else "metadata already complete"
            return
        if song.ext != ".mp3" and (artwork or lyrics):
            artwork = lyrics = None  # only MP3 artwork/lyrics writing is supported
        status("Writing tags")
        old_id = song.id
        new = self.index.update_tags(song.id, changes, organize=False, artwork=artwork, lyrics=lyrics)
        job.song_id = new.id
        added = [k for k in changes] + (["artwork"] if artwork else []) + (["lyrics"] if lyrics else [])
        job.status, job.stage = "done", "Metadata updated"
        job.message = "added " + ", ".join(added).replace("_", " ")
        if old_id != new.id:
            logger.debug("Song id changed %s -> %s", old_id, new.id)
