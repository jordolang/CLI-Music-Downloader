"""
Catalog metadata lookup: album, genre, release date, track/disc numbers, artwork and lyrics.

Sources (all free, no API key):
  * iTunes Search API  - primary; it is the same catalog the Apple Music song list came from
  * Deezer API         - fallback when iTunes has no match
  * LRCLIB             - lyrics
"""

import logging
import re
import threading
import time
import unicodedata
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Dict, List, Optional

import requests

from .songlist import Track

logger = logging.getLogger(__name__)

USER_AGENT = "CLI-Music-Downloader/2.0 (https://github.com/jordolang/CLI-Music-Downloader)"
ARTWORK_SIZE = 1400

_session = requests.Session()
_session.headers["User-Agent"] = USER_AGENT
_rate_lock = threading.Lock()
_last_call: Dict[str, float] = {}


def _get_json(url: str, params: Optional[Dict] = None, host_key: str = "", min_interval: float = 0.0,
              retries: int = 3) -> Optional[Dict]:
    """GET a JSON document, spacing calls per host and retrying on throttling."""
    for attempt in range(retries):
        if min_interval:
            with _rate_lock:
                wait = _last_call.get(host_key, 0) + min_interval - time.monotonic()
                if wait > 0:
                    time.sleep(wait)
                _last_call[host_key] = time.monotonic()
        try:
            resp = _session.get(url, params=params, timeout=20)
            if resp.status_code in (403, 429, 503):
                time.sleep(3 * (attempt + 1))
                continue
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()
        except (requests.RequestException, ValueError) as exc:
            logger.debug("Request failed (%s): %s", url, exc)
            time.sleep(1 + attempt)
    return None


# ------------------------------------------------------------------ text matching

_FEAT_RE = re.compile(r"[\(\[]\s*(feat\.?|ft\.?|featuring|with)\s[^\)\]]*[\)\]]?", re.I)


def normalize(text: str) -> str:
    """Lower-case, strip accents and punctuation, collapse whitespace."""
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.replace("’", "'").replace("‘", "'").replace("&", " and ").casefold()
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def base_title(title: str) -> str:
    """Title without "(feat. ...)" credits, e.g. "Wasted (feat. Lil Uzi Vert)" -> "Wasted"."""
    stripped = _FEAT_RE.sub("", title or "").strip()
    return stripped or (title or "")


def split_artists(artist: str) -> List[str]:
    """ "mgk, YUNGBLUD & Travis Barker" -> ["mgk", "YUNGBLUD", "Travis Barker"]."""
    parts = re.split(r"\s*(?:,|&|\band\b|\bx\b|\bfeat\.?|\bft\.?|\bwith\b)\s*", artist or "", flags=re.I)
    return [p.strip() for p in parts if p and p.strip()]


def similarity(a: str, b: str) -> float:
    a, b = normalize(a), normalize(b)
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def prefix_match(listed: str, full: str) -> bool:
    """True when `listed` is a cut-off version of `full`."""
    a, b = normalize(listed), normalize(full)
    return bool(a) and b.startswith(a)


def text_match(listed: str, candidate: str, truncated: bool) -> float:
    """0..1 score of how well a catalog value matches a listed value."""
    if truncated and prefix_match(listed, candidate):
        return 1.0
    if normalize(listed) == normalize(candidate):
        return 1.0
    return similarity(listed, candidate)


# ---------------------------------------------------------------------- data model


@dataclass
class CatalogInfo:
    """Metadata for one recording from a catalog."""

    source: str
    title: str
    artist: str
    album: str = ""
    album_artist: str = ""
    genre: str = ""
    release_date: str = ""  # YYYY-MM-DD or YYYY
    track_number: Optional[int] = None
    track_count: Optional[int] = None
    disc_number: Optional[int] = None
    disc_count: Optional[int] = None
    duration: Optional[int] = None
    artwork_url: str = ""
    explicit: bool = False
    isrc: str = ""
    copyright: str = ""
    url: str = ""
    score: float = 0.0
    extra: Dict = field(default_factory=dict)

    @property
    def year(self) -> str:
        return (self.release_date or "")[:4]


