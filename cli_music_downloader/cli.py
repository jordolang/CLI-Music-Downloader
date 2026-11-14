#!/usr/bin/env python3
"""
CLI Music Downloader - command-line entry points.

  cli-music-downloader list      Music.pdf            Show the parsed song list
  cli-music-downloader songlist  Music.pdf -o DIR     Download every song in a list
  cli-music-downloader download  "Artist - Title"     Download one song
  cli-music-downloader suggest   [-o ~/Music]         Suggest songs for your library (TUI with previews)
  cli-music-downloader gui       [--library ~/Music]  Desktop music app: library, player, search, previews, downloads
  cli-music-downloader verify    DIR                  Check tags/artwork of downloaded files
  cli-music-downloader batch ...                      Legacy metadata batch processor
  cli-music-downloader fix-art ...                    Legacy album-art fixer
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

from . import __version__
from .download_music import DEFAULT_OUTPUT, add_common_options, configure_logging, make_downloader
from .download_music import main as download_music_main


def _songlist_parser(prog: str = "download-songlist") -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Download every song in a song list (Apple Music PDF printout, CSV, or text) "
                    "into <output>/<Artist>/<Title>.mp3 with metadata, artwork and lyrics.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  download-songlist Music.pdf
  download-songlist Music.pdf -o ~/Music/Library --workers 4
  download-songlist Music.pdf --only 1-25,40
  download-songlist Music.pdf --dry-run          # show what would be downloaded

Re-running is safe: files that already exist are skipped, so an interrupted run resumes.
A report (download_report.json / .csv) is written to the output folder.
""",
    )
    parser.add_argument("songlist", help="Song list file (.pdf, .csv or .txt)")
    parser.add_argument("--only", metavar="NUMBERS", help='Only these list numbers, e.g. "1-20,45"')
    parser.add_argument("-w", "--workers", type=int, default=2,
                        help="Parallel downloads (default: 2; more makes YouTube throttle sooner)")
    parser.add_argument("--retries", type=int, default=1, help="Extra passes over failed songs (default: 1)")
    parser.add_argument("--retry-wait", type=int, default=120, help="Seconds to wait before a retry pass")
    parser.add_argument("--dry-run", action="store_true", help="Resolve names and paths without downloading")
    add_common_options(parser)
    return parser


def run_songlist(argv=None, prog: str = "download-songlist") -> int:
    from .library import summarize
    from .songlist import load_song_list, select_tracks

    args = _songlist_parser(prog).parse_args(argv)
    configure_logging(args.verbose)
    tracks = select_tracks(load_song_list(args.songlist), args.only)
    if not tracks:
        print("❌ No songs selected", file=sys.stderr)
        return 2
    out = Path(args.output).expanduser()
    print(f"🎵 {len(tracks)} songs from {args.songlist} → {out}/<Artist>/<Title>.mp3\n", flush=True)
    downloader = make_downloader(args, workers=args.workers, dry_run=args.dry_run,
                                 retry_passes=args.retries, retry_wait=args.retry_wait)
    try:
        results = downloader.run(tracks)
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted — run the same command again to resume.", file=sys.stderr)
        return 130
    failures = summarize(results)
    if downloader.finder and downloader.finder.age_restricted and not (args.cookies_from_browser or args.cookies):
        print(f"\nℹ️  YouTube asked for sign-in on {downloader.finder.age_restricted} result(s) (age-restricted/explicit)."
              "\n   Re-run with --cookies-from-browser chrome (or safari/firefox) to use those official uploads.")
    if downloader.finder and downloader.finder.throttled:
        print("\nℹ️  YouTube rate-limited some requests. Wait a while and run the same command again —"
              "\n   finished songs are skipped. --cookies-from-browser chrome also reduces throttling.")
    if not args.dry_run:
        print(f"\n📄 Report: {out / 'download_report.csv'}")
    return 1 if failures else 0


