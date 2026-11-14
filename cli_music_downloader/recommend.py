"""
Song suggestions based on the music you already have.

The library folder (normally ~/Music) is scanned for MP3s; their tags tell us which
artists you listen to most. Deezer's free API (no key needed) then supplies:

  * artists related to your favourites  -> their top songs ("Similar to ...")
  * top songs of your favourite artists -> the hits you are missing ("You have N songs by ...")

Songs you already own, songs on a song list you downloaded (download_report.json) and
songs you dismissed are never suggested.
"""

import json
import logging
import math
import os
import random
import re
import threading
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Set, Tuple

from . import catalog
from .catalog import base_title, normalize, similarity, split_artists
from .songlist import Track

logger = logging.getLogger(__name__)

DEEZER = "https://api.deezer.com"
MIN_COUNT, MAX_COUNT, DEFAULT_COUNT = 25, 50, 40
DEFAULT_SEEDS = 20
CACHE_TTL = 3 * 24 * 3600
KNOWN_SHARE = 0.3  # part of the list taken from artists already in the library
PER_ARTIST = 2

# Versions that should not be suggested in place of the original recording.
SKIP_WORDS = (
    "live", "acoustic", "remix", "rmx", "mix", "instrumental", "karaoke", "sped up", "speed up",
    "slowed", "reverb", "nightcore", "demo", "stripped", "unplugged", "mashup", "medley",
    "extended", "radio edit", "commentary", "interview", "skit", "intro", "outro", "a cappella",
    "acapella", "clean", "8d",
)
# Bracketed or dashed suffixes that do not make a different song.
_NOISE_RE = re.compile(
    r"\s*(?:[\(\[][^\)\]]*\b(?:remaster(?:ed)?|version|edit|mono|stereo|deluxe|anniversary|bonus)\b[^\)\]]*[\)\]]"
    r"|\s-\s.*\b(?:remaster(?:ed)?|version|edit|mono|stereo)\b.*$)",
    re.I,
)
UNKNOWN_ARTISTS = {"", "unknown artist", "various artists"}

Progress = Callable[[str, int, int], None]


def cache_dir() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    return Path(base) / "cli-music-downloader"


def core_title(title: str) -> str:
    """Title reduced to what identifies the song: no feat. credits, remaster or version tags."""
    return normalize(_NOISE_RE.sub("", base_title(title or ""))) or normalize(title)


def song_key(artist: str, title: str) -> str:
    return f"{normalize(artist)}|{core_title(title)}"


def _has_skip_word(text: str) -> bool:
    t = f" {normalize(text)} "
    return any(f" {w} " in t for w in SKIP_WORDS)


# ------------------------------------------------------------------ library


@dataclass
class LibrarySong:
    path: str
    title: str
    artist: str
    album: str = ""
    genre: str = ""


class LibraryProfile:
    """What is in the library: owned songs, and how much each artist is listened to."""

    def __init__(self, folder: Path, songs: List[LibrarySong], listed: Iterable[Tuple[str, str]] = ()):
        self.folder = Path(folder)
        self.songs = songs
        self.artist_weight: Dict[str, float] = defaultdict(float)
        self.artist_songs: Counter = Counter()
        self.artist_names: Dict[str, str] = {}
        self.genres: Counter = Counter()
        self._owned: Set[str] = set()
        for s in songs:
            self.add_owned(s.artist, s.title)
            if s.genre:
                self.genres[s.genre] += 1
            if normalize(s.artist) in UNKNOWN_ARTISTS:
                continue
            # The full credit counts as one artist ("Florence and the Machine"), and each
            # collaborator in it counts a little too ("Alex Warren & Jelly Roll").
            names = [s.artist] + [p for p in split_artists(s.artist) if normalize(p) != normalize(s.artist)]
            for i, name in enumerate(names):
                key = normalize(name)
                self.artist_weight[key] += 1.0 if i == 0 else 0.5
                self.artist_songs[key] += 1
                self.artist_names.setdefault(key, name)
        for artist, title in listed:
            self.add_owned(artist, title)

    def add_owned(self, artist: str, title: str) -> None:
        self._owned.add(song_key(artist, title))
        for part in split_artists(artist):
            self._owned.add(song_key(part, title))

    def owns(self, artist: str, title: str) -> bool:
        keys = {song_key(artist, title)} | {song_key(p, title) for p in split_artists(artist)}
        return bool(keys & self._owned)

    def knows_artist(self, artist: str) -> bool:
        return normalize(artist) in self.artist_weight

    def songs_by(self, artist: str) -> int:
        return self.artist_songs.get(normalize(artist), 0)

    def top_artists(self, n: int) -> List[Tuple[str, float]]:
        ranked = sorted(self.artist_weight.items(), key=lambda kv: (-kv[1], kv[0]))
        return [(self.artist_names[k], w) for k, w in ranked[:n]]

    def top_genres(self, n: int = 3) -> List[str]:
        return [g for g, _ in self.genres.most_common(n)]

    @property
    def artist_count(self) -> int:
        return len({normalize(s.artist) for s in self.songs})


