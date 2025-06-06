#!/usr/bin/env python3
"""
Metadata Manager for CLI Music Downloader
Handles metadata validation, correction, and integration from multiple sources
"""

import os
import sys
import logging
import re
import asyncio
from typing import Optional, Dict, Any, List, Tuple, Union
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum

# Import metadata libraries
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

try:
    import pylast
except ImportError:
    print("pylast not found. Install with: pip install pylast")
    pylast = None

try:
    import discogs_client
except ImportError:
    print("discogs_client not found. Install with: pip install discogs-client")
    discogs_client = None

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Configure MusicBrainz
if musicbrainzngs:
    musicbrainzngs.set_useragent(
        "CLI-Music-Downloader-Metadata-Manager",
        "1.0",
        "https://github.com/yourusername/CLI-Music-Downloader"
    )

class MetadataSource(Enum):
    """Enumeration of metadata sources"""
    MUSICBRAINZ = "musicbrainz"
    LASTFM = "lastfm"
    DISCOGS = "discogs"

@dataclass
class MetadataField:
    """Represents a metadata field with validation rules"""
    name: str
    required: bool = False
    max_length: Optional[int] = None
    pattern: Optional[str] = None
    validator: Optional[callable] = None
    corrector: Optional[callable] = None

@dataclass
class MetadataRecord:
    """Complete metadata record for a track"""
    # Required fields
    title: str = ""
    artist: str = ""
    album: str = ""
    year: str = ""
    track_number: str = ""
    
    # Optional fields
    genre: str = ""
    album_artist: str = ""
    composer: str = ""
    
    # Additional fields
    total_tracks: str = ""
    disc_number: str = ""
    total_discs: str = ""
    duration: str = ""
    isrc: str = ""
    
    # Source identifiers
    musicbrainz_recording_id: str = ""
    musicbrainz_artist_id: str = ""
    musicbrainz_album_id: str = ""
    lastfm_url: str = ""
    discogs_release_id: str = ""
    
    # Metadata about metadata
    source: str = ""
    confidence: float = 0.0
    validation_errors: List[str] = field(default_factory=list)
    corrections_applied: List[str] = field(default_factory=list)

