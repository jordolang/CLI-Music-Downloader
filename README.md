# CLI Music Downloader

🎵 **A powerful command-line music downloader with automatic album artwork and intelligent organization**

[![Platform](https://img.shields.io/badge/platform-macOS-blue.svg)](https://www.apple.com/macos/)
[![Shell](https://img.shields.io/badge/shell-zsh%20%7C%20bash-green.svg)](https://www.zsh.org/)
[![License](https://img.shields.io/badge/license-MIT-orange.svg)](LICENSE)

By The Way! This is my first major software release. If you enjoyed this tool please consider donating via the following link:
<a href="https://www.buymeacoffee.com/jordolang" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 60px !important;width: 217px !important;" ></a>

## ✨ Features

- 🎵 **High-quality music downloads** from YouTube with optimal audio extraction
- 🎨 **Automatic album artwork** fetching from iTunes API and Google Images
- 📁 **Smart organization** by artist in `~/Music/<Artist>/<Song>.mp3`
- 🏷️ **Enhanced metadata system** with MusicBrainz, Last.fm, and Discogs integration
- 🎼 **MusicBrainz integration** for comprehensive music metadata
- 🎧 **Audio fingerprinting** with Shazam for accurate song identification
- 📝 **Automatic lyrics** fetching and embedding from Genius API
- 🔧 **Warp Terminal integration** with custom workflows
- 🛠️ **Robust error handling** and fallback mechanisms
- 📱 **Multiple image formats** support (JPEG, PNG, WebP)
- 🔍 **Intelligent search** with artist/track parsing
- 📊 **Batch processing** for existing music libraries
- ⚙️ **Flexible metadata sources** with a priority system

## 🚀 Quick Start

### Prerequisites

- macOS (tested on macOS Monterey+)
- Python 3.8+ with pip
- Homebrew (for system dependencies)
- Warp Terminal (optional, for workflow integration)

### System Dependencies

The downloader uses several metadata management tools that need to be installed via Homebrew:

```bash
brew install exiftool id3v2
```

- **exiftool**: Advanced metadata extraction and manipulation
- **id3v2**: Command-line ID3 tag editor for MP3 files

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/CLI-Music-Downloader.git
   cd CLI-Music-Downloader
   ```

2. **Run the installation script:**
   ```bash
   chmod +x scripts/install.sh
   ./scripts/install.sh
   ```

3. **Or install manually:**
   ```bash
   # Install core dependencies
   pip install instantmusic eyed3 requests
   
   # Install enhanced metadata dependencies
   pip install musicbrainzngs mutagen lyricsgenius shazamio pylast discogs-client
   
   # Copy scripts to local bin
   cp bin/download_music ~/.local/bin/
   cp bin/fixalbumart_improved ~/.local/bin/
   cp scripts/download_music.py ~/.local/bin/
   cp batch_metadata.py ~/.local/bin/
   chmod +x ~/.local/bin/download_music
   chmod +x ~/.local/bin/fixalbumart_improved
   chmod +x ~/.local/bin/download_music.py
   chmod +x ~/.local/bin/batch_metadata.py
   
   # Install Warp workflow (optional)
   mkdir -p ~/.config/warp/workflows
   cp workflows/download_music.yaml ~/.config/warp/workflows/
   ```

## 🎵 Usage

### Basic Downloads

```bash
# Download a song with enhanced metadata
download_music "The Beatles Hey Jude"
download_music "Pink Floyd - Comfortably Numb"
download_music "Queen Bohemian Rhapsody"
```

### Enhanced Metadata Features

```bash
# Download with full metadata from MusicBrainz
download_music "https://example.com/song" --metadata-source musicbrainz

# Download with specific metadata source
download_music "Adele Rolling in the Deep" --metadata-source all

# Force metadata refresh for existing files
download_music "Artist Song" --force-metadata

# Skip metadata enhancement entirely
download_music "Artist Song" --skip-metadata

# Provide explicit artist and title hints
download_music "search term" --artist "The Beatles" --title "Hey Jude"
```

### Batch Metadata Processing

```bash
# Fix metadata for existing files
batch_metadata.py --fix "Adele - Rolling in the Deep.mp3"

# Scan entire music library for metadata issues
batch_metadata.py --scan ~/Music

# View detailed metadata report
batch_metadata.py --report --detailed

# Dry run to see what would be fixed
batch_metadata.py --fix ~/Music/Artist --dry-run
```

### Warp Terminal Workflow

1. Open Warp Terminal
2. Press `Cmd+Shift+R` to open workflow picker
3. Type "Download Music" and select the workflow
4. Enter your search query (e.g., "Radiohead Creep")
5. Press Enter and enjoy! 🎉

### Album Art Fixer (Standalone)

```bash
# Fix album art for existing files
fixalbumart_improved "/path/to/song.mp3" "Artist Name" "Track Name"

# Auto-detect from filename (works with "Artist - Track.mp3" format)
fixalbumart_improved "/path/to/Artist - Track.mp3"
```

## 📁 Project Structure

```
CLI-Music-Downloader/
├── bin/
│   ├── download_music          # Main download script
│   └── fixalbumart_improved    # Album art processor
├── workflows/
│   └── download_music.yaml     # Warp Terminal workflow
├── scripts/
│   ├── install.sh                # Installation script
│   ├── uninstall.sh              # Uninstallation script
│   ├── download_music.py          # Enhanced Python downloader
│   ├── lyrics_metadata.py         # Lyrics and metadata handler
│   └── metadata_manager.py        # Multi-source metadata manager
├── batch_metadata.py              # Batch metadata processor
├── examples/
│   └── sample_usage.md         # Usage examples
├── docs/
│   ├── TROUBLESHOOTING.md      # Common issues and solutions
│   └── API.md                  # Technical documentation
├── README.md                   # This file
├── LICENSE                     # MIT License
└── requirements.txt            # Python dependencies
```

## 🔧 How It Works

1. **Download Audio**: Uses `instantmusic` (powered by yt-dlp) to download high-quality audio from YouTube
2. **Organize Files**: Automatically creates artist folders and moves files to `~/Music/<Artist>/`
3. **Fetch Album Art**: 
   - Primary: iTunes API for high-quality official artwork
   - Fallback: Google Images search with quality filtering
4. **Embed Metadata**: Uses `eyed3` to properly tag files and embed album artwork
5. **Error Recovery**: Graceful handling of network issues and missing artwork

## 📚 Metadata Sources and Priorities

The CLI Music Downloader uses multiple metadata sources to ensure comprehensive and accurate music information:

### 1. MusicBrainz (Primary Source)
- **Data Retrieved:** Artist, album, year, track numbers, genre, MusicBrainz IDs
- **Features:** Release group analysis, artist credit handling
- **Confidence:** High (90%)
- **Use Case:** Primary source for all metadata lookups

### 2. Shazam (Audio Fingerprinting)
- **Data Retrieved:** Artist, title, album (when available)
- **Features:** Audio identification from downloaded file
- **Confidence:** Medium-High (70%)
- **Use Case:** When filename parsing fails or metadata is missing

### 3. Genius (Lyrics)
- **Data Retrieved:** Song lyrics
- **Features:** Clean lyrics processing, embedded in ID3 tags
- **Integration:** Uses existing LyricsMetadataHandler
- **Use Case:** Lyrics enhancement for downloaded tracks

### 4. Last.fm (Genre and Artist Info)
- **Data Retrieved:** Genre tags, artist information, album details
- **Features:** Community-driven tagging, extensive database
- **Confidence:** Medium (60%)
- **Use Case:** Fallback for genre and additional artist information

### 5. Discogs (Release Information)
- **Data Retrieved:** Detailed release info, catalog numbers, formats
- **Features:** Comprehensive release database
- **Confidence:** Medium (60%)
- **Use Case:** Specialized release information and catalog data

### Source Selection Strategy
The system automatically selects the best source based on:
- Data availability and completeness
- Source reliability and confidence scores
- User preferences (via `--metadata-source` flag)
- Fallback hierarchy when primary sources fail

## 📍 Troubleshooting Common Metadata Issues

### Missing Metadata
**Symptoms:** Downloaded files have empty or incomplete metadata fields

**Solutions:**
```bash
# Force metadata refresh
download_music "Artist Song" --force-metadata

# Try different metadata source
download_music "Artist Song" --metadata-source musicbrainz

# Provide explicit artist/title hints
download_music "search term" --artist "Artist" --title "Song"
```

### Incorrect Metadata
**Symptoms:** Wrong artist, title, album, or other metadata fields

**Solutions:**
```bash
# Force metadata refresh with specific source
batch_metadata.py --fix "path/to/file.mp3" --dry-run

# Use batch processor to fix multiple files
batch_metadata.py --fix ~/Music/Artist --verbose
```

### API Rate Limiting
**Symptoms:** "Rate limit exceeded" or slow metadata fetching

**Solutions:**
- Wait before retrying requests
- Use batch processing with delays: `batch_metadata.py --fix ~/Music`
- Check API key configurations for Last.fm and Discogs

### Audio Fingerprinting Failures
**Symptoms:** Shazam identification not working

**Solutions:**
- Ensure audio file is not corrupted
- Try with different metadata source: `--metadata-source musicbrainz`
- Check file format compatibility (MP3, FLAC, M4A supported)

### Network Connectivity Issues
**Symptoms:** Metadata lookup timeouts or connection errors

**Solutions:**
```bash
# Skip metadata if network issues persist
download_music "Artist Song" --skip-metadata

# Run metadata enhancement later
batch_metadata.py --fix ~/Music/newly_downloaded
```

### Configuration Issues
**Symptoms:** Metadata sources not working despite correct setup

**Solutions:**
```bash
# View current configuration
batch_metadata.py --config

# Set API keys via environment variables
export GENIUS_API_KEY="your_key_here"
export LASTFM_API_KEY="your_key_here"
export DISCOGS_USER_TOKEN="your_token_here"
```

For extensive troubleshooting tips, visit the [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md).

---

## 🎨 Album Art Sources

### iTunes API (Primary)
- ✅ High-quality official artwork (600x600px)
- ✅ Reliable metadata
- ✅ Fast response times
- ✅ No rate limiting for reasonable usage

### Google Images (Fallback)
- ✅ Extensive coverage
- ✅ Quality filtering (1KB-5MB)
- ✅ Multiple format support
- ⚠️ May require user-agent headers

## 🛠️ Dependencies

### Core Dependencies
- **[instantmusic](https://github.com/yask123/Instant-Music-Downloader)**: Core music downloading
- **[eyed3](https://eyed3.readthedocs.io/)**: ID3 tag manipulation
- **[requests](https://requests.readthedocs.io/)**: HTTP requests for album art
- **[yt-dlp](https://github.com/yt-dlp/yt-dlp)**: YouTube audio extraction (dependency of instantmusic)

### Enhanced Metadata Dependencies
- **[musicbrainzngs](https://python-musicbrainzngs.readthedocs.io/)**: MusicBrainz API client
- **[mutagen](https://mutagen.readthedocs.io/)**: Advanced audio metadata handling
- **[lyricsgenius](https://lyricsgenius.readthedocs.io/)**: Genius API for lyrics
- **[shazamio](https://github.com/dotX12/ShazamIO)**: Audio fingerprinting and identification
- **[pylast](https://github.com/pylast/pylast)**: Last.fm API client
- **[discogs-client](https://github.com/joalla/discogs_client)**: Discogs API client

## 📱 Output Structure

Downloaded music is organized as:
```
~/Music/
├── Coldplay/
│   └── Yellow (Official Video).mp3
├── The Beatles/
│   └── Hey Jude.mp3
├── Queen/
│   └── Bohemian Rhapsody (Official Video).mp3
└── ...
```

Each file includes:
- 🏷️ **Comprehensive ID3 tags:** artist, title, album, year, track number, genre
- 🎨 **High-quality embedded album artwork** (up to 600x600px)
- 🎵 **Optimal audio quality** (typically 128-320 kbps)
- 📝 **Embedded lyrics** (when available from Genius API)
- 🆔 **MusicBrainz IDs** for precise music identification
- 📊 **Validation metadata** ensuring data quality

## 🔍 Troubleshooting

### Common Issues

**"Command not found: download_music"**
```bash
# Ensure ~/.local/bin is in your PATH
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

**"Album art processing failed"**
- Network connectivity issues
- Try running `fixalbumart_improved` manually on the file
- Check if Python dependencies are properly installed

**"No such file or directory"**
- Run the installation script: `./scripts/install.sh`
- Verify all dependencies are installed

See [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) for more detailed solutions.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes, please open an issue first to discuss what you would like to change.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [instantmusic](https://github.com/yask123/Instant-Music-Downloader) for the core downloading functionality
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) for reliable YouTube audio extraction
- [eyed3](https://eyed3.readthedocs.io/) for ID3 tag manipulation
- Apple iTunes API for high-quality album artwork
- The open-source community for inspiration and tools

## ⭐ Star History

If this project helped you, please consider giving it a star! ⭐

---

**Made with ❤️ for music lovers who appreciate good tooling**


