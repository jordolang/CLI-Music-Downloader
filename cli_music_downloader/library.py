"""
Download a whole song list into  <output>/<Artist>/<Title>.mp3  with full metadata.

Names come from the song list exactly as listed. The only exceptions are values the
printout cut off, which are completed from the catalog, and characters that cannot
appear in a file name ("/" and ":"), which become "-" in the path only (tags keep the
original text).
"""

import csv
import json
import logging
import re
import sys
import threading
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Callable, Iterable, List, Optional

from . import catalog
from .songlist import Track
from .sources import DEFAULT_SOURCES, Candidate, SourceFinder
from .tagger import TagData, prepare_artwork, write_tags

logger = logging.getLogger(__name__)

UNKNOWN_ARTIST = "Unknown Artist"
REPORT_NAME = "download_report"


def safe_name(name: str, fallback: str = "Untitled") -> str:
    """Make a single path component: keep the text as-is except characters filesystems reject."""
    name = unicodedata.normalize("NFC", name or "").strip()
    name = name.replace("/", "-").replace(":", "-").replace("\\", "-")
    name = re.sub(r"[\x00-\x1f]", "", name)
    name = name.strip().lstrip(".").strip() or fallback
    # Most filesystems cap a name at 255 bytes; leave room for ".mp3.part".
    while len(name.encode("utf-8")) > 240:
        name = name[:-1]
    return name


def track_path(output_dir: Path, artist: str, title: str) -> Path:
    return Path(output_dir) / safe_name(artist, UNKNOWN_ARTIST) / f"{safe_name(title)}.mp3"


@dataclass
class Result:
    number: int
    title: str
    artist: str
    album: str
    status: str  # downloaded | exists | duplicate | failed | planned
    path: str = ""
    source: str = ""
    source_url: str = ""
    source_title: str = ""
    match_score: float = 0.0
    metadata_source: str = ""
    artwork: bool = False
    lyrics: bool = False
    message: str = ""
    seconds: float = 0.0