def run_list(argv=None) -> int:
    from .songlist import load_song_list, select_tracks

    parser = argparse.ArgumentParser(prog="cli-music-downloader list", description="Show a parsed song list")
    parser.add_argument("songlist")
    parser.add_argument("--only", metavar="NUMBERS")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args(argv)
    tracks = select_tracks(load_song_list(args.songlist), args.only)
    if args.json:
        print(json.dumps([t.to_dict() for t in tracks], indent=2, ensure_ascii=False))
        return 0
    for t in tracks:
        dur = f"{t.duration // 60}:{t.duration % 60:02d}" if t.duration else ""
        cut = "*" if (t.title_truncated or t.artist_truncated or t.album_truncated) else " "
        print(f"{t.number:>4}{cut} {t.title:<45.45} {dur:>6}  {t.album:<38.38}  {t.artist}")
    print(f"\n{len(tracks)} songs  (* = name cut off in the printout; completed from the catalog when downloading)")
    return 0


def run_verify(argv=None) -> int:
    from .tagger import read_summary

    parser = argparse.ArgumentParser(prog="cli-music-downloader verify",
                                     description="Check that downloaded MP3s have title/artist/album tags and artwork")
    parser.add_argument("folder", nargs="?", default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    files = sorted(Path(args.folder).expanduser().rglob("*.mp3"))
    problems = 0
    for f in files:
        try:
            s = read_summary(f)
        except Exception as exc:
            print(f"❌ {f}: unreadable tags ({exc})")
            problems += 1
            continue
        missing = [k for k in ("title", "artist", "album") if not s[k]]
        if not s["has_artwork"]:
            missing.append("artwork")
        if missing:
            problems += 1
            print(f"⚠️  {f.relative_to(Path(args.folder).expanduser())}: missing {', '.join(missing)}")
    print(f"\n{len(files)} files checked, {problems} with problems")
    return 1 if problems else 0


def _suggest_parser(prog: str = "music-suggester") -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Read the MP3s in your library, suggest 25-50 songs you are likely to enjoy, "
                    "preview the first 30 seconds of each, and download them into the library "
                    "as <Artist>/<Title>.mp3 with metadata, artwork and lyrics.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Keys in the suggester:
  p / Enter  preview 30s     s  stop          d  download song     a  download all
  Space      mark            D  download marked                     x  not for me
  r          new picks       q  quit

Examples:
  music-suggester                      # library and downloads: ~/Music
  music-suggester -o ~/Music/Library -n 50
  music-suggester --print              # list suggestions without the TUI
  music-suggester --download-all       # download every suggestion without the TUI
""",
    )
    parser.add_argument("-n", "--count", type=int, default=40, help="How many songs to suggest, 25-50 (default: 40)")
    parser.add_argument("--seeds", type=int, default=20,
                        help="How many of your most-played artists to base suggestions on (default: 20)")
    parser.add_argument("--print", dest="print_only", action="store_true", help="Print the suggestions and exit")
    parser.add_argument("--json", action="store_true", help="Print the suggestions as JSON and exit")
    parser.add_argument("--download-all", action="store_true", help="Download every suggestion without the TUI")
    parser.add_argument("--no-cache", action="store_true", help="Ignore cached Deezer lookups")
    add_common_options(parser)
    for action in parser._actions:  # in the suggester, -o is both the library and the download folder
        if action.dest == "output":
            action.help = f"Music library to read and download into (default: {DEFAULT_OUTPUT})"
    return parser


def run_suggest(argv=None, prog: str = "music-suggester") -> int:
    import logging

    from .recommend import Recommender, SuggesterState, cache_dir, scan_library

    args = _suggest_parser(prog).parse_args(argv)
    library = Path(args.output).expanduser()
    if not library.is_dir():
        print(f"❌ Library folder not found: {library}", file=sys.stderr)
        return 2

    def downloader():
        return make_downloader(args, workers=1, retry_passes=0, report=False)

    if not (args.print_only or args.json or args.download_all):
        if not sys.stdout.isatty():
            print("❌ The suggester needs a terminal; use --print or --json to list suggestions.", file=sys.stderr)
            return 2
        if args.verbose:  # log to a file: writing to the terminal would garble the TUI
            cache_dir().mkdir(parents=True, exist_ok=True)
            logging.basicConfig(filename=cache_dir() / "suggester.log", level=logging.DEBUG,
                                format="%(asctime)s %(levelname)s %(name)s: %(message)s")
        from .suggest_tui import run_tui

        return run_tui(library, count=args.count, seeds=args.seeds, use_cache=not args.no_cache,
                       downloader_factory=downloader)

    configure_logging(args.verbose)

    def progress(message, done, total):
        print(f"\r{message}: {done}/{total}   ", end="", file=sys.stderr, flush=True)

    profile = scan_library(library, progress)
    print(f"\r🎵 {len(profile.songs)} songs by {profile.artist_count} artists in {library}" + " " * 20,
          file=sys.stderr)
    picks = Recommender(profile, seeds=args.seeds, dismissed=SuggesterState().dismissed,
                        use_cache=not args.no_cache).recommend(args.count, progress=progress)
    print("\r" + " " * 70 + "\r", end="", file=sys.stderr)
    if not picks:
        print("❌ No suggestions found (no internet connection, or an empty library?)", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps([s.to_dict() for s in picks], indent=2, ensure_ascii=False))
        return 0
    for i, s in enumerate(picks, 1):
        print(f"{i:>3}. {s.artist[:24]:<24} {s.title[:40]:<40} {s.length:>5}  {s.reason}")
    if not args.download_all:
        return 0

    from .library import summarize

    print(f"\n⬇  Downloading {len(picks)} songs into {library}/<Artist>/<Title>.mp3\n", flush=True)
    results = downloader().run([s.to_track(i) for i, s in enumerate(picks, 1)])
    return 1 if summarize(results) else 0


def _legacy_batch(argv) -> int:
    import asyncio

    from .batch_metadata import main as batch_metadata_main

    sys.argv = ["batch-metadata", *argv]
    asyncio.run(batch_metadata_main())
    return 0


def _legacy_fixart(argv) -> int:
    script = Path(__file__).resolve().parent.parent / "bin" / "fixalbumart_improved"
    if not script.exists():
        print("❌ bin/fixalbumart_improved not found", file=sys.stderr)
        return 1
    return subprocess.run([str(script), *argv], check=False).returncode


def run_gui(argv=None, prog: str = "music-player") -> int:
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Desktop music app: library browser and player, playlists, tag editing, "
                    "search with song and video previews, and one-click downloads.",
    )
    parser.add_argument("--library", help="Music library folder (default: the saved setting, else ~/Music)")
    parser.add_argument("--port", type=int, default=0, help="Local server port (default: any free port)")
    parser.add_argument("--browser", action="store_true", help="Open in your web browser instead of a native window")
    parser.add_argument("-v", "--verbose", action="store_true", help="Log server activity and enable web inspector")
    args = parser.parse_args(argv)
    from .gui import run_gui as _run

    return _run(library=args.library, port=args.port, browser=args.browser, verbose=args.verbose) or 0


COMMANDS = {
    "gui": lambda argv: run_gui(argv, prog="cli-music-downloader gui"),
    "songlist": lambda argv: run_songlist(argv, prog="cli-music-downloader songlist"),
    "list": run_list,
    "download": download_music_main,
    "suggest": lambda argv: run_suggest(argv, prog="cli-music-downloader suggest"),
    "verify": run_verify,
    "batch": _legacy_batch,
    "fix-art": _legacy_fixart,
}


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__.strip())
        return 0
    if argv[0] == "--version":
        print(f"cli-music-downloader {__version__}")
        return 0
    command, rest = argv[0], argv[1:]
    if command not in COMMANDS:
        # A song-list file as the first argument is a shortcut for "songlist".
        if Path(command).suffix.lower() in (".pdf", ".csv", ".txt") and Path(command).expanduser().exists():
            command, rest = "songlist", argv
        else:
            print(f"Unknown command: {command}\n\n{__doc__.strip()}", file=sys.stderr)
            return 2
    try:
        return COMMANDS[command](rest) or 0
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted", file=sys.stderr)
        return 130


def _exit(code) -> None:
    sys.exit(code or 0)


# Console-script entry points (see pyproject.toml)
def cli_main():
    _exit(main())


def download_music():
    _exit(download_music_main())


def download_songlist():
    _exit(run_songlist())


def music_suggester():
    _exit(run_suggest())


def music_player():
    _exit(run_gui())


def batch_metadata():
    _exit(_legacy_batch(sys.argv[1:]))


def fixalbumart_improved():
    _exit(_legacy_fixart(sys.argv[1:]))


if __name__ == "__main__":
    cli_main()
