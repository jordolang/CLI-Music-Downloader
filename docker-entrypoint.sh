#!/bin/bash
set -e

# CLI Music Downloader Docker Entrypoint
# This script sets up the environment and handles configuration

echo "🎵 CLI Music Downloader Container Starting..."
echo "📁 Music directory: $MUSIC_PATH"
echo "⚙️  Configuration directory: $CONFIG_PATH"

# Create directories if they don't exist
mkdir -p "$MUSIC_PATH" "$CONFIG_PATH" "$CACHE_PATH" "$LOGS_PATH"

# Set up configuration file
CONFIG_FILE="$CONFIG_PATH/config.json"
if [[ ! -f "$CONFIG_FILE" ]]; then
    echo "📝 Creating default configuration..."
    cat > "$CONFIG_FILE" << EOF
{
    "music_path": "$MUSIC_PATH",
    "download_quality": "${DOWNLOAD_QUALITY:-best}",
    "audio_format": "${AUDIO_FORMAT:-mp3}",
    "organize_by_artist": ${ORGANIZE_BY_ARTIST:-true},
    "metadata_source": "${METADATA_SOURCE:-all}",
    "skip_metadata": ${SKIP_METADATA:-false},
    "force_metadata": ${FORCE_METADATA:-false},
    "api_keys": {
        "genius": "${GENIUS_API_KEY:-}",
        "lastfm": "${LASTFM_API_KEY:-}",
        "lastfm_secret": "${LASTFM_API_SECRET:-}",
        "discogs": "${DISCOGS_USER_TOKEN:-}"
    }
}
EOF
fi

# Set up environment variables for scripts
export MUSIC_PATH
export CONFIG_PATH
export CACHE_PATH
export LOGS_PATH

# Update the download_music script to use the configured music path
if [[ -f "/app/bin/download_music" ]]; then
    # Create a wrapper script that uses the environment variable
    cat > /tmp/download_music_wrapper << 'EOF'
#!/bin/bash
# Wrapper script to use Docker environment variables

# Override the music directory in the original script
export HOME_MUSIC_DIR="$MUSIC_PATH"

# Source the original script with modifications
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Replace ~/Music with $MUSIC_PATH in the original script
sed "s|~/Music|$MUSIC_PATH|g" /app/bin/download_music > /tmp/download_music_modified
sed -i "s|\$HOME/Music|$MUSIC_PATH|g" /tmp/download_music_modified

# Make it executable and run it
chmod +x /tmp/download_music_modified
/tmp/download_music_modified "$@"
EOF
    
    chmod +x /tmp/download_music_wrapper
    cp /tmp/download_music_wrapper /usr/local/bin/download_music
fi

# Display environment information
echo "🔧 Environment Configuration:"
echo "   Music Path: $MUSIC_PATH"
echo "   Config Path: $CONFIG_PATH"
echo "   Cache Path: $CACHE_PATH"
echo "   Logs Path: $LOGS_PATH"
echo "   Download Quality: ${DOWNLOAD_QUALITY:-best}"
echo "   Audio Format: ${AUDIO_FORMAT:-mp3}"
echo "   Organize by Artist: ${ORGANIZE_BY_ARTIST:-true}"
echo "   Metadata Source: ${METADATA_SOURCE:-all}"
echo ""

# Check API keys
echo "🔑 API Keys Status:"
[[ -n "${GENIUS_API_KEY:-}" ]] && echo "   ✅ Genius API Key configured" || echo "   ❌ Genius API Key not configured"
[[ -n "${LASTFM_API_KEY:-}" ]] && echo "   ✅ Last.fm API Key configured" || echo "   ❌ Last.fm API Key not configured"
[[ -n "${DISCOGS_USER_TOKEN:-}" ]] && echo "   ✅ Discogs Token configured" || echo "   ❌ Discogs Token not configured"
echo ""

# Display usage information
echo "📖 Usage Examples:"
echo "   download_music 'The Beatles Hey Jude'"
echo "   download_music 'Taylor Swift Shake It Off'"
echo "   batch_metadata /music --scan"
echo ""

# Check if music directory is writable
if [[ ! -w "$MUSIC_PATH" ]]; then
    echo "⚠️  Warning: Music directory is not writable"
    echo "   Please check volume mount permissions"
fi

# Run the provided command
exec "$@"
