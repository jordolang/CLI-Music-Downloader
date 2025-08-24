#!/usr/bin/env python3
"""
Enhanced CLI Music Downloader with Integrated Metadata
Downloads music and applies comprehensive metadata using multiple sources
"""

import os
import sys
import logging
import argparse
import asyncio
import subprocess
import tempfile
from typing import Optional, Dict, Any, List
from pathlib import Path

# Import metadata handler from package
try:
    from .lyrics_metadata import LyricsMetadataHandler, process_audio_file
except ImportError as e:
    print(f"Error importing lyrics_metadata: {e}")
    print("Please ensure all dependencies are installed: pip install -r requirements.txt")
    sys.exit(1)

# Additional imports for MusicBrainz
try:
    import musicbrainzngs
except ImportError:
    print("musicbrainzngs not found. Install with: pip install musicbrainzngs")
    musicbrainzngs = None

try:
    import requests
except ImportError:
    print("requests not found. Install with: pip install requests")
    requests = None

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Configure MusicBrainz
if musicbrainzngs:
    musicbrainzngs.set_useragent(
        "CLI-Music-Downloader",
        "1.0",
        "https://github.com/yourusername/CLI-Music-Downloader"
    )

class MusicBrainzMetadata:
    """Handler for MusicBrainz metadata lookup"""
    
    def __init__(self):
        self.available = musicbrainzngs is not None
        if not self.available:
            logger.warning("MusicBrainz not available - install musicbrainzngs")
    
    def search_recording(self, artist: str, title: str, limit: int = 10) -> Optional[Dict[str, Any]]:
        """Search for recording metadata in MusicBrainz"""
        if not self.available:
            return None
        
        try:
            logger.info(f"Searching MusicBrainz for: {artist} - {title}")
            
            # Search for recordings
            result = musicbrainzngs.search_recordings(
                artist=artist,
                recording=title,
                limit=limit
            )
            
            if result and 'recording-list' in result and result['recording-list']:
                # Get the best match (first result)
                recording = result['recording-list'][0]
                
                metadata = {
                    'title': recording.get('title', ''),
                    'artist': '',
                    'album': '',
                    'album_artist': '',
                    'year': '',
                    'genre': '',
                    'track_number': '',
                    'total_tracks': '',
                    'disc_number': '',
                    'total_discs': '',
                    'composer': '',
                    'musicbrainz_recording_id': recording.get('id', ''),
                    'musicbrainz_artist_id': '',
                    'musicbrainz_album_id': ''
                }
                
                # Extract artist information
                if 'artist-credit' in recording and recording['artist-credit']:
                    artists = []
                    for credit in recording['artist-credit']:
                        if isinstance(credit, dict) and 'artist' in credit:
                            artist_name = credit['artist'].get('name', '')
                            artists.append(artist_name)
                            if not metadata['musicbrainz_artist_id']:
                                metadata['musicbrainz_artist_id'] = credit['artist'].get('id', '')
                    metadata['artist'] = ', '.join(artists)
                    metadata['album_artist'] = metadata['artist']
                
                # Extract release information
                if 'release-list' in recording and recording['release-list']:
                    release = recording['release-list'][0]
                    metadata['album'] = release.get('title', '')
                    metadata['musicbrainz_album_id'] = release.get('id', '')
                    
                    # Get release date
                    if 'date' in release:
                        metadata['year'] = release['date'][:4]  # Extract year
                    
                    # Get track number if available
                    if 'medium-list' in release and release['medium-list']:
                        medium = release['medium-list'][0]
                        if 'track-list' in medium and medium['track-list']:
                            for i, track in enumerate(medium['track-list']):
                                if ('recording' in track and 
                                    track['recording'].get('id') == recording.get('id')):
                                    metadata['track_number'] = str(i + 1)
                                    metadata['total_tracks'] = str(len(medium['track-list']))
                                    break
                
                # Try to get more detailed release info
                try:
                    if metadata['musicbrainz_album_id']:
                        release_detail = musicbrainzngs.get_release_by_id(
                            metadata['musicbrainz_album_id'],
                            includes=['artist-credits', 'release-groups']
                        )
                        
                        if 'release' in release_detail:
                            release_info = release_detail['release']
                            
                            # Get release group info for genre
                            if 'release-group' in release_info:
                                rg = release_info['release-group']
                                if 'tag-list' in rg and rg['tag-list']:
                                    # Use the most popular tag as genre
                                    tags = sorted(rg['tag-list'], 
                                                 key=lambda x: int(x.get('count', 0)), 
                                                 reverse=True)
                                    if tags:
                                        metadata['genre'] = tags[0].get('name', '')
                
                except Exception as e:
                    logger.warning(f"Error getting detailed release info: {e}")
                
                logger.info(f"Found MusicBrainz metadata: {metadata['artist']} - {metadata['title']}")
                return metadata
            
            else:
                logger.warning(f"No MusicBrainz results for: {artist} - {title}")
        
        except Exception as e:
            logger.error(f"MusicBrainz search error: {e}")
        
        return None

