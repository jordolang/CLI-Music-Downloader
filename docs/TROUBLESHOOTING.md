# CLI Music Downloader Troubleshooting Guide

This comprehensive guide covers common issues and their solutions for the CLI Music Downloader with enhanced metadata features.

## Table of Contents

1. [Installation Issues](#installation-issues)
2. [Metadata Problems](#metadata-problems)
3. [Network and API Issues](#network-and-api-issues)
4. [Audio File Issues](#audio-file-issues)
5. [Batch Processing Issues](#batch-processing-issues)
6. [Performance Problems](#performance-problems)
7. [Configuration Issues](#configuration-issues)

---

## Installation Issues

### Missing Dependencies

**Problem:** Import errors or "module not found" messages

```
ModuleNotFoundError: No module named 'musicbrainzngs'
```

**Solution:**
```bash
# Install all required dependencies
pip install -r requirements.txt

# Or install individually
pip install musicbrainzngs mutagen lyricsgenius shazamio pylast discogs-client
```

### System Dependencies Missing

**Problem:** Command not found errors for system tools

**Solution:**
```bash
# macOS with Homebrew
brew install exiftool id3v2

# Ubuntu/Debian
sudo apt-get install exiftool id3v2

# CentOS/RHEL
sudo yum install perl-Image-ExifTool id3v2
```

### PATH Issues

**Problem:** "Command not found: download_music"

**Solution:**
```bash
# Add ~/.local/bin to PATH
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc

# Or for bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

---

## Metadata Problems

### Missing Metadata Fields

**Problem:** Downloaded files have empty or incomplete metadata

**Diagnosis:**
```bash
# Check current metadata
batch_metadata.py --scan ~/Music/problematic_file.mp3
```

**Solutions:**

1. **Force metadata refresh:**
   ```bash
   download_music "Artist Song" --force-metadata
   ```

2. **Try different metadata source:**
   ```bash
   download_music "Artist Song" --metadata-source musicbrainz
   download_music "Artist Song" --metadata-source all
   ```

3. **Provide explicit hints:**
   ```bash
   download_music "search term" --artist "Exact Artist" --title "Exact Title"
   ```

4. **Use batch processing:**
   ```bash
   batch_metadata.py --fix "path/to/file.mp3"
   ```

### Incorrect Metadata

**Problem:** Wrong artist, title, album, or other metadata fields

**Solutions:**

1. **Force refresh with specific source:**
   ```bash
   batch_metadata.py --fix "file.mp3" --verbose
   ```

2. **Check validation errors:**
   ```bash
   batch_metadata.py --report --detailed
   ```

3. **Manual correction:**
   ```bash
   # Use the enhanced Python script with explicit metadata
   python3 scripts/download_music.py "search" --artist "Correct Artist" --title "Correct Title" --force-metadata
   ```

### Genre Classification Issues

**Problem:** Incorrect or missing genre information

**Root Causes:**
- MusicBrainz genre tags may be incomplete
- Last.fm tags might be inconsistent

**Solutions:**

1. **Try different metadata sources:**
   ```bash
   download_music "Artist Song" --metadata-source lastfm
   ```

2. **Manual genre correction:**
   ```bash
   # Edit the metadata_manager.py genre mapping
   # Add custom genre mappings in the _load_genre_mapping() method
   ```

---

## Network and API Issues

### API Rate Limiting

**Problem:** "Rate limit exceeded" or slow metadata fetching

**Symptoms:**
- Slow metadata lookup
- HTTP 429 errors
- Temporary bans from API services

**Solutions:**

1. **Use batch processing with delays:**
   ```bash
   batch_metadata.py --fix ~/Music --verbose
   ```

2. **Configure rate limiting:**
   ```bash
   # Edit ~/.batch_metadata_config.json
   {
     "delay_between_requests": 2.0,  # Increase delay
     "max_workers": 2              # Reduce parallel requests
   }
   ```

3. **Wait and retry:**
   ```bash
   # Wait 15-30 minutes before retrying
   sleep 1800 && batch_metadata.py --fix ~/Music
   ```

### Network Connectivity Issues

**Problem:** Metadata lookup timeouts or connection errors

**Diagnosis:**
```bash
# Test network connectivity
curl -I https://musicbrainz.org/ws/2/
curl -I https://api.genius.com/
```

**Solutions:**

1. **Skip metadata temporarily:**
   ```bash
   download_music "Artist Song" --skip-metadata
   ```

2. **Process metadata later:**
   ```bash
   # Download first, then process metadata when network is stable
   batch_metadata.py --fix ~/Music/newly_downloaded
   ```

3. **Check proxy settings:**
   ```bash
   # If behind corporate firewall
   export HTTP_PROXY=http://proxy.company.com:8080
   export HTTPS_PROXY=http://proxy.company.com:8080
   ```

### API Key Issues

**Problem:** Metadata sources not working despite correct setup

**Symptoms:**
- Authentication errors
- Limited functionality
- "API key not found" messages

**Solutions:**

1. **Set API keys properly:**
   ```bash
   export GENIUS_API_KEY="your_genius_key_here"
   export LASTFM_API_KEY="your_lastfm_key_here"
   export LASTFM_API_SECRET="your_lastfm_secret_here"
   export DISCOGS_USER_TOKEN="your_discogs_token_here"
   ```

2. **Verify configuration:**
   ```bash
   batch_metadata.py --config
   ```

3. **Test API keys:**
   ```bash
   # Test individual metadata providers
   python3 -c "from scripts.metadata_manager import MetadataManager; import asyncio; asyncio.run(MetadataManager().get_metadata('The Beatles', 'Hey Jude'))"
   ```

---

## Audio File Issues

### Audio Fingerprinting Failures

**Problem:** Shazam identification not working

**Symptoms:**
- "Audio identification failed" messages
- Shazam returning no results

**Solutions:**

1. **Check file format compatibility:**
   ```bash
   # Supported formats: MP3, FLAC, M4A, MP4, OGG
   file "problematic_file.mp3"
   ```

2. **Verify file integrity:**
   ```bash
   # Check if file is corrupted
   ffprobe "file.mp3" 2>&1 | grep -i error
   ```

3. **Use alternative metadata sources:**
   ```bash
   download_music "Artist Song" --metadata-source musicbrainz
   ```

4. **Manual audio file repair:**
   ```bash
   # Re-encode if necessary
   ffmpeg -i "corrupted.mp3" -c copy "repaired.mp3"
   ```

### Unsupported File Formats

**Problem:** "Unsupported file format" errors

**Supported Formats:**
- MP3 (primary)
- FLAC
- M4A/MP4
- OGG Vorbis
- WMA (limited support)

**Solutions:**

1. **Convert to supported format:**
   ```bash
   # Convert to MP3
   ffmpeg -i "input.wav" -c:a libmp3lame -b:a 192k "output.mp3"
   ```

2. **Use format-specific tools:**
   ```bash
   # For FLAC files
   metaflac --show-all "file.flac"
   ```

---

## Batch Processing Issues

### Large Library Performance

**Problem:** Batch processing is slow or fails on large libraries

**Solutions:**

1. **Process in smaller chunks:**
   ```bash
   # Process by artist
   find ~/Music -maxdepth 1 -type d -exec batch_metadata.py --fix {} \;
   ```

2. **Optimize configuration:**
   ```bash
   # Edit ~/.batch_metadata_config.json
   {
     "max_workers": 8,              # Increase parallel workers
     "delay_between_requests": 0.5  # Reduce delay if no rate limiting
   }
   ```

3. **Use incremental processing:**
   ```bash
   # Skip files that already have complete metadata
   batch_metadata.py --scan ~/Music
   batch_metadata.py --fix ~/Music --verbose
   ```

### Memory Issues

**Problem:** Out of memory errors during batch processing

**Solutions:**

1. **Reduce batch size:**
   ```bash
   # Process smaller directories
   for dir in ~/Music/*/; do
     batch_metadata.py --fix "$dir"
     sleep 5
   done
   ```

2. **Monitor resource usage:**
   ```bash
   # Monitor memory usage
   top -pid $(pgrep -f batch_metadata)
   ```

---

## Performance Problems

### Slow Metadata Lookup

**Problem:** Metadata fetching takes too long

**Optimization strategies:**

1. **Prioritize faster sources:**
   ```bash
   download_music "Artist Song" --metadata-source musicbrainz
   ```

2. **Cache results:**
   ```bash
   # Metadata results are automatically cached by source
   # Clear cache if needed
   rm -rf ~/.cache/musicbrainz/
   ```

3. **Parallel processing:**
   ```bash
   # Use batch processor for multiple files
   batch_metadata.py --fix ~/Music/Artist --verbose
   ```

### High CPU Usage

**Problem:** Metadata processing uses too much CPU

**Solutions:**

1. **Reduce worker threads:**
   ```bash
   # Edit configuration
   {
     "max_workers": 2  # Reduce from default 4
   }
   ```

2. **Add processing delays:**
   ```bash
   {
     "delay_between_requests": 2.0  # Increase delay
   }
   ```

---

## Configuration Issues

### Invalid Configuration

**Problem:** Configuration file errors

**Reset configuration:**
```bash
# Remove corrupted config
rm ~/.batch_metadata_config.json

# Regenerate with defaults
batch_metadata.py --config
```

### Permission Issues

**Problem:** Cannot write to music files or configuration

**Solutions:**

1. **Fix file permissions:**
   ```bash
   # Make files writable
   chmod 644 ~/Music/**/*.mp3
   
   # Fix directory permissions
   chmod 755 ~/Music/*/
   ```

2. **Check ownership:**
   ```bash
   # Take ownership if needed
   sudo chown -R $(whoami) ~/Music/
   ```

---

## Debug Mode

### Enable Verbose Logging

```bash
# For download operations
download_music "Artist Song" --verbose

# For batch operations
batch_metadata.py --fix ~/Music --verbose

# For debugging specific metadata manager
python3 -c "
import logging
logging.basicConfig(level=logging.DEBUG)
from scripts.metadata_manager import MetadataManager
import asyncio
manager = MetadataManager()
result = asyncio.run(manager.get_metadata('Artist', 'Song'))
print(result)
"
```

### Log File Analysis

```bash
# Redirect output to file for analysis
batch_metadata.py --scan ~/Music --verbose 2>&1 | tee metadata_scan.log

# Filter for errors
grep -i error metadata_scan.log
grep -i warning metadata_scan.log
```

---

## Getting Help

If you're still experiencing issues after trying these solutions:

1. **Check the GitHub Issues**: [CLI-Music-Downloader Issues](https://github.com/yourusername/CLI-Music-Downloader/issues)

2. **Create a detailed bug report** including:
   - Operating system and version
   - Python version
   - Error messages (full stack trace)
   - Steps to reproduce
   - Configuration file contents

3. **Provide debug information:**
   ```bash
   # Generate system info
   python3 --version
   pip list | grep -E "(musicbrainz|mutagen|eyed3|requests)"
   batch_metadata.py --config
   ```

4. **Test with minimal example:**
   ```bash
   # Try with a simple, known song
   download_music "The Beatles Hey Jude" --verbose
   ```

This troubleshooting guide should resolve most common issues. For complex problems, don't hesitate to seek community support or file a detailed issue report.

# Troubleshooting Guide

## Common Issues and Solutions

### Installation Issues

#### "Command not found: download_music"

**Cause**: The script is not in your PATH or not executable.

**Solutions**:

1. **Check if installed**:
   ```bash
   ls -la ~/.local/bin/download_music
   ```

2. **Add to PATH** (if not already there):
   ```bash
   echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
   source ~/.zshrc
   ```

3. **Make executable**:
   ```bash
   chmod +x ~/.local/bin/download_music
   ```

#### "No module named 'instantmusic'"

**Cause**: Python dependencies not installed.

**Solution**:
```bash
pip install instantmusic eyed3 requests
# or
pip3 install instantmusic eyed3 requests
```

#### "Permission denied"

**Cause**: Insufficient permissions for installation.

**Solution**:
```bash
# For user installation (recommended)
pip install --user instantmusic eyed3 requests

# For system-wide (may require sudo)
sudo pip install instantmusic eyed3 requests
```

### Download Issues

#### "ERROR: Unable to extract video info"

**Cause**: Network issues or video not available.

**Solutions**:

1. **Check internet connection**
2. **Try a different search term**:
   ```bash
   # Instead of:
   download_music "Song Name"
   
   # Try:
   download_music "Artist Song Name"
   download_music "Artist Song Name official"
   ```

3. **Update yt-dlp**:
   ```bash
   pip install --upgrade yt-dlp
   ```

#### "Video unavailable" or "Private video"

**Cause**: The specific video found is restricted.

**Solution**: Try different search terms or add descriptive keywords:
```bash
download_music "Artist Song official music video"
download_music "Artist Song live performance"
download_music "Artist Song acoustic version"
```

#### Download is very slow

**Cause**: Network congestion or server limitations.

**Solutions**:
1. **Wait and try later**
2. **Check network connection**
3. **Use a VPN** if regional restrictions apply

### Album Art Issues

#### "Album art processing failed"

**Cause**: Network issues, incorrect artist/track info, or API limitations.

**Solutions**:

1. **Manual retry**:
   ```bash
   fixalbumart_improved "/path/to/song.mp3" "Correct Artist" "Correct Track"
   ```

2. **Check internet connection**

3. **Try alternative search terms**:
   ```bash
   # If artist has special characters or is multi-word
   fixalbumart_improved "/path/to/song.mp3" "AC DC" "Thunderstruck"
   fixalbumart_improved "/path/to/song.mp3" "Guns N Roses" "Sweet Child O Mine"
   ```

#### "No album art found"

**Cause**: Rare or misspelled artist/track names.

**Solutions**:

1. **Check spelling**:
   ```bash
   # Make sure artist and track names are correct
   fixalbumart_improved "/path/to/song.mp3" "Led Zeppelin" "Stairway to Heaven"
   ```

2. **Try simplified names**:
   ```bash
   # Remove special characters
   fixalbumart_improved "/path/to/song.mp3" "Pink Floyd" "Wish You Were Here"
   ```

3. **Manual download**: Find album art online and use a tag editor

#### "Error in album art processing: a bytes-like object is required, not 'str'"

**Cause**: This is the old instantmusic bug that our improved system fixes.

**Solution**: The new system should handle this automatically. If you still see this:

1. **Update the scripts**:
   ```bash
   cd ~/Repos/CLI-Music-Downloader
   git pull
   ./scripts/install.sh
   ```

2. **Use the improved album art fixer directly**:
   ```bash
   fixalbumart_improved "/path/to/song.mp3" "Artist" "Track"
   ```

### File Organization Issues

#### Songs going to wrong folders

**Cause**: instantmusic's automatic artist detection.

**Solutions**:

1. **Manual organization**:
   ```bash
   # Move files manually
   mkdir -p "~/Music/Correct Artist"
   mv "~/Music/Wrong Artist/Song.mp3" "~/Music/Correct Artist/"
   ```

2. **Use specific search terms**:
   ```bash
   download_music "Correct Artist Song Name"
   ```

#### Duplicate files

**Cause**: Multiple downloads of the same song.

**Solution**:
```bash
# Find duplicates
find ~/Music -name "*.mp3" -exec basename {} \; | sort | uniq -d

# Remove duplicates manually or use a duplicate finder tool
```

### Warp Workflow Issues

#### Workflow not appearing in Warp

**Solutions**:

1. **Check installation**:
   ```bash
   ls -la ~/.config/warp/workflows/download_music.yaml
   ```

2. **Reinstall workflow**:
   ```bash
   mkdir -p ~/.config/warp/workflows
   cp workflows/download_music.yaml ~/.config/warp/workflows/
   ```

3. **Restart Warp Terminal**

#### Workflow runs but command not found

**Cause**: PATH issues in Warp.

**Solution**:
```bash
# Add to your shell config file
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
```

### Performance Issues

#### High CPU usage during download

**Cause**: Video processing and audio extraction.

**Solutions**:
1. **Normal behavior** - CPU usage is expected
2. **Close other applications** during download
3. **Download one song at a time**

#### High memory usage

**Cause**: Large video files being processed.

**Solutions**:
1. **Normal for large files**
2. **Restart the process** if memory usage is excessive
3. **Close other applications**

### Network and Connectivity

#### Timeouts during download

**Solutions**:
1. **Check internet connection**
2. **Try again later**
3. **Use a VPN** if regional restrictions apply

#### iTunes API not responding

**Symptoms**: Album art falls back to Google Images.

**Solutions**:
1. **Usually temporary** - try again later
2. **Check internet connection**
3. **The fallback should still work**

## Advanced Troubleshooting

### Debug Mode

For detailed error information:

```bash
# Enable debug output
bash -x download_music "Artist Song"

# For Python scripts
python3 -u ~/.local/bin/fixalbumart_improved "/path/to/song.mp3" "Artist" "Track"
```

### Log Files

Check system logs for additional information:

```bash
# macOS Console logs
log show --predicate 'process CONTAINS "download_music"' --last 1h

# Check Python errors
python3 -c "import instantmusic, eyed3, requests; print('All modules OK')"
```

### Clean Reinstall

If all else fails:

```bash
# Uninstall
./scripts/uninstall.sh

# Remove Python packages
pip uninstall instantmusic eyed3 requests yt-dlp

# Reinstall
pip install instantmusic eyed3 requests
./scripts/install.sh
```

## Getting Help

If you're still having issues:

1. **Check the GitHub Issues** page for similar problems
2. **Create a new issue** with:
   - Your operating system and version
   - Python version (`python3 --version`)
   - Complete error messages
   - Steps to reproduce the issue
3. **Include relevant logs** and error output

## Prevention Tips

1. **Keep dependencies updated**:
   ```bash
   pip install --upgrade instantmusic eyed3 requests yt-dlp
   ```

2. **Regular maintenance**:
   ```bash
   # Clean up temporary files
   rm -rf ~/.cache/instantmusic/
   ```

3. **Backup your music**:
   ```bash
   # Regular backups of your music collection
   rsync -av ~/Music/ ~/Backups/Music/
   ```

