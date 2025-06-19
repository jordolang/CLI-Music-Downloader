#!/usr/bin/env python3
"""
Lyrics and Metadata Handler for CLI Music Downloader
Downloads lyrics and applies comprehensive metadata to MP3 files
"""

import os
import sys
import logging
import asyncio
from typing import Optional, Dict, Any
import requests
from pathlib import Path

# Metadata libraries
try:
    import eyed3
    from mutagen.id3 import ID3, TIT2, TPE1, TALB, TPE2, TCOM, TIT1, TCON, TDRC, TRCK, TPOS, TCMP, COMM, USLT
    from mutagen.mp3 import MP3
    from mutagen.id3._util import error as ID3Error
except ImportError as e:
    print(f"Error importing metadata libraries: {e}")
    print("Please install required dependencies: pip install -r requirements.txt")
    sys.exit(1)

# Lyrics library
try:
    import lyricsgenius
except ImportError:
    print("lyricsgenius not found. Install with: pip install lyricsgenius")
    lyricsgenius = None

# Music recognition
try:
    from shazamio import Shazam
except ImportError:
    print("shazamio not found. Install with: pip install shazamio")
    Shazam = None

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

class LyricsMetadataHandler:
    def __init__(self, genius_api_key: Optional[str] = None):
        self.genius_api_key = genius_api_key
        self.genius = None
        
        if genius_api_key and lyricsgenius:
            try:
                self.genius = lyricsgenius.Genius(genius_api_key)
                self.genius.verbose = False
                self.genius.remove_section_headers = True
                logger.info("Genius API initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize Genius API: {e}")
        
        self.shazam = Shazam() if Shazam else None
    
    async def identify_song(self, audio_file: str) -> Optional[Dict[str, Any]]:
        """Use Shazam to identify song metadata"""
        if not self.shazam:
            logger.warning("Shazam not available")
            return None
        
        try:
            logger.info(f"Identifying song: {audio_file}")
            result = await self.shazam.recognize_song(audio_file)
            
            if result and 'track' in result:
                track = result['track']
                metadata = {
                    'title': track.get('title', ''),
                    'artist': track.get('subtitle', ''),
                    'album': '',
                    'genre': '',
                    'year': '',
                }
                
                # Try to extract additional metadata
                if 'sections' in track:
                    for section in track['sections']:
                        if section.get('type') == 'SONG':
                            for item in section.get('metadata', []):
                                if item.get('title') == 'Album':
                                    metadata['album'] = item.get('text', '')
                                elif item.get('title') == 'Released':
                                    metadata['year'] = item.get('text', '')
                                elif item.get('title') == 'Genre':
                                    metadata['genre'] = item.get('text', '')
                
                logger.info(f"Identified: {metadata['artist']} - {metadata['title']}")
                return metadata
        
        except Exception as e:
            logger.error(f"Error identifying song: {e}")
        
        return None
    
    def get_lyrics(self, artist: str, title: str) -> Optional[str]:
        """Fetch lyrics using Genius API"""
        if not self.genius:
            logger.warning("Genius API not available")
            return None
        
        try:
            logger.info(f"Searching for lyrics: {artist} - {title}")
            song = self.genius.search_song(title, artist)
            
            if song and song.lyrics:
                lyrics = song.lyrics
                # Clean up lyrics
                lyrics = lyrics.replace('\n\n', '\n')
                logger.info("Lyrics found successfully")
                return lyrics
            else:
                logger.warning(f"No lyrics found for: {artist} - {title}")
        
        except Exception as e:
            logger.error(f"Error fetching lyrics: {e}")
        
        return None
    
    def extract_metadata_from_filename(self, filename: str) -> Dict[str, str]:
        """Extract metadata from filename"""
        base_name = os.path.splitext(os.path.basename(filename))[0]
        
        # Try common patterns
        patterns = [
            r'^(.+?)\s*-\s*(.+)$',  # Artist - Title
            r'^(.+?)\s+(.+)$',     # Artist Title
        ]
        
        import re
        for pattern in patterns:
            match = re.match(pattern, base_name)
            if match:
                return {
                    'artist': match.group(1).strip(),
                    'title': match.group(2).strip()
                }
        
        return {'artist': '', 'title': base_name}
    
    def update_metadata(self, file_path: str, metadata: Dict[str, Any], lyrics: Optional[str] = None) -> bool:
        """Update MP3 file with comprehensive metadata"""
        try:
            # Use mutagen for comprehensive ID3 tag support
            audio_file = MP3(file_path)
            
            # Ensure ID3 tags exist
            if audio_file.tags is None:
                audio_file.add_tags()
            
            tags = audio_file.tags
            
            # Set basic metadata
            if metadata.get('title'):
                tags.setall('TIT2', [TIT2(encoding=3, text=metadata['title'])])
            
            if metadata.get('artist'):
                tags.setall('TPE1', [TPE1(encoding=3, text=metadata['artist'])])
            
            if metadata.get('album'):
                tags.setall('TALB', [TALB(encoding=3, text=metadata['album'])])
            
            if metadata.get('album_artist'):
                tags.setall('TPE2', [TPE2(encoding=3, text=metadata['album_artist'])])
            
            if metadata.get('composer'):
                tags.setall('TCOM', [TCOM(encoding=3, text=metadata['composer'])])
            
            if metadata.get('grouping'):
                tags.setall('TIT1', [TIT1(encoding=3, text=metadata['grouping'])])
            
            if metadata.get('genre'):
                tags.setall('TCON', [TCON(encoding=3, text=metadata['genre'])])
            
            if metadata.get('year'):
                tags.setall('TDRC', [TDRC(encoding=3, text=str(metadata['year']))])
            
            if metadata.get('track_number'):
                track_text = str(metadata['track_number'])
                if metadata.get('total_tracks'):
                    track_text += f"/{metadata['total_tracks']}"
                tags.setall('TRCK', [TRCK(encoding=3, text=track_text)])
            
            if metadata.get('disc_number'):
                disc_text = str(metadata['disc_number'])
                if metadata.get('total_discs'):
                    disc_text += f"/{metadata['total_discs']}"
                tags.setall('TPOS', [TPOS(encoding=3, text=disc_text)])
            
            if metadata.get('compilation'):
                tags.setall('TCMP', [TCMP(encoding=3, text='1' if metadata['compilation'] else '0')])
            
            if metadata.get('comments'):
                tags.setall('COMM', [COMM(encoding=3, lang='eng', desc='', text=metadata['comments'])])
            
            # Add lyrics
            if lyrics:
                tags.setall('USLT', [USLT(encoding=3, lang='eng', desc='', text=lyrics)])
                logger.info("Lyrics added to metadata")
            
            # Save the file
            audio_file.save()
            logger.info(f"Metadata updated successfully for: {os.path.basename(file_path)}")
            return True
        
        except Exception as e:
            logger.error(f"Error updating metadata: {e}")
            return False

