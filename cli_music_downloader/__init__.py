"""
CLI Music Downloader - download songs (or a whole Apple Music song list) as
<Artist>/<Title>.mp3 with full metadata, album artwork and lyrics.

Audio comes from YouTube Music, YouTube, SoundCloud or Audius; metadata from the
iTunes Search API and Deezer; lyrics from LRCLIB.
"""

__version__ = "2.1.0"
__author__ = "Jordan Lang"
__license__ = "MIT"
__description__ = "Download music with metadata and album artwork, from a single song or an Apple Music song list"

__all__ = [
    "Track",
    "load_song_list",
    "LibraryDownloader",
    "SourceFinder",
    "__version__",
]


def __getattr__(name):
    # Lazy imports keep `import cli_music_downloader` light and free of optional dependencies.
    if name in ("Track", "load_song_list"):
        from . import songlist
        return getattr(songlist, name)
    if name == "LibraryDownloader":
        from .library import LibraryDownloader
        return LibraryDownloader
    if name == "SourceFinder":
        from .sources import SourceFinder
        return SourceFinder
    raise AttributeError(name)
