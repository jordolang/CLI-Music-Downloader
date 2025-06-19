# Sample Usage Examples

## Basic Downloads

```bash
# Single word artist
download_music "Adele Hello"
download_music "Drake Hotline"
download_music "Beyoncé Halo"

# Multi-word artists
download_music "The Beatles Yesterday"
download_music "Pink Floyd Wish You Were Here"
download_music "Led Zeppelin Kashmir"

# Complex song titles
download_music "Queen Don't Stop Me Now"
download_music "Bohemian Rhapsody Queen"
download_music "Guns N Roses Sweet Child O Mine"
```

## Album Art Fixing

```bash
# Fix album art for a specific file
fixalbumart_improved "/Users/john/Music/Queen/Bohemian Rhapsody.mp3" "Queen" "Bohemian Rhapsody"

# Auto-detect from filename (works with "Artist - Song.mp3" format)
fixalbumart_improved "/Users/john/Music/Various/The Beatles - Hey Jude.mp3"

# Batch fix multiple files
for file in ~/Music/*/*.mp3; do
    echo "Processing: $file"
    fixalbumart_improved "$file"
done
```

## Advanced Usage

### Download with Custom Organization

```bash
# The script automatically organizes by artist
# Result: ~/Music/Coldplay/Yellow (Official Video).mp3
download_music "Coldplay Yellow"
```

### Handling Special Characters

```bash
# Use quotes for songs with special characters
download_music "AC/DC Thunderstruck"
download_music "Guns N' Roses November Rain"
download_music "System of a Down B.Y.O.B."
```

### Batch Downloads

```bash
#!/bin/bash
# Create a playlist script

SONGS=(
    "The Beatles Hey Jude"
    "Queen Bohemian Rhapsody"
    "Led Zeppelin Stairway to Heaven"
    "Pink Floyd Comfortably Numb"
    "The Rolling Stones Paint It Black"
)

for song in "${SONGS[@]}"; do
    echo "Downloading: $song"
    download_music "$song"
    sleep 2  # Be nice to the servers
done
```

## Warp Terminal Workflow Examples

1. **Open Warp Terminal**
2. **Press `Cmd+Shift+R`**
3. **Type**: "Download Music"
4. **Select the workflow**
5. **Enter queries like**:
   - `Radiohead Creep`
   - `Taylor Swift Shake It Off`
   - `Michael Jackson Billie Jean`

## Error Handling Examples

### When Album Art Fails

```bash
# The download will still complete, but you can fix album art later
download_music "Obscure Artist Unknown Song"

# Then manually fix the album art
fixalbumart_improved "~/Music/Obscure Artist/Unknown Song.mp3" "Obscure Artist" "Unknown Song"
```

### Network Issues

```bash
# If download fails due to network issues, just retry
download_music "The Beatles Hey Jude"
# If it fails, try again later or with a different search term
download_music "Beatles Hey Jude Official"
```

## Integration Examples

### Alfred Workflow (macOS)

```bash
# Create an Alfred workflow that runs:
download_music "{query}"
```

### Shell Alias

```bash
# Add to your ~/.zshrc or ~/.bashrc
alias dl='download_music'
alias dlmusic='download_music'

# Usage:
dl "Coldplay Yellow"
dlmusic "Queen Bohemian Rhapsody"
```

### Desktop Automation

```bash
# Create a desktop shortcut (macOS)
echo '#!/bin/bash
open -a Terminal "download_music \"$1\""' > ~/Desktop/download_music.command
chmod +x ~/Desktop/download_music.command
```

## Quality and Format Notes

- **Audio Quality**: Typically 128-320 kbps depending on source
- **Format**: MP3 with ID3v2 tags
- **Album Art**: 600x600px when available from iTunes API
- **Fallback**: Lower resolution from Google Images if iTunes fails
- **Organization**: `~/Music/<Artist>/<Song>.mp3`

## Pro Tips

1. **Use specific search terms** for better results
2. **Include "official" or "music video"** for studio versions
3. **Try different variations** if the first search doesn't work
4. **Check your network connection** if downloads fail
5. **Use the album art fixer** on existing music collections

