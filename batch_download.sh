#!/bin/zsh
# Batch download a song list into ~/Music/<Artist>/<Title>.mp3
#   ./batch_download.sh Music.pdf            (Apple Music printout)
#   ./batch_download.sh ~/Desktop/songs.txt  (one "Artist - Title" per line)
SCRIPT_DIR="${0:A:h}"
exec "$SCRIPT_DIR/bin/download_songlist" "${1:-$HOME/Desktop/songs_list.txt}" "${@:2}"