def _score(track: Track, title: str, artist: str, album: str, duration: Optional[int]) -> float:
    """Weighted match score (0..100) between a listed track and a catalog entry."""
    t = max(text_match(track.title, title, track.title_truncated),
            text_match(base_title(track.title), base_title(title), track.title_truncated))
    listed_artists = split_artists(track.artist)
    cand_artists = normalize(artist)
    if track.artist_truncated and prefix_match(track.artist, artist):
        a = 1.0
    elif listed_artists:
        hits = sum(1 for la in listed_artists if normalize(la) and normalize(la) in cand_artists)
        a = max(hits / len(listed_artists), similarity(track.artist, artist))
    else:
        a = 0.5
    al = text_match(track.album, album, track.album_truncated) if track.album else 0.5
    score = 50 * t + 30 * a + 12 * al
    if track.duration and duration:
        diff = abs(track.duration - duration)
        score += 8 if diff <= 2 else 4 if diff <= 6 else -10 if diff > 30 else 0
    return score


# --------------------------------------------------------------------------- iTunes


def _itunes_search(term: str, limit: int = 25) -> List[Dict]:
    data = _get_json(
        "https://itunes.apple.com/search",
        {"term": term, "media": "music", "entity": "song", "limit": limit, "country": "US"},
        host_key="itunes", min_interval=0.4,
    )
    return (data or {}).get("results", [])


def _itunes_info(r: Dict, score: float) -> CatalogInfo:
    art = r.get("artworkUrl100") or r.get("artworkUrl60") or ""
    if art:
        art = re.sub(r"/\d+x\d+bb\.(jpg|png)$", f"/{ARTWORK_SIZE}x{ARTWORK_SIZE}bb.jpg", art)
    return CatalogInfo(
        source="itunes",
        title=r.get("trackName", ""),
        artist=r.get("artistName", ""),
        album=r.get("collectionName", ""),
        album_artist=r.get("collectionArtistName") or r.get("artistName", ""),
        genre=r.get("primaryGenreName", ""),
        release_date=(r.get("releaseDate") or "")[:10],
        track_number=r.get("trackNumber"),
        track_count=r.get("trackCount"),
        disc_number=r.get("discNumber"),
        disc_count=r.get("discCount"),
        duration=round(r["trackTimeMillis"] / 1000) if r.get("trackTimeMillis") else None,
        artwork_url=art,
        explicit=r.get("trackExplicitness") == "explicit",
        url=r.get("trackViewUrl", ""),
        score=score,
    )


def lookup_itunes(track: Track) -> Optional[CatalogInfo]:
    terms = []
    artist_q = split_artists(track.artist)[0] if track.artist else ""
    terms.append(f"{artist_q} {base_title(track.title)}".strip())
    if track.artist and track.artist != artist_q:
        terms.append(f"{track.artist} {base_title(track.title)}")
    if track.album:
        terms.append(f"{base_title(track.title)} {track.album}")
    best: Optional[CatalogInfo] = None
    seen = set()
    for term in terms:
        for r in _itunes_search(term):
            if r.get("trackId") in seen:
                continue
            seen.add(r.get("trackId"))
            duration = round(r["trackTimeMillis"] / 1000) if r.get("trackTimeMillis") else None
            s = _score(track, r.get("trackName", ""), r.get("artistName", ""),
                       r.get("collectionName", ""), duration)
            if not best or s > best.score:
                best = _itunes_info(r, s)
        if best and best.score >= 90:
            break
    return best


# --------------------------------------------------------------------------- Deezer


def lookup_deezer(track: Track) -> Optional[CatalogInfo]:
    artist_q = split_artists(track.artist)[0] if track.artist else ""
    queries = [f'artist:"{artist_q}" track:"{base_title(track.title)}"',
               f"{artist_q} {base_title(track.title)}"]
    best, best_raw = None, None
    for q in queries:
        data = _get_json("https://api.deezer.com/search", {"q": q, "limit": 25},
                         host_key="deezer", min_interval=0.15)
        for r in (data or {}).get("data", []):
            s = _score(track, r.get("title", ""), (r.get("artist") or {}).get("name", ""),
                       (r.get("album") or {}).get("title", ""), r.get("duration"))
            if not best or s > best:
                best, best_raw = s, r
        if best and best >= 90:
            break
    if not best_raw:
        return None

    info = CatalogInfo(
        source="deezer",
        title=best_raw.get("title", ""),
        artist=(best_raw.get("artist") or {}).get("name", ""),
        album=(best_raw.get("album") or {}).get("title", ""),
        duration=best_raw.get("duration"),
        artwork_url=(best_raw.get("album") or {}).get("cover_xl", ""),
        explicit=bool(best_raw.get("explicit_lyrics")),
        url=best_raw.get("link", ""),
        score=best,
    )
    # Track and album details carry numbering, ISRC, genre and release date.
    detail = _get_json(f"https://api.deezer.com/track/{best_raw['id']}", host_key="deezer", min_interval=0.15)
    if detail and not detail.get("error"):
        info.track_number = detail.get("track_position")
        info.disc_number = detail.get("disk_number")
        info.isrc = detail.get("isrc", "")
        info.release_date = detail.get("release_date", "") or ""
    album_id = (best_raw.get("album") or {}).get("id")
    if album_id:
        album = _get_json(f"https://api.deezer.com/album/{album_id}", host_key="deezer", min_interval=0.15)
        if album and not album.get("error"):
            info.album_artist = (album.get("artist") or {}).get("name", "")
            info.track_count = album.get("nb_tracks")
            info.release_date = album.get("release_date") or info.release_date
            genres = (album.get("genres") or {}).get("data") or []
            if genres:
                info.genre = genres[0].get("name", "")
    return info


