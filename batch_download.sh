#!/bin/zsh

# Navigate to Music directory
mkdir -p ~/Music

# Path to songs list file
echo "Downloading songs from: ~/Desktop/songs_list.txt"
songs_list_file=~/Desktop/songs_list.txt

# Read each line in songs_list.txt
echo "Starting batch download..."
while IFS= read -r line
  do
    # Extract song title from each line (ignoring the initial number)
    song_title=$(echo "$line" | sed 's/^[0-9]*|//')
    
    # Output the song being downloaded
echo "🎵 Downloading: $song_title"

    # Use the InstantMusic command to download
    download_music "$song_title"
    
    # Output completion message for the song
echo "✅ $song_title - Download Complete!"
  done < "$songs_list_file"

echo "All songs downloaded to ~/Music"

