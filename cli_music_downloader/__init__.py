"""
CLI Music Downloader - A powerful command-line music downloader with automatic metadata and album artwork.

This package provides high-quality music downloads from YouTube with intelligent organization,
automatic album artwork, lyrics, and comprehensive metadata enhancement from multiple sources.
"""

__version__ = "1.0.0"
__author__ = "Jordan Lang"
__email__ = "jordolang@example.com"
__license__ = "MIT"
__description__ = "A powerful command-line music downloader with automatic album artwork and intelligent organization"

# Core functionality imports
from .download_music import EnhancedMusicDownloader, MusicBrainzMetadata
from .batch_metadata import BatchMetadataProcessor
from .lyrics_metadata import LyricsMetadataHandler

__all__ = [
    "EnhancedMusicDownloader",
    "MusicBrainzMetadata", 
    "BatchMetadataProcessor",
    "LyricsMetadataHandler",
    "__version__",
    "__author__",
    "__email__",
    "__license__",
    "__description__"
]