# ------------------------------------------------------------------------- public


MIN_SCORE = 70.0


def lookup(track: Track) -> Optional[CatalogInfo]:
    """Best catalog match for a listed track, or None if nothing matches well enough."""
    if not track.title:
        return None
    best = None
    for fn in (lookup_itunes, lookup_deezer):
        try:
            info = fn(track)
        except Exception as exc:  # a broken catalog must not stop the download
            logger.debug("%s lookup failed for %s: %s", fn.__name__, track, exc)
            continue
        if info and (not best or info.score > best.score):
            best = info
        if best and best.score >= 85:
            break
    if best and best.score >= MIN_SCORE:
        # Deezer fills in genre/numbering that a lower-confidence iTunes hit lacks, and vice versa.
        return best
    return None


def complete_names(track: Track, info: Optional[CatalogInfo]) -> Track:
    """Restore names the printout cut off; everything else stays exactly as listed."""
    if not info:
        return track
    title, artist, album = track.title, track.artist, track.album
    if track.title_truncated and prefix_match(track.title, info.title) and len(info.title) > len(title):
        title = info.title
    if track.artist_truncated and prefix_match(track.artist, info.artist) and len(info.artist) > len(artist):
        artist = info.artist
    if track.album_truncated and prefix_match(track.album, info.album) and len(info.album) > len(album):
        album = info.album
    return Track(
        number=track.number, title=title, artist=artist, album=album, duration=track.duration,
        title_truncated=track.title_truncated and title == track.title,
        artist_truncated=track.artist_truncated and artist == track.artist,
        album_truncated=track.album_truncated and album == track.album,
    )


def album_matches(track: Track, info: CatalogInfo) -> bool:
    """Whether the catalog entry is from the same release as the listed album."""
    if not track.album or not info.album:
        return False
    return (normalize(track.album) == normalize(info.album)
            or prefix_match(track.album, info.album)
            or similarity(track.album, info.album) >= 0.85)


def fetch_artwork(url: str) -> Optional[bytes]:
    if not url:
        return None
    try:
        resp = _session.get(url, timeout=30)
        if resp.ok and len(resp.content) > 1000:
            return resp.content
    except requests.RequestException as exc:
        logger.debug("Artwork download failed: %s", exc)
    return None


def fetch_lyrics(title: str, artist: str, album: str = "", duration: Optional[int] = None) -> Optional[str]:
    """Plain (unsynced) lyrics from LRCLIB."""
    primary = split_artists(artist)[0] if artist else ""
    attempts = []
    if duration:
        attempts.append(("https://lrclib.net/api/get",
                         {"track_name": title, "artist_name": artist, "album_name": album, "duration": duration}))
        if primary != artist:
            attempts.append(("https://lrclib.net/api/get",
                             {"track_name": title, "artist_name": primary, "album_name": album, "duration": duration}))
    attempts.append(("https://lrclib.net/api/search", {"track_name": base_title(title), "artist_name": primary}))

    for url, params in attempts:
        data = _get_json(url, params, host_key="lrclib", min_interval=0.2, retries=2)
        if isinstance(data, list):
            for item in data:
                if item.get("instrumental"):
                    continue
                if duration and item.get("duration") and abs(item["duration"] - duration) > 10:
                    continue
                if similarity(base_title(title), base_title(item.get("trackName", ""))) < 0.8:
                    continue
                if item.get("plainLyrics"):
                    return item["plainLyrics"].strip()
        elif isinstance(data, dict) and data.get("plainLyrics"):
            return data["plainLyrics"].strip()
    return None