class MetadataValidator:
    """Validates and corrects metadata fields"""
    
    def __init__(self):
        self.fields = self._define_validation_rules()
        self.genre_mapping = self._load_genre_mapping()
        self.bad_patterns = self._load_bad_patterns()
    
    def _define_validation_rules(self) -> Dict[str, MetadataField]:
        """Define validation rules for each metadata field"""
        return {
            'title': MetadataField(
                name='title',
                required=True,
                max_length=255,
                corrector=self._correct_title
            ),
            'artist': MetadataField(
                name='artist',
                required=True,
                max_length=255,
                corrector=self._correct_artist
            ),
            'album': MetadataField(
                name='album',
                required=True,
                max_length=255,
                corrector=self._correct_album
            ),
            'year': MetadataField(
                name='year',
                required=True,
                pattern=r'^\d{4}$',
                validator=self._validate_year,
                corrector=self._correct_year
            ),
            'track_number': MetadataField(
                name='track_number',
                required=True,
                pattern=r'^\d+$',
                validator=self._validate_track_number
            ),
            'genre': MetadataField(
                name='genre',
                required=False,
                max_length=100,
                corrector=self._correct_genre
            ),
            'album_artist': MetadataField(
                name='album_artist',
                required=False,
                max_length=255,
                corrector=self._correct_artist
            ),
            'composer': MetadataField(
                name='composer',
                required=False,
                max_length=255,
                corrector=self._correct_artist
            )
        }
    
    def _load_genre_mapping(self) -> Dict[str, str]:
        """Load standardized genre mappings"""
        return {
            # Rock genres
            'rock': 'Rock',
            'alternative rock': 'Alternative Rock',
            'alt rock': 'Alternative Rock',
            'indie rock': 'Indie Rock',
            'punk rock': 'Punk Rock',
            'hard rock': 'Hard Rock',
            'classic rock': 'Classic Rock',
            'progressive rock': 'Progressive Rock',
            'prog rock': 'Progressive Rock',
            
            # Pop genres
            'pop': 'Pop',
            'pop rock': 'Pop Rock',
            'electropop': 'Electropop',
            'dance pop': 'Dance Pop',
            'indie pop': 'Indie Pop',
            
            # Electronic genres
            'electronic': 'Electronic',
            'edm': 'EDM',
            'house': 'House',
            'techno': 'Techno',
            'trance': 'Trance',
            'dubstep': 'Dubstep',
            'drum and bass': 'Drum & Bass',
            'dnb': 'Drum & Bass',
            
            # Hip-hop genres
            'hip hop': 'Hip-Hop',
            'hip-hop': 'Hip-Hop',
            'rap': 'Hip-Hop',
            'trap': 'Trap',
            
            # Jazz genres
            'jazz': 'Jazz',
            'smooth jazz': 'Smooth Jazz',
            'bebop': 'Bebop',
            'fusion': 'Jazz Fusion',
            
            # Classical genres
            'classical': 'Classical',
            'baroque': 'Baroque',
            'romantic': 'Romantic',
            'contemporary classical': 'Contemporary Classical',
            
            # Country genres
            'country': 'Country',
            'country rock': 'Country Rock',
            'bluegrass': 'Bluegrass',
            
            # R&B/Soul genres
            'r&b': 'R&B',
            'rnb': 'R&B',
            'soul': 'Soul',
            'funk': 'Funk',
            
            # Metal genres
            'metal': 'Metal',
            'heavy metal': 'Heavy Metal',
            'death metal': 'Death Metal',
            'black metal': 'Black Metal',
            'thrash metal': 'Thrash Metal',
            
            # Folk genres
            'folk': 'Folk',
            'folk rock': 'Folk Rock',
            'acoustic': 'Acoustic',
            
            # Blues genres
            'blues': 'Blues',
            'blues rock': 'Blues Rock',
            
            # Reggae genres
            'reggae': 'Reggae',
            'ska': 'Ska',
            'dub': 'Dub'
        }
    
    def _load_bad_patterns(self) -> List[str]:
        """Load patterns to remove from titles and other fields"""
        return [
            r'\(official video\)',
            r'\(official music video\)',
            r'\(official audio\)',
            r'\(lyric video\)',
            r'\(lyrics\)',
            r'\(hd\)',
            r'\(hq\)',
            r'\(high quality\)',
            r'\(remastered\)',
            r'\[official video\]',
            r'\[official music video\]',
            r'\[official audio\]',
            r'\[lyric video\]',
            r'\[lyrics\]',
            r'\[hd\]',
            r'\[hq\]',
            r'\[high quality\]',
            r'\[remastered\]',
            r'- official video',
            r'- official music video',
            r'- official audio',
            r'- lyric video',
            r'- lyrics',
            r'ft\.',
            r'feat\.',
            r'featuring',
        ]
    
    def validate_record(self, record: MetadataRecord) -> Tuple[bool, List[str]]:
        """Validate a complete metadata record"""
        errors = []
        record.validation_errors = []
        
        for field_name, field_def in self.fields.items():
            value = getattr(record, field_name, "")
            field_errors = self._validate_field(field_def, value)
            if field_errors:
                errors.extend([f"{field_name}: {error}" for error in field_errors])
        
        record.validation_errors = errors
        return len(errors) == 0, errors
    
    def _validate_field(self, field_def: MetadataField, value: str) -> List[str]:
        """Validate a single field"""
        errors = []
        
        # Check required fields
        if field_def.required and not value.strip():
            errors.append(f"Required field '{field_def.name}' is empty")
            return errors
        
        # Skip validation for empty optional fields
        if not value.strip():
            return errors
        
        # Check max length
        if field_def.max_length and len(value) > field_def.max_length:
            errors.append(f"Field exceeds maximum length of {field_def.max_length}")
        
        # Check pattern
        if field_def.pattern and not re.match(field_def.pattern, value):
            errors.append(f"Field does not match required pattern: {field_def.pattern}")
        
        # Custom validator
        if field_def.validator:
            try:
                if not field_def.validator(value):
                    errors.append(f"Custom validation failed")
            except Exception as e:
                errors.append(f"Validation error: {e}")
        
        return errors
    
    def correct_record(self, record: MetadataRecord) -> MetadataRecord:
        """Apply automatic corrections to a metadata record"""
        record.corrections_applied = []
        
        for field_name, field_def in self.fields.items():
            if field_def.corrector:
                original_value = getattr(record, field_name, "")
                corrected_value = field_def.corrector(original_value)
                
                if corrected_value != original_value:
                    setattr(record, field_name, corrected_value)
                    record.corrections_applied.append(
                        f"{field_name}: '{original_value}' -> '{corrected_value}'"
                    )
        
        return record
    
    def _validate_year(self, year: str) -> bool:
        """Validate year format and range"""
        try:
            year_int = int(year)
            current_year = datetime.now().year
            return 1900 <= year_int <= current_year + 1
        except ValueError:
            return False
    
    def _validate_track_number(self, track_number: str) -> bool:
        """Validate track number"""
        try:
            track_int = int(track_number)
            return 1 <= track_int <= 999
        except ValueError:
            return False
    
    def _correct_title(self, title: str) -> str:
        """Apply title corrections"""
        if not title:
            return title
        
        corrected = title
        
        # Remove bad patterns (case insensitive)
        for pattern in self.bad_patterns:
            corrected = re.sub(pattern, '', corrected, flags=re.IGNORECASE)
        
        # Clean up whitespace
        corrected = re.sub(r'\s+', ' ', corrected).strip()
        
        # Apply title case
        corrected = self._apply_title_case(corrected)
        
        return corrected
    
    def _correct_artist(self, artist: str) -> str:
        """Apply artist name corrections"""
        if not artist:
            return artist
        
        corrected = artist
        
        # Clean up whitespace
        corrected = re.sub(r'\s+', ' ', corrected).strip()
        
        # Apply title case
        corrected = self._apply_title_case(corrected)
        
        return corrected
    
    def _correct_album(self, album: str) -> str:
        """Apply album title corrections"""
        if not album:
            return album
        
        corrected = album
        
        # Remove bad patterns (case insensitive)
        for pattern in self.bad_patterns:
            corrected = re.sub(pattern, '', corrected, flags=re.IGNORECASE)
        
        # Clean up whitespace
        corrected = re.sub(r'\s+', ' ', corrected).strip()
        
        # Apply title case
        corrected = self._apply_title_case(corrected)
        
        return corrected
    
    def _correct_year(self, year: str) -> str:
        """Extract and format year"""
        if not year:
            return year
        
        # Extract 4-digit year from various formats
        year_match = re.search(r'\b(\d{4})\b', year)
        if year_match:
            return year_match.group(1)
        
        return year
    
    def _correct_genre(self, genre: str) -> str:
        """Standardize genre names"""
        if not genre:
            return genre
        
        # Normalize case and lookup in mapping
        normalized = genre.lower().strip()
        return self.genre_mapping.get(normalized, self._apply_title_case(genre))
    
    def _apply_title_case(self, text: str) -> str:
        """Apply proper title case formatting"""
        if not text:
            return text
        
        # Words that should remain lowercase in titles
        lowercase_words = {
            'a', 'an', 'the', 'and', 'but', 'or', 'for', 'nor', 'on', 'at', 
            'to', 'from', 'by', 'of', 'in', 'with', 'without', 'through',
            'over', 'under', 'above', 'below', 'up', 'down', 'out', 'off',
            'into', 'onto', 'upon'
        }
        
        words = text.split()
        result = []
        
        for i, word in enumerate(words):
            # First and last words are always capitalized
            if i == 0 or i == len(words) - 1:
                result.append(word.capitalize())
            # Check if word should remain lowercase
            elif word.lower() in lowercase_words:
                result.append(word.lower())
            else:
                result.append(word.capitalize())
        
        return ' '.join(result)

