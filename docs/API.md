# Technical Documentation

## Architecture Overview

The CLI Music Downloader consists of three main components:

1. **`download_music`** - Main bash script that orchestrates the download process
2. **`fixalbumart_improved`** - Python script for album art processing
3. **`download_music.yaml`** - Warp Terminal workflow configuration

## Component Details

### download_music (Bash Script)

**Purpose**: Main entry point that downloads audio and coordinates album art processing.

**Process Flow**:
1. Parse command-line arguments
2. Create output directory structure
3. Scan for existing MP3 files (for delta detection)
4. Execute `instantmusic` for audio download
5. Detect newly downloaded files
6. Extract artist/track from search term
7. Process album art for new files
8. Report results

**Key Functions**:
- Argument parsing and validation
- File delta detection (before/after comparison)
- Artist/track extraction from search terms
- Error handling and user feedback

### fixalbumart_improved (Python Script)

**Purpose**: Fetch and embed high-quality album artwork into MP3 files.

**Dependencies**:
- `requests` - HTTP client for API calls and image downloads
- `eyed3` - ID3 tag manipulation
- `urllib.parse` - URL encoding

**Album Art Sources**:

1. **iTunes API** (Primary)
   - Endpoint: `https://itunes.apple.com/search`
   - Parameters: `term`, `media=music`, `limit=1`
   - Returns: JSON with artwork URLs
   - Quality: 600x600px (upscaled from 100x100)

2. **Google Images** (Fallback)
   - Endpoint: `https://www.google.com/search?tbm=isch`
   - Method: HTML scraping with regex
   - Quality: Variable (filtered 1KB-5MB)
   - Headers: User-Agent spoofing for access

**Image Processing**:
- Format detection (JPEG, PNG, WebP)
- Size validation (1KB minimum, 5MB maximum)
- Automatic format conversion for ID3 compatibility
- Error handling for network failures

### Warp Workflow

**File**: `download_music.yaml`

**Structure**:
```yaml
name: String               # Workflow display name
description: String        # Workflow description
command: String            # Multi-line bash command
arguments: Array           # Input parameter definitions
tags: Array               # Searchable tags
examples: Array           # Usage examples
author: String            # Author information
version: String           # Version number
```

**Template Variables**:
- `{{song_query}}` - User input for artist and song

## APIs and External Services

### iTunes Search API

**Base URL**: `https://itunes.apple.com/search`

**Parameters**:
- `term` - Search query (URL encoded)
- `media` - Media type (fixed to "music")
- `limit` - Result limit (fixed to 1)

**Response Format**:
```json
{
  "resultCount": 1,
  "results": [
    {
      "artworkUrl100": "https://is1-ssl.mzstatic.com/image/thumb/.../100x100bb.jpg",
      "artistName": "Artist Name",
      "trackName": "Track Name",
      "collectionName": "Album Name"
    }
  ]
}
```

**Image Quality Enhancement**:
- Replace `100x100bb.jpg` with `600x600bb.jpg` for higher resolution

### Google Images (Fallback)

**URL Pattern**: `https://www.google.com/search?tbm=isch&q={query}`

**Scraping Method**:
- Regex pattern: `r'"(https?://[^"]*\.(?:jpg|jpeg|png|webp))'`
- User-Agent spoofing required
- Rate limiting considerations

**Quality Filtering**:
- HTTP HEAD requests to check file size
- Content-Length header validation
- Size range: 1KB - 5MB

### YouTube (via instantmusic/yt-dlp)

**Process**:
1. Search YouTube for audio content
2. Extract audio stream using yt-dlp
3. Convert to MP3 format
4. Apply basic ID3 tags
5. Organize into artist directories

## File Organization

### Directory Structure
```
~/Music/
├── <Artist>/
│   ├── <Song1>.mp3
│   ├── <Song2>.mp3
│   └── ...
└── <Artist2>/
    └── ...
```

