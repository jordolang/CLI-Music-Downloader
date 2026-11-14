# Spotify Library Export - Quick Start Guide

Get your entire Spotify library ready for offline downloading in minutes!

## Prerequisites

- Python 3.8+
- Spotify account
- `requests` library: `pip install requests`

## 5-Minute Setup

### Step 1: Create Spotify App (2 minutes)

1. Go to https://developer.spotify.com/dashboard
2. Click **"Create an App"**
3. Fill in:
   - Name: `Music Library Export`
   - Description: `Export my Spotify library`
4. Click **"Create"**
5. Click **"Edit Settings"**
6. Add Redirect URI: `http://localhost:8888/callback`
7. Click **"Save"**
8. Copy your **Client ID** and **Client Secret**

### Step 2: Set Environment Variables (1 minute)

```bash
# Add to ~/.zshrc (macOS) or ~/.bashrc (Linux)
export SPOTIFY_CLIENT_ID="your_client_id_here"
export SPOTIFY_CLIENT_SECRET="your_client_secret_here"

# Reload shell
source ~/.zshrc  # or source ~/.bashrc
```

### Step 3: Run the Export (2 minutes)

```bash
# Export your library
python3 scripts/spotify_library_export.py

# Follow the prompts:
# 1. Browser opens automatically
# 2. Log in to Spotify
# 3. Click "Agree" to authorize
# 4. Script fetches all your songs
# 5. Creates spotify_library.txt
```

## Done! Now What?

### Download All Songs

```bash
# Option 1: Simple loop
while read line; do download_music "$line"; done < spotify_library.txt

# Option 2: With error logging
while read line; do
    echo "Downloading: $line"
    download_music "$line" || echo "Failed: $line" >> failed.log
done < spotify_library.txt

# Option 3: Batch script
./batch_download.sh spotify_library.txt
```

### Output Format

The exported file looks like this:
```
Taylor Swift - Shake It Off
The Beatles - Hey Jude
Queen - Bohemian Rhapsody
...
```

## Troubleshooting

### "Authorization failed"
- Check redirect URI is exactly: `http://localhost:8888/callback`
- Verify Client ID and Secret are correct

### "Port already in use"
```bash
# Kill whatever is using port 8888
lsof -i :8888
kill -9 <PID>
```

### "No tracks found"
- Make sure you have saved songs in Spotify (not just playlists)
- Verify you logged into the correct Spotify account

## What Next?

After downloading:
- Songs saved to `~/Music/Artist/Song.mp3`
- Automatic album art and metadata
- Automatic lyrics (if Genius API configured)

## Advanced Usage

```bash
# Download with full metadata
while read line; do
    download_music "$line" --metadata-source all
done < spotify_library.txt

# Download only specific artists
grep "Taylor Swift" spotify_library.txt | \
while read line; do download_music "$line"; done

# Export to custom file
python3 scripts/spotify_library_export.py my_songs.txt
```

## Need More Help?

- Full documentation: [docs/SPOTIFY_EXPORT.md](docs/SPOTIFY_EXPORT.md)
- Usage examples: [examples/spotify_export_example.md](examples/spotify_export_example.md)
- Main README: [README.md](README.md)

---

**Time to complete**: ~5 minutes setup + download time (depends on library size)

**Typical library**: 300 songs ≈ 30-60 minutes to download (with metadata)

**Storage**: ~3-5 MB per song (300 songs ≈ 1-1.5 GB)
