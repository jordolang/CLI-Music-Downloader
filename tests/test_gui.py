"""Tests for the desktop music app backend: library index, app state and the local HTTP API."""

import json
import shutil
import subprocess
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

pytest.importorskip("mutagen")
from mutagen.id3 import ID3, TALB, TCON, TIT2, TPE1  # noqa: E402

from cli_music_downloader.gui.index import LibraryIndex  # noqa: E402
from cli_music_downloader.gui.remote import clean_video_title  # noqa: E402
from cli_music_downloader.gui.state import AppState  # noqa: E402

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")


def make_mp3(path: Path, title: str, artist: str, album: str = "", genre: str = "") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=22050:cl=mono",
         "-t", "1", "-b:a", "32k", str(path)],
        check=True,
    )
    tags = ID3()
    tags.add(TIT2(encoding=3, text=title))
    tags.add(TPE1(encoding=3, text=artist))
    if album:
        tags.add(TALB(encoding=3, text=album))
    if genre:
        tags.add(TCON(encoding=3, text=genre))
    tags.save(path)
    return path


@pytest.fixture
def cache(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    return tmp_path / "cache"


# ------------------------------------------------------------------ helpers


def test_clean_video_title():
    assert clean_video_title("Adele - Hello (Official Music Video)", "AdeleVEVO") == ("Adele", "Hello")
    assert clean_video_title("Blinding Lights [Official Audio]", "The Weeknd - Topic") == ("The Weeknd", "Blinding Lights")
    assert clean_video_title("Artist – Song | Live at Wembley", "") == ("Artist", "Song")


# ------------------------------------------------------------------ state


def test_state_playlists_and_rename(cache):
    st = AppState()
    pl = st.create_playlist("Road Trip", ["a", "b"])
    st.update_playlist(pl["id"], add=["c", "a"])
    assert st.playlist(pl["id"])["songs"] == ["a", "b", "c"]
    st.update_playlist(pl["id"], remove=["b"])
    st.record_play("a")
    st.set_loved("a", True)
    st.rename_song("a", "z")
    assert st.playlist(pl["id"])["songs"] == ["z", "c"]
    assert "z" in st.loved and "a" not in st.loved
    assert st.plays["z"]["count"] == 1

    reloaded = AppState()
    assert reloaded.playlist(pl["id"])["name"] == "Road Trip"
    reloaded.delete_playlist(pl["id"])
    assert reloaded.playlist(pl["id"]) is None


def test_state_settings_validation(cache, tmp_path):
    st = AppState()
    st.update_settings({"workers": "9", "library": str(tmp_path / "Lib"), "unknown": 1})
    assert 1 <= st.settings["workers"] <= 4
    assert st.settings["library"] == str(tmp_path / "Lib")
    assert "unknown" not in st.settings


# ------------------------------------------------------------------ index


@needs_ffmpeg
def test_index_scan_edit_organize(tmp_path):
    root = tmp_path / "Music"
    make_mp3(root / "random name.mp3", "Hello", "Adele", album="25", genre="Pop")
    make_mp3(root / "Logic" / "skip.mp3", "Loop", "Apple")  # skipped top-level folder
    make_mp3(root / "Some.bundle" / "x.mp3", "Bundle", "Apple")  # skipped package
    idx = LibraryIndex(root)
    idx.scan()
    songs = idx.songs()
    assert [s.title for s in songs] == ["Hello"]
    song = songs[0]
    assert song.artist == "Adele" and song.album == "25" and song.duration > 0

    assert idx.find("adele", "HELLO").id == song.id
    assert len(idx.misplaced()) == 1

    moved = idx.organize_all()
    assert len(moved) == 1
    assert (root / "Adele" / "Hello.mp3").exists()
    assert not idx.misplaced()

    new = idx.update_tags(moved[song.id], {"title": "Hello (Live)", "genre": "Soul"}, organize=True,
                          lyrics="Hello, it's me")
    assert (root / "Adele" / "Hello (Live).mp3").exists()
    assert new.genre == "Soul" and new.has_lyrics
    assert idx.lyrics(new.id) == "Hello, it's me"


# ------------------------------------------------------------------ server


@pytest.fixture
def server(cache, tmp_path, monkeypatch):
    from cli_music_downloader.gui.server import App, make_server

    root = tmp_path / "Music"
    root.mkdir()
    if shutil.which("ffmpeg"):
        make_mp3(root / "Adele" / "Hello.mp3", "Hello", "Adele")
    app = App(library=str(root))
    app.index.scan()
    httpd = make_server(app, 0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    yield app, base
    httpd.shutdown()
    app.downloads.shutdown() if hasattr(app.downloads, "shutdown") else None


def call(base, app, path, method="GET", body=None, headers=None, token=True):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, data=data, method=method)
    if token:
        req.add_header("X-Token", app.token)
    if data:
        req.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=10) as res:
        raw = res.read()
        return res.status, res.headers, raw