class MusicBrainzProvider:
    """MusicBrainz metadata provider"""
    
    def __init__(self):
        self.available = musicbrainzngs is not None
        if not self.available:
            logger.warning("MusicBrainz not available - install musicbrainzngs")
    
    async def search_metadata(self, artist: str, title: str, album: str = "") -> Optional[MetadataRecord]:
        """Search for metadata in MusicBrainz"""
        if not self.available:
            return None
        
        try:
            logger.info(f"Searching MusicBrainz for: {artist} - {title}")
            
            # Search for recordings
            search_params = {
                'artist': artist,
                'recording': title,
                'limit': 10
            }
            
            if album:
                search_params['release'] = album
            
            result = musicbrainzngs.search_recordings(**search_params)
            
            if result and 'recording-list' in result and result['recording-list']:
                recording = result['recording-list'][0]
                
                record = MetadataRecord(
                    source=MetadataSource.MUSICBRAINZ.value,
                    confidence=0.9  # High confidence for MusicBrainz
                )
                
                # Extract basic info
                record.title = recording.get('title', '')
                record.musicbrainz_recording_id = recording.get('id', '')
                
                # Extract artist information
                if 'artist-credit' in recording and recording['artist-credit']:
                    artists = []
                    for credit in recording['artist-credit']:
                        if isinstance(credit, dict) and 'artist' in credit:
                            artist_name = credit['artist'].get('name', '')
                            artists.append(artist_name)
                            if not record.musicbrainz_artist_id:
                                record.musicbrainz_artist_id = credit['artist'].get('id', '')
                    record.artist = ', '.join(artists)
                    record.album_artist = record.artist
                
                # Extract release information
                if 'release-list' in recording and recording['release-list']:
                    release = recording['release-list'][0]
                    record.album = release.get('title', '')
                    record.musicbrainz_album_id = release.get('id', '')
                    
                    # Get release date
                    if 'date' in release:
                        record.year = release['date'][:4]
                    
                    # Get track information
                    if 'medium-list' in release and release['medium-list']:
                        medium = release['medium-list'][0]
                        if 'track-list' in medium and medium['track-list']:
                            for i, track in enumerate(medium['track-list']):
                                if ('recording' in track and 
                                    track['recording'].get('id') == recording.get('id')):
                                    record.track_number = str(i + 1)
                                    record.total_tracks = str(len(medium['track-list']))
                                    break
                
                # Try to get genre information
                try:
                    if record.musicbrainz_album_id:
                        release_detail = musicbrainzngs.get_release_by_id(
                            record.musicbrainz_album_id,
                            includes=['artist-credits', 'release-groups']
                        )
                        
                        if 'release' in release_detail:
                            release_info = release_detail['release']
                            
                            if 'release-group' in release_info:
                                rg = release_info['release-group']
                                if 'tag-list' in rg and rg['tag-list']:
                                    tags = sorted(rg['tag-list'], 
                                                 key=lambda x: int(x.get('count', 0)), 
                                                 reverse=True)
                                    if tags:
                                        record.genre = tags[0].get('name', '')
                
                except Exception as e:
                    logger.warning(f"Error getting detailed release info: {e}")
                
                logger.info(f"Found MusicBrainz metadata: {record.artist} - {record.title}")
                return record
            
            else:
                logger.warning(f"No MusicBrainz results for: {artist} - {title}")
        
        except Exception as e:
            logger.error(f"MusicBrainz search error: {e}")
        
        return None

