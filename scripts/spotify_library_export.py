#!/usr/bin/env python3
"""
Spotify Library Exporter
Authenticates with Spotify and exports user's saved tracks to a formatted text file
for batch downloading with CLI Music Downloader.

Usage:
    python3 spotify_library_export.py [output_file]

Output format: "Artist Name - Song Name" (one per line)
"""

import os
import sys
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
import base64
import requests
from typing import List, Dict, Optional

# Spotify API Configuration
SPOTIFY_CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID', '')
SPOTIFY_CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET', '')
REDIRECT_URI = 'http://localhost:8888/callback'
SCOPE = 'user-library-read'
AUTH_URL = 'https://accounts.spotify.com/authorize'
TOKEN_URL = 'https://accounts.spotify.com/api/token'
API_BASE_URL = 'https://api.spotify.com/v1'

# Global variable to store the authorization code
auth_code = None


class CallbackHandler(BaseHTTPRequestHandler):
    """HTTP server handler to capture OAuth callback"""

    def do_GET(self):
        """Handle GET request from Spotify OAuth callback"""
        global auth_code

        # Parse the callback URL
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        if 'code' in params:
            auth_code = params['code'][0]
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()

            success_html = """
            <html>
            <head><title>Spotify Authorization Success</title></head>
            <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
                <h1 style="color: #1DB954;">✓ Authorization Successful!</h1>
                <p>You can close this window and return to your terminal.</p>
                <p>Your Spotify library is now being exported...</p>
            </body>
            </html>
            """
            self.wfile.write(success_html.encode())
        else:
            self.send_response(400)
            self.send_header('Content-type', 'text/html')
            self.end_headers()

            error_html = """
            <html>
            <head><title>Authorization Error</title></head>
            <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
                <h1 style="color: #f44336;">✗ Authorization Failed</h1>
                <p>There was an error during authorization. Please try again.</p>
            </body>
            </html>
            """
            self.wfile.write(error_html.encode())

    def log_message(self, format, *args):
        """Suppress server log messages"""
        pass


def get_spotify_credentials():
    """Prompt user for Spotify API credentials if not set in environment"""
    client_id = SPOTIFY_CLIENT_ID
    client_secret = SPOTIFY_CLIENT_SECRET

    if not client_id or not client_secret:
        print("\n" + "="*60)
        print("SPOTIFY API CREDENTIALS REQUIRED")
        print("="*60)
        print("\nTo export your Spotify library, you need to create a Spotify app:")
        print("\n1. Go to https://developer.spotify.com/dashboard")
        print("2. Log in with your Spotify account")
        print("3. Click 'Create an App'")
        print("4. Fill in App Name (e.g., 'Music Library Export') and Description")
        print("5. Click 'Create'")
        print("6. In the app settings, add Redirect URI: http://localhost:8888/callback")
        print("7. Copy your Client ID and Client Secret")
        print("\n" + "="*60 + "\n")

        if not client_id:
            client_id = input("Enter your Spotify Client ID: ").strip()
        if not client_secret:
            client_secret = input("Enter your Spotify Client Secret: ").strip()

        # Offer to save credentials
        save = input("\nWould you like to save these credentials? (y/n): ").strip().lower()
        if save == 'y':
            print("\nAdd these lines to your ~/.zshrc or ~/.bashrc:")
            print(f'export SPOTIFY_CLIENT_ID="{client_id}"')
            print(f'export SPOTIFY_CLIENT_SECRET="{client_secret}"')

    return client_id, client_secret


def authorize_spotify(client_id: str) -> str:
    """
    Start OAuth flow and get authorization code
    Returns: Authorization code
    """
    # Build authorization URL
    auth_params = {
        'client_id': client_id,
        'response_type': 'code',
        'redirect_uri': REDIRECT_URI,
        'scope': SCOPE
    }

    auth_url = f"{AUTH_URL}?{'&'.join([f'{k}={v}' for k, v in auth_params.items()])}"

    print("\n" + "="*60)
    print("SPOTIFY AUTHORIZATION")
    print("="*60)
    print("\nOpening browser for Spotify login...")
    print("Please log in and authorize the application.")
    print("Waiting for authorization...")

    # Open browser for user to authorize
    webbrowser.open(auth_url)

    # Start local server to receive callback
    server = HTTPServer(('localhost', 8888), CallbackHandler)
    server.handle_request()  # Handle one request and then stop

    if auth_code is None:
        raise Exception("Failed to receive authorization code")

    return auth_code