def _read_song(path: Path, folder: Path) -> LibrarySong:
    title = artist = album = genre = ""
    try:
        from mutagen.id3 import ID3

        id3 = ID3(str(path))

        def text(key):
            frame = id3.get(key)
            return str(frame.text[0]).strip() if frame and getattr(frame, "text", None) else ""

        title, artist, album, genre = text("TIT2"), text("TPE1"), text("TALB"), text("TCON")
    except Exception:
        pass  # untagged or unreadable: fall back to the <Artist>/<Title>.mp3 layout
    if not title:
        title = path.stem
    if not artist and path.parent != folder:
        artist = path.parent.name
    return LibrarySong(path=str(path), title=title, artist=artist, album=album, genre=genre)


def _listed_songs(folder: Path) -> List[Tuple[str, str]]:
    """Songs from a downloaded song list (download_report.json), including ones still pending."""
    report = folder / "download_report.json"
    try:
        rows = json.loads(report.read_text()).get("tracks", [])
    except Exception:
        return []
    return [(r.get("artist", ""), r.get("title", "")) for r in rows if r.get("title")]


def scan_library(folder, progress: Optional[Progress] = None) -> LibraryProfile:
    folder = Path(folder).expanduser()
    files = sorted(p for p in folder.rglob("*.mp3")
                   if not any(part.startswith(".") for part in p.relative_to(folder).parts))
    songs = []
    for i, path in enumerate(files, 1):
        songs.append(_read_song(path, folder))
        if progress and (i % 25 == 0 or i == len(files)):
            progress(f"Reading your library ({i}/{len(files)} songs)", i, len(files))
    return LibraryProfile(folder, songs, _listed_songs(folder))


# ------------------------------------------------------------------ suggestions


@dataclass
class Suggestion:
    title: str
    artist: str
    album: str = ""
    duration: Optional[int] = None
    deezer_id: int = 0
    explicit: bool = False
    popularity: float = 0.0
    score: float = 0.0
    reason: str = ""
    kind: str = "new"  # new = artist not in the library; known = artist you already have
    seed: str = ""  # library artist that led to this suggestion

    @property
    def key(self) -> str:
        return song_key(self.artist, self.title)

    @property
    def length(self) -> str:
        return f"{self.duration // 60}:{self.duration % 60:02d}" if self.duration else ""

    def to_track(self, number: int = 1) -> Track:
        return Track(number=number, title=self.title, artist=self.artist, album=self.album,
                     duration=self.duration)

    def to_dict(self) -> dict:
        return asdict(self)


class _JsonCache:
    """Small on-disk cache so relaunching the suggester does not repeat every API call."""

    def __init__(self, path: Optional[Path], ttl: int = CACHE_TTL):
        self.path = path
        self.ttl = ttl
        self._lock = threading.Lock()
        self._data: Dict[str, dict] = {}
        if path and path.exists():
            try:
                now = time.time()
                self._data = {k: v for k, v in json.loads(path.read_text()).items() if now - v.get("t", 0) < ttl}
            except Exception:
                self._data = {}

    def get(self, key: str):
        with self._lock:
            hit = self._data.get(key)
            return hit["v"] if hit else None

    def set(self, key: str, value) -> None:
        with self._lock:
            self._data[key] = {"t": time.time(), "v": value}

    def save(self) -> None:
        if not self.path:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self._lock:
                text = json.dumps(self._data)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(text)
            tmp.replace(self.path)
        except OSError as exc:
            logger.debug("Could not save cache: %s", exc)


