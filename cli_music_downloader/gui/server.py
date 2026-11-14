"""
Local HTTP server behind the GUI: a JSON API, the library's audio files (with Range
support so the player can seek), artwork, and a proxy for YouTube/Deezer streams.

It only listens on 127.0.0.1 and every /api request must carry the per-launch token,
so other web pages open in a browser cannot drive it.
"""

import json
import logging
import mimetypes
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, unquote, urljoin, urlparse

import requests

from .. import __version__
from ..catalog import USER_AGENT
from ..songlist import load_song_list
from .index import LibraryIndex
from .jobs import DownloadManager
from .remote import Remote
from .state import AppState

logger = logging.getLogger(__name__)

STATIC = Path(__file__).parent / "static"
CHUNK = 1 << 16
MAX_UPLOAD = 50 * 1024 * 1024

mimetypes.add_type("audio/mp4", ".m4a")
mimetypes.add_type("audio/flac", ".flac")
mimetypes.add_type("audio/ogg", ".ogg")
mimetypes.add_type("audio/ogg", ".opus")
mimetypes.add_type("text/javascript", ".js")


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


class ForYou:
    """Runs the recommender in the background and keeps its latest picks."""

    def __init__(self, app: "App"):
        self.app = app
        self.status = "idle"
        self.message = ""
        self.items: List[Dict] = []
        self.updated = 0.0
        self._lock = threading.Lock()

    def snapshot(self) -> Dict:
        owned = self.app.index.owned_keys()
        items = [dict(i, owned=i["key"] in owned) for i in self.items]
        return {"status": self.status, "message": self.message, "items": items, "updated": self.updated}

    def start(self, shuffle: bool = False) -> None:
        with self._lock:
            if self.status == "running":
                return
            self.status, self.message = "running", "Reading your library"
        threading.Thread(target=self._run, args=(shuffle,), daemon=True).start()

    def _run(self, shuffle: bool) -> None:
        from ..recommend import Recommender, SuggesterState, scan_library

        def progress(message, done, total):
            self.message = f"{message}" if not total else f"{message} ({done}/{total})"

        try:
            profile = scan_library(self.app.index.root, progress)
            picks = Recommender(profile, dismissed=SuggesterState().dismissed).recommend(
                40, progress=progress, shuffle=shuffle)
            self.items = [dict(p.to_dict(), key=p.key) for p in picks]
            self.status = "ready"
            self.message = "" if picks else "No suggestions found (offline, or an empty library?)"
            self.updated = time.time()
        except Exception as exc:
            logger.debug("Recommendations failed", exc_info=True)
            self.status, self.message = "error", str(exc)

    def dismiss(self, key: str) -> None:
        from ..recommend import SuggesterState

        SuggesterState().dismiss(key)
        self.items = [i for i in self.items if i["key"] != key]


class App:
    def __init__(self, library: Optional[str] = None):
        self.token = secrets.token_urlsafe(18)
        self.state = AppState()
        if library:
            self.state.update_settings({"library": library})
        self.index = LibraryIndex(self.state.settings["library"])
        self.remote = Remote(lambda: self.state.settings)
        self.downloads = DownloadManager(self.index, lambda: self.state.settings)
        self.foryou = ForYou(self)
        self.window = None  # pywebview window, when running as a desktop app

    def start_background(self) -> None:
        def loop():
            self.index.scan()
            while True:
                time.sleep(20)
                try:
                    self.index.scan()
                except Exception:
                    logger.debug("Background rescan failed", exc_info=True)
        threading.Thread(target=loop, daemon=True, name="library-scan").start()


# ---------------------------------------------------------------------- routing

Route = Tuple[str, "re.Pattern", Callable]
ROUTES: List[Route] = []


def route(method: str, pattern: str):
    def wrap(fn):
        ROUTES.append((method, re.compile("^" + pattern + "$"), fn))
        return fn
    return wrap


