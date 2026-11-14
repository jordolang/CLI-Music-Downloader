#!/usr/bin/env python3
"""
Download a single song into <output>/<Artist>/<Title>.mp3 with metadata, artwork and lyrics.

Uses the same search, matching and tagging pipeline as the song-list downloader.
"""

import argparse
import logging
import re
import sys
from typing import Tuple

from .library import LibraryDownloader, summarize
from .songlist import Track, parse_duration
from .sources import DEFAULT_SOURCES

DEFAULT_OUTPUT = "~/Music"


def parse_search_term(search_term: str) -> Tuple[str, str]:
    """Split "Artist - Title" or "Title by Artist" into (artist, title)."""
    term = search_term.strip()
    m = re.match(r"^(.+?)\s+-\s+(.+)$", term)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    m = re.match(r"^(.+?)\s+by\s+(.+)$", term, re.I)
    if m:
        return m.group(2).strip(), m.group(1).strip()
    return "", term


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="download-music",
        description="Download one song as <Artist>/<Title>.mp3 with metadata, artwork and lyrics",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  download-music "Evanescence - Bring Me to Life"
  download-music "Bring Me to Life by Evanescence"
  download-music --artist "Creed" --title "One Last Breath" --duration 3:58
""",
    )
    parser.add_argument("search_term", nargs="?", default="", help='"Artist - Title"')
    parser.add_argument("--artist", help="Artist name (overrides parsing)")
    parser.add_argument("--title", help="Song title (overrides parsing)")
    parser.add_argument("--album", default="", help="Album name (helps pick the right release)")
    parser.add_argument("--duration", help="Song length, e.g. 3:58 (helps pick the right version)")
    add_common_options(parser)
    return parser


def add_common_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("-o", "--output", default=DEFAULT_OUTPUT, help=f"Output folder (default: {DEFAULT_OUTPUT})")
    parser.add_argument("--sources", default=",".join(DEFAULT_SOURCES),
                        help=f"Comma-separated source order (default: {','.join(DEFAULT_SOURCES)})")
    parser.add_argument("--no-lyrics", action="store_true", help="Do not embed lyrics")
    parser.add_argument("--overwrite", action="store_true", help="Re-download files that already exist")
    parser.add_argument("--quality", default="0",
                        help="MP3 quality: VBR 0 (best) - 9, or a bitrate like 320 (default: 0)")
    parser.add_argument("--cookies-from-browser", metavar="BROWSER",
                        help="Use YouTube cookies from a browser (chrome, safari, firefox...) if YouTube blocks requests")
    parser.add_argument("--cookies", metavar="FILE", help="Netscape cookies.txt file for YouTube")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")


def configure_logging(verbose: bool) -> None:
    logging.basicConfig(level=logging.DEBUG if verbose else logging.WARNING,
                        format="%(levelname)s %(name)s: %(message)s")
    if not verbose:
        logging.getLogger("urllib3").setLevel(logging.ERROR)


def make_downloader(args, **kwargs) -> LibraryDownloader:
    return LibraryDownloader(
        args.output,
        sources=[s.strip() for s in args.sources.split(",") if s.strip()],
        overwrite=args.overwrite,
        lyrics=not args.no_lyrics,
        cookies_from_browser=args.cookies_from_browser,
        cookies_file=args.cookies,
        audio_quality=str(args.quality),
        **kwargs,
    )


def download_music_ui(search_term: str, progress_callback=None, output: str = DEFAULT_OUTPUT) -> Tuple[bool, str]:
    """Download one song for the TUI. Returns (success, message)."""
    from .library import LibraryDownloader

    artist, title = parse_search_term(search_term)
    if not title:
        return False, "❌ Enter a song as \"Artist - Title\""
    if progress_callback:
        progress_callback(f"🔍 Searching for {artist + ' - ' if artist else ''}{title}...")
    try:
        result = LibraryDownloader(output, workers=1, on_result=lambda *a: None).run(
            [Track(number=1, title=title, artist=artist)])[0]
    except Exception as exc:
        return False, f"💥 {exc}"
    if result.status in ("downloaded", "exists"):
        return True, f"🎉 Saved to {result.path}"
    return False, f"❌ {result.message}"


def get_download_help() -> str:
    return (
        "Enter a song as \"Artist - Title\" (or \"Title by Artist\").\n"
        "It is saved as ~/Music/<Artist>/<Title>.mp3 with metadata, album artwork and lyrics.\n"
        "Sources tried: YouTube Music, YouTube, SoundCloud, Audius."
    )


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    configure_logging(args.verbose)

    artist, title = parse_search_term(args.search_term) if args.search_term else ("", "")
    artist = args.artist or artist
    title = args.title or title
    if not title:
        print("❌ Give a song as \"Artist - Title\" or use --artist/--title", file=sys.stderr)
        return 2

    track = Track(number=1, title=title, artist=artist, album=args.album,
                  duration=parse_duration(args.duration) if args.duration else None)
    results = make_downloader(args, workers=1).run([track])
    r = results[0]
    if r.status in ("downloaded", "exists"):
        print(f"📂 {r.path}")
    return 1 if summarize(results) else 0


if __name__ == "__main__":
    sys.exit(main())