def get_access_token(client_id: str, client_secret: str, auth_code: str) -> str:
    """
    Exchange authorization code for access token
    Returns: Access token
    """
    # Encode credentials
    credentials = f"{client_id}:{client_secret}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()

    headers = {
        'Authorization': f'Basic {encoded_credentials}',
        'Content-Type': 'application/x-www-form-urlencoded'
    }

    data = {
        'grant_type': 'authorization_code',
        'code': auth_code,
        'redirect_uri': REDIRECT_URI
    }

    response = requests.post(TOKEN_URL, headers=headers, data=data)
    response.raise_for_status()

    return response.json()['access_token']


def get_user_saved_tracks(access_token: str) -> List[Dict]:
    """
    Fetch all saved tracks from user's Spotify library
    Returns: List of track dictionaries
    """
    headers = {
        'Authorization': f'Bearer {access_token}'
    }

    tracks = []
    url = f"{API_BASE_URL}/me/tracks"
    params = {'limit': 50}  # Max allowed by Spotify API

    print("\n" + "="*60)
    print("FETCHING SPOTIFY LIBRARY")
    print("="*60 + "\n")

    total_tracks = None

    while url:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()

        data = response.json()

        if total_tracks is None:
            total_tracks = data['total']
            print(f"Total tracks in library: {total_tracks}")

        tracks.extend(data['items'])
        print(f"Fetched {len(tracks)}/{total_tracks} tracks...", end='\r')

        url = data['next']  # Next page URL or None
        params = {}  # Clear params for next requests (URL contains all needed params)

    print(f"\nSuccessfully fetched {len(tracks)} tracks!")

    return tracks


def format_track(track_item: Dict) -> str:
    """
    Format track data as "Artist Name - Song Name"
    Returns: Formatted string
    """
    track = track_item['track']

    # Get primary artist (first artist in the list)
    artist = track['artists'][0]['name'] if track['artists'] else 'Unknown Artist'

    # Get track name
    song = track['name']

    return f"{artist} - {song}"


def export_to_file(tracks: List[Dict], output_file: str):
    """
    Export tracks to text file in format ready for batch download
    """
    print("\n" + "="*60)
    print("EXPORTING TO FILE")
    print("="*60 + "\n")

    # Format tracks
    formatted_tracks = [format_track(item) for item in tracks]

    # Remove duplicates while preserving order
    seen = set()
    unique_tracks = []
    for track in formatted_tracks:
        if track not in seen:
            seen.add(track)
            unique_tracks.append(track)

    if len(formatted_tracks) != len(unique_tracks):
        print(f"Removed {len(formatted_tracks) - len(unique_tracks)} duplicate entries")

    # Write to file
    with open(output_file, 'w', encoding='utf-8') as f:
        for track in unique_tracks:
            f.write(track + '\n')

    print(f"✓ Exported {len(unique_tracks)} unique tracks to: {output_file}")
    print(f"\nYou can now use this file for batch downloading:")
    print(f"  while read line; do download_music \"$line\"; done < {output_file}")
    print(f"\nOr use the batch download script:")
    print(f"  ./batch_download.sh {output_file}")


def main():
    """Main execution function"""
    # Default output file
    output_file = sys.argv[1] if len(sys.argv) > 1 else 'spotify_library.txt'

    try:
        # Get Spotify credentials
        client_id, client_secret = get_spotify_credentials()

        if not client_id or not client_secret:
            print("\nError: Spotify credentials are required!")
            sys.exit(1)

        # Start OAuth flow
        code = authorize_spotify(client_id)

        # Get access token
        print("\n✓ Authorization successful!")
        print("Getting access token...")
        access_token = get_access_token(client_id, client_secret, code)

        # Fetch user's saved tracks
        tracks = get_user_saved_tracks(access_token)

        if not tracks:
            print("\nNo tracks found in your Spotify library!")
            sys.exit(0)

        # Export to file
        export_to_file(tracks, output_file)

        print("\n" + "="*60)
        print("EXPORT COMPLETE!")
        print("="*60 + "\n")

    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nError: {str(e)}")
        sys.exit(1)


if __name__ == '__main__':
    main()
