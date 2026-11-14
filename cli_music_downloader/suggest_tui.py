"""
Music Suggester - a terminal UI that reads your library and suggests songs to add.

  p / Enter  play the first 30 seconds        d      download the highlighted song
  s          stop the preview                 Space  mark / unmark
  D          download the marked songs        a      download every suggestion
  x          "not for me" (never suggest it)  r      new suggestions
  q          quit

Downloads use the same search, matching and tagging as the song-list downloader, so
they land in <library>/<Artist>/<Title>.mp3 with metadata, artwork and lyrics.
"""

import queue
import threading
import time
from typing import Dict, List, Optional, Set

from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable, Footer, Header, ProgressBar, RichLog, Static

from .library import LibraryDownloader, Result
from .preview import Previewer, PreviewError
from .recommend import DEFAULT_COUNT, LibraryProfile, Recommender, SuggesterState, Suggestion, scan_library

COLUMNS = (("mark", "", 1), ("title", "Title", 34), ("artist", "Artist", 22), ("album", "Album", 24),
           ("time", "Time", 5), ("why", "Why", 34), ("status", "Status", 20))

STATUS_STYLE = {"queued": "yellow", "downloading": "bold cyan", "saved": "green", "have": "dim",
                "failed": "red", "playing": "magenta"}


def _cut(text: str, width: int) -> str:
    return text if len(text) <= width else text[: width - 1] + "…"