class EnhancedMusicDownloader:
    """Enhanced music downloader with integrated metadata"""
    
    def __init__(self, options):
        self.options = options
        self.music_dir = Path.home() / "Music"
        self.music_dir.mkdir(exist_ok=True)
        
        # Initialize metadata sources
        self.musicbrainz = MusicBrainzMetadata()
        self.lyrics_handler = LyricsMetadataHandler(options.genius_key)
    
    def download_audio(self, search_term: str) -> List[Path]:
        """Download audio using instantmusic"""
        logger.info(f"🎵 Downloading audio for: {search_term}")
        
        # Get list of files before download
        before_files = set()
        if self.music_dir.exists():
            for file in self.music_dir.rglob("*.mp3"):
                before_files.add(file)
        
        try:
            # Run instantmusic
            cmd = ["instantmusic", "-q", "-s", search_term]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            logger.info("Audio download completed")
        
        except subprocess.CalledProcessError as e:
            logger.error(f"Download failed: {e}")
            logger.error(f"Command output: {e.stderr}")
            return []
        
        # Find new files
        after_files = set()
        if self.music_dir.exists():
            for file in self.music_dir.rglob("*.mp3"):
                after_files.add(file)
        
        new_files = list(after_files - before_files)
        logger.info(f"Found {len(new_files)} new file(s)")
        
        return new_files
    
    def enhance_metadata(self, file_path: Path, artist_hint: str = "", title_hint: str = "") -> bool:
        """Enhanced metadata processing with multiple sources"""
        logger.info(f"🎯 Enhancing metadata for: {file_path.name}")
        
        # Start with basic metadata
        metadata = {
            'artist': artist_hint,
            'title': title_hint,
            'album': '',
            'album_artist': artist_hint,
            'composer': '',
            'grouping': '',
            'genre': '',
            'year': '',
            'track_number': '',
            'total_tracks': '',
            'disc_number': '',
            'total_discs': '',
            'compilation': False,
            'comments': 'Downloaded with CLI Music Downloader (Enhanced)'
        }
        
        # Extract from filename if no hints provided
        if not artist_hint or not title_hint:
            filename_meta = self.lyrics_handler.extract_metadata_from_filename(str(file_path))
            metadata['artist'] = metadata['artist'] or filename_meta.get('artist', '')
            metadata['title'] = metadata['title'] or filename_meta.get('title', '')
            metadata['album_artist'] = metadata['artist']
        
        # MusicBrainz lookup (if not skipped and source is musicbrainz)
        if (not self.options.skip_metadata and 
            self.options.metadata_source in ['musicbrainz', 'all'] and 
            metadata['artist'] and metadata['title']):
            
            logger.info("🎼 Querying MusicBrainz...")
            mb_metadata = self.musicbrainz.search_recording(metadata['artist'], metadata['title'])
            
            if mb_metadata:
                # Update metadata with MusicBrainz data
                for key, value in mb_metadata.items():
                    if value and (self.options.force_metadata or not metadata.get(key)):
                        metadata[key] = value
                logger.info("✅ MusicBrainz metadata applied")
            else:
                logger.warning("⚠️ No MusicBrainz metadata found")
        
        # Audio fingerprinting (if enabled)
        if (not self.options.skip_metadata and 
            self.options.metadata_source in ['shazam', 'all']):
            try:
                logger.info("🎧 Attempting audio identification...")
                identified_meta = asyncio.run(
                    self.lyrics_handler.identify_song(str(file_path))
                )
                if identified_meta:
                    for key, value in identified_meta.items():
                        if value and (self.options.force_metadata or not metadata.get(key)):
                            metadata[key] = value
                    logger.info("✅ Audio identification metadata applied")
            except Exception as e:
                logger.warning(f"Audio identification failed: {e}")
        
        # Get lyrics (if not skipped)
        lyrics = None
        if (not self.options.skip_metadata and 
            metadata['artist'] and metadata['title']):
            logger.info("📝 Fetching lyrics...")
            lyrics = self.lyrics_handler.get_lyrics(metadata['artist'], metadata['title'])
            if lyrics:
                logger.info("✅ Lyrics found")
            else:
                logger.warning("⚠️ No lyrics found")
        
        # Apply metadata to file
        logger.info("💾 Applying metadata to file...")
        success = self.lyrics_handler.update_metadata(str(file_path), metadata, lyrics)
        
        if success:
            logger.info(f"✅ Metadata enhancement completed for: {file_path.name}")
        else:
            logger.error(f"❌ Metadata enhancement failed for: {file_path.name}")
        
        return success
    
    def download_and_process(self, search_term: str, artist_hint: str = "", title_hint: str = "") -> bool:
        """Main download and processing pipeline"""
        logger.info(f"🚀 Starting download and processing for: {search_term}")
        
        # Step 1: Download audio
        new_files = self.download_audio(search_term)
        
        if not new_files:
            logger.error("No files downloaded")
            return False
        
        # Step 2: Process each file
        success_count = 0
        for file_path in new_files:
            logger.info(f"\n🎵 Processing: {file_path.name}")
            
            # Add album art (using existing fixalbumart_improved)
            logger.info("🖼️ Adding album art...")
            try:
                if artist_hint and title_hint:
                    subprocess.run(["fixalbumart_improved", str(file_path), artist_hint, title_hint], 
                                 check=False)  # Don't fail if album art fails
                else:
                    subprocess.run(["fixalbumart_improved", str(file_path)], 
                                 check=False)  # Don't fail if album art fails
                logger.info("✅ Album art processing completed")
            except Exception as e:
                logger.warning(f"Album art processing failed: {e}")
            
            # Enhance metadata
            if self.enhance_metadata(file_path, artist_hint, title_hint):
                success_count += 1
        
        logger.info(f"\n🎉 Processing completed! {success_count}/{len(new_files)} files processed successfully")
        return success_count > 0