async def process_audio_file(file_path: str, genius_api_key: Optional[str] = None, 
                           artist_hint: str = "", title_hint: str = "") -> bool:
    """Process a single audio file with lyrics and metadata"""
    handler = LyricsMetadataHandler(genius_api_key)
    
    logger.info(f"Processing: {os.path.basename(file_path)}")
    
    # Start with hints or extract from filename
    if artist_hint and title_hint:
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
            'disc_number': '',
            'compilation': False,
            'comments': 'Downloaded with CLI Music Downloader'
        }
    else:
        filename_meta = handler.extract_metadata_from_filename(file_path)
        metadata = {
            'artist': filename_meta.get('artist', ''),
            'title': filename_meta.get('title', ''),
            'album': '',
            'album_artist': filename_meta.get('artist', ''),
            'composer': '',
            'grouping': '',
            'genre': '',
            'year': '',
            'track_number': '',
            'disc_number': '',
            'compilation': False,
            'comments': 'Downloaded with CLI Music Downloader'
        }
    
    # Try to identify the song for better metadata
    try:
        identified_meta = await handler.identify_song(file_path)
        if identified_meta:
            metadata.update(identified_meta)
            logger.info("Enhanced metadata with song identification")
    except Exception as e:
        logger.warning(f"Song identification failed: {e}")
    
    # Get lyrics
    lyrics = None
    if metadata['artist'] and metadata['title']:
        lyrics = handler.get_lyrics(metadata['artist'], metadata['title'])
    
    # Update the file
    success = handler.update_metadata(file_path, metadata, lyrics)
    
    if success:
        logger.info(f"✅ Successfully processed: {os.path.basename(file_path)}")
    else:
        logger.error(f"❌ Failed to process: {os.path.basename(file_path)}")
    
    return success

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Add lyrics and metadata to MP3 files')
    parser.add_argument('file_path', help='Path to MP3 file')
    parser.add_argument('--genius-key', help='Genius API key for lyrics')
    parser.add_argument('--artist', help='Artist name hint')
    parser.add_argument('--title', help='Song title hint')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.file_path):
        logger.error(f"File not found: {args.file_path}")
        sys.exit(1)
    
    # Check for API key in environment if not provided
    genius_key = args.genius_key or os.getenv('GENIUS_API_KEY')
    
    # Run the async function
    success = asyncio.run(process_audio_file(
        args.file_path, 
        genius_key, 
        args.artist or "", 
        args.title or ""
    ))
    
    sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()