class LastFmProvider:
    """Last.fm metadata provider"""
    
    def __init__(self, api_key: str, api_secret: str = ""):
        self.api_key = api_key
        self.api_secret = api_secret
        self.available = pylast is not None and api_key
        
        if not pylast:
            logger.warning("Last.fm not available - install pylast")
        elif not api_key:
            logger.warning("Last.fm API key not provided")
        else:
            try:
                self.network = pylast.LastFMNetwork(
                    api_key=api_key,
                    api_secret=api_secret
                )
                logger.info("Last.fm API initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize Last.fm API: {e}")
                self.available = False
    
    async def search_metadata(self, artist: str, title: str, album: str = "") -> Optional[MetadataRecord]:
        """Search for metadata in Last.fm"""
        if not self.available:
            return None
        
        try:
            logger.info(f"Searching Last.fm for: {artist} - {title}")
            
            # Search for track
            track = self.network.get_track(artist, title)
            track_info = track.get_info()
            
            if track_info:
                record = MetadataRecord(
                    source=MetadataSource.LASTFM.value,
                    confidence=0.7  # Medium confidence for Last.fm
                )
                
                record.title = track_info.get('name', title)
                record.artist = track_info.get('artist', {}).get('name', artist)
                record.album = track_info.get('album', {}).get('title', album)
                record.lastfm_url = track_info.get('url', '')
                
                # Get additional info
                try:
                    album_info = track.get_album()
                    if album_info:
                        album_details = album_info.get_info()
                        if album_details:
                            # Extract year from release date
                            release_date = album_details.get('release_date')
                            if release_date:
                                record.year = release_date[:4]
                            
                            # Get track number
                            tracks = album_details.get('tracks', [])
                            for i, track_item in enumerate(tracks):
                                if track_item.get('name', '').lower() == title.lower():
                                    record.track_number = str(i + 1)
                                    record.total_tracks = str(len(tracks))
                                    break
                
                except Exception as e:
                    logger.warning(f"Error getting Last.fm album info: {e}")
                
                # Get top tags as genre
                try:
                    tags = track.get_top_tags(limit=5)
                    if tags:
                        record.genre = tags[0].item.get_name()
                except Exception as e:
                    logger.warning(f"Error getting Last.fm tags: {e}")
                
                logger.info(f"Found Last.fm metadata: {record.artist} - {record.title}")
                return record
        
        except Exception as e:
            logger.error(f"Last.fm search error: {e}")
        
        return None