### ID3 Tag Structure
```
ID3v2.4:
├── TIT2 (Title): Song Name
├── TPE1 (Artist): Artist Name
├── TALB (Album): Album Name (if available)
├── APIC (Attached Picture):
│   ├── Type: 0 (Front Cover)
│   ├── MIME: image/jpeg|image/png|image/webp
│   └── Data: Binary image data
└── ...
```

## Error Handling

### Network Errors
- **Connection timeouts**: Retry with exponential backoff
- **HTTP errors**: Fallback to alternative sources
- **DNS failures**: User notification and graceful degradation

### File System Errors
- **Permission denied**: Clear error messages with solutions
- **Disk space**: Early detection and user warnings
- **File conflicts**: Automatic deduplication strategies

### Processing Errors
- **Invalid audio**: Format validation and conversion
- **Corrupt downloads**: Checksum validation where possible
- **Tag writing failures**: Fallback to basic tags

## Performance Considerations

### Optimization Strategies
- **Parallel processing**: Multiple album art sources queried simultaneously
- **Caching**: Avoid re-downloading existing album art
- **Streaming**: Process audio without full file downloads where possible

### Resource Usage
- **Memory**: ~50-100MB during processing
- **CPU**: High during audio extraction, low during art processing
- **Network**: Burst usage during download, minimal for art fetching
- **Disk**: Temporary files cleaned up automatically

## Security Considerations

### Data Privacy
- **No personal data collection**: All processing is local
- **Search queries**: Sent to iTunes API and Google (standard web requests)
- **IP address**: Visible to service providers (normal web usage)

### File Safety
- **No file overwrites**: Delta detection prevents accidental replacements
- **Path traversal protection**: Input validation for file paths
- **Executable safety**: No dynamic code execution from downloads

## Extensibility

### Adding New Album Art Sources

```python
def new_art_source(artist, track):
    """Template for new album art sources"""
    try:
        # Implement API call or scraping
        response = requests.get(f"https://api.example.com/search?artist={artist}&track={track}")
        data = response.json()
        return data.get('image_url')
    except Exception as e:
        print(f"New source failed: {e}")
        return None

# Add to grab_albumart() function before existing sources
```

### Custom Output Formats

Modify the `download_music` script to support different organization schemes:

```bash
# Example: Genre-based organization
if [[ "$genre_mode" == "true" ]]; then
    output_dir="$HOME/Music/$genre/$artist"
else
    output_dir="$HOME/Music/$artist"
fi
```

### Integration APIs

The scripts can be integrated into other applications:

```bash
# Return machine-readable status
download_music --json "Artist Song" | jq '.status'

# Batch processing with status reporting
echo "Artist1 Song1\nArtist2 Song2" | xargs -I {} download_music "{}"
```

## Testing

### Unit Testing Framework

```bash
# Test album art fetching
python3 -c "
import sys
sys.path.append('bin')
from fixalbumart_improved import grab_albumart
result = grab_albumart('The Beatles', 'Hey Jude')
print('PASS' if result else 'FAIL')
"
```

### Integration Testing

```bash
# Test complete workflow
test_song="Test Artist Test Song"
download_music "$test_song"
if [[ -f ~/Music/Test\ Artist/Test\ Song*.mp3 ]]; then
    echo "PASS: Download successful"
else
    echo "FAIL: Download failed"
fi
```

## Monitoring and Logging

### Debug Mode

```bash
# Enable verbose output
export DEBUG=1
download_music "Artist Song"
```

### Performance Metrics

```bash
# Time tracking
time download_music "Artist Song"

# Memory usage
/usr/bin/time -l download_music "Artist Song"
```

## Version Compatibility

### Python Versions
- **Minimum**: Python 3.8
- **Recommended**: Python 3.9+
- **Tested**: Python 3.8, 3.9, 3.10, 3.11

### macOS Versions
- **Minimum**: macOS Big Sur (11.0)
- **Recommended**: macOS Monterey (12.0)+
- **Tested**: macOS Big Sur through Sonoma

### Shell Compatibility
- **Primary**: zsh (default on macOS)
- **Secondary**: bash 4.0+
- **Features**: BASH_REMATCH regex support required

