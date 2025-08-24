#!/usr/bin/env ./venv/bin/python3
"""
Batch Metadata Processor for CLI Music Downloader
Scans music libraries, generates reports, and batch processes multiple files for metadata enhancement.

Usage:
    ./batch_metadata.py --scan ~/Music
    ./batch_metadata.py --fix ~/Music/Adele
    ./batch_metadata.py --report
"""

import os
import sys
import json
import asyncio
import argparse
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, asdict
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import time

# Import our custom metadata manager from package
try:
    from .metadata_manager import MetadataManager, MetadataRecord
except ImportError:
    print("Error: Could not import metadata_manager. Make sure it's installed properly.")
    sys.exit(1)

# Import music file handling
try:
    from mutagen.id3 import ID3, TIT2, TPE1, TALB, TPE2, TCOM, TCON, TDRC, TRCK, TPOS
    from mutagen.mp3 import MP3
    from mutagen.flac import FLAC
    from mutagen.mp4 import MP4
    from mutagen import File
except ImportError:
    print("Error: mutagen library required. Install with: pip install mutagen")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Supported audio formats
SUPPORTED_FORMATS = {'.mp3', '.flac', '.m4a', '.mp4', '.ogg', '.wma'}

# Configuration file path
CONFIG_FILE = os.path.expanduser('~/.batch_metadata_config.json')
REPORT_FILE = os.path.expanduser('~/.batch_metadata_report.json')

@dataclass
class FileMetadataStatus:
    """Status of metadata for a single file"""
    file_path: str
    file_size: int
    format: str
    duration: Optional[float]
    
    # Current metadata
    title: str = ""
    artist: str = ""
    album: str = ""
    year: str = ""
    track_number: str = ""
    genre: str = ""
    album_artist: str = ""
    
    # Status flags
    has_basic_metadata: bool = False
    has_complete_metadata: bool = False
    needs_correction: bool = False
    
    # Missing fields
    missing_fields: List[str] = None
    
    # Validation issues
    validation_errors: List[str] = None
    
    # Processing status
    last_scanned: str = ""
    last_processed: str = ""
    processing_errors: List[str] = None
    
    def __post_init__(self):
        if self.missing_fields is None:
            self.missing_fields = []
        if self.validation_errors is None:
            self.validation_errors = []
        if self.processing_errors is None:
            self.processing_errors = []

@dataclass
class BatchReport:
    """Comprehensive report of batch scanning/processing results"""
    scan_date: str
    total_files: int
    files_by_format: Dict[str, int]
    
    # Metadata completeness
    files_with_basic_metadata: int
    files_with_complete_metadata: int
    files_needing_correction: int
    files_without_metadata: int
    
    # Most common issues
    common_missing_fields: Dict[str, int]
    common_validation_errors: Dict[str, int]
    
    # Processing summary
    files_processed: int = 0
    files_fixed: int = 0
    processing_errors: int = 0
    
    # File details
    file_statuses: List[FileMetadataStatus] = None
    
    def __post_init__(self):
        if self.file_statuses is None:
            self.file_statuses = []

