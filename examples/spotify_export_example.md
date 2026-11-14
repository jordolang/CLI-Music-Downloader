# Spotify Library Export - Usage Examples

This guide shows practical examples of using the Spotify library export feature.

## Example 1: Basic Export

```bash
# Export your entire Spotify library
python3 scripts/spotify_library_export.py

# Output: spotify_library.txt
# Format: Artist - Song (one per line)
```

**Expected Output:**
```
Total tracks in library: 342
Fetched 342/342 tracks...
Successfully fetched 342 tracks!
✓ Exported 342 unique tracks to: spotify_library.txt
```

## Example 2: Custom Output File

```bash
# Export to a specific file
python3 scripts/spotify_library_export.py my_music_collection.txt
```

## Example 3: Export and Download Immediately

```bash
# Chain export and download commands
python3 scripts/spotify_library_export.py && \
while read line; do
    download_music "$line"
done < spotify_library.txt
```

## Example 4: Export with Progress Monitoring

```bash
# Export and monitor the file as it's being used
python3 scripts/spotify_library_export.py my_songs.txt

# In another terminal, watch downloads
tail -f ~/Music/download.log
```

## Example 5: Selective Download

```bash
# Export library
python3 scripts/spotify_library_export.py

# Download only specific artists
grep "Taylor Swift" spotify_library.txt | while read line; do
    download_music "$line"
done

# Download only songs matching a pattern
grep -i "love" spotify_library.txt | while read line; do
    download_music "$line"
done
```

## Example 6: Download with Enhanced Metadata

```bash
# Export library
python3 scripts/spotify_library_export.py

# Download with full metadata from all sources
while read line; do
    download_music "$line" --metadata-source all --force-metadata
done < spotify_library.txt
```

## Example 7: Batch Download with Error Handling

```bash
#!/bin/bash
# download_spotify_library.sh

LIBRARY_FILE="spotify_library.txt"
LOG_FILE="download_log_$(date +%Y%m%d_%H%M%S).txt"

# Export library
echo "Exporting Spotify library..."
python3 scripts/spotify_library_export.py "$LIBRARY_FILE"

# Download with error logging
echo "Starting downloads..."
while IFS= read -r line; do
    echo "Downloading: $line" | tee -a "$LOG_FILE"

    if download_music "$line" 2>&1 | tee -a "$LOG_FILE"; then
        echo "✓ Success: $line" >> "$LOG_FILE"
    else
        echo "✗ Failed: $line" >> "$LOG_FILE"
    fi

    # Add delay to avoid rate limiting
    sleep 2
done < "$LIBRARY_FILE"

echo "Download complete! Check $LOG_FILE for details."
```

## Example 8: Export Multiple Times for Different Purposes

```bash
# Export full library
python3 scripts/spotify_library_export.py full_library.txt

# Create filtered versions
grep -i "rock" full_library.txt > rock_songs.txt
grep -i "pop" full_library.txt > pop_songs.txt
grep -i "jazz" full_library.txt > jazz_songs.txt

# Download by genre
while read line; do download_music "$line"; done < rock_songs.txt
```

## Example 9: Compare Libraries Over Time

```bash
# Export current library with timestamp
python3 scripts/spotify_library_export.py "library_$(date +%Y%m%d).txt"

# Later, compare with previous export
diff library_20260103.txt library_20260110.txt

# Download only new songs
comm -13 library_20260103.txt library_20260110.txt | \
while read line; do
    download_music "$line"
done
```

## Example 10: Using with Docker

```bash
# Export library using Docker container
docker-compose exec cli-music-downloader \
    python3 scripts/spotify_library_export.py /music/spotify_library.txt

# Download in Docker
docker-compose exec cli-music-downloader \
    bash -c 'while read line; do download_music "$line"; done < /music/spotify_library.txt'
```

## Example 11: Automated Daily Export

```bash
# Create a cron job for daily exports
# Edit crontab: crontab -e

# Add this line (exports daily at 2 AM):
0 2 * * * cd /path/to/CLI-Music-Downloader && python3 scripts/spotify_library_export.py ~/Music/spotify_library_$(date +\%Y\%m\%d).txt
```

## Example 12: Export with Credentials from File

```bash
# Create credentials file (NOT recommended for security)
cat > .spotify_credentials <<EOF
export SPOTIFY_CLIENT_ID="your_client_id"
export SPOTIFY_CLIENT_SECRET="your_client_secret"
EOF

# Source and export
source .spotify_credentials
python3 scripts/spotify_library_export.py
```

## Example 13: Parallel Downloads (Advanced)

```bash
# Export library
python3 scripts/spotify_library_export.py

# Download with GNU parallel (faster but more resource-intensive)
# Install: brew install parallel

cat spotify_library.txt | parallel -j 4 download_music {}

# -j 4 = 4 parallel downloads at a time
```

## Example 14: Export Statistics

```bash
# Export library
python3 scripts/spotify_library_export.py

# Get statistics
echo "Total songs: $(wc -l < spotify_library.txt)"
echo "Unique artists: $(cut -d'-' -f1 spotify_library.txt | sort -u | wc -l)"
echo "Top 10 artists:"
cut -d'-' -f1 spotify_library.txt | sort | uniq -c | sort -rn | head -10
```

## Example 15: Integration with Existing Batch Script

```bash
# Use with the existing batch_download.sh script
python3 scripts/spotify_library_export.py spotify_songs.txt
./batch_download.sh spotify_songs.txt
```

## Sample Output File

After running the export, your `spotify_library.txt` will look like:

```
Taylor Swift - Shake It Off
The Beatles - Hey Jude
Queen - Bohemian Rhapsody
Ed Sheeran - Perfect
Adele - Rolling in the Deep
Coldplay - Yellow
The Weeknd - Blinding Lights
Bruno Mars - Uptown Funk
Billie Eilish - bad guy
Post Malone - Circles
...
```

## Tips and Best Practices

1. **First-Time Setup**: Run once to test with a few songs before doing full library export
2. **Rate Limiting**: Add delays between downloads to avoid YouTube rate limits
3. **Disk Space**: Check available space before downloading large libraries (342 songs ≈ 1-2 GB)
4. **Backup**: Keep the exported text file as a backup of your library
5. **Updates**: Re-export periodically to get newly added songs
6. **Error Logs**: Always log errors for troubleshooting failed downloads
7. **Metadata Quality**: Use `--metadata-source all` for best quality but slower downloads

## Troubleshooting Examples

### Fix Failed Downloads

```bash
# Create a list of successfully downloaded songs
ls ~/Music/*/*.mp3 | xargs -n1 basename | sed 's/\.mp3$//' > downloaded.txt

# Compare with library to find failed songs
comm -23 <(sort spotify_library.txt) <(sort downloaded.txt) > failed_downloads.txt

# Retry failed downloads
while read line; do download_music "$line"; done < failed_downloads.txt
```

### Verify Downloads

```bash
# Check if all songs were downloaded
EXPECTED=$(wc -l < spotify_library.txt)
ACTUAL=$(find ~/Music -name "*.mp3" | wc -l)
echo "Expected: $EXPECTED, Downloaded: $ACTUAL, Missing: $((EXPECTED - ACTUAL))"
```

## Next Steps

After exporting and downloading:

1. **Fix Metadata**: `batch_metadata.py --scan ~/Music`
2. **Fix Album Art**: `batch_metadata.py --fix ~/Music`
3. **Organize**: Songs are automatically organized by artist
4. **Enjoy**: Your Spotify library is now available offline!

---

For more information, see the [full documentation](../docs/SPOTIFY_EXPORT.md).