def test_server_requires_token(server):
    app, base = server
    with pytest.raises(urllib.error.HTTPError) as exc:
        call(base, app, "/api/bootstrap", token=False)
    assert exc.value.code == 403


def test_server_index_page_has_token(server):
    app, base = server
    status, _, raw = call(base, app, "/", token=False)
    assert status == 200 and app.token.encode() in raw
    for asset in ("/app.js", "/app.css"):
        assert call(base, app, asset, token=False)[0] == 200


def test_server_bootstrap_and_playlists(server):
    app, base = server
    _, _, raw = call(base, app, "/api/bootstrap")
    boot = json.loads(raw)
    assert {"state", "library", "downloads", "version"} <= boot.keys()

    _, _, raw = call(base, app, "/api/playlists", "POST", {"name": "Mix", "songs": []})
    pid = json.loads(raw)["playlist"]["id"]
    _, _, raw = call(base, app, f"/api/playlists/{pid}", "PUT", {"name": "Mix 2"})
    assert json.loads(raw)["playlist"]["name"] == "Mix 2"
    call(base, app, f"/api/playlists/{pid}", "DELETE")
    assert app.state.playlist(pid) is None


@needs_ffmpeg
def test_server_audio_range_and_tags(server):
    app, base = server
    song = app.index.songs()[0]
    status, headers, raw = call(base, app, f"/api/audio/{song.id}", headers={"Range": "bytes=0-99"})
    assert status == 206 and len(raw) == 100 and headers["Content-Range"].startswith("bytes 0-99/")

    _, _, raw = call(base, app, f"/api/songs/{song.id}", "PUT",
                     {"changes": {"album": "25", "year": "2015"}, "organize": True})
    res = json.loads(raw)
    assert res["song"]["album"] == "25" and res["song"]["year"] == "2015"

    _, _, raw = call(base, app, f"/api/love/{res['song']['id']}", "POST", {"loved": True})
    assert res["song"]["id"] in json.loads(raw)["loved"]


def test_server_rejects_non_youtube_video_download(server):
    app, base = server
    with pytest.raises(urllib.error.HTTPError) as exc:
        call(base, app, "/api/downloads", "POST",
             {"kind": "video", "title": "x", "artist": "y", "video_url": "https://evil.example/x"})
    assert exc.value.code == 400


def test_rewrite_hls_playlist():
    from cli_music_downloader.gui.server import rewrite_playlist

    tokens = iter(f"T{i}" for i in range(10))
    master = '#EXTM3U\n#EXT-X-MEDIA:URI="a/aud.m3u8",TYPE=AUDIO\n#EXT-X-STREAM-INF:BANDWIDTH=1\nhttps://x/v.m3u8\n'
    out = rewrite_playlist(master, "https://h/p/master.m3u8", lambda u: next(tokens), "K")
    assert 'URI="/api/hls/T0.m3u8?t=K"' in out and "\n/api/hls/T1.m3u8?t=K" in out
    media = '#EXTM3U\n#EXT-X-MAP:URI="init.mp4"\n#EXTINF:3,\nseg1.ts\n'
    out = rewrite_playlist(media, "https://h/p/v.m3u8", lambda u: next(tokens), "K")
    assert 'URI="/api/proxy/T2?t=K"' in out and "\n/api/proxy/T3?t=K" in out


def test_server_rejects_foreign_host(server):
    """DNS rebinding: a page on another hostname must not get the index page (and its token)."""
    app, base = server
    port = base.rsplit(":", 1)[1]
    for headers in ({"Host": f"evil.example:{port}"}, {"Origin": "http://evil.example"}):
        with pytest.raises(urllib.error.HTTPError) as exc:
            call(base, app, "/", headers=headers, token=False)
        assert exc.value.code == 403
