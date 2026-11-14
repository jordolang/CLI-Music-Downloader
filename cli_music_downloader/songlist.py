"""
Song list parsing.

Reads a song list exported from Apple Music / iTunes ("File > Print" saved as PDF,
with Title / Time / Album / Artist columns) and returns one Track per row, in order.

PDF rows are rebuilt character-by-character from their x positions rather than from
text spans, because the PDF sometimes merges the Album and Artist columns into one
span. Values that run up to a column's right edge were cut off by the printout; they
are flagged as truncated so the catalog lookup can restore the full name.

Plain-text lists ("Artist - Title" per line) and CSV files (title/artist/album/time
columns) are supported as well.
"""

import csv
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# A value whose right edge lands this close to the widest value in its column
# is treated as possibly cut off by the printout.
TRUNCATION_TOLERANCE = 10.0

HEADER_LABELS = ("Title", "Time", "Album", "Artist")


@dataclass
class Track:
    """One row of the song list, exactly as listed."""

    number: int
    title: str
    artist: str
    album: str = ""
    duration: Optional[int] = None  # seconds
    title_truncated: bool = False
    artist_truncated: bool = False
    album_truncated: bool = False

    def to_dict(self) -> Dict:
        return asdict(self)

    def __str__(self) -> str:
        return f"{self.artist or 'Unknown Artist'} - {self.title}"


def parse_duration(text: str) -> Optional[int]:
    """Convert "3:45" or "1:02:03" to seconds."""
    text = (text or "").strip()
    if not re.fullmatch(r"\d+(:\d{1,2}){1,2}", text):
        return None
    seconds = 0
    for part in text.split(":"):
        seconds = seconds * 60 + int(part)
    return seconds


def load_song_list(path) -> List[Track]:
    """Load a song list from a PDF, CSV or text file."""
    path = Path(path).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"Song list not found: {path}")
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return parse_pdf(path)
    if suffix == ".csv":
        return parse_csv(path)
    return parse_text(path)


# --------------------------------------------------------------------------- PDF


def _column_bounds(header: Dict[str, float]) -> List[Tuple[str, float]]:
    """Left boundaries of each column, derived from the header label positions."""
    # Times are right-aligned under the "Time" label, so they start slightly left of it.
    return [
        ("number", float("-inf")),
        ("title", header["Title"] - 2),
        ("time", header["Time"] - 8),
        ("album", header["Album"] - 2),
        ("artist", header["Artist"] - 2),
    ]


def _column_for(x_center: float, bounds: List[Tuple[str, float]]) -> str:
    name = bounds[0][0]
    for col, left in bounds:
        if x_center >= left:
            name = col
    return name


def parse_pdf(path) -> List[Track]:
    """Parse an Apple Music / iTunes printed playlist PDF."""
    try:
        import pymupdf
    except ImportError:  # older PyMuPDF releases only ship the "fitz" name
        import fitz as pymupdf

    rows = []  # (cells, right_edges)
    header: Optional[Dict[str, float]] = None

    with pymupdf.open(str(path)) as doc:
        for page in doc:
            raw = page.get_text("rawdict")
            # Group characters into visual rows by their vertical position.
            lines: Dict[int, List[Tuple[float, float, str]]] = {}
            for block in raw.get("blocks", []):
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        for ch in span.get("chars", []):
                            x0, y0, x1, y1 = ch["bbox"]
                            key = round((y0 + y1) / 2)
                            lines.setdefault(key, []).append((x0, x1, ch["c"]))

            for key in sorted(lines):
                chars = sorted(lines[key])
                text = "".join(c for _, _, c in chars)

                # Header row: remember where each column starts on this page.
                found = {}
                for label in HEADER_LABELS:
                    idx = text.find(label)
                    if idx >= 0:
                        found[label] = chars[idx][0]
                if len(found) >= 3 and "Title" in found:
                    header = {**(header or {}), **found}
                    continue
                if not header or len(header) < 4:
                    continue

                bounds = _column_bounds(header)
                cells: Dict[str, List[Tuple[float, float, str]]] = {}
                for x0, x1, c in chars:
                    cells.setdefault(_column_for((x0 + x1) / 2, bounds), []).append((x0, x1, c))

                number = "".join(c for *_, c in cells.get("number", [])).strip()
                if not number.isdigit():
                    continue  # page titles, footers, etc.

                values = {col: "".join(c for *_, c in cs).strip() for col, cs in cells.items()}
                # Trailing spaces count: a value clipped at a word boundary ends in one.
                edges = {col: max(x1 for _, x1, _ in cs) for col, cs in cells.items() if cs}
                rows.append((int(number), values, edges))

    if not rows:
        raise ValueError(f"No songs found in {path}. Is it a printed Apple Music/iTunes playlist?")

    # Widest rendered value per column = the column's clipping edge.
    widest: Dict[str, float] = {}
    for _, _, edges in rows:
        for col, x1 in edges.items():
            widest[col] = max(widest.get(col, 0.0), x1)

    def truncated(col: str, values: Dict[str, str], edges: Dict[str, float]) -> bool:
        text = values.get(col, "")
        if not text:
            return False
        unbalanced = text.count("(") > text.count(")") or text.count("[") > text.count("]")
        return unbalanced or text[-1] in "&,-" or edges[col] >= widest[col] - TRUNCATION_TOLERANCE

    tracks = []
    for number, values, edges in rows:
        tracks.append(
            Track(
                number=number,
                title=_clean(values.get("title", "")),
                artist=_clean(values.get("artist", "")),
                album=_clean(values.get("album", "")),
                duration=parse_duration(values.get("time", "")),
                title_truncated=truncated("title", values, edges),
                artist_truncated=truncated("artist", values, edges),
                album_truncated=truncated("album", values, edges),
            )
        )
    return tracks


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


# ---------------------------------------------------------------------- CSV / text


def parse_csv(path) -> List[Track]:
    """CSV with a header containing at least title and artist (album/time optional)."""
    tracks = []
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        fields = {name.lower().strip(): name for name in (reader.fieldnames or [])}

        def pick(row, *names):
            for n in names:
                if n in fields and row.get(fields[n]):
                    return row[fields[n]].strip()
            return ""

        for i, row in enumerate(reader, 1):
            title = pick(row, "title", "name", "track", "song")
            if not title:
                continue
            tracks.append(
                Track(
                    number=i,
                    title=title,
                    artist=pick(row, "artist", "artists"),
                    album=pick(row, "album"),
                    duration=parse_duration(pick(row, "time", "duration", "length")),
                )
            )
    return tracks


def parse_text(path) -> List[Track]:
    """One song per line as "Artist - Title". Blank lines and # comments are ignored."""
    tracks = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            artist, sep, title = line.partition(" - ")
            if not sep:
                artist, title = "", line
            tracks.append(Track(number=len(tracks) + 1, title=title.strip(), artist=artist.strip()))
    return tracks


def select_tracks(tracks: List[Track], spec: Optional[str]) -> List[Track]:
    """Filter tracks by list number, e.g. "1-20,45,300-303"."""
    if not spec:
        return tracks
    wanted = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            lo, hi = part.split("-", 1)
            wanted.update(range(int(lo), int(hi) + 1))
        else:
            wanted.add(int(part))
    return [t for t in tracks if t.number in wanted]
