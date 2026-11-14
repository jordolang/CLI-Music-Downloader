## CLI Music desktop app

Standalone builds for Windows and macOS. Python, ffmpeg and deno are bundled, so there is nothing else to install.

| Download | For |
| --- | --- |
| `CLI-Music-*-windows-x64.zip` | Windows 10 / 11 (64-bit) |
| `CLI-Music-*-macos-arm64.dmg` | Macs with Apple silicon (M1 and later) |
| `CLI-Music-*-macos-intel.dmg` | Intel Macs |

**What it does**
- Library browser and player, playlists, tag editing and organizing
- Search with song and video previews, one-click downloads saved as `Artist/Title.mp3` with metadata, album artwork and lyrics
- Song-list (PDF/CSV) downloader and music suggester from the command line

**First launch**
- **macOS:** the app is not notarized. Open it once, then go to System Settings → Privacy & Security and click **Open Anyway**. Or run `xattr -dr com.apple.quarantine "/Applications/CLI Music.app"`.
- **Windows:** if SmartScreen shows a warning, click **More info → Run anyway**.

**Command line:** run `CLI Music` (macOS: `CLI Music.app/Contents/MacOS/CLI Music`) or `cli-music-downloader.exe` (Windows) with `--help`.

Verify downloads with `SHA256SUMS.txt`.