class LibraryDownloader:
    def __init__(self, output_dir, sources: Iterable[str] = DEFAULT_SOURCES, workers: int = 2,
                 overwrite: bool = False, lyrics: bool = True, dry_run: bool = False,
                 cookies_from_browser: Optional[str] = None, cookies_file: Optional[str] = None,
                 audio_quality: str = "0", on_result: Optional[Callable[[Result, int, int], None]] = None,
                 retry_passes: int = 1, retry_wait: int = 120, report: bool = True):
        self.output_dir = Path(output_dir).expanduser()
        self.workers = max(1, workers)
        self.overwrite = overwrite
        self.lyrics = lyrics
        self.dry_run = dry_run
        self.on_result = on_result or self._print_result
        self.retry_passes = retry_passes
        self.retry_wait = retry_wait
        self.report = report
        self.finder = None if dry_run else SourceFinder(
            sources, cookies_from_browser=cookies_from_browser, cookies_file=cookies_file,
            audio_quality=audio_quality)
        self._claimed = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ helpers

    def _claim(self, path: Path, number: int) -> Optional[int]:
        """Reserve an output path; returns the list number that already owns it, if any."""
        key = str(path).casefold()  # macOS/Windows file names are case-insensitive
        with self._lock:
            owner = self._claimed.get(key)
            if owner is None:
                self._claimed[key] = number
            return owner

    @staticmethod
    def _print_result(r: Result, done: int, total: int) -> None:
        icon = {"downloaded": "✅", "exists": "⏭️ ", "duplicate": "🔁", "failed": "❌", "planned": "📝"}
        line = f"{icon.get(r.status, '•')} [{done}/{total}] #{r.number} {r.artist} - {r.title}"
        if r.status == "downloaded":
            line += f"  ← {r.source} (score {r.match_score:.0f})"
            if not r.artwork:
                line += "  [no artwork]"
        elif r.message:
            line += f"  — {r.message}"
        print(line, flush=True)

    # ------------------------------------------------------------- per-track

    def process(self, listed: Track, candidate: Optional[Candidate] = None,
                status: Optional[Callable[[str, Optional[float]], None]] = None) -> Result:
        """Download one track. `candidate` forces a specific upload (skips the search);
        `status(stage, fraction)` is told about each step (used by the GUI)."""
        started = time.monotonic()
        notify = status or (lambda stage, fraction=None: None)
        notify("Looking up metadata", None)
        info = catalog.lookup(listed)
        track = catalog.complete_names(listed, info)
        artist = track.artist or UNKNOWN_ARTIST
        dest = track_path(self.output_dir, artist, track.title)
        result = Result(number=track.number, title=track.title, artist=artist, album=track.album,
                        status="failed", path=str(dest),
                        metadata_source=info.source if info else "")

        owner = self._claim(dest, track.number)
        if owner is not None and owner != track.number:
            result.status = "duplicate"
            result.message = f"same artist/title as #{owner}"
            return result
        if dest.exists() and not self.overwrite:
            result.status = "exists"
            result.message = "already downloaded"
            return result
        if self.dry_run:
            result.status = "planned"
            result.message = f"catalog: {info.source} {info.album!r}" if info else "no catalog match"
            return result

        # Find and download the audio.
        chosen: Optional[Candidate] = None
        errors = []

        def on_progress(fraction: float) -> None:
            notify("Downloading", fraction)

        if candidate is not None:
            notify("Downloading", 0.0)
            try:
                # A hand-picked upload (e.g. a music video) may not match the listed length.
                self.finder.download(candidate, dest, None, on_progress=on_progress)
                chosen = candidate
            except Exception as exc:
                errors.append(f"{candidate.source}: {exc}")
                self.finder._note_error(exc)
        for source in ([] if candidate is not None else self.finder.sources):
            notify(f"Searching {source}", None)
            for cand in self.finder.search(source, track)[:3]:
                try:
                    notify("Downloading", 0.0)
                    self.finder.download(cand, dest, track.duration, on_progress=on_progress)
                    chosen = cand
                    break
                except Exception as exc:
                    errors.append(f"{source}: {exc}")
                    self.finder._note_error(exc)
                    logger.debug("Download failed from %s: %s", cand.url, exc)
            if chosen:
                break
        if not chosen:
            result.message = ("download failed" if candidate is not None
                              else "no matching audio found on " + ", ".join(self.finder.sources))
            if errors:
                result.message += f" ({errors[-1][:120]})"
            result.seconds = round(time.monotonic() - started, 1)
            return result

        # Metadata: listed names always win; the catalog fills in everything else.
        same_release = bool(info and catalog.album_matches(track, info))
        tags = TagData(
            title=track.title,
            artist=artist,
            album=track.album or (info.album if info else ""),
            album_artist=artist,
            genre=info.genre if info else "",
            date=(info.release_date if info else "") or "",
            track_number=info.track_number if same_release else None,
            track_count=info.track_count if same_release else None,
            disc_number=info.disc_number if same_release else None,
            disc_count=info.disc_count if same_release else None,
            isrc=info.isrc if info else "",
            explicit=bool(info and info.explicit),
            source_url=chosen.url if chosen.source != "audius" else "",
            comment=f"Source: {chosen.source}",
        )

        notify("Adding artwork, lyrics and tags", None)
        artwork = None
        if info and info.artwork_url:
            artwork = prepare_artwork(catalog.fetch_artwork(info.artwork_url))
        if not artwork:  # fall back to the source's own cover / thumbnail
            artwork = prepare_artwork(self.finder.fetch_thumbnail(chosen))

        lyrics = None
        if self.lyrics:
            lyrics = catalog.fetch_lyrics(track.title, artist, track.album, track.duration)

        write_tags(dest, tags, artwork, lyrics)

        result.status = "downloaded"
        result.source = chosen.source
        result.source_url = chosen.url
        result.source_title = f"{chosen.title} — {chosen.uploader}"
        result.match_score = round(chosen.score, 1)
        result.artwork = bool(artwork)
        result.lyrics = bool(lyrics)
        result.seconds = round(time.monotonic() - started, 1)
        return result

    def _safe_process(self, track: Track) -> Result:
        try:
            return self.process(track)
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            logger.debug("Unexpected error for %s", track, exc_info=True)
            return Result(number=track.number, title=track.title, artist=track.artist or UNKNOWN_ARTIST,
                          album=track.album, status="failed", message=f"error: {exc}")

    # --------------------------------------------------------------- batch

    def run(self, tracks: List[Track]) -> List[Result]:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        # Claim paths in list order so the first listing of a duplicate always wins.
        ordered = sorted(tracks, key=lambda t: t.number)
        for t in ordered:
            self._claim(track_path(self.output_dir, t.artist or UNKNOWN_ARTIST, t.title), t.number)
        results = {r.number: r for r in self._run_pass(ordered, self.workers)}

        # Failures are often temporary YouTube throttling: pause, then retry them one at a time.
        for attempt in range(self.retry_passes if not self.dry_run else 0):
            failed = [t for t in ordered if results[t.number].status == "failed"]
            if not failed:
                break
            print(f"\n🔄 Retrying {len(failed)} song(s) in {self.retry_wait}s "
                  f"(pass {attempt + 1}/{self.retry_passes})...\n", flush=True)
            time.sleep(self.retry_wait)
            for r in self._run_pass(failed, 1):
                results[r.number] = r

        final = [results[t.number] for t in ordered]
        if self.report and not self.dry_run:
            self.write_report(final)
        return final

    def _run_pass(self, ordered: List[Track], workers: int) -> List[Result]:
        total = len(ordered)
        results: List[Result] = []
        if workers == 1:
            for i, t in enumerate(ordered, 1):
                r = self._safe_process(t)
                results.append(r)
                self.on_result(r, i, total)
        else:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {}
                for t in ordered:
                    futures[pool.submit(self._safe_process, t)] = t
                for i, fut in enumerate(as_completed(futures), 1):
                    r = fut.result()
                    results.append(r)
                    self.on_result(r, i, total)
        return results

    def write_report(self, results: List[Result]) -> Path:
        """Write download_report.json/.csv in the output folder (merged with earlier runs)."""
        json_path = self.output_dir / f"{REPORT_NAME}.json"
        merged = {}
        if json_path.exists():
            try:
                for row in json.loads(json_path.read_text()).get("tracks", []):
                    merged[row["number"]] = row
            except Exception:
                pass
        for r in results:
            prev = merged.get(r.number)
            # A re-run that skips an existing file must not erase how it was downloaded.
            if r.status == "exists" and prev and prev.get("status") == "downloaded":
                continue
            merged[r.number] = asdict(r)
        rows = [merged[k] for k in sorted(merged)]
        json_path.write_text(json.dumps({"generated": time.strftime("%Y-%m-%d %H:%M:%S"),
                                         "tracks": rows}, indent=2, ensure_ascii=False))
        csv_path = self.output_dir / f"{REPORT_NAME}.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(Result.__dataclass_fields__))
            writer.writeheader()
            writer.writerows(rows)
        return json_path


def summarize(results: List[Result], out=sys.stdout) -> int:
    """Print a summary; returns the number of failures."""
    counts = {}
    for r in results:
        counts[r.status] = counts.get(r.status, 0) + 1
    print("\n" + "─" * 60, file=out)
    print("Summary: " + ", ".join(f"{v} {k}" for k, v in sorted(counts.items())), file=out)
    failed = [r for r in results if r.status == "failed"]
    if failed:
        print("\nNot downloaded:", file=out)
        for r in failed:
            print(f"  #{r.number} {r.artist} - {r.title}: {r.message}", file=out)
    dl = [r for r in results if r.status == "downloaded"]
    if dl:
        no_art = [r for r in dl if not r.artwork]
        no_lyr = sum(1 for r in dl if not r.lyrics)
        print(f"\nArtwork embedded: {len(dl) - len(no_art)}/{len(dl)}   Lyrics embedded: {len(dl) - no_lyr}/{len(dl)}",
              file=out)
    return len(failed)