class Handler(BaseHTTPRequestHandler):
    server_version = f"CLIMusic/{__version__}"
    protocol_version = "HTTP/1.1"
    app: App = None  # set by make_server

    def log_message(self, fmt, *args):
        logger.debug("%s - %s", self.address_string(), fmt % args)

    # ------------------------------------------------------------- plumbing

    def _query(self) -> Dict[str, str]:
        return {k: v[-1] for k, v in parse_qs(urlparse(self.path).query).items()}

    def _body(self) -> bytes:
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_UPLOAD:
            raise ApiError(413, "Upload too large")
        return self.rfile.read(length) if length else b""

    def json_body(self) -> Dict:
        raw = self._body()
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except ValueError:
            raise ApiError(400, "Invalid JSON")

    def send_json(self, data, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_bytes(self, data: bytes, mime: str, cache: bool = False) -> None:
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "private, max-age=3600" if cache else "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _authorized(self) -> bool:
        token = self.headers.get("X-Token") or self._query().get("t", "")
        return secrets.compare_digest(token, self.app.token)

    def _local_host(self) -> bool:
        """Reject DNS-rebinding requests: the Host must be this server's loopback address."""
        port = self.server.server_address[1]
        allowed = {f"127.0.0.1:{port}", f"localhost:{port}", f"[::1]:{port}"}
        if self.headers.get("Host", "").lower() not in allowed:
            return False
        origin = self.headers.get("Origin")
        return not origin or origin.lower() in {f"http://{h}" for h in allowed}

    def _dispatch(self, method: str) -> None:
        path = unquote(urlparse(self.path).path)
        try:
            if not self._local_host():
                raise ApiError(403, "Forbidden")
            if not path.startswith("/api/"):
                if method != "GET":
                    raise ApiError(405, "Method not allowed")
                return self._static(path)
            if not self._authorized():
                raise ApiError(403, "Forbidden")
            for m, pattern, fn in ROUTES:
                if m != method:
                    continue
                match = pattern.match(path)
                if match:
                    return fn(self, *match.groups())
            raise ApiError(404, "Not found")
        except ApiError as exc:
            self._error(exc.status, str(exc))
        except (BrokenPipeError, ConnectionResetError):
            pass
        except KeyError as exc:
            self._error(404, f"Not found: {exc}")
        except Exception as exc:
            logger.warning("Error handling %s %s: %s", method, path, exc, exc_info=logger.isEnabledFor(logging.DEBUG))
            self._error(500, str(exc) or exc.__class__.__name__)

    def _error(self, status: int, message: str) -> None:
        try:
            self.send_json({"error": message}, status)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")

    def do_PUT(self):
        self._dispatch("PUT")

    def do_DELETE(self):
        self._dispatch("DELETE")

    # ------------------------------------------------------------- static

    def _static(self, path: str) -> None:
        if path in ("/", "/index.html"):
            html = (STATIC / "index.html").read_text(encoding="utf-8")
            html = html.replace("__TOKEN__", self.app.token).replace("__VERSION__", __version__)
            return self.send_bytes(html.encode("utf-8"), "text/html; charset=utf-8")
        target = (STATIC / path.lstrip("/")).resolve()
        if STATIC.resolve() not in target.parents or not target.is_file():
            raise ApiError(404, "Not found")
        mime = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        self.send_bytes(target.read_bytes(), mime)

    def send_file(self, path: Path, mime: Optional[str] = None) -> None:
        size = path.stat().st_size
        mime = mime or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        start, end = 0, size - 1
        rng = self.headers.get("Range")
        status = 200
        if rng:
            m = re.match(r"bytes=(\d*)-(\d*)", rng)
            if m:
                if m.group(1):
                    start = int(m.group(1))
                    end = int(m.group(2)) if m.group(2) else size - 1
                elif m.group(2):  # suffix range: last N bytes
                    start = max(0, size - int(m.group(2)))
                end = min(end, size - 1)
                if start > end:
                    self.send_response(416)
                    self.send_header("Content-Range", f"bytes */{size}")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                status = 206
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        if status == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        with open(path, "rb") as fh:
            fh.seek(start)
            remaining = end - start + 1
            while remaining > 0:
                chunk = fh.read(min(CHUNK, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)

    def proxy(self, url: str, headers: Dict[str, str], mime: str = "") -> None:
        upstream_headers = {"User-Agent": USER_AGENT, **headers}
        if self.headers.get("Range"):
            upstream_headers["Range"] = self.headers["Range"]
        try:
            resp = requests.get(url, headers=upstream_headers, stream=True, timeout=(10, 60))
        except requests.RequestException as exc:
            raise ApiError(502, f"Stream unavailable: {exc}")
        with resp:
            if resp.status_code >= 400:
                raise ApiError(502, f"Stream unavailable (HTTP {resp.status_code})")
            self.send_response(resp.status_code)
            ctype = resp.headers.get("Content-Type", "")
            if mime and (not ctype or ctype.startswith(("application/octet-stream", "binary/"))):
                ctype = mime
            self.send_header("Content-Type", ctype or mime or "application/octet-stream")
            for name in ("Content-Length", "Content-Range"):
                if resp.headers.get(name):
                    self.send_header(name, resp.headers[name])
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Cache-Control", "no-store")
            if not resp.headers.get("Content-Length"):
                self.send_header("Connection", "close")
                self.close_connection = True
            self.end_headers()
            for chunk in resp.iter_content(CHUNK):
                self.wfile.write(chunk)


# ---------------------------------------------------------------------- API


def _song_or_404(h: Handler, sid: str):
    song = h.app.index.get(sid)
    if not song:
        raise ApiError(404, "Song not found")
    return song


def _library_payload(app: App) -> Dict:
    return {"version": app.index.version, "root": str(app.index.root), "exists": app.index.root.is_dir(),
            "songs": [s.to_dict() for s in app.index.songs()]}


@route("GET", r"/api/bootstrap")
def api_bootstrap(h: Handler):
    app = h.app
    h.send_json({
        "version": __version__,
        "desktop": app.window is not None,
        "state": app.state.to_dict(),
        "library": _library_payload(app),
        "downloads": {"version": app.downloads.version, "jobs": app.downloads.jobs()},
        "ffmpeg": bool(shutil.which("ffmpeg")),
    })


@route("GET", r"/api/poll")
def api_poll(h: Handler):
    h.send_json({"library": h.app.index.version, "downloads": h.app.downloads.version,
                 "active": h.app.downloads.active_count(), "scanning": h.app.index.scanning,
                 "foryou": h.app.foryou.status})


@route("GET", r"/api/library")
def api_library(h: Handler):
    h.send_json(_library_payload(h.app))


@route("POST", r"/api/library/rescan")
def api_rescan(h: Handler):
    h.app.index.scan()
    h.send_json({"version": h.app.index.version})


@route("GET", r"/api/art/([0-9a-f]+)")
def api_art(h: Handler, sid: str):
    size = max(0, min(1400, int(h._query().get("s", "300"))))
    data = h.app.index.artwork(sid, size)
    if not data:
        raise ApiError(404, "No artwork")
    h.send_bytes(data, "image/jpeg", cache=True)


@route("GET", r"/api/audio/([0-9a-f]+)")
def api_audio(h: Handler, sid: str):
    song = _song_or_404(h, sid)
    path = h.app.index.abspath(song)
    if not path.exists():
        raise ApiError(404, "File is missing")
    h.send_file(path)


@route("GET", r"/api/lyrics/([0-9a-f]+)")
def api_lyrics(h: Handler, sid: str):
    _song_or_404(h, sid)
    h.send_json({"lyrics": h.app.index.lyrics(sid)})


@route("PUT", r"/api/songs/([0-9a-f]+)")
def api_update_song(h: Handler, sid: str):
    body = h.json_body()
    _song_or_404(h, sid)
    organize = body.get("organize", h.app.state.settings.get("organize_on_edit", True))
    lyrics = body.get("lyrics")
    new = h.app.index.update_tags(sid, body.get("changes") or {}, organize=bool(organize),
                                  lyrics=lyrics if isinstance(lyrics, str) and lyrics.strip() else None)
    h.app.state.rename_song(sid, new.id)
    h.send_json({"song": new.to_dict(), "old_id": sid})


@route("DELETE", r"/api/songs/([0-9a-f]+)")
def api_delete_song(h: Handler, sid: str):
    _song_or_404(h, sid)
    h.app.index.delete(sid)
    for pl in h.app.state.playlists:
        if sid in pl["songs"]:
            h.app.state.update_playlist(pl["id"], remove=[sid])
    h.send_json({"ok": True})


@route("POST", r"/api/songs/([0-9a-f]+)/reveal")
def api_reveal(h: Handler, sid: str):
    song = _song_or_404(h, sid)
    path = h.app.index.abspath(song)
    if sys.platform == "darwin":
        subprocess.Popen(["open", "-R", str(path)])
    else:
        webbrowser.open(path.parent.as_uri())
    h.send_json({"ok": True})


@route("POST", r"/api/songs/([0-9a-f]+)/fix")
def api_fix(h: Handler, sid: str):
    song = _song_or_404(h, sid)
    job = h.app.downloads.add("fix", song.title, song.artist, song_id=song.id,
                              artwork=f"/api/art/{song.id}?s=120&t={h.app.token}" if song.has_art else "")
    h.send_json({"job": job.to_dict()})


@route("POST", r"/api/fix-missing")
def api_fix_missing(h: Handler):
    body = h.json_body()
    ids = set(body.get("ids") or [])
    jobs = []
    for s in h.app.index.songs():
        if ids and s.id not in ids:
            continue
        if not ids and s.has_art and s.has_lyrics and s.album and s.genre:
            continue
        jobs.append(h.app.downloads.add("fix", s.title, s.artist, song_id=s.id).to_dict())
    h.send_json({"queued": len(jobs)})


@route("GET", r"/api/organize")
def api_organize_preview(h: Handler):
    h.send_json({"moves": h.app.index.misplaced()})


@route("POST", r"/api/organize")
def api_organize(h: Handler):
    moved = h.app.index.organize_all()
    for old, new in moved.items():
        h.app.state.rename_song(old, new)
    h.send_json({"moved": len(moved)})


@route("POST", r"/api/play/([0-9a-f]+)")
def api_play(h: Handler, sid: str):
    h.send_json(h.app.state.record_play(sid))


@route("POST", r"/api/love/([0-9a-f]+)")
def api_love(h: Handler, sid: str):
    h.send_json({"loved": h.app.state.set_loved(sid, bool(h.json_body().get("loved", True)))})


@route("POST", r"/api/playlists")
def api_new_playlist(h: Handler):
    body = h.json_body()
    h.send_json({"playlist": h.app.state.create_playlist(body.get("name", ""), body.get("songs"))})


@route("PUT", r"/api/playlists/([0-9a-f]+)")
def api_edit_playlist(h: Handler, pid: str):
    b = h.json_body()
    h.send_json({"playlist": h.app.state.update_playlist(pid, b.get("name"), b.get("songs"), b.get("add"),
                                                         b.get("remove"))})


@route("DELETE", r"/api/playlists/([0-9a-f]+)")
def api_delete_playlist(h: Handler, pid: str):
    h.app.state.delete_playlist(pid)
    h.send_json({"ok": True})


@route("PUT", r"/api/settings")
def api_settings(h: Handler):
    app = h.app
    old_root = app.state.settings["library"]
    settings = app.state.update_settings(h.json_body())
    if settings["library"] != old_root:
        threading.Thread(target=app.index.set_root, args=(settings["library"],), daemon=True).start()
    h.send_json({"settings": settings})


# --- online

@route("GET", r"/api/search/songs")
def api_search_songs(h: Handler):
    q = h._query().get("q", "").strip()
    h.send_json({"results": h.app.remote.search_songs(q, h.app.index.owned_keys()) if q else []})


@route("GET", r"/api/search/videos")
def api_search_videos(h: Handler):
    q = h._query().get("q", "").strip()
    try:
        results = h.app.remote.search_videos(q, h.app.index.owned_keys()) if q else []
    except Exception as exc:
        raise ApiError(502, str(exc))
    h.send_json({"results": results})


@route("GET", r"/api/youtube/([\w-]{6,20})")
def api_youtube_stream(h: Handler, vid: str):
    kind = "video" if h._query().get("kind") == "video" else "audio"
    try:
        h.send_json(h.app.remote.resolve_stream(vid, kind))
    except Exception as exc:
        raise ApiError(502, str(exc))


_HLS_URI = re.compile(r'URI="([^"]+)"')


def rewrite_playlist(text: str, base_url: str, add: Callable[[str], str], auth: str) -> str:
    """Point every URI in an HLS playlist at the local proxy.

    In a master playlist the URIs are sub-playlists (served again through /api/hls);
    in a media playlist they are segments, keys and init maps (plain byte proxy).
    """
    master = "#EXT-X-STREAM-INF" in text

    def local(uri: str, playlist: bool) -> str:
        token = add(urljoin(base_url, uri.strip()))
        return f"/api/hls/{token}.m3u8?t={auth}" if playlist else f"/api/proxy/{token}?t={auth}"

    out = []
    for line in text.splitlines():
        if line.startswith("#"):
            nested = line.startswith(("#EXT-X-MEDIA:", "#EXT-X-I-FRAME-STREAM-INF:"))
            out.append(_HLS_URI.sub(lambda m: f'URI="{local(m.group(1), nested)}"', line))
        elif line.strip():
            out.append(local(line, master))
        else:
            out.append(line)
    return "\n".join(out) + "\n"


@route("GET", r"/api/hls/([\w-]+)(?:\.m3u8)?")
def api_hls(h: Handler, token: str):
    item = h.app.remote.streams.get(token)
    if not item:
        raise ApiError(404, "Stream expired")
    try:
        resp = requests.get(item["url"], headers={"User-Agent": USER_AGENT, **item["headers"]}, timeout=(10, 30))
    except requests.RequestException as exc:
        raise ApiError(502, f"Stream unavailable: {exc}")
    if resp.status_code >= 400:
        raise ApiError(502, f"Stream unavailable (HTTP {resp.status_code})")
    streams = h.app.remote.streams
    body = rewrite_playlist(resp.text, resp.url, lambda url: streams.add(url, item["headers"]), h.app.token)
    h.send_bytes(body.encode(), "application/vnd.apple.mpegurl")


@route("GET", r"/api/proxy/([\w-]+)")
def api_proxy(h: Handler, token: str):
    item = h.app.remote.streams.get(token)
    if not item:
        raise ApiError(404, "Stream expired")
    h.proxy(item["url"], item["headers"], item["mime"])


@route("GET", r"/api/deezer/(\d+)")
def api_deezer(h: Handler, did: str):
    h.send_json(h.app.remote.deezer_track(int(did)))


@route("GET", r"/api/foryou")
def api_foryou(h: Handler):
    q = h._query()
    fy = h.app.foryou
    if q.get("refresh") == "1" or (fy.status == "idle"):
        fy.start(shuffle=q.get("refresh") == "1" and fy.status != "idle")
    h.send_json(fy.snapshot())


@route("POST", r"/api/foryou/dismiss")
def api_foryou_dismiss(h: Handler):
    h.app.foryou.dismiss(h.json_body().get("key", ""))
    h.send_json({"ok": True})


@route("POST", r"/api/open-url")
def api_open_url(h: Handler):
    url = h.json_body().get("url", "")
    if not re.match(r"^https://", url):
        raise ApiError(400, "Only https links can be opened")
    webbrowser.open(url)
    h.send_json({"ok": True})


# --- downloads

@route("GET", r"/api/downloads")
def api_downloads(h: Handler):
    h.send_json({"version": h.app.downloads.version, "jobs": h.app.downloads.jobs()})


@route("POST", r"/api/downloads")
def api_add_download(h: Handler):
    b = h.json_body()
    kind = "video" if b.get("kind") == "video" else "song"
    if kind == "video" and not re.match(r"^https://(www\.)?(youtube\.com|youtu\.be|music\.youtube\.com)/", b.get("video_url", "")):
        raise ApiError(400, "A YouTube link is required")
    try:
        duration = int(b["duration"]) if b.get("duration") else None
    except (TypeError, ValueError):
        duration = None
    try:
        job = h.app.downloads.add(kind, b.get("title", ""), b.get("artist", ""), album=b.get("album", ""),
                                  duration=duration, video_url=b.get("video_url", ""),
                                  video_title=b.get("video_title", ""), artwork=b.get("artwork", ""))
    except ValueError as exc:
        raise ApiError(400, str(exc))
    h.send_json({"job": job.to_dict()})


@route("POST", r"/api/downloads/(\d+)/cancel")
def api_cancel(h: Handler, jid: str):
    h.app.downloads.cancel(int(jid))
    h.send_json({"ok": True})


@route("POST", r"/api/downloads/(\d+)/retry")
def api_retry(h: Handler, jid: str):
    job = h.app.downloads.retry(int(jid))
    h.send_json({"job": job.to_dict() if job else None})


@route("POST", r"/api/downloads/clear")
def api_clear(h: Handler):
    h.app.downloads.clear_finished()
    h.send_json({"ok": True})


def _queue_list_file(app: App, path: Path) -> int:
    tracks = load_song_list(path)
    if not tracks:
        raise ApiError(400, "No songs found in that file")
    app.downloads.add_tracks(tracks)
    return len(tracks)


@route("POST", r"/api/import-list")
def api_import_list(h: Handler):
    name = Path(h.headers.get("X-Filename") or "list.txt").name
    suffix = Path(name).suffix.lower()
    if suffix not in (".pdf", ".csv", ".txt"):
        raise ApiError(400, "Song lists must be PDF, CSV or TXT")
    data = h._body()
    with tempfile.TemporaryDirectory(prefix="cmd-list-") as tmp:
        path = Path(tmp) / f"list{suffix}"
        path.write_bytes(data)
        count = _queue_list_file(h.app, path)
    h.send_json({"queued": count})


@route("POST", r"/api/dialog")
def api_dialog(h: Handler):
    """Native open dialogs (desktop app only): song lists, audio files to import, library folder."""
    app = h.app
    if app.window is None:
        raise ApiError(400, "Dialogs are only available in the desktop app")
    import webview

    kind = h.json_body().get("kind")
    if kind == "folder":
        picked = app.window.create_file_dialog(webview.FileDialog.FOLDER, directory=str(app.index.root))
        return h.send_json({"paths": list(picked or [])})
    if kind == "list":
        picked = app.window.create_file_dialog(webview.FileDialog.OPEN, allow_multiple=False,
                                               file_types=("Song lists (*.pdf;*.csv;*.txt)",))
        if not picked:
            return h.send_json({"queued": 0})
        return h.send_json({"queued": _queue_list_file(app, Path(picked[0]))})
    if kind == "audio":
        picked = app.window.create_file_dialog(
            webview.FileDialog.OPEN, allow_multiple=True,
            file_types=("Audio files (*.mp3;*.m4a;*.flac;*.ogg;*.wav;*.aiff)",))
        return h.send_json({"imported": app.index.import_files(picked or [])})
    raise ApiError(400, "Unknown dialog")


def make_server(app: App, port: int = 0) -> ThreadingHTTPServer:
    handler = type("BoundHandler", (Handler,), {"app": app})
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    server.daemon_threads = True
    return server
