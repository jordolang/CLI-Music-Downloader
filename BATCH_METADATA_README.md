# Batch Metadata Processor

The `batch_metadata.py` script provides comprehensive batch processing capabilities for music metadata management. It can scan music libraries, generate detailed reports, and automatically fix incomplete or incorrect metadata.

## Features

### 1. Library Scanning
- Recursively scans directories for supported audio files
- Supports MP3, FLAC, M4A, MP4, OGG, and WMA formats
- Analyzes metadata completeness and quality
- Identifies missing fields and validation errors
- Multi-threaded processing for large libraries

### 2. Comprehensive Reporting
- Detailed metadata completeness statistics
- File format breakdown
- Most common missing fields
- Validation error summaries
- File-by-file detailed reports
- Persistent report storage

### 3. Batch Metadata Enhancement
- Automatic metadata lookup from MusicBrainz, Last.fm, and Discogs
- Intelligent field validation and correction
- Backup creation before modifications
- Dry-run mode for safe testing
- Rate limiting to respect API guidelines

## Installation

1. Ensure all dependencies are installed:
```bash
pip install -r requirements.txt
```

2. The script uses a virtual environment. If not already created:
```bash
python3 -m venv venv
source venv/bin/activate
pip install mutagen requests musicbrainzngs eyed3 pylast discogs-client
```

## Usage

### Basic Commands

#### Scan a Music Library
```bash
./batch_metadata.py --scan ~/Music
```
Recursively scans the specified directory and generates a comprehensive report of metadata completeness.

#### Fix Metadata for Specific Directory
```bash
./batch_metadata.py --fix ~/Music/Adele
```
Automatically enhances metadata for all music files in the specified directory.

#### View Latest Report
```bash
./batch_metadata.py --report
```
Displays the most recent scan report with summary statistics.

#### Detailed File Report
```bash
./batch_metadata.py --report --detailed
```
Shows detailed file-by-file status including missing fields and validation errors.

### Advanced Options

#### Dry Run Mode
```bash
./batch_metadata.py --fix ~/Music --dry-run
```
Shows what would be fixed without making any actual changes to files.

#### Verbose Logging
```bash
./batch_metadata.py --scan ~/Music --verbose
```
Enables detailed logging for troubleshooting.

#### View Configuration
```bash
./batch_metadata.py --config
```
Displays current configuration settings.

## Configuration

The script uses a configuration file stored at `~/.batch_metadata_config.json`. You can customize:

### API Keys (Optional but Recommended)
- **LASTFM_API_KEY**: Last.fm API key for enhanced metadata
- **LASTFM_API_SECRET**: Last.fm API secret
- **DISCOGS_USER_TOKEN**: Discogs user token for release information

### Processing Settings
- **required_fields**: Fields that must be present (default: title, artist, album, year)
- **optional_fields**: Fields that should be present (default: track_number, genre, album_artist)
- **max_workers**: Number of parallel processing threads (default: 4)
- **delay_between_requests**: Delay between API requests in seconds (default: 1.0)
- **backup_original_files**: Create backups before modifying files (default: true)

### Setting API Keys

You can set API keys via environment variables:
```bash
export LASTFM_API_KEY="your_lastfm_api_key"
export LASTFM_API_SECRET="your_lastfm_api_secret"
export DISCOGS_USER_TOKEN="your_discogs_token"
```

Or by editing the configuration file directly:
```json
{
  "lastfm_api_key": "your_api_key",
  "lastfm_api_secret": "your_api_secret",
  "discogs_user_token": "your_token"
}
```

## Output Examples

### Scan Report
```
================================================================================
BATCH METADATA REPORT
================================================================================
Scan Date: 2024-06-06T11:42:12
Total Files: 1,247

FILES BY FORMAT:
  .mp3: 892
  .flac: 203
  .m4a: 152

METADATA COMPLETENESS:
  Files with basic metadata: 1,089 (87.3%)
  Files with complete metadata: 734 (58.9%)
  Files needing correction: 245 (19.6%)
  Files without metadata: 158 (12.7%)

MOST COMMON MISSING FIELDS:
  genre: 513 files
  album_artist: 289 files
  track_number: 167 files
  year: 89 files
```

### Processing Results
```
Processed 45 files
Fixed 32 files
8 files had errors
```

## Supported Metadata Sources

1. **MusicBrainz** (Primary): Comprehensive music database with high-quality metadata
2. **Last.fm**: Popular music platform with extensive genre and artist information
3. **Discogs**: Detailed release information and catalog data

## File Format Support

- **MP3**: Full ID3v2 tag support
- **FLAC**: Vorbis comment support
- **M4A/MP4**: iTunes-style metadata
- **OGG**: Vorbis comment support
- **WMA**: Basic tag support

## Safety Features

- **Automatic Backups**: Original files are backed up before modification
- **Dry Run Mode**: Test changes without modifying files
- **Validation**: Metadata is validated before application
- **Error Handling**: Graceful handling of corrupted or unsupported files
- **Rate Limiting**: Respects API rate limits to avoid service blocks

## Performance

- **Multi-threaded**: Processes multiple files simultaneously
- **Efficient Scanning**: Fast metadata extraction using optimized libraries
- **Progress Tracking**: Real-time progress updates for large libraries
- **Incremental Processing**: Skip files that already have complete metadata

## Troubleshooting

### Common Issues

1. **No metadata providers available**: Install missing packages or set API keys
2. **Permission errors**: Ensure write access to music directories
3. **Unsupported file formats**: Check that files are valid audio files
4. **API rate limiting**: Increase delay_between_requests in config

### Debug Mode
```bash
./batch_metadata.py --scan ~/Music --verbose
```

### Log Files
Detailed logs are written to the console. Use `--verbose` for additional debugging information.

## Integration

The batch processor integrates seamlessly with the existing CLI Music Downloader metadata system:

- Uses the same MetadataManager class for consistency
- Applies the same validation and correction rules
- Compatible with all existing metadata sources
- Maintains the same file format support

This ensures that batch-processed metadata follows the same quality standards as individually processed files.

