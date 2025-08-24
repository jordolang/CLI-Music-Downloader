# Changelog

All notable changes to the CLI Music Downloader project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2024-08-24

### Added
- 🎯 **pip install support**: Package can now be installed with `pip install CLI-Music-Downloader`
- 📦 **PyPI packaging**: Complete pyproject.toml configuration for modern Python packaging
- 🚀 **Multiple entry points**: 
  - `cli-music-downloader` - Main CLI with subcommands
  - `download-music` - Direct music downloader
  - `batch-metadata` - Batch metadata processor
  - `fixalbumart-improved` - Album artwork fixer
- 🏗️ **Package structure**: Restructured as proper Python package (`cli_music_downloader`)
- 📚 **Installation guide**: Comprehensive [INSTALL.md](INSTALL.md) with multiple installation methods
- ⚙️ **Optional dependencies**: Audio fingerprinting, development tools, and documentation extras
- 🔧 **Development tools**: Black, isort, flake8, mypy configuration
- 📋 **PyPI publishing**: Scripts and templates for publishing to PyPI
- 🛡️ **Backward compatibility**: Original shell scripts and manual installation still supported

### Enhanced
- 🎵 **Music downloading**: High-quality downloads from YouTube with yt-dlp
- 🎨 **Album artwork**: Automatic fetching from iTunes API and Google Images
- 🏷️ **Metadata system**: Integration with MusicBrainz, Last.fm, Shazam, and Discogs
- 📝 **Lyrics support**: Genius API integration with embedded lyrics
- 📊 **Batch processing**: Comprehensive metadata analysis and fixing
- 🔍 **Smart parsing**: Intelligent artist/track detection from search terms
- 🛠️ **Error handling**: Robust fallback mechanisms and graceful failures

### Technical
- 📁 **Project structure**: Clean separation of core package and legacy scripts
- 🐍 **Python compatibility**: Support for Python 3.8+ with type hints
- 📦 **Dependencies**: Conservative version requirements for stability
- 🧪 **Testing framework**: pytest configuration with async support
- 📖 **Documentation**: Enhanced README with pip installation instructions
- 🔧 **Build system**: Modern setuptools with pyproject.toml
- 🚢 **Publishing**: Automated PyPI publishing scripts

### Docker & Environment
- 🐳 **Docker support**: Multi-environment configuration (development, production)
- ⚙️ **Environment variables**: Flexible configuration for different deployment scenarios
- 📋 **Configuration files**: Template files for various environments

### Development Experience
- 🛠️ **Development mode**: `pip install -e .` for editable installations
- 🧹 **Code quality**: Automated formatting and linting configuration
- 📊 **Coverage**: Test coverage reporting setup
- 🔍 **Type checking**: mypy configuration with proper module handling

---

## Pre-1.0.0 (Legacy)

### Earlier Development
- Initial development as shell scripts
- Basic YouTube downloading functionality
- Manual installation process
- Individual Python scripts for metadata processing
- Docker containerization
- Warp Terminal integration
- Basic album art fetching
- MusicBrainz integration
- Comprehensive metadata sources

---

## Installation Methods by Version

### v1.0.0+
```bash
# Recommended
pip install CLI-Music-Downloader

# From GitHub
pip install git+https://github.com/jordolang/CLI-Music-Downloader.git

# Development
git clone https://github.com/jordolang/CLI-Music-Downloader.git
cd CLI-Music-Downloader
pip install -e .[dev]
```

### Legacy (Pre-1.0.0)
```bash
git clone https://github.com/jordolang/CLI-Music-Downloader.git
cd CLI-Music-Downloader
./scripts/install.sh
```

---

**Note**: Version 1.0.0 represents the first official release with pip packaging support. All previous development was in pre-release state with manual installation only.