class SuggesterApp(App):
    TITLE = "Music Suggester"
    CSS = """
    #loading { height: auto; padding: 1 2; }
    #loading-text { margin-bottom: 1; }
    #table { height: 1fr; }
    #bottom { height: 11; }
    #details { width: 1fr; border: round $accent; padding: 0 1; }
    #log { width: 1fr; border: round $secondary; }
    """
    BINDINGS = [
        Binding("p", "preview", "Preview 30s"),
        Binding("s", "stop", "Stop"),
        Binding("d", "download", "Download"),
        Binding("space", "mark", "Mark"),
        Binding("D", "download_marked", "Download marked"),
        Binding("a", "download_all", "Download all"),
        Binding("x", "dismiss", "Not for me"),
        Binding("r", "refresh", "New picks"),
        Binding("q", "quit_app", "Quit"),
    ]

    def __init__(self, library_dir, count: int = DEFAULT_COUNT, seeds: int = 20, use_cache: bool = True,
                 downloader: Optional[LibraryDownloader] = None, previewer: Optional[Previewer] = None,
                 downloader_error: str = ""):
        super().__init__()
        self.library_dir = library_dir
        self.count = count
        self.seeds = seeds
        self.use_cache = use_cache
        self.downloader = downloader
        self.downloader_error = downloader_error
        self.previewer = previewer
        self.state = SuggesterState()
        self.profile: Optional[LibraryProfile] = None
        self.suggestions: List[Suggestion] = []
        self.known: Dict[str, Suggestion] = {}  # every suggestion shown this session
        self.status: Dict[str, str] = {}
        self.marked: Set[str] = set()
        self.shown: Set[str] = set()
        self.analyzing = False
        self.playing_key: Optional[str] = None
        self.preview_note = ""
        self._queue: "queue.Queue[Optional[str]]" = queue.Queue()
        self._busy = 0
        self._number = 0
        self._quit_armed = 0.0

    # ------------------------------------------------------------------ layout

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="loading"):
            yield Static("Reading your library…", id="loading-text")
            yield ProgressBar(id="progress", show_eta=False)
        yield DataTable(id="table", cursor_type="row", zebra_stripes=True)
        with Horizontal(id="bottom"):
            yield Static("", id="details")
            yield RichLog(id="log", markup=True, wrap=True)
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        for key, label, width in COLUMNS:
            table.add_column(label, width=width, key=key)
        table.display = False
        threading.Thread(target=self._download_loop, name="downloads", daemon=True).start()
        if self.downloader_error:
            self.log_line(f"[red]Downloads unavailable: {self.downloader_error}[/]")
        if self.previewer and not self.previewer.available:
            self.log_line("[yellow]No audio player found for previews — install ffmpeg (brew install ffmpeg).[/]")
        self.analyze()

    # ------------------------------------------------------------------ analysis

    @work(thread=True, exclusive=True, group="analyze")
    def analyze(self, shuffle: bool = False) -> None:
        self.analyzing = True
        try:
            if self.profile is None:
                self.profile = scan_library(self.library_dir, self._progress_cb)
                self.call_from_thread(self._show_profile)
            if not self.profile.songs:
                self.call_from_thread(self._loading, f"No MP3 files found in {self.library_dir}", None, None)
                return
            self.call_from_thread(self._loading, "Finding artists like the ones you play most…", 0, None)
            rec = Recommender(self.profile, seeds=self.seeds, dismissed=self.state.dismissed,
                              use_cache=self.use_cache)
            picks = rec.recommend(self.count, progress=self._progress_cb, shuffle=shuffle,
                                  exclude=self.shown if shuffle else ())
            if shuffle and len(picks) < 25:  # explored everything: allow earlier picks again
                picks = rec.recommend(self.count, progress=self._progress_cb, shuffle=True)
            self.call_from_thread(self._show_suggestions, picks)
        except Exception as exc:
            self.call_from_thread(self._loading, f"Could not build suggestions: {exc}", None, None)
        finally:
            self.analyzing = False

    def _progress_cb(self, message: str, done: int, total: int) -> None:
        self.call_from_thread(self._loading, message, done, total)

    def _loading(self, message: str, done: Optional[int], total: Optional[int]) -> None:
        self.query_one("#loading").display = True
        self.query_one("#loading-text", Static).update(message)
        bar = self.query_one(ProgressBar)
        bar.display = done is not None
        if done is not None:
            bar.update(total=total, progress=done)

    def _show_profile(self) -> None:
        p = self.profile
        genres = ", ".join(p.top_genres(3))
        self.sub_title = f"{len(p.songs)} songs · {p.artist_count} artists" + (f" · {genres}" if genres else "")

    def _show_suggestions(self, picks: List[Suggestion]) -> None:
        self.suggestions = picks
        self.marked &= {s.key for s in picks}
        table = self.query_one(DataTable)
        table.clear()
        for s in picks:
            self.known[s.key] = s
            self.shown.add(s.key)
            table.add_row(*self._cells(s), key=s.key)
        self.query_one("#loading").display = False
        table.display = True
        table.focus()
        if not picks:
            self._loading("No new suggestions found — check your internet connection and press r to retry.",
                          None, None)
            return
        self.log_line(f"🎧 {len(picks)} suggestions based on your library. "
                      "[b]p[/] preview · [b]d[/] download · [b]a[/] download all")
        self._update_details()

    def _cells(self, s: Suggestion):
        title = _cut(s.title, 34) + (" 🅴" if s.explicit else "")
        return (self._mark_cell(s.key), title, _cut(s.artist, 22), _cut(s.album, 24), s.length,
                Text(_cut(s.reason, 34), style="dim"), self._status_cell(s.key))

    def _mark_cell(self, key: str) -> Text:
        return Text("●", style="bold yellow") if key in self.marked else Text("")

    def _status_cell(self, key: str) -> Text:
        status = self.status.get(key, "")
        if key == self.playing_key:
            status = status or "playing"
        labels = {"queued": "⏳ queued", "downloading": "⬇ downloading…", "saved": "✅ saved",
                  "have": "⏭ in library", "playing": "▶ playing"}
        label = labels.get(status, status if not status.startswith("failed") else "❌ failed")
        return Text(label, style=STATUS_STYLE.get(status.split(":")[0], ""))

    # ------------------------------------------------------------------ helpers

    def log_line(self, markup: str) -> None:
        self.query_one(RichLog).write(Text.from_markup(markup))

    def _current(self) -> Optional[Suggestion]:
        table = self.query_one(DataTable)
        if not table.display or not table.row_count:
            return None
        try:
            key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value
        except Exception:
            return None
        return self.known.get(key)

    def _refresh_row(self, key: str) -> None:
        table = self.query_one(DataTable)
        if key not in table.rows:
            return
        table.update_cell(key, "mark", self._mark_cell(key))
        table.update_cell(key, "status", self._status_cell(key))

    def _set_status(self, key: str, status: str) -> None:
        self.status[key] = status
        self._refresh_row(key)
        self._update_details()

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        self._update_details()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self.action_preview()

    def _update_details(self) -> None:
        s = self._current()
        details = self.query_one("#details", Static)
        if not s:
            details.update("")
            return
        lines = [f"[b]{s.title}[/b]" + ("  [red]🅴 explicit[/]" if s.explicit else ""),
                 f"[cyan]{s.artist}[/cyan]",
                 f"{s.album}" + (f"  ·  {s.length}" if s.length else ""),
                 f"[dim]{s.reason} · popularity {round(s.popularity * 100)}%[/dim]"]
        status = self.status.get(s.key, "")
        if status.startswith("failed"):
            lines.append(f"[red]Download failed: {status.split(':', 1)[-1].strip()}[/]")
        elif status:
            lines.append(f"[green]{self._status_cell(s.key).plain}[/]")
        if s.key == self.playing_key and self.preview_note:
            lines.append(f"[magenta]▶ {self.preview_note}[/]")
        details.update("\n".join(lines))

    # ------------------------------------------------------------------ preview

    def action_preview(self) -> None:
        s = self._current()
        if not s or not self.previewer:
            return
        if s.key == self.playing_key and self.previewer.is_playing():
            self.action_stop()
            return
        self._start_preview(s)

    def _start_preview(self, s: Suggestion) -> None:
        old = self.playing_key
        self.playing_key = s.key
        self.preview_note = "finding the song…"
        if old:
            self._refresh_row(old)
        self._refresh_row(s.key)
        self._update_details()
        self._preview_worker(s)

    @work(thread=True, exclusive=True, group="preview")
    def _preview_worker(self, s: Suggestion) -> None:
        try:
            source = self.previewer.play(s)
        except PreviewError as exc:
            self.call_from_thread(self._preview_done, s.key, f"no preview: {exc}")
            return
        except Exception as exc:
            self.call_from_thread(self._preview_done, s.key, f"preview failed: {exc}")
            return
        if source is None:  # superseded by another preview
            return
        self.call_from_thread(self._preview_started, s.key, source.label)
        time.sleep(1)
        while self.previewer.is_playing() and self.playing_key == s.key:
            time.sleep(0.5)
        if self.playing_key == s.key:
            self.call_from_thread(self._preview_done, s.key, "")

    def _preview_started(self, key: str, label: str) -> None:
        if key != self.playing_key:
            return
        self.preview_note = f"playing first {self.previewer.seconds}s · {label}"
        self._update_details()

    def _preview_done(self, key: str, message: str) -> None:
        if key != self.playing_key:
            return
        self.playing_key = None
        self.preview_note = ""
        self._refresh_row(key)
        self._update_details()
        if message:
            s = self.known.get(key)
            self.log_line(f"[yellow]{s.artist} - {s.title}: {message}[/]" if s else message)

    def action_stop(self) -> None:
        if self.previewer:
            self.previewer.stop()
        key, self.playing_key, self.preview_note = self.playing_key, None, ""
        if key:
            self._refresh_row(key)
        self._update_details()

    # ------------------------------------------------------------------ marking / dismissing

    def action_mark(self) -> None:
        s = self._current()
        if not s:
            return
        self.marked ^= {s.key}
        self._refresh_row(s.key)
        table = self.query_one(DataTable)
        if table.cursor_row < table.row_count - 1:
            table.move_cursor(row=table.cursor_row + 1)

    def action_dismiss(self) -> None:
        s = self._current()
        if not s or self.status.get(s.key) in ("queued", "downloading"):
            return
        if s.key == self.playing_key:
            self.action_stop()
        self.state.dismiss(s.key)
        self.marked.discard(s.key)
        self.suggestions = [x for x in self.suggestions if x.key != s.key]
        self.query_one(DataTable).remove_row(s.key)
        self.log_line(f"[dim]Won't suggest {s.artist} - {s.title} again.[/]")
        self._update_details()

    def action_refresh(self) -> None:
        if self.analyzing:
            return
        self.action_stop()
        self.query_one(DataTable).display = False
        self._loading("Finding new suggestions…", 0, None)
        self.analyze(shuffle=True)

    # ------------------------------------------------------------------ downloads

    def _enqueue(self, songs: List[Suggestion]) -> None:
        if not self.downloader:
            self.log_line(f"[red]Downloads unavailable: {self.downloader_error or 'no downloader'}[/]")
            return
        added = 0
        for s in songs:
            if self.status.get(s.key) in ("queued", "downloading", "saved", "have"):
                continue
            self.known[s.key] = s
            self._set_status(s.key, "queued")
            self._queue.put(s.key)
            added += 1
        if added:
            self.log_line(f"⏳ Queued {added} song{'s' if added != 1 else ''} for download")

    def action_download(self) -> None:
        s = self._current()
        if s:
            self._enqueue([s])

    def action_download_marked(self) -> None:
        songs = [s for s in self.suggestions if s.key in self.marked]
        if not songs:
            self.notify("Mark songs with Space first (or press a to download all)")
            return
        self.marked.clear()
        for s in songs:
            self._refresh_row(s.key)
        self._enqueue(songs)

    def action_download_all(self) -> None:
        self._enqueue(list(self.suggestions))

    def _download_loop(self) -> None:
        # One song at a time: parallel requests make YouTube rate-limit sooner.
        while True:
            key = self._queue.get()
            if key is None:
                return
            s = self.known.get(key)
            if not s:
                continue
            self._busy += 1
            self._number += 1
            self.call_from_thread(self._set_status, key, "downloading")
            try:
                result = self.downloader.run([s.to_track(self._number)])[0]
            except Exception as exc:
                result = Result(number=self._number, title=s.title, artist=s.artist, album=s.album,
                                status="failed", message=str(exc))
            finally:
                self._busy -= 1
            self.call_from_thread(self._download_done, key, result)

    def _download_done(self, key: str, r: Result) -> None:
        s = self.known.get(key)
        if r.status == "downloaded":
            self._set_status(key, "saved")
            extras = ", ".join(x for x, ok in (("artwork", r.artwork), ("lyrics", r.lyrics)) if ok)
            self.log_line(f"[green]✅ {r.artist} - {r.title}[/] → {r.path} [dim]({r.source}"
                          f"{', ' + extras if extras else ''})[/]")
        elif r.status in ("exists", "duplicate"):
            self._set_status(key, "have")
            self.log_line(f"[dim]⏭ {r.artist} - {r.title} is already in your library[/]")
        else:
            self._set_status(key, f"failed: {r.message}")
            self.log_line(f"[red]❌ {r.artist} - {r.title}: {r.message}[/]")
        if s and r.status in ("downloaded", "exists", "duplicate") and self.profile:
            self.profile.add_owned(s.artist, s.title)
        pending = self._queue.qsize() + self._busy
        if not pending:
            done = sum(1 for v in self.status.values() if v == "saved")
            self.notify(f"Downloads finished · {done} saved this session")

    # ------------------------------------------------------------------ quit

    def action_quit_app(self) -> None:
        pending = self._queue.qsize() + self._busy
        if pending and time.monotonic() - self._quit_armed > 4:
            self._quit_armed = time.monotonic()
            self.notify(f"{pending} download(s) still running — press q again to quit anyway "
                        "(unfinished songs are not saved).", severity="warning")
            return
        if self.previewer:
            self.previewer.stop()
        self._queue.put(None)
        self.exit()


def run_tui(library_dir, count: int = DEFAULT_COUNT, seeds: int = 20, use_cache: bool = True,
            downloader_factory=None) -> int:
    downloader, error, finder = None, "", None
    if downloader_factory:
        try:
            downloader = downloader_factory()
            finder = downloader.finder
        except Exception as exc:  # e.g. ffmpeg or yt-dlp missing: browsing still works
            error = str(exc)
    app = SuggesterApp(library_dir, count=count, seeds=seeds, use_cache=use_cache, downloader=downloader,
                       previewer=Previewer(finder), downloader_error=error)
    try:
        app.run()
    finally:
        if app.previewer:
            app.previewer.stop()
    return 0