class DiscogsProvider:
    """Discogs metadata provider"""
    
    def __init__(self, user_token: str = ""):
        self.user_token = user_token
        self.available = discogs_client is not None and user_token
        
        if not discogs_client:
            logger.warning("Discogs not available - install discogs-client")
        elif not user_token:
            logger.warning("Discogs user token not provided")
        else:
            try:
                self.client = discogs_client.Client(
                    'CLI-Music-Downloader/1.0',
                    user_token=user_token
                )
                logger.info("Discogs API initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize Discogs API: {e}")
                self.available = False
    
    async def search_metadata(self, artist: str, title: str, album: str = "") -> Optional[MetadataRecord]:
        """Search for metadata in Discogs"""
        if not self.available:
            return None
        
        try:
            logger.info(f"Searching Discogs for: {artist} - {title}")
            
            # Search for release
            search_query = f"{artist} {title}"
            if album:
                search_query = f"{artist} {album}"
            
            results = self.client.search(search_query, type='release')
            
            if results:
                release = results[0]  # Take first result
                
                record = MetadataRecord(
                    source=MetadataSource.DISCOGS.value,
                    confidence=0.6  # Lower confidence for Discogs
                )
                
                record.album = release.title
                record.year = str(release.year) if release.year else ""
                record.discogs_release_id = str(release.id)
                
                # Extract artist
                if release.artists:
                    record.artist = release.artists[0].name
                    record.album_artist = record.artist
                
                # Extract genre
                if release.genres:
                    record.genre = release.genres[0]
                
                # Find matching track
                try:
                    tracklist = release.tracklist
                    for i, track in enumerate(tracklist):
                        if title.lower() in track.title.lower():
                            record.title = track.title
                            record.track_number = str(i + 1)
                            record.total_tracks = str(len(tracklist))
                            if track.duration:
                                record.duration = track.duration
                            break
                except Exception as e:
                    logger.warning(f"Error processing Discogs tracklist: {e}")
                
                logger.info(f"Found Discogs metadata: {record.artist} - {record.title}")
                return record
        
        except Exception as e:
            logger.error(f"Discogs search error: {e}")
        
        return None

