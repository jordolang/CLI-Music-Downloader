# Spotify Library Export Guide

Export your entire Spotify library to a text file for batch downloading with CLI Music Downloader.

## Quick Start

```bash
# Run the export script
python3 scripts/spotify_library_export.py

# Or use the wrapper
./bin/spotify_export

# Specify custom output file
python3 scripts/spotify_library_export.py my_spotify_songs.txt
```

## Setup Instructions

### 1. Create a Spotify App

To access your Spotify library, you need to create a Spotify application:

1. **Go to Spotify Developer Dashboard**
   - Visit: https://developer.spotify.com/dashboard
   - Log in with your Spotify account

2. **Create an App**
   - Click "Create an App"
   - Fill in the details:
     - **App Name**: `Music Library Export` (or any name you prefer)
     - **App Description**: `Export my Spotify library for offline downloads`
   - Accept the terms and click "Create"

3. **Configure Redirect URI**
   - In your app settings, click "Edit Settings"
   - Under "Redirect URIs", add: `http://localhost:8888/callback`
   - Click "Add"
   - Click "Save" at the bottom

4. **Get Your Credentials**
   - You'll see your **Client ID** on the app page
   - Click "Show Client Secret" to reveal your **Client Secret**
   - Copy both values

### 2. Set Up Environment Variables (Recommended)

To avoid entering credentials every time, add them to your shell profile:

```bash
# For Zsh (macOS default)
echo 'export SPOTIFY_CLIENT_ID="your_client_id_here"' >> ~/.zshrc
echo 'export SPOTIFY_CLIENT_SECRET="your_client_secret_here"' >> ~/.zshrc
source ~/.zshrc

# For Bash
echo 'export SPOTIFY_CLIENT_ID="your_client_id_here"' >> ~/.bashrc
echo 'export SPOTIFY_CLIENT_SECRET="your_client_secret_here"' >> ~/.bashrc
source ~/.bashrc
```

Replace `your_client_id_here` and `your_client_secret_here` with your actual credentials.

### 3. Install Required Dependencies

The script uses the `requests` library:

```bash
pip install requests
```

Or install all dependencies from the project:

```bash
pip install -r requirements.txt
```

## Usage

### Basic Export

```bash
python3 scripts/spotify_library_export.py
```

This will:
1. Open your browser for Spotify login
2. Request permission to read your library
3. Fetch all saved tracks
4. Export them to `spotify_library.txt`

### Custom Output File

```bash
python3 scripts/spotify_library_export.py my_songs.txt
```

### Authorization Flow

When you run the script:

1. **Browser Opens**: You'll be redirected to Spotify login
2. **Login**: Enter your Spotify credentials
3. **Authorize**: Click "Agree" to grant read access to your library
4. **Redirect**: You'll be redirected to localhost (a success page will appear)
5. **Export**: The script automatically fetches and exports your library

## Output Format

The exported file contains one song per line in the format:

```
Artist Name - Song Name
Artist Name - Song Name
...
```

Example:
```
Taylor Swift - Shake It Off
The Beatles - Hey Jude
Queen - Bohemian Rhapsody
Ed Sheeran - Perfect
```

This format is optimized for batch downloading with `download_music`.

## Batch Downloading

After exporting, download all songs using one of these methods:

### Method 1: Using While Loop

```bash
while read line; do
    download_music "$line"
done < spotify_library.txt
```

### Method 2: Using batch_download.sh Script

```bash
./batch_download.sh spotify_library.txt
```

### Method 3: Using CLI Music Downloader Batch Feature

```bash
cli-music-downloader batch --file spotify_library.txt
```

## Features

- **Complete Library Export**: Fetches all saved tracks from your Spotify account
- **OAuth Authentication**: Secure web-based login (no password storage)
- **Duplicate Removal**: Automatically removes duplicate entries
- **Progress Tracking**: Shows real-time progress during fetch
- **UTF-8 Support**: Handles international characters and special symbols
- **Pagination Handling**: Automatically fetches all pages (supports 1000+ songs)
- **Format Ready**: Output is immediately ready for batch downloading

## Troubleshooting

### "Authorization Failed"

**Problem**: Browser shows authorization error

**Solutions**:
- Verify redirect URI is exactly `http://localhost:8888/callback`
- Check that Client ID and Client Secret are correct
- Make sure you clicked "Agree" on the authorization page

### "Connection Refused" or Port Issues

**Problem**: Port 8888 is already in use

**Solutions**:
```bash
# Check what's using port 8888
lsof -i :8888

# Kill the process if needed
kill -9 <PID>
```

### "Invalid Client" Error

**Problem**: Spotify API returns invalid client error

**Solutions**:
- Double-check your Client ID and Client Secret
- Ensure there are no extra spaces in your credentials
- Verify your Spotify app is active (not deleted)

### No Tracks Found

**Problem**: Script says "No tracks found in your Spotify library"

**Solutions**:
- Make sure you have saved tracks in your Spotify library
- Check that you authorized with the correct Spotify account
- Try refreshing the authorization by running the script again

### Rate Limiting

**Problem**: Too many requests error

**Solutions**:
- Wait a few minutes before trying again
- Spotify has generous rate limits, this should be rare
- If it persists, check Spotify API status: https://status.spotify.com/

## Advanced Usage

### Scripted Export (Non-Interactive)

If you've saved credentials as environment variables:

```bash
# Export and immediately start downloading
python3 scripts/spotify_library_export.py spotify.txt && \
while read line; do download_music "$line"; done < spotify.txt
```

### Export Specific Playlists

To export playlists instead of your library, you can modify the script:

1. Change the scope to include `playlist-read-private`
2. Use the `/me/playlists` endpoint instead of `/me/tracks`
3. Fetch tracks from specific playlist IDs

### Export with Metadata

For enhanced metadata, you can pipe the output through the batch metadata processor:

```bash
# Download with full metadata enhancement
while read line; do
    download_music "$line" --metadata-source all
done < spotify_library.txt
```

## Security Notes

- **Client Secret**: Keep your Client Secret private, never commit it to version control
- **Scope Permissions**: The script only requests `user-library-read` (read-only access)
- **Local Server**: The OAuth callback runs locally on your machine (localhost:8888)
- **No Storage**: Access tokens are not saved and expire after use
- **Open Source**: Review the script source code to verify security

## API Limitations

- **Rate Limits**: Spotify allows ~100 requests per hour per app
- **Pagination**: Maximum 50 tracks per request (handled automatically)
- **Token Expiration**: Access tokens expire after 1 hour (script completes in seconds/minutes)
- **Scope**: Only reads saved tracks, cannot access playlists without additional scope

## Contributing

To add playlist support, caching, or other features:

1. Fork the repository
2. Modify `scripts/spotify_library_export.py`
3. Test your changes
4. Submit a pull request

## References

- [Spotify Web API Documentation](https://developer.spotify.com/documentation/web-api/)
- [Spotify Authorization Guide](https://developer.spotify.com/documentation/general/guides/authorization-guide/)
- [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)

## License

This script is part of CLI Music Downloader and is licensed under the MIT License.

---

**Need Help?**

- Check the [main troubleshooting guide](TROUBLESHOOTING.md)
- Open an issue on GitHub
- Review the Spotify API documentation
