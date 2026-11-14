# PyInstaller spec for the Windows and macOS desktop builds.
# Build with:  python packaging/fetch_tools.py && pyinstaller packaging/cli_music.spec
import os
import sys

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

HERE = os.path.dirname(os.path.abspath(SPEC))
ROOT = os.path.dirname(HERE)
VERSION = os.environ.get("APP_VERSION", "2.1.0")
TOOLS = os.path.join(HERE, "tools")
if not os.path.isdir(TOOLS) or not os.listdir(TOOLS):
    raise SystemExit("packaging/tools is empty: run python packaging/fetch_tools.py first")

datas = [
    (os.path.join(ROOT, "cli_music_downloader", "gui", "static"), "cli_music_downloader/gui/static"),
]
datas += collect_data_files("textual")
datas += collect_data_files("yt_dlp_ejs")
binaries = [(os.path.join(TOOLS, f), "tools") for f in os.listdir(TOOLS)]
hiddenimports = (
    collect_submodules("cli_music_downloader")
    + collect_submodules("textual")
    + collect_submodules("rich")
    + collect_submodules("yt_dlp_ejs")
)

a = Analysis(
    [os.path.join(HERE, "launcher.py")],
    pathex=[ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "pytest", "eyed3", "lyricsgenius", "shazamio", "musicbrainzngs", "pylast",
              "discogs_client", "acrcloud"],
    noarchive=False,
)
pyz = PYZ(a.pure)

gui_exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="CLI Music",
    console=False,
    upx=False,
    argv_emulation=False,
)
targets = [gui_exe]

if sys.platform == "win32":
    # A console twin for running the command-line tool from PowerShell / cmd.
    targets.append(EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name="cli-music-downloader",
        console=True,
        upx=False,
    ))

coll = COLLECT(*targets, a.binaries, a.datas, upx=False, name="CLI Music")

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="CLI Music.app",
        bundle_identifier="com.jordolang.climusic",
        version=VERSION,
        info_plist={
            "CFBundleDisplayName": "CLI Music",
            "CFBundleShortVersionString": VERSION,
            "CFBundleVersion": VERSION,
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "11.0",
            "NSAppleEventsUsageDescription": "CLI Music opens downloaded songs in Finder.",
        },
    )
