CLI Music - desktop app
=======================

Everything is included: ffmpeg (audio conversion) and deno (needed by YouTube
downloads) are bundled, so there is nothing else to install.

macOS
-----
1. Drag "CLI Music.app" into Applications.
2. The app is not notarized by Apple, so the first launch is blocked. Open
   System Settings > Privacy & Security, scroll down and click "Open Anyway"
   next to CLI Music (or run:  xattr -dr com.apple.quarantine "/Applications/CLI Music.app").
Command line:  "/Applications/CLI Music.app/Contents/MacOS/CLI Music" --help

Windows
-------
1. Unzip the folder anywhere (e.g. C:\Program Files or your Documents).
2. Double-click "CLI Music.exe". If SmartScreen warns about an unknown
   publisher, click "More info" > "Run anyway".
3. The window uses Microsoft Edge WebView2, which ships with Windows 10/11.
Command line:  "cli-music-downloader.exe" --help   (in the same folder)

Command line examples
---------------------
  songlist Music.pdf -o ~/Music        download every song on a song list
  download "Artist - Title"            download one song as Artist/Title.mp3
  suggest                              terminal music suggester
  gui                                  the desktop app (default with no arguments)

Songs are saved as <Library>/<Artist>/<Title>.mp3 with metadata, artwork and lyrics.