class Recommender:
    def __init__(self, profile: LibraryProfile, seeds: int = DEFAULT_SEEDS, dismissed: Iterable[str] = (),
                 use_cache: bool = True, workers: int = 6):
        self.profile = profile
        self.seeds = seeds
        self.dismissed = set(dismissed)
        self.workers = workers
        self.cache = _JsonCache(cache_dir() / "deezer_cache.json" if use_cache else None)

    # ------------------------------------------------------------- Deezer

    def _get(self, path: str, **params) -> Optional[dict]:
        key = path + "?" + "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        hit = self.cache.get(key)
        if hit is not None:
            return hit
        for attempt in range(3):
            data = catalog._get_json(DEEZER + path, params or None, host_key="deezer", min_interval=0.11)
            if isinstance(data, dict) and data.get("error"):
                # Deezer reports its quota (50 requests / 5 s) as an error body.
                logger.debug("Deezer error for %s: %s", key, data["error"])
                time.sleep(2 + 2 * attempt)
                continue
            if data is not None:
                self.cache.set(key, data)
            return data
        return None

    def find_artist(self, name: str) -> Optional[dict]:
        data = self._get("/search/artist", q=name, limit=5) or {}
        for a in data.get("data") or []:
            if normalize(a.get("name", "")) == normalize(name) or similarity(a.get("name", ""), name) >= 0.9:
                return a
        return None

    def _list(self, path: str, limit: int) -> List[dict]:
        return (self._get(path, limit=limit) or {}).get("data") or []

    # ------------------------------------------------------------- picking

    def _pick_seeds(self, rng: random.Random, shuffle: bool) -> List[Tuple[str, float]]:
        ranked = self.profile.top_artists(max(self.seeds * 2, 40))
        if not shuffle or len(ranked) <= self.seeds:
            return ranked[: self.seeds]
        # Weighted sample without replacement, so "new picks" explores more of the library.
        pool = list(ranked)
        chosen = []
        while pool and len(chosen) < self.seeds:
            total = sum(w for _, w in pool)
            r = rng.uniform(0, total)
            for i, (name, w) in enumerate(pool):
                r -= w
                if r <= 0:
                    chosen.append(pool.pop(i))
                    break
            else:
                chosen.append(pool.pop())
        return chosen

    def _parallel(self, jobs, label: str, progress: Optional[Progress]):
        results = []
        if not jobs:
            return results
        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            futures = [pool.submit(fn) for fn in jobs]
            for i, fut in enumerate(as_completed(futures), 1):
                try:
                    res = fut.result()
                except Exception as exc:  # one failed lookup must not stop the rest
                    logger.debug("Lookup failed: %s", exc)
                    res = None
                if res is not None:
                    results.append(res)
                if progress:
                    progress(label, i, len(jobs))
        return results

    def _usable(self, t: dict, seen: Set[str], exclude: Set[str]) -> bool:
        title = t.get("title") or ""
        artist = (t.get("artist") or {}).get("name") or ""
        duration = t.get("duration") or 0
        key = song_key(artist, title)
        if not title or not artist or key in seen or key in exclude or key in self.dismissed:
            return False
        if self.profile.owns(artist, title):
            return False
        if _has_skip_word(f"{title} {t.get('title_version') or ''}"):
            return False
        if duration and not 90 <= duration <= 600:  # skits, interludes, long mixes
            return False
        return True

    @staticmethod
    def _popularity(t: dict) -> float:
        return min(1.0, math.log10((t.get("rank") or 0) + 1) / 6)

    def _suggestion(self, t: dict, score: float, reason: str, kind: str, pop: float, seed: str) -> Suggestion:
        artist = (t.get("artist") or {}).get("name") or ""
        # Artists already in the library keep the spelling used there ("Theory of a Deadman").
        artist = self.profile.artist_names.get(normalize(artist), artist)
        return Suggestion(
            title=t.get("title") or "",
            artist=artist,
            album=(t.get("album") or {}).get("title") or "",
            duration=t.get("duration") or None,
            deezer_id=t.get("id") or 0,
            explicit=bool(t.get("explicit_lyrics")),
            popularity=round(pop, 3),
            score=round(score, 4),
            reason=reason,
            kind=kind,
            seed=seed,
        )

    def recommend(self, count: int = DEFAULT_COUNT, progress: Optional[Progress] = None, shuffle: bool = False,
                  exclude: Iterable[str] = ()) -> List[Suggestion]:
        """25-50 songs you do not have yet, best first."""
        count = max(MIN_COUNT, min(MAX_COUNT, count))
        exclude = set(exclude)
        rng = random.Random() if shuffle else random.Random(0)
        seeds = self._pick_seeds(rng, shuffle)
        if not seeds:
            return []

        def seed_job(name: str, weight: float):
            def run():
                artist = self.find_artist(name)
                if not artist:
                    return None
                related = self._list(f"/artist/{artist['id']}/related", 25)
                top = self._list(f"/artist/{artist['id']}/top", 25)
                return name, weight, artist, related, top
            return run

        seed_data = self._parallel([seed_job(n, w) for n, w in seeds],
                                   "Finding artists like the ones you play most", progress)
        if not seed_data:
            return []
        max_weight = max(w for _, w, _, _, _ in seed_data)
        seed_ids = {a["id"] for _, _, a, _, _ in seed_data}

        # Artists related to several of your favourites rank highest.
        related: Dict[int, dict] = {}
        for name, weight, _, rel, _ in seed_data:
            for i, r in enumerate(rel):
                contrib = (weight / max_weight) * (1 - 0.6 * i / max(1, len(rel)))
                entry = related.setdefault(r["id"], {"artist": r, "score": 0.0, "via": Counter()})
                entry["score"] += contrib
                entry["via"][name] += contrib
        new_artists = sorted(
            (e for aid, e in related.items()
             if aid not in seed_ids and not self.profile.knows_artist(e["artist"].get("name", ""))),
            key=lambda e: -e["score"])[: max(30, count)]

        def top_job(entry):
            return lambda: (entry, self._list(f"/artist/{entry['artist']['id']}/top", 10))

        new_data = self._parallel([top_job(e) for e in new_artists], "Picking songs from similar artists", progress)
        self.cache.save()

        seen: Set[str] = set()
        jitter = (lambda: rng.uniform(0.75, 1.0)) if shuffle else (lambda: 1.0)

        new_pool: List[Suggestion] = []
        max_rel = max((e["score"] for e in new_artists), default=1.0) or 1.0
        for entry, tracks in new_data:
            via = [n for n, _ in entry["via"].most_common(2)]
            reason = "Similar to " + " & ".join(via)
            for i, t in enumerate(tracks):
                if not self._usable(t, seen, exclude):
                    continue
                seen.add(song_key(t["artist"]["name"], t["title"]))
                pop = self._popularity(t)
                score = (0.6 * entry["score"] / max_rel + 0.25 * pop + 0.15 * (1 - i / max(1, len(tracks)))) * jitter()
                new_pool.append(self._suggestion(t, score, reason, "new", pop, via[0]))

        known_pool: List[Suggestion] = []
        for name, weight, _, _, tracks in seed_data:
            for i, t in enumerate(tracks):
                if not self._usable(t, seen, exclude):
                    continue
                seen.add(song_key(t["artist"]["name"], t["title"]))
                pop = self._popularity(t)
                n = self.profile.songs_by(name)
                songs = f"{n} song{'s' if n != 1 else ''}"
                if normalize(t["artist"]["name"]) == normalize(name):
                    reason = f"You have {songs} by {name}"
                else:  # a collaboration listed among the artist's top songs
                    reason = f"Features {name} (you have {songs})"
                score = (0.5 * weight / max_weight + 0.3 * pop + 0.2 * (1 - i / max(1, len(tracks)))) * jitter()
                known_pool.append(self._suggestion(t, score, reason, "known", pop, name))

        return _assemble(new_pool, known_pool, count)


