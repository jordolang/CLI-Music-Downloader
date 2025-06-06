# Enhanced Metadata Functionality

The CLI Music Downloader now supports enhanced metadata functionality with integrated MusicBrainz API lookup and multiple metadata sources.

## Features

### 🎼 MusicBrainz Integration
- Automatic lookup of comprehensive metadata from MusicBrainz database
- Artist, album, track number, year, genre, and more
- MusicBrainz IDs stored for future reference
- Release group information for better genre classification

### 🎧 Multiple Metadata Sources
- **MusicBrainz**: Comprehensive music database
- **Shazam**: Audio fingerprinting for identification
- **Genius**: Lyrics lookup
- **All**: Use all available sources (default)

### 🚀 Enhanced Download Script

The new Python implementation (`scripts/download_music.py`) provides:

- Integrated metadata enhancement during download
- Multiple command-line options for fine-grained control
- Automatic fallback to filename parsing
- Comprehensive logging and error handling

## Usage

### Basic Usage
```bash
# Use the enhanced script directly
python3 scripts/download_music.py "The Beatles Hey Jude"

# Or use the wrapper script for automatic selection
./bin/download_music_enhanced "Pink Floyd - Comfortably Numb"
```

### Command Line Options

#### Metadata Control
```bash
# Skip metadata enhancement entirely
download_music.py "Artist Song" --skip-metadata

# Force metadata refresh even if tags exist
download_music.py "Artist Song" --force-metadata

# Choose specific metadata source
download_music.py "Artist Song" --metadata-source musicbrainz
download_music.py "Artist Song" --metadata-source shazam
download_music.py "Artist Song" --metadata-source all  # default
```

#### Artist/Title Hints
```bash
# Provide explicit artist and title
download_music.py "search term" --artist "The Beatles" --title "Hey Jude"

# Override automatic parsing
download_music.py "Beatles Hey Jude" --artist "The Beatles" --title "Hey Jude"
```

#### API Keys
```bash
# Provide Genius API key for lyrics
download_music.py "Artist Song" --genius-key YOUR_KEY

# Or set environment variable
export GENIUS_API_KEY=your_key_here
download_music.py "Artist Song"
```

#### Logging
```bash
# Verbose output
download_music.py "Artist Song" --verbose

# Quiet mode (errors only)
download_music.py "Artist Song" --quiet
```

### Enhanced Wrapper Script

The `download_music_enhanced` script provides automatic selection between implementations:

```bash
# Automatically use Python implementation if available
download_music_enhanced "Artist Song"

# Force Python implementation
download_music_enhanced "Artist Song" --python

# Force original bash implementation
download_music_enhanced "Artist Song" --bash

# All Python script options are supported
download_music_enhanced "Artist Song" --metadata-source musicbrainz --force-metadata
```

## Implementation Details

### Enhanced Metadata Flow

1. **Download Phase**: Uses `instantmusic` to download audio
2. **Album Art Phase**: Uses existing `fixalbumart_improved` script
3. **Metadata Enhancement Phase**:
   - Parse artist/title from search term or filename
   - Query MusicBrainz for comprehensive metadata
   - Optionally use audio fingerprinting (Shazam)
   - Fetch lyrics from Genius API
   - Apply all metadata to MP3 file using mutagen

### MusicBrainz Metadata

The MusicBrainz integration provides:

- **Basic Info**: Artist, title, album, year
- **Track Info**: Track number, total tracks, disc number
- **IDs**: MusicBrainz recording, artist, and release IDs
- **Genre**: Extracted from release group tags
- **Detailed Matching**: Smart artist credit handling

### Code Structure

```python
class MusicBrainzMetadata:
    """Handler for MusicBrainz metadata lookup"""
    
    def search_recording(self, artist, title):
        # Query MusicBrainz API
        # Extract comprehensive metadata
        # Return structured metadata dict

class EnhancedMusicDownloader:
    """Enhanced music downloader with integrated metadata"""
    
    def download_audio(self, search_term):
        # Download using instantmusic
        # Track new files
    
    def enhance_metadata(self, file_path, artist_hint, title_hint):
        # Query MusicBrainz
        # Use audio fingerprinting
        # Fetch lyrics
        # Apply comprehensive metadata
    
    def download_and_process(self, search_term, artist_hint, title_hint):
        # Complete pipeline:
        # 1. Download audio
        # 2. Add album art
        # 3. Enhance metadata
```

## Dependencies

Ensure all dependencies are installed:

```bash
pip install -r requirements.txt
```

Key new dependencies:
- `musicbrainzngs`: MusicBrainz API client
- `mutagen`: Advanced MP3 metadata handling
- `eyed3`: ID3 tag manipulation

## Migration from Original Script

### Backward Compatibility

The original bash script (`bin/download_music`) continues to work unchanged. The enhanced functionality is available through:

1. **Direct Python script**: `scripts/download_music.py`
2. **Enhanced wrapper**: `bin/download_music_enhanced`

### Feature Comparison

| Feature | Original Script | Enhanced Script |
|---------|----------------|----------------|
| Audio Download | ✅ instantmusic | ✅ instantmusic |
| Album Art | ✅ fixalbumart_improved | ✅ fixalbumart_improved |
| Basic Metadata | ✅ filename parsing | ✅ enhanced parsing |
| MusicBrainz Lookup | ❌ | ✅ comprehensive |
| Audio Fingerprinting | ❌ | ✅ Shazam integration |
| Lyrics | ✅ basic Genius | ✅ enhanced Genius |
| Metadata Control | ❌ | ✅ skip/force/source |
| Error Handling | ✅ basic | ✅ comprehensive |
| Logging | ✅ basic | ✅ configurable |

## Examples

### Download with MusicBrainz metadata only
```bash
download_music.py "Radiohead Creep" --metadata-source musicbrainz
```

### Download without any metadata enhancement
```bash
download_music.py "Song Name" --skip-metadata
```

### Download with forced metadata refresh
```bash
download_music.py "Artist - Song" --force-metadata
```

### Download with explicit artist/title and verbose logging
```bash
download_music.py "search term" --artist "The Beatles" --title "Yesterday" --verbose
```

### Use enhanced wrapper with automatic fallback
```bash
download_music_enhanced "Queen - Bohemian Rhapsody"
```

The enhanced functionality provides a powerful, flexible, and comprehensive solution for downloading music with rich metadata while maintaining backward compatibility with existing workflows.

