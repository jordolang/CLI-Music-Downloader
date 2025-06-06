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

