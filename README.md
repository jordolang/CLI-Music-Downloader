# CLI Music Downloader

🎵 **A powerful command-line music downloader with automatic album artwork and intelligent organization**

[![Platform](https://img.shields.io/badge/platform-macOS-blue.svg)](https://www.apple.com/macos/)
[![Shell](https://img.shields.io/badge/shell-zsh%20%7C%20bash-green.svg)](https://www.zsh.org/)
[![License](https://img.shields.io/badge/license-MIT-orange.svg)](LICENSE)

## ✨ Features

- 🎵 **High-quality music downloads** from YouTube with optimal audio extraction
- 🎨 **Automatic album artwork** fetching from iTunes API and Google Images
- 📁 **Smart organization** by artist in `~/Music/<Artist>/<Song>.mp3`
- 🏷️ **Proper ID3 tagging** with metadata and embedded album art
- 🔧 **Warp Terminal integration** with custom workflows
- 🛠️ **Robust error handling** and fallback mechanisms
- 📱 **Multiple image formats** support (JPEG, PNG, WebP)
- 🔍 **Intelligent search** with artist/track parsing

## 🚀 Quick Start

### Prerequisites

- macOS (tested on macOS Monterey+)
- Python 3.8+ with pip
- Warp Terminal (optional, for workflow integration)

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
   # Install dependencies
   pip install instantmusic eyed3 requests
   
   # Copy scripts to local bin
   cp bin/download_music ~/.local/bin/
   cp bin/fixalbumart_improved ~/.local/bin/
   chmod +x ~/.local/bin/download_music
   chmod +x ~/.local/bin/fixalbumart_improved
   
   # Install Warp workflow (optional)
   mkdir -p ~/.config/warp/workflows
   cp workflows/download_music.yaml ~/.config/warp/workflows/
   ```

## 🎵 Usage

### Command Line

```bash
# Download a song
download_music "Coldplay Yellow"
download_music "The Beatles Hey Jude"
download_music "Queen Bohemian Rhapsody"

# Multiple word artists work too
download_music "Pink Floyd Comfortably Numb"
download_music "Led Zeppelin Stairway to Heaven"
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
│   ├── install.sh             # Installation script
│   └── uninstall.sh           # Uninstallation script
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

- **[instantmusic](https://github.com/yask123/Instant-Music-Downloader)**: Core music downloading
- **[eyed3](https://eyed3.readthedocs.io/)**: ID3 tag manipulation
- **[requests](https://requests.readthedocs.io/)**: HTTP requests for album art
- **[yt-dlp](https://github.com/yt-dlp/yt-dlp)**: YouTube audio extraction (dependency of instantmusic)

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
- 🏷️ Proper ID3 tags (artist, title, album)
- 🎨 High-quality embedded album artwork
- 🎵 Optimal audio quality (typically 128-320 kbps)

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

