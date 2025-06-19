# Enhanced CLI Music Downloader Usage Examples

This document provides comprehensive usage examples for the CLI Music Downloader with enhanced metadata features.

## Table of Contents

1. [Basic Downloads](#basic-downloads)
2. [Enhanced Metadata Features](#enhanced-metadata-features) 
3. [Batch Processing](#batch-processing)
4. [Common Use Cases](#common-use-cases)
5. [Troubleshooting Examples](#troubleshooting-examples)

---

## Basic Downloads

### Simple Downloads with Enhanced Metadata
```bash
# Download with automatic metadata enhancement
download_music "The Beatles Hey Jude"
download_music "Pink Floyd - Comfortably Numb"
download_music "Queen Bohemian Rhapsody"
```

### Using the Enhanced Python Script
```bash
# Use the enhanced downloader directly
python3 scripts/download_music.py "Radiohead Creep"
python3 scripts/download_music.py "Led Zeppelin Stairway to Heaven"
```

---

## Enhanced Metadata Features

### Download with Full Metadata from MusicBrainz
```bash
# Example from the task requirements
download_music "https://example.com/song" --metadata-source musicbrainz

# Download specific songs with MusicBrainz metadata
download_music "The Beatles Yesterday" --metadata-source musicbrainz
download_music "Pink Floyd Wish You Were Here" --metadata-source musicbrainz
```

### Metadata Source Selection
```bash
# Use MusicBrainz only
download_music "Adele Rolling in the Deep" --metadata-source musicbrainz

# Use Shazam audio fingerprinting
download_music "Unknown Song File" --metadata-source shazam

# Use all available sources (default)
download_music "Artist Song" --metadata-source all
```

### Force Metadata Refresh
```bash
# Force metadata refresh for existing files
download_music "Artist Song" --force-metadata

# Combine with specific source
download_music "The Beatles Hey Jude" --force-metadata --metadata-source musicbrainz
```

### Skip Metadata Enhancement
```bash
# Download without metadata enhancement
download_music "Artist Song" --skip-metadata

# Useful for quick downloads or network issues
download_music "Quick Download" --skip-metadata
```

### Provide Explicit Artist and Title
```bash
# Provide explicit metadata hints
download_music "search term" --artist "The Beatles" --title "Hey Jude"
download_music "unclear filename" --artist "Pink Floyd" --title "Comfortably Numb"
```

---

## Batch Processing

### Fix Metadata for Existing Files
```bash
# Example from the task requirements  
batch_metadata.py --fix "Adele - Rolling in the Deep.mp3"

# Fix metadata for specific files
batch_metadata.py --fix "~/Music/Beatles - Yesterday.mp3"
batch_metadata.py --fix "~/Music/Queen/Bohemian Rhapsody.mp3"
```

### Scan Music Library
```bash
# Scan entire music library for metadata issues
batch_metadata.py --scan ~/Music

# Scan specific artist directory
batch_metadata.py --scan ~/Music/The Beatles

# Scan and generate detailed report
batch_metadata.py --scan ~/Music --verbose
```

### View Metadata Reports
```bash
# View summary report
batch_metadata.py --report

# View detailed file-by-file report
batch_metadata.py --report --detailed

# View configuration
batch_metadata.py --config
```

### Dry Run Operations
```bash
# See what would be fixed without making changes
batch_metadata.py --fix ~/Music/Artist --dry-run

# Dry run with verbose output
batch_metadata.py --fix ~/Music --dry-run --verbose
```

---

## Common Use Cases

### Organizing a New Music Collection
```bash
# Step 1: Download with enhanced metadata
download_music "The Beatles Abbey Road" --metadata-source all
download_music "Pink Floyd Dark Side of the Moon" --metadata-source all
download_music "Queen A Night at the Opera" --metadata-source all

# Step 2: Scan for any metadata issues
batch_metadata.py --scan ~/Music

# Step 3: Fix any problems found
batch_metadata.py --fix ~/Music --verbose
```

### Cleaning Up Existing Library
```bash
# Generate comprehensive metadata report
batch_metadata.py --scan ~/Music
batch_metadata.py --report --detailed > music_library_report.txt

# Fix files with incomplete metadata
batch_metadata.py --fix ~/Music --verbose

# Verify improvements
batch_metadata.py --scan ~/Music
batch_metadata.py --report
```

### Genre-Specific Processing
```bash
# Classical music (complex metadata)
download_music "Mozart Symphony No. 40" --artist "Wolfgang Amadeus Mozart" --metadata-source musicbrainz

# Electronic music (may need fingerprinting)
download_music "Daft Punk Get Lucky" --metadata-source all

# Rock music (standard processing)
download_music "Led Zeppelin Stairway to Heaven" --metadata-source musicbrainz
```

### Processing Different Audio Formats
```bash
# Fix metadata for various formats
batch_metadata.py --fix "~/Music/song.mp3"
batch_metadata.py --fix "~/Music/song.flac"
batch_metadata.py --fix "~/Music/song.m4a"

# Batch process multiple formats
find ~/Music -name "*.mp3" -o -name "*.flac" -o -name "*.m4a" | xargs -I {} batch_metadata.py --fix "{}"
```

---

## Troubleshooting Examples

### Missing Metadata Issues
```bash
# Diagnose missing metadata
batch_metadata.py --scan ~/Music/problematic_file.mp3

# Try different metadata sources
download_music "Artist Song" --metadata-source musicbrainz --force-metadata
download_music "Artist Song" --metadata-source shazam --force-metadata

# Provide explicit artist/title information
download_music "unclear search" --artist "Exact Artist" --title "Exact Title"
```

### Incorrect Metadata Issues
```bash
# Force refresh with specific source
batch_metadata.py --fix "path/to/file.mp3" --verbose

# Check validation errors
batch_metadata.py --report --detailed | grep -i error

# Manual correction with explicit metadata
python3 scripts/download_music.py "search" --artist "Correct Artist" --title "Correct Title" --force-metadata
```

### Network and API Issues
```bash
# Skip metadata if network issues persist
download_music "Artist Song" --skip-metadata

# Process metadata later when network is stable
batch_metadata.py --fix ~/Music/newly_downloaded

# Use batch processing with built-in delays
batch_metadata.py --fix ~/Music --verbose
```

### API Rate Limiting
```bash
# Configure rate limiting in ~/.batch_metadata_config.json
# {
#   "delay_between_requests": 2.0,
#   "max_workers": 2
# }

# Process with delays
batch_metadata.py --fix ~/Music --verbose

# Wait and retry if rate limited
sleep 1800 && batch_metadata.py --fix ~/Music
```

### Audio Fingerprinting Issues
```bash
# Check file format compatibility
file "problematic_file.mp3"

# Use alternative metadata sources
download_music "Artist Song" --metadata-source musicbrainz

# Verify file integrity
ffprobe "file.mp3" 2>&1 | grep -i error
```

---

## Advanced Configuration Examples

### API Key Setup
```bash
# Set environment variables for enhanced features
export GENIUS_API_KEY="your_genius_api_key"
export LASTFM_API_KEY="your_lastfm_api_key"
export LASTFM_API_SECRET="your_lastfm_secret"
export DISCOGS_USER_TOKEN="your_discogs_token"

# Use with specific API key
download_music "Artist Song" --genius-key "your_key_here"
```

### Custom Configuration
```bash
# Copy example configuration
cp examples/config_example.json ~/.batch_metadata_config.json

# Edit configuration as needed
# nano ~/.batch_metadata_config.json

# View current configuration
batch_metadata.py --config
```

### Verbose and Debug Mode
```bash
# Enable verbose logging
download_music "Artist Song" --verbose
batch_metadata.py --fix ~/Music --verbose

# Quiet mode (errors only)
download_music "Artist Song" --quiet

# Debug metadata manager directly
python3 -c "
import logging
logging.basicConfig(level=logging.DEBUG)
from scripts.metadata_manager import MetadataManager
import asyncio
manager = MetadataManager()
result = asyncio.run(manager.get_metadata('The Beatles', 'Hey Jude'))
print(result)
"
```

---

## Performance Optimization

### Large Library Processing
```bash
# Process in smaller chunks
find ~/Music -maxdepth 1 -type d -exec batch_metadata.py --fix {} \;

# Optimize configuration for large libraries
# Edit ~/.batch_metadata_config.json:
# {
#   "max_workers": 8,
#   "delay_between_requests": 0.5
# }

# Process incrementally
batch_metadata.py --scan ~/Music
batch_metadata.py --fix ~/Music --verbose
```

### Memory and CPU Optimization
```bash
# Reduce worker threads for memory-constrained systems
# Config: "max_workers": 2

# Add processing delays for CPU optimization
# Config: "delay_between_requests": 2.0

# Monitor resource usage
top -pid $(pgrep -f batch_metadata)
```

---

## Integration Examples

### Shell Script Automation
```bash
#!/bin/bash
# enhanced_playlist_download.sh

PLAYLIST=(
  "The Beatles Hey Jude"
  "Queen Bohemian Rhapsody"
  "Pink Floyd Comfortably Numb"
  "Led Zeppelin Stairway to Heaven"
)

for song in "${PLAYLIST[@]}"; do
  echo "Downloading: $song"
  download_music "$song" --metadata-source all --verbose
  sleep 5  # Rate limiting
done

# Run metadata verification
batch_metadata.py --scan ~/Music
batch_metadata.py --report
```

### Backup and Recovery
```bash
# Enable automatic backups in configuration
# "backup_original_files": true

# Manual backup before batch processing
cp -r ~/Music ~/Music_backup_$(date +%Y%m%d)

# Process with backups enabled
batch_metadata.py --fix ~/Music --verbose
```

---

## Quality Assurance Workflows

### Complete Metadata Validation
```bash
# Step 1: Download with comprehensive metadata
download_music "Artist Song" --metadata-source all --verbose

# Step 2: Verify metadata quality
batch_metadata.py --scan ~/Music/Artist

# Step 3: Generate quality report
batch_metadata.py --report --detailed | grep -E "(validation|error|missing)"

# Step 4: Fix any issues found
batch_metadata.py --fix ~/Music/Artist --verbose

# Step 5: Final verification
batch_metadata.py --scan ~/Music/Artist
```

### Metadata Source Comparison
```bash
# Download same song with different sources for comparison
download_music "Test Song" --metadata-source musicbrainz --force-metadata
cp "~/Music/Artist/Test Song.mp3" "~/Music/Artist/Test Song (MusicBrainz).mp3"

download_music "Test Song" --metadata-source shazam --force-metadata  
cp "~/Music/Artist/Test Song.mp3" "~/Music/Artist/Test Song (Shazam).mp3"

# Compare metadata quality
batch_metadata.py --scan ~/Music/Artist
batch_metadata.py --report --detailed
```

These examples demonstrate the full range of enhanced metadata capabilities and should help you make the most of the CLI Music Downloader's new features!