def parse_search_term(search_term: str) -> tuple[str, str]:
    """Parse search term to extract artist and title hints"""
    # Try to split on common patterns
    import re
    
    patterns = [
        r'^(.+?)\s*-\s*(.+)$',  # Artist - Title
        r'^(.+?)\s+by\s+(.+)$',  # Title by Artist
        r'^([^\s]+)\s+(.+)$',   # First word as artist, rest as title
    ]
    
    for pattern in patterns:
        match = re.match(pattern, search_term.strip())
        if match:
            if pattern == r'^(.+?)\s+by\s+(.+)$':
                # "Title by Artist" format
                return match.group(2).strip(), match.group(1).strip()
            else:
                # "Artist - Title" or "Artist Title" format
                return match.group(1).strip(), match.group(2).strip()
    
    return "", ""

def main():
    parser = argparse.ArgumentParser(
        description='Enhanced CLI Music Downloader with Integrated Metadata',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  download_music.py "The Beatles Hey Jude"
  download_music.py "Pink Floyd - Comfortably Numb" --metadata-source musicbrainz
  download_music.py "Queen Bohemian Rhapsody" --force-metadata
  download_music.py "Adele Hello" --skip-metadata
  download_music.py "Artist - Song" --artist "Artist" --title "Song"
        '''
    )
    
    parser.add_argument('search_term', help='Search term for the music (e.g., "Artist - Song")')
    parser.add_argument('--artist', help='Artist name hint (overrides parsing)')
    parser.add_argument('--title', help='Song title hint (overrides parsing)')
    
    # Metadata control flags
    parser.add_argument('--skip-metadata', action='store_true',
                       help='Skip metadata enhancement phase')
    parser.add_argument('--force-metadata', action='store_true',
                       help='Force metadata refresh even if tags exist')
    parser.add_argument('--metadata-source', 
                       choices=['musicbrainz', 'shazam', 'all'], 
                       default='all',
                       help='Choose metadata source (default: all)')
    
    # API keys
    parser.add_argument('--genius-key', 
                       help='Genius API key for lyrics (or set GENIUS_API_KEY env var)')
    
    # Logging
    parser.add_argument('-v', '--verbose', action='store_true',
                       help='Enable verbose logging')
    parser.add_argument('-q', '--quiet', action='store_true',
                       help='Quiet mode (errors only)')
    
    args = parser.parse_args()
    
    # Configure logging level
    if args.quiet:
        logging.getLogger().setLevel(logging.ERROR)
    elif args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Get API keys from environment if not provided
    genius_key = args.genius_key or os.getenv('GENIUS_API_KEY')
    args.genius_key = genius_key
    
    # Parse search term for artist/title hints if not explicitly provided
    if not args.artist or not args.title:
        parsed_artist, parsed_title = parse_search_term(args.search_term)
        args.artist = args.artist or parsed_artist
        args.title = args.title or parsed_title
    
    if args.artist and args.title:
        logger.info(f"🎯 Parsed: Artist='{args.artist}', Title='{args.title}'")
    
    # Create downloader and process
    try:
        downloader = EnhancedMusicDownloader(args)
        success = downloader.download_and_process(
            args.search_term,
            args.artist or "",
            args.title or ""
        )
        
        if success:
            logger.info("\n🎉 Download and processing completed successfully!")
            logger.info(f"📂 Check ~/Music for your organized music collection")
            sys.exit(0)
        else:
            logger.error("\n❌ Download or processing failed")
            sys.exit(1)
    
    except KeyboardInterrupt:
        logger.info("\n⚠️ Process interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"\n💥 Unexpected error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()

