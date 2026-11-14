"""
Download the helper programs bundled with the desktop builds into packaging/tools/:

  * ffmpeg, ffprobe, ffplay - audio conversion, tagging checks and previews
  * deno                    - the JavaScript runtime yt-dlp needs for YouTube

Usage: python packaging/fetch_tools.py [--arch arm64|x86_64]
"""

import argparse
import io
import os
import platform
import shutil
import stat
import sys
import urllib.request
import zipfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parent / "tools"
DENO = "https://github.com/denoland/deno/releases/latest/download/deno-{target}.zip"
WIN_FFMPEG = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
MAC_FFMPEG = "https://ffmpeg.martin-riedl.de/redirect/latest/macos/{arch}/release/{name}.zip"


def _download(url: str) -> zipfile.ZipFile:
    print(f"  downloading {url}", flush=True)
    req = urllib.request.Request(url, headers={"User-Agent": "cli-music-downloader-build"})
    with urllib.request.urlopen(req, timeout=300) as resp:
        return zipfile.ZipFile(io.BytesIO(resp.read()))


def _extract(zf: zipfile.ZipFile, wanted: str) -> None:
    """Copy the archive member whose file name is `wanted` into TOOLS."""
    for info in zf.infolist():
        if not info.is_dir() and Path(info.filename).name == wanted:
            dest = TOOLS / wanted
            with zf.open(info) as src, open(dest, "wb") as out:
                shutil.copyfileobj(src, out)
            dest.chmod(dest.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            print(f"  -> {dest.name} ({dest.stat().st_size // 1_000_000} MB)")
            return
    raise SystemExit(f"{wanted} not found in archive")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arch", default=platform.machine().lower())
    args = parser.parse_args()
    arch = {"aarch64": "arm64", "amd64": "x86_64", "x64": "x86_64"}.get(args.arch, args.arch)

    shutil.rmtree(TOOLS, ignore_errors=True)
    TOOLS.mkdir(parents=True)
    if sys.platform == "win32":
        zf = _download(WIN_FFMPEG)
        for name in ("ffmpeg.exe", "ffprobe.exe", "ffplay.exe"):
            _extract(zf, name)
        _extract(_download(DENO.format(target="x86_64-pc-windows-msvc")), "deno.exe")
    elif sys.platform == "darwin":
        mac_arch = "arm64" if arch == "arm64" else "amd64"
        for name in ("ffmpeg", "ffprobe", "ffplay"):
            _extract(_download(MAC_FFMPEG.format(arch=mac_arch, name=name)), name)
        target = "aarch64-apple-darwin" if arch == "arm64" else "x86_64-apple-darwin"
        _extract(_download(DENO.format(target=target)), "deno")
    else:
        raise SystemExit("Desktop builds are made for Windows and macOS only")
    print(f"Tools ready in {TOOLS}: {', '.join(sorted(os.listdir(TOOLS)))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