def _capped(pool: List[Suggestion], limit: int, per_artist: int = PER_ARTIST,
            per_seed: Optional[int] = None, already: Iterable[Suggestion] = ()) -> List[Suggestion]:
    """Best-scored songs, with at most `per_artist` per artist and `per_seed` per library artist
    (counting the songs `already` picked)."""
    out = []
    per = Counter(normalize(s.artist) for s in already)
    seeds = Counter(s.seed for s in already)
    for s in sorted(pool, key=lambda s: -s.score):
        if len(out) >= limit:
            break
        a = normalize(s.artist)
        if per[a] >= per_artist or (per_seed and seeds[s.seed] >= per_seed):
            continue
        per[a] += 1
        seeds[s.seed] += 1
        out.append(s)
    return out


def _assemble(new_pool: List[Suggestion], known_pool: List[Suggestion], count: int) -> List[Suggestion]:
    # Spread the list over the different kinds of music in the library rather than
    # filling it with artists similar to the single most-played one.
    per_seed = max(4, count // 6)
    known = _capped(known_pool, round(count * KNOWN_SHARE), per_seed=per_seed)
    new = _capped(new_pool, count - len(known), per_seed=per_seed)
    picked = {s.key for s in known + new}
    for pool, cap in ((new_pool, PER_ARTIST), (known_pool, PER_ARTIST + 1)):  # top up if a cap left gaps
        missing = count - len(picked)
        if missing <= 0:
            break
        extra = _capped([s for s in pool if s.key not in picked], missing, cap, already=new + known)
        (new if pool is new_pool else known).extend(extra)
        picked |= {s.key for s in extra}
    return sorted(new + known, key=lambda s: -s.score)[:count]


# ------------------------------------------------------------------ state


class SuggesterState:
    """Songs you marked "not for me" (kept between runs)."""

    def __init__(self, path: Optional[Path] = None):
        self.path = path or cache_dir() / "suggester.json"
        self.dismissed: Set[str] = set()
        try:
            self.dismissed = set(json.loads(self.path.read_text()).get("dismissed", []))
        except Exception:
            pass

    def dismiss(self, key: str) -> None:
        self.dismissed.add(key)
        self.save()

    def save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps({"dismissed": sorted(self.dismissed)}, indent=1))
        except OSError as exc:
            logger.debug("Could not save suggester state: %s", exc)