class MetadataManager:
    """Main metadata manager coordinating validation, correction, and multi-source integration"""
    
    def __init__(self, 
                 lastfm_api_key: str = "",
                 lastfm_api_secret: str = "",
                 discogs_user_token: str = ""):
        
        self.validator = MetadataValidator()
        
        # Initialize providers
        self.providers = {
            MetadataSource.MUSICBRAINZ: MusicBrainzProvider(),
            MetadataSource.LASTFM: LastFmProvider(lastfm_api_key, lastfm_api_secret),
            MetadataSource.DISCOGS: DiscogsProvider(discogs_user_token)
        }
        
        # Log available providers
        available_providers = [name.value for name, provider in self.providers.items() if provider.available]
        logger.info(f"Available metadata providers: {', '.join(available_providers)}")
    
    async def get_metadata(self, 
                          artist: str, 
                          title: str, 
                          album: str = "",
                          sources: List[MetadataSource] = None) -> Optional[MetadataRecord]:
        """Get metadata from multiple sources with automatic validation and correction"""
        
        if sources is None:
            sources = [MetadataSource.MUSICBRAINZ, MetadataSource.LASTFM, MetadataSource.DISCOGS]
        
        logger.info(f"Fetching metadata for: {artist} - {title}")
        
        best_record = None
        best_confidence = 0.0
        
        # Try each source in order
        for source in sources:
            provider = self.providers.get(source)
            if not provider or not provider.available:
                logger.warning(f"Provider {source.value} not available")
                continue
            
            try:
                record = await provider.search_metadata(artist, title, album)
                if record:
                    # Apply corrections
                    record = self.validator.correct_record(record)
                    
                    # Validate
                    is_valid, errors = self.validator.validate_record(record)
                    
                    if is_valid and record.confidence > best_confidence:
                        best_record = record
                        best_confidence = record.confidence
                        logger.info(f"Found better metadata from {source.value} (confidence: {record.confidence})")
                    elif not is_valid:
                        logger.warning(f"Metadata from {source.value} failed validation: {errors}")
            
            except Exception as e:
                logger.error(f"Error getting metadata from {source.value}: {e}")
        
        if best_record:
            logger.info(f"Selected metadata from {best_record.source} with confidence {best_record.confidence}")
            if best_record.corrections_applied:
                logger.info(f"Applied corrections: {', '.join(best_record.corrections_applied)}")
        else:
            logger.warning("No valid metadata found from any source")
        
        return best_record
    
    def validate_metadata(self, record: MetadataRecord) -> Tuple[bool, List[str]]:
        """Validate a metadata record"""
        return self.validator.validate_record(record)
    
    def correct_metadata(self, record: MetadataRecord) -> MetadataRecord:
        """Apply automatic corrections to metadata"""
        return self.validator.correct_record(record)
    
    def merge_metadata(self, 
                      primary: MetadataRecord, 
                      secondary: MetadataRecord, 
                      prefer_non_empty: bool = True) -> MetadataRecord:
        """Merge two metadata records, preferring primary unless fields are empty"""
        
        merged = MetadataRecord()
        
        # Get all field names from both records
        field_names = set(dir(primary)) | set(dir(secondary))
        field_names = {name for name in field_names 
                      if not name.startswith('_') and not callable(getattr(primary, name, None))}
        
        for field_name in field_names:
            primary_value = getattr(primary, field_name, "")
            secondary_value = getattr(secondary, field_name, "")
            
            if prefer_non_empty and not primary_value and secondary_value:
                setattr(merged, field_name, secondary_value)
            else:
                setattr(merged, field_name, primary_value)
        
        # Merge corrections applied
        merged.corrections_applied = (primary.corrections_applied + 
                                    secondary.corrections_applied)
        
        # Use higher confidence
        merged.confidence = max(primary.confidence, secondary.confidence)
        
        return merged

# Example usage and testing
async def main():
    """Example usage of the metadata manager"""
    
    # Initialize manager (API keys would normally come from environment variables)
    manager = MetadataManager(
        lastfm_api_key=os.getenv('LASTFM_API_KEY', ''),
        lastfm_api_secret=os.getenv('LASTFM_API_SECRET', ''),
        discogs_user_token=os.getenv('DISCOGS_USER_TOKEN', '')
    )
    
    # Example search
    record = await manager.get_metadata(
        artist="The Beatles",
        title="Hey Jude",
        album=""
    )
    
    if record:
        print(f"Found metadata:")
        print(f"  Title: {record.title}")
        print(f"  Artist: {record.artist}")
        print(f"  Album: {record.album}")
        print(f"  Year: {record.year}")
        print(f"  Genre: {record.genre}")
        print(f"  Source: {record.source}")
        print(f"  Confidence: {record.confidence}")
        
        if record.corrections_applied:
            print(f"  Corrections applied: {', '.join(record.corrections_applied)}")
        
        # Validate the record
        is_valid, errors = manager.validate_metadata(record)
        print(f"  Valid: {is_valid}")
        if errors:
            print(f"  Validation errors: {', '.join(errors)}")
    else:
        print("No metadata found")

if __name__ == '__main__':
    asyncio.run(main())