class BatchMetadataProcessor:
    """Main class for batch metadata processing"""
    
    def __init__(self):
        self.config = self._load_config()
        self.metadata_manager = None
        self.report = None
        
        # Initialize metadata manager
        self._init_metadata_manager()
    
    def _load_config(self) -> Dict:
        """Load configuration from file"""
        default_config = {
            'lastfm_api_key': os.getenv('LASTFM_API_KEY', ''),
            'lastfm_api_secret': os.getenv('LASTFM_API_SECRET', ''),
            'discogs_user_token': os.getenv('DISCOGS_USER_TOKEN', ''),
            'required_fields': ['title', 'artist', 'album', 'year'],
            'optional_fields': ['track_number', 'genre', 'album_artist'],
            'max_workers': 4,
            'delay_between_requests': 1.0,
            'backup_original_files': True,
            'auto_correct_metadata': True
        }
        
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    config = json.load(f)
                # Merge with defaults
                default_config.update(config)
            except Exception as e:
                logger.warning(f"Error loading config file: {e}. Using defaults.")
        
        return default_config
    
    def _save_config(self):
        """Save current configuration to file"""
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving config file: {e}")
    
    def _init_metadata_manager(self):
        """Initialize the metadata manager with API keys from config"""
        try:
            self.metadata_manager = MetadataManager(
                lastfm_api_key=self.config.get('lastfm_api_key', ''),
                lastfm_api_secret=self.config.get('lastfm_api_secret', ''),
                discogs_user_token=self.config.get('discogs_user_token', '')
            )
            logger.info("Metadata manager initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing metadata manager: {e}")
            self.metadata_manager = None
    
    def find_music_files(self, directory: str) -> List[str]:
        """Recursively find all supported music files in a directory"""
        music_files = []
        directory_path = Path(directory)
        
        if not directory_path.exists():
            logger.error(f"Directory does not exist: {directory}")
            return music_files
        
        logger.info(f"Scanning directory: {directory}")
        
        for file_path in directory_path.rglob('*'):
            if file_path.is_file() and file_path.suffix.lower() in SUPPORTED_FORMATS:
                music_files.append(str(file_path))
        
        logger.info(f"Found {len(music_files)} music files")
        return music_files
    
    def extract_current_metadata(self, file_path: str) -> FileMetadataStatus:
        """Extract current metadata from a music file"""
        try:
            audio_file = File(file_path)
            if audio_file is None:
                raise ValueError("Unsupported file format")
            
            file_stat = os.stat(file_path)
            status = FileMetadataStatus(
                file_path=file_path,
                file_size=file_stat.st_size,
                format=Path(file_path).suffix.lower(),
                duration=getattr(audio_file.info, 'length', None),
                last_scanned=datetime.now().isoformat()
            )
            
            # Extract metadata based on file format
            if isinstance(audio_file, MP3):
                status = self._extract_mp3_metadata(audio_file, status)
            elif isinstance(audio_file, FLAC):
                status = self._extract_flac_metadata(audio_file, status)
            elif isinstance(audio_file, MP4):
                status = self._extract_mp4_metadata(audio_file, status)
            else:
                # Generic extraction for other formats
                status = self._extract_generic_metadata(audio_file, status)
            
            # Analyze metadata completeness
            self._analyze_metadata_completeness(status)
            
            return status
            
        except Exception as e:
            logger.error(f"Error extracting metadata from {file_path}: {e}")
            status = FileMetadataStatus(
                file_path=file_path,
                file_size=0,
                format=Path(file_path).suffix.lower(),
                duration=None,
                last_scanned=datetime.now().isoformat()
            )
            status.processing_errors.append(f"Metadata extraction failed: {e}")
            return status
    
    def _extract_mp3_metadata(self, audio_file: MP3, status: FileMetadataStatus) -> FileMetadataStatus:
        """Extract metadata from MP3 files"""
        tags = audio_file.tags
        if tags:
            status.title = str(tags.get('TIT2', [''])[0]) if tags.get('TIT2') else ""
            status.artist = str(tags.get('TPE1', [''])[0]) if tags.get('TPE1') else ""
            status.album = str(tags.get('TALB', [''])[0]) if tags.get('TALB') else ""
            status.year = str(tags.get('TDRC', [''])[0]) if tags.get('TDRC') else ""
            status.track_number = str(tags.get('TRCK', [''])[0]) if tags.get('TRCK') else ""
            status.genre = str(tags.get('TCON', [''])[0]) if tags.get('TCON') else ""
            status.album_artist = str(tags.get('TPE2', [''])[0]) if tags.get('TPE2') else ""
        
        return status
    
    def _extract_flac_metadata(self, audio_file: FLAC, status: FileMetadataStatus) -> FileMetadataStatus:
        """Extract metadata from FLAC files"""
        tags = audio_file.tags
        if tags:
            status.title = tags.get('TITLE', [''])[0] if tags.get('TITLE') else ""
            status.artist = tags.get('ARTIST', [''])[0] if tags.get('ARTIST') else ""
            status.album = tags.get('ALBUM', [''])[0] if tags.get('ALBUM') else ""
            status.year = tags.get('DATE', [''])[0] if tags.get('DATE') else ""
            status.track_number = tags.get('TRACKNUMBER', [''])[0] if tags.get('TRACKNUMBER') else ""
            status.genre = tags.get('GENRE', [''])[0] if tags.get('GENRE') else ""
            status.album_artist = tags.get('ALBUMARTIST', [''])[0] if tags.get('ALBUMARTIST') else ""
        
        return status
    
    def _extract_mp4_metadata(self, audio_file: MP4, status: FileMetadataStatus) -> FileMetadataStatus:
        """Extract metadata from MP4/M4A files"""
        tags = audio_file.tags
        if tags:
            status.title = tags.get('\xa9nam', [''])[0] if tags.get('\xa9nam') else ""
            status.artist = tags.get('\xa9ART', [''])[0] if tags.get('\xa9ART') else ""
            status.album = tags.get('\xa9alb', [''])[0] if tags.get('\xa9alb') else ""
            status.year = str(tags.get('\xa9day', [''])[0]) if tags.get('\xa9day') else ""
            status.track_number = str(tags.get('trkn', [('', '')])[0][0]) if tags.get('trkn') else ""
            status.genre = tags.get('\xa9gen', [''])[0] if tags.get('\xa9gen') else ""
            status.album_artist = tags.get('aART', [''])[0] if tags.get('aART') else ""
        
        return status
    
    def _extract_generic_metadata(self, audio_file, status: FileMetadataStatus) -> FileMetadataStatus:
        """Extract metadata from generic audio files"""
        tags = audio_file.tags
        if tags:
            # Try common tag names
            for title_tag in ['TITLE', 'TIT2', '\xa9nam']:
                if title_tag in tags:
                    status.title = str(tags[title_tag][0] if isinstance(tags[title_tag], list) else tags[title_tag])
                    break
            
            for artist_tag in ['ARTIST', 'TPE1', '\xa9ART']:
                if artist_tag in tags:
                    status.artist = str(tags[artist_tag][0] if isinstance(tags[artist_tag], list) else tags[artist_tag])
                    break
            
            for album_tag in ['ALBUM', 'TALB', '\xa9alb']:
                if album_tag in tags:
                    status.album = str(tags[album_tag][0] if isinstance(tags[album_tag], list) else tags[album_tag])
                    break
        
        return status
    
    def _analyze_metadata_completeness(self, status: FileMetadataStatus):
        """Analyze how complete the metadata is for a file"""
        required_fields = self.config.get('required_fields', ['title', 'artist', 'album', 'year'])
        optional_fields = self.config.get('optional_fields', ['track_number', 'genre', 'album_artist'])
        
        # Check required fields
        missing_required = []
        for field in required_fields:
            value = getattr(status, field, "").strip()
            if not value:
                missing_required.append(field)
        
        # Check optional fields
        missing_optional = []
        for field in optional_fields:
            value = getattr(status, field, "").strip()
            if not value:
                missing_optional.append(field)
        
        status.missing_fields = missing_required + missing_optional
        status.has_basic_metadata = len(missing_required) == 0
        status.has_complete_metadata = len(missing_required) == 0 and len(missing_optional) == 0
        
        # Check for validation issues
        if self.metadata_manager:
            record = MetadataRecord(
                title=status.title,
                artist=status.artist,
                album=status.album,
                year=status.year,
                track_number=status.track_number,
                genre=status.genre,
                album_artist=status.album_artist
            )
            
            is_valid, errors = self.metadata_manager.validate_metadata(record)
            if not is_valid:
                status.validation_errors = errors
                status.needs_correction = True
    
    async def scan_directory(self, directory: str) -> BatchReport:
        """Scan a directory and analyze metadata completeness"""
        logger.info(f"Starting batch scan of: {directory}")
        start_time = time.time()
        
        # Find all music files
        music_files = self.find_music_files(directory)
        
        if not music_files:
            logger.warning("No music files found")
            return BatchReport(
                scan_date=datetime.now().isoformat(),
                total_files=0,
                files_by_format={},
                files_with_basic_metadata=0,
                files_with_complete_metadata=0,
                files_needing_correction=0,
                files_without_metadata=0,
                common_missing_fields={},
                common_validation_errors={}
            )
        
        # Process files in batches
        file_statuses = []
        max_workers = self.config.get('max_workers', 4)
        
        logger.info(f"Processing {len(music_files)} files with {max_workers} workers")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_file = {executor.submit(self.extract_current_metadata, file_path): file_path 
                            for file_path in music_files}
            
            # Collect results
            for i, future in enumerate(future_to_file):
                try:
                    status = future.result()
                    file_statuses.append(status)
                    
                    if (i + 1) % 100 == 0:
                        logger.info(f"Processed {i + 1}/{len(music_files)} files")
                        
                except Exception as e:
                    file_path = future_to_file[future]
                    logger.error(f"Error processing {file_path}: {e}")
        
        # Generate report
        report = self._generate_report(file_statuses)
        
        elapsed_time = time.time() - start_time
        logger.info(f"Scan completed in {elapsed_time:.2f} seconds")
        
        # Save report
        self._save_report(report)
        
        self.report = report
        return report
    
    def _generate_report(self, file_statuses: List[FileMetadataStatus]) -> BatchReport:
        """Generate a comprehensive report from file statuses"""
        total_files = len(file_statuses)
        
        # Count by format
        files_by_format = {}
        for status in file_statuses:
            format_name = status.format
            files_by_format[format_name] = files_by_format.get(format_name, 0) + 1
        
        # Count metadata completeness
        files_with_basic = sum(1 for s in file_statuses if s.has_basic_metadata)
        files_with_complete = sum(1 for s in file_statuses if s.has_complete_metadata)
        files_needing_correction = sum(1 for s in file_statuses if s.needs_correction)
        files_without_metadata = sum(1 for s in file_statuses if not s.has_basic_metadata)
        
        # Count common missing fields
        common_missing_fields = {}
        for status in file_statuses:
            for field in status.missing_fields:
                common_missing_fields[field] = common_missing_fields.get(field, 0) + 1
        
        # Count common validation errors
        common_validation_errors = {}
        for status in file_statuses:
            for error in status.validation_errors:
                common_validation_errors[error] = common_validation_errors.get(error, 0) + 1
        
        return BatchReport(
            scan_date=datetime.now().isoformat(),
            total_files=total_files,
            files_by_format=files_by_format,
            files_with_basic_metadata=files_with_basic,
            files_with_complete_metadata=files_with_complete,
            files_needing_correction=files_needing_correction,
            files_without_metadata=files_without_metadata,
            common_missing_fields=common_missing_fields,
            common_validation_errors=common_validation_errors,
            file_statuses=file_statuses
        )
    
    def _save_report(self, report: BatchReport):
        """Save report to file"""
        try:
            # Create a serializable version of the report
            report_dict = asdict(report)
            
            with open(REPORT_FILE, 'w') as f:
                json.dump(report_dict, f, indent=2, default=str)
            
            logger.info(f"Report saved to: {REPORT_FILE}")
            
        except Exception as e:
            logger.error(f"Error saving report: {e}")
    
    def _load_report(self) -> Optional[BatchReport]:
        """Load the most recent report"""
        try:
            if os.path.exists(REPORT_FILE):
                with open(REPORT_FILE, 'r') as f:
                    report_dict = json.load(f)
                
                # Convert back to objects
                file_statuses = []
                for status_dict in report_dict.get('file_statuses', []):
                    status = FileMetadataStatus(**status_dict)
                    file_statuses.append(status)
                
                report_dict['file_statuses'] = file_statuses
                report = BatchReport(**report_dict)
                
                return report
        except Exception as e:
            logger.error(f"Error loading report: {e}")
        
        return None
    
    async def fix_metadata(self, directory: str, dry_run: bool = False) -> Dict[str, int]:
        """Fix metadata for files in a directory"""
        logger.info(f"Starting metadata fix for: {directory}")
        
        if not self.metadata_manager:
            logger.error("Metadata manager not available. Cannot fix metadata.")
            return {'processed': 0, 'fixed': 0, 'errors': 0}
        
        # Find files to process
        music_files = self.find_music_files(directory)
        
        if not music_files:
            logger.warning("No music files found")
            return {'processed': 0, 'fixed': 0, 'errors': 0}
        
        results = {'processed': 0, 'fixed': 0, 'errors': 0}
        delay = self.config.get('delay_between_requests', 1.0)
        
        for file_path in music_files:
            try:
                logger.info(f"Processing: {os.path.basename(file_path)}")
                
                # Extract current metadata
                current_status = self.extract_current_metadata(file_path)
                
                # Skip if metadata is complete and valid
                if current_status.has_complete_metadata and not current_status.needs_correction:
                    logger.info(f"Skipping {os.path.basename(file_path)} - metadata is complete")
                    continue
                
                # Get enhanced metadata
                enhanced_metadata = await self.metadata_manager.get_metadata(
                    artist=current_status.artist or "Unknown Artist",
                    title=current_status.title or os.path.splitext(os.path.basename(file_path))[0],
                    album=current_status.album
                )
                
                if enhanced_metadata:
                    # Apply metadata to file
                    if not dry_run:
                        success = self._apply_metadata_to_file(file_path, enhanced_metadata)
                        if success:
                            results['fixed'] += 1
                            logger.info(f"Successfully updated metadata for {os.path.basename(file_path)}")
                        else:
                            results['errors'] += 1
                    else:
                        logger.info(f"[DRY RUN] Would update metadata for {os.path.basename(file_path)}")
                        results['fixed'] += 1
                else:
                    logger.warning(f"No enhanced metadata found for {os.path.basename(file_path)}")
                
                results['processed'] += 1
                
                # Rate limiting
                if delay > 0:
                    await asyncio.sleep(delay)
                    
            except Exception as e:
                logger.error(f"Error processing {file_path}: {e}")
                results['errors'] += 1
        
        logger.info(f"Processing complete. Processed: {results['processed']}, Fixed: {results['fixed']}, Errors: {results['errors']}")
        return results
    
    def _apply_metadata_to_file(self, file_path: str, metadata: MetadataRecord) -> bool:
        """Apply metadata to a music file"""
        try:
            # Backup original file if configured
            if self.config.get('backup_original_files', True):
                backup_path = file_path + '.backup'
                if not os.path.exists(backup_path):
                    import shutil
                    shutil.copy2(file_path, backup_path)
            
            audio_file = File(file_path)
            if audio_file is None:
                logger.error(f"Unsupported file format: {file_path}")
                return False
            
            # Apply metadata based on file type
            if isinstance(audio_file, MP3):
                return self._apply_mp3_metadata(audio_file, metadata)
            elif isinstance(audio_file, FLAC):
                return self._apply_flac_metadata(audio_file, metadata)
            elif isinstance(audio_file, MP4):
                return self._apply_mp4_metadata(audio_file, metadata)
            else:
                logger.warning(f"Metadata application not implemented for {type(audio_file)}")
                return False
                
        except Exception as e:
            logger.error(f"Error applying metadata to {file_path}: {e}")
            return False
    
    def _apply_mp3_metadata(self, audio_file: MP3, metadata: MetadataRecord) -> bool:
        """Apply metadata to MP3 file"""
        try:
            if audio_file.tags is None:
                audio_file.add_tags()
            
            tags = audio_file.tags
            
            if metadata.title:
                tags['TIT2'] = TIT2(encoding=3, text=metadata.title)
            if metadata.artist:
                tags['TPE1'] = TPE1(encoding=3, text=metadata.artist)
            if metadata.album:
                tags['TALB'] = TALB(encoding=3, text=metadata.album)
            if metadata.year:
                tags['TDRC'] = TDRC(encoding=3, text=metadata.year)
            if metadata.track_number:
                tags['TRCK'] = TRCK(encoding=3, text=metadata.track_number)
            if metadata.genre:
                tags['TCON'] = TCON(encoding=3, text=metadata.genre)
            if metadata.album_artist:
                tags['TPE2'] = TPE2(encoding=3, text=metadata.album_artist)
            
            audio_file.save()
            return True
            
        except Exception as e:
            logger.error(f"Error applying MP3 metadata: {e}")
            return False
    
    def _apply_flac_metadata(self, audio_file: FLAC, metadata: MetadataRecord) -> bool:
        """Apply metadata to FLAC file"""
        try:
            if metadata.title:
                audio_file['TITLE'] = metadata.title
            if metadata.artist:
                audio_file['ARTIST'] = metadata.artist
            if metadata.album:
                audio_file['ALBUM'] = metadata.album
            if metadata.year:
                audio_file['DATE'] = metadata.year
            if metadata.track_number:
                audio_file['TRACKNUMBER'] = metadata.track_number
            if metadata.genre:
                audio_file['GENRE'] = metadata.genre
            if metadata.album_artist:
                audio_file['ALBUMARTIST'] = metadata.album_artist
            
            audio_file.save()
            return True
            
        except Exception as e:
            logger.error(f"Error applying FLAC metadata: {e}")
            return False
    
    def _apply_mp4_metadata(self, audio_file: MP4, metadata: MetadataRecord) -> bool:
        """Apply metadata to MP4/M4A file"""
        try:
            if metadata.title:
                audio_file['\xa9nam'] = metadata.title
            if metadata.artist:
                audio_file['\xa9ART'] = metadata.artist
            if metadata.album:
                audio_file['\xa9alb'] = metadata.album
            if metadata.year:
                audio_file['\xa9day'] = metadata.year
            if metadata.track_number:
                try:
                    track_num = int(metadata.track_number)
                    audio_file['trkn'] = [(track_num, 0)]
                except ValueError:
                    pass
            if metadata.genre:
                audio_file['\xa9gen'] = metadata.genre
            if metadata.album_artist:
                audio_file['aART'] = metadata.album_artist
            
            audio_file.save()
            return True
            
        except Exception as e:
            logger.error(f"Error applying MP4 metadata: {e}")
            return False
    
    def display_report(self, detailed: bool = False):
        """Display the most recent report"""
        report = self._load_report()
        
        if not report:
            print("No report found. Run a scan first.")
            return
        
        print("\n" + "=" * 80)
        print("BATCH METADATA REPORT")
        print("=" * 80)
        print(f"Scan Date: {report.scan_date}")
        print(f"Total Files: {report.total_files}")
        print()
        
        # File format breakdown
        print("FILES BY FORMAT:")
        for format_name, count in sorted(report.files_by_format.items()):
            print(f"  {format_name}: {count}")
        print()
        
        # Metadata completeness
        print("METADATA COMPLETENESS:")
        print(f"  Files with basic metadata: {report.files_with_basic_metadata} ({report.files_with_basic_metadata/report.total_files*100:.1f}%)")
        print(f"  Files with complete metadata: {report.files_with_complete_metadata} ({report.files_with_complete_metadata/report.total_files*100:.1f}%)")
        print(f"  Files needing correction: {report.files_needing_correction} ({report.files_needing_correction/report.total_files*100:.1f}%)")
        print(f"  Files without metadata: {report.files_without_metadata} ({report.files_without_metadata/report.total_files*100:.1f}%)")
        print()
        
        # Most common issues
        if report.common_missing_fields:
            print("MOST COMMON MISSING FIELDS:")
            sorted_missing = sorted(report.common_missing_fields.items(), key=lambda x: x[1], reverse=True)
            for field, count in sorted_missing[:10]:
                print(f"  {field}: {count} files")
            print()
        
        if report.common_validation_errors:
            print("MOST COMMON VALIDATION ERRORS:")
            sorted_errors = sorted(report.common_validation_errors.items(), key=lambda x: x[1], reverse=True)
            for error, count in sorted_errors[:10]:
                print(f"  {error}: {count} files")
            print()
        
        # Processing summary (if available)
        if report.files_processed > 0:
            print("PROCESSING SUMMARY:")
            print(f"  Files processed: {report.files_processed}")
            print(f"  Files fixed: {report.files_fixed}")
            print(f"  Processing errors: {report.processing_errors}")
            print()
        
        # Detailed file listing
        if detailed and report.file_statuses:
            print("DETAILED FILE STATUS:")
            print("-" * 80)
            
            # Sort by completeness (incomplete first)
            sorted_files = sorted(report.file_statuses, 
                                key=lambda x: (x.has_complete_metadata, x.has_basic_metadata))
            
            for i, status in enumerate(sorted_files[:50]):  # Limit to first 50
                filename = os.path.basename(status.file_path)
                status_str = "✓ Complete" if status.has_complete_metadata else "⚠ Incomplete" if status.has_basic_metadata else "✗ Missing"
                print(f"  {filename}")
                print(f"    Status: {status_str}")
                if status.missing_fields:
                    print(f"    Missing: {', '.join(status.missing_fields)}")
                if status.validation_errors:
                    print(f"    Errors: {', '.join(status.validation_errors[:2])}")
                print()
                
                if i >= 49 and len(sorted_files) > 50:
                    print(f"    ... and {len(sorted_files) - 50} more files")
                    break

