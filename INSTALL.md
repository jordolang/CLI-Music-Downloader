# Installation Guide

CLI Music Downloader can be installed in several ways. Choose the method that best fits your needs.

## 🚀 Quick Installation (Recommended)

### From PyPI (Once Published)

```bash
# Install the latest stable version
pip install CLI-Music-Downloader

# Or install with all optional features
pip install CLI-Music-Downloader[all]
```

### From GitHub

```bash
# Install directly from GitHub (latest version)
pip install git+https://github.com/jordolang/CLI-Music-Downloader.git

# Or install from a specific branch
pip install git+https://github.com/jordolang/CLI-Music-Downloader.git@main
```

## 🛠️ Development Installation

If you want to contribute to the project or modify the code:

```bash
# Clone the repository
git clone https://github.com/jordolang/CLI-Music-Downloader.git
cd CLI-Music-Downloader

# Install in development mode (editable)
pip install -e .

# Or install with development dependencies
pip install -e .[dev]
```

## 📦 Optional Dependencies

The package includes several optional dependency groups:

### Audio Fingerprinting
For enhanced metadata detection using ACRCloud:
```bash
pip install CLI-Music-Downloader[audio-fingerprinting]
```

### Development
For contributing to the project:
```bash
pip install CLI-Music-Downloader[dev]
```

### Documentation
For building documentation:
```bash
pip install CLI-Music-Downloader[docs]
```

### All Features
To install everything:
```bash
pip install CLI-Music-Downloader[all]
```

## 🔧 System Dependencies

The CLI Music Downloader relies on some system tools that need to be installed separately:

### macOS (using Homebrew)
```bash
# Required for metadata management
brew install exiftool id3v2

# Optional: For enhanced audio processing
brew install ffmpeg
```

### Linux (Ubuntu/Debian)
```bash
# Required for metadata management
sudo apt-get update
sudo apt-get install exiftool id3v2

# Optional: For enhanced audio processing
sudo apt-get install ffmpeg
```

## 🎯 Verification

After installation, verify that everything works:

```bash
# Check the main CLI
cli-music-downloader --version

# Test individual commands
download-music --help
batch-metadata --help
fixalbumart-improved --help
```

## 🆘 Legacy Installation (Manual)

If you prefer the original manual installation method:

```bash
# Clone the repository
git clone https://github.com/jordolang/CLI-Music-Downloader.git
cd CLI-Music-Downloader

# Install dependencies manually
pip install -r requirements.txt

# Run the installation script
chmod +x scripts/install.sh
./scripts/install.sh
```

## 🐍 Python Version Requirements

- **Python 3.8+** is required
- **Python 3.11+** is recommended for best performance

## 🔑 API Keys Configuration

To enable lyrics functionality, you'll need a Genius API key:

1. Visit [Genius API](https://genius.com/api-clients)
2. Create an account and generate a Client Access Token
3. Set the environment variable:

```bash
# Add to your shell profile (.bashrc, .zshrc, etc.)
export GENIUS_API_KEY="your_token_here"
```

For enhanced metadata features, you can also configure:
- **Last.fm API**: Set `LASTFM_API_KEY` and `LASTFM_API_SECRET`
- **Discogs API**: Set `DISCOGS_USER_TOKEN`

## 🐳 Docker Installation (Alternative)

If you prefer Docker:

```bash
# Clone the repository
git clone https://github.com/jordolang/CLI-Music-Downloader.git
cd CLI-Music-Downloader

# Build and run with Docker Compose
docker-compose up -d

# Use the CLI through Docker
docker-compose exec cli-music-downloader cli-music-downloader --help
```

## 🚨 Troubleshooting

### Common Installation Issues

**"Command not found" after installation:**
```bash
# Ensure pip's bin directory is in your PATH
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

**Permission errors on macOS/Linux:**
```bash
# Install to user directory
pip install --user CLI-Music-Downloader
```

**Dependency conflicts:**
```bash
# Use a virtual environment
python3 -m venv cli-music-env
source cli-music-env/bin/activate
pip install CLI-Music-Downloader
```

### Getting Help

- **Documentation**: Check the main [README.md](README.md)
- **Issues**: Report bugs at [GitHub Issues](https://github.com/jordolang/CLI-Music-Downloader/issues)
- **Troubleshooting**: See [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)

## ⚡ Quick Start After Installation

Once installed, you can start downloading music immediately:

```bash
# Download a song
cli-music-downloader download "The Beatles Hey Jude"

# Or use the direct command
download-music "Taylor Swift Shake It Off"

# Process existing music files
batch-metadata --scan ~/Music

# Fix album art for a file
fixalbumart-improved "/path/to/song.mp3"
```

Enjoy your enhanced music downloading experience! 🎵
