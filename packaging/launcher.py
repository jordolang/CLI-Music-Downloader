"""
Entry point of the packaged desktop app (PyInstaller).

With no arguments it opens the desktop music app; with arguments it runs the command
line tool, e.g. `CLI Music --help` or `cli-music-downloader songlist Music.pdf`.
"""

import os
import sys


def _use_bundled_tools() -> None:
    """Put the bundled ffmpeg/ffprobe/ffplay/deno first on PATH."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    tools = os.path.join(base, "tools")
    if os.path.isdir(tools):
        os.environ["PATH"] = tools + os.pathsep + os.environ.get("PATH", "")


def main() -> None:
    _use_bundled_tools()
    from cli_music_downloader import cli

    args = sys.argv[1:]
    # macOS passes -psn_* when an app is opened from Finder on older systems.
    args = [a for a in args if not a.startswith("-psn_")]
    if not args:
        cli.run_gui([])
        return
    sys.exit(cli.main(args) or 0)


if __name__ == "__main__":
    import multiprocessing

    multiprocessing.freeze_support()
    main()