async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Batch Metadata Processor for CLI Music Downloader",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    ./batch_metadata.py --scan ~/Music
    ./batch_metadata.py --fix ~/Music/Adele
    ./batch_metadata.py --report
    ./batch_metadata.py --report --detailed
    ./batch_metadata.py --fix ~/Music --dry-run
        """
    )
    
    parser.add_argument(
        '--scan', 
        metavar='DIRECTORY',
        help='Scan directory for incomplete metadata'
    )
    
    parser.add_argument(
        '--fix', 
        metavar='DIRECTORY',
        help='Fix metadata for files in directory'
    )
    
    parser.add_argument(
        '--report', 
        action='store_true',
        help='Display the most recent scan report'
    )
    
    parser.add_argument(
        '--detailed', 
        action='store_true',
        help='Show detailed file-by-file report (use with --report)'
    )
    
    parser.add_argument(
        '--dry-run', 
        action='store_true',
        help='Show what would be fixed without making changes (use with --fix)'
    )
    
    parser.add_argument(
        '--config', 
        action='store_true',
        help='Show current configuration'
    )
    
    parser.add_argument(
        '--verbose', '-v', 
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Initialize processor
    processor = BatchMetadataProcessor()
    
    try:
        if args.config:
            print("Current Configuration:")
            print(json.dumps(processor.config, indent=2))
        
        elif args.scan:
            directory = os.path.expanduser(args.scan)
            if not os.path.exists(directory):
                print(f"Error: Directory does not exist: {directory}")
                sys.exit(1)
            
            report = await processor.scan_directory(directory)
            processor.display_report(detailed=False)
        
        elif args.fix:
            directory = os.path.expanduser(args.fix)
            if not os.path.exists(directory):
                print(f"Error: Directory does not exist: {directory}")
                sys.exit(1)
            
            results = await processor.fix_metadata(directory, dry_run=args.dry_run)
            
            if args.dry_run:
                print(f"\n[DRY RUN] Would have processed {results['processed']} files")
                print(f"[DRY RUN] Would have fixed {results['fixed']} files")
                print(f"[DRY RUN] {results['errors']} files had errors")
            else:
                print(f"\nProcessed {results['processed']} files")
                print(f"Fixed {results['fixed']} files")
                print(f"{results['errors']} files had errors")
        
        elif args.report:
            processor.display_report(detailed=args.detailed)
        
        else:
            parser.print_help()
    
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    asyncio.run(main())

