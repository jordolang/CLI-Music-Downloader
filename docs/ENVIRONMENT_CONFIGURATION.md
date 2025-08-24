# Environment-Specific Configuration

This document explains how to configure the CLI Music Downloader for different deployment scenarios using Docker and environment variables.

## 📋 Table of Contents

- [Quick Start](#quick-start)
- [Environment Variables](#environment-variables)
- [Deployment Scenarios](#deployment-scenarios)
- [Configuration Files](#configuration-files)
- [Custom Music Directories](#custom-music-directories)
- [API Configuration](#api-configuration)
- [Troubleshooting](#troubleshooting)

## 🚀 Quick Start

### Development Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/CLI-Music-Downloader.git
   cd CLI-Music-Downloader
   ```

2. **Create environment file:**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Start development environment:**
   ```bash
   docker-compose up -d
   ```

### Production Setup

1. **Create production environment file:**
   ```bash
   cp .env.production .env
   # Configure production settings
   ```

2. **Start production environment:**
   ```bash
   docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
   ```

## 🔧 Environment Variables

### Core Configuration

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `MUSIC_PATH` | Music directory path | `~/Music` | `/data/music` |
| `CONFIG_PATH` | Configuration directory | `~/.config/cli-music-downloader` | `/data/config` |
| `CACHE_PATH` | Cache directory | `~/.cache/cli-music-downloader` | `/data/cache` |
| `LOGS_PATH` | Logs directory | `~/.logs/cli-music-downloader` | `/data/logs` |

### API Configuration

| Variable | Description | Required | Where to Get |
|----------|-------------|----------|--------------|
| `GENIUS_API_KEY` | Genius API for lyrics | Optional | [Genius API](https://genius.com/api-clients) |
| `LASTFM_API_KEY` | Last.fm API for metadata | Optional | [Last.fm API](https://www.last.fm/api) |
| `LASTFM_API_SECRET` | Last.fm API secret | Optional | [Last.fm API](https://www.last.fm/api) |
| `DISCOGS_USER_TOKEN` | Discogs API for release info | Optional | [Discogs Developer](https://www.discogs.com/settings/developers) |

### Download Configuration

| Variable | Description | Default | Options |
|----------|-------------|---------|---------|
| `DOWNLOAD_QUALITY` | Audio quality | `best` | `best`, `worst`, `320`, `256`, `128` |
| `AUDIO_FORMAT` | Audio format | `mp3` | `mp3`, `flac`, `m4a`, `ogg` |
| `ORGANIZE_BY_ARTIST` | Organize by artist | `true` | `true`, `false` |
| `METADATA_SOURCE` | Metadata source | `all` | `all`, `musicbrainz`, `lastfm`, `discogs` |

## 🌍 Deployment Scenarios

### Development Environment

**Characteristics:**
- Uses local directories (`~/Music`, `~/.config`, etc.)
- Enables debug mode and verbose logging
- Mounts source code for live development
- Includes web interface by default

**Setup:**
```bash
# Use development environment
cp .env.development .env

# Start development stack
docker-compose up -d

# Access container for development
docker-compose exec cli-music-downloader bash
```

**Configuration:**
```bash
# .env.development
MUSIC_PATH=~/Music
CONFIG_PATH=~/.config/cli-music-downloader
DEBUG=true
VERBOSE=true
DOWNLOAD_QUALITY=best
METADATA_SOURCE=all
```

### Production Environment

**Characteristics:**
- Uses persistent volumes (`/data/music`, `/data/config`, etc.)
- Optimized for performance and stability
- Includes monitoring and logging
- Secure API key management

**Setup:**
```bash
# Use production environment
cp .env.production .env

# Configure production settings
export GENIUS_API_KEY="your-production-key"
export LASTFM_API_KEY="your-production-key"

# Start production stack
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

**Configuration:**
```bash
# .env.production
MUSIC_PATH=/data/music
CONFIG_PATH=/data/config
DEBUG=false
DOWNLOAD_QUALITY=320
METADATA_SOURCE=musicbrainz
```

### Testing Environment

**Characteristics:**
- Isolated test environment
- Temporary storage
- All features enabled for testing

**Setup:**
```bash
# Create test environment
MUSIC_PATH=/tmp/test-music docker-compose up -d

# Run tests
docker-compose exec cli-music-downloader python -m pytest
```

## 📁 Configuration Files

### Environment Files

| File | Purpose | Usage |
|------|---------|-------|
| `.env.example` | Template file | Copy to `.env` and customize |
| `.env.development` | Development settings | For local development |
| `.env.production` | Production settings | For production deployment |
| `.env` | Active configuration | Used by docker-compose |

### Docker Compose Files

| File | Purpose | Usage |
|------|---------|-------|
| `docker-compose.yml` | Base configuration | Main service definitions |
| `docker-compose.override.yml` | Development overrides | Automatically loaded in development |
| `docker-compose.prod.yml` | Production overrides | Use with `-f` flag for production |

## 🎵 Custom Music Directories

### Local Development

```bash
# Use custom local directory
export MUSIC_PATH=~/MyMusic
docker-compose up -d
```

### Network Storage

```bash
# Use network-mounted storage
export MUSIC_PATH=/mnt/nas/music
docker-compose up -d
```

### External Drive

```bash
# Use external drive
export MUSIC_PATH=/media/external-drive/music
docker-compose up -d
```

### Multiple Environments

```bash
# Development
export MUSIC_PATH=~/Music/dev

# Staging
export MUSIC_PATH=~/Music/staging

# Production
export MUSIC_PATH=/data/music/prod
```

## 🔑 API Configuration

### Genius API (Lyrics)

1. **Get API Key:**
   - Visit [Genius API](https://genius.com/api-clients)
   - Create an account and generate a Client Access Token

2. **Configure:**
   ```bash
   export GENIUS_API_KEY="your-genius-api-key"
   ```

### Last.fm API (Metadata)

1. **Get API Key:**
   - Visit [Last.fm API](https://www.last.fm/api)
   - Create an account and get API key/secret

2. **Configure:**
   ```bash
   export LASTFM_API_KEY="your-lastfm-api-key"
   export LASTFM_API_SECRET="your-lastfm-api-secret"
   ```

### Discogs API (Release Info)

1. **Get Token:**
   - Visit [Discogs Developer](https://www.discogs.com/settings/developers)
   - Generate a personal access token

2. **Configure:**
   ```bash
   export DISCOGS_USER_TOKEN="your-discogs-token"
   ```

## 🛠️ Usage Examples

### Basic Usage

```bash
# Start with default settings
docker-compose up -d

# Download music
docker-compose exec cli-music-downloader download_music "The Beatles Hey Jude"
```

### Custom Music Directory

```bash
# Use custom directory
MUSIC_PATH=/path/to/custom/music docker-compose up -d

# Verify directory is being used
docker-compose exec cli-music-downloader ls -la /music
```

### Different Quality Settings

```bash
# High quality for archival
DOWNLOAD_QUALITY=best docker-compose up -d

# Balanced quality for everyday use
DOWNLOAD_QUALITY=320 docker-compose up -d

# Lower quality for mobile/limited storage
DOWNLOAD_QUALITY=128 docker-compose up -d
```

### Metadata Source Selection

```bash
# Use only MusicBrainz for metadata
METADATA_SOURCE=musicbrainz docker-compose up -d

# Use all available sources
METADATA_SOURCE=all docker-compose up -d

# Skip metadata entirely
SKIP_METADATA=true docker-compose up -d
```

## 🔍 Troubleshooting

### Common Issues

#### Permission Errors
```bash
# Fix directory permissions
sudo chown -R $USER:$USER ~/Music
chmod 755 ~/Music
```

#### Environment Variables Not Loading
```bash
# Check if .env file exists
ls -la .env

# Verify environment variables
docker-compose config
```

#### Volume Mount Issues
```bash
# Check volume mounts
docker-compose exec cli-music-downloader mount | grep /music

# Verify directory exists
docker-compose exec cli-music-downloader ls -la /music
```

### Debug Mode

```bash
# Enable debug mode
export DEBUG=true
export VERBOSE=true
docker-compose up -d

# View logs
docker-compose logs -f cli-music-downloader
```

### Configuration Validation

```bash
# Test configuration
docker-compose exec cli-music-downloader python -c "
import json
import os
config = {
    'music_path': os.getenv('MUSIC_PATH', '/music'),
    'config_path': os.getenv('CONFIG_PATH', '/config'),
    'cache_path': os.getenv('CACHE_PATH', '/cache'),
    'logs_path': os.getenv('LOGS_PATH', '/logs')
}
print(json.dumps(config, indent=2))
"
```

## 📊 Monitoring

### Health Checks

```bash
# Check service health
docker-compose ps

# View health check logs
docker inspect --format='{{json .State.Health}}' music-downloader
```

### Resource Usage

```bash
# Monitor resource usage
docker stats music-downloader

# View container logs
docker-compose logs -f cli-music-downloader
```

## 🚀 Advanced Configuration

### Custom Network Configuration

```yaml
# docker-compose.override.yml
networks:
  music-network:
    driver: bridge
    ipam:
      config:
        - subnet: 172.20.0.0/16
```

### Resource Limits

```yaml
# docker-compose.override.yml
services:
  cli-music-downloader:
    deploy:
      resources:
        limits:
          cpus: '4.0'
          memory: 2G
        reservations:
          cpus: '1.0'
          memory: 512M
```

### Backup Configuration

```bash
# Backup music and configuration
docker run --rm \
  -v music_data:/data/music \
  -v config_data:/data/config \
  -v $(pwd):/backup \
  alpine tar czf /backup/music-backup.tar.gz /data
```

This configuration system provides flexibility for different deployment scenarios while maintaining consistency and ease of use across development, staging, and production environments.
