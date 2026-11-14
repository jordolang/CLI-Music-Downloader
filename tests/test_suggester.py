"""Tests for the music suggester: library scan, recommendations, previews and the TUI."""

import asyncio
import json

import pytest

from cli_music_downloader import recommend
from cli_music_downloader.library import Result
from cli_music_downloader.preview import Previewer, PreviewSource
from cli_music_downloader.recommend import (LibraryProfile, LibrarySong, Recommender, Suggestion, core_title,
                                            scan_library)


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))


def _profile(*songs, listed=()):
    return LibraryProfile("/music", [LibrarySong(path="", title=t, artist=a) for a, t in songs], listed)


# ------------------------------------------------------------------ library


def test_scan_library_uses_tags_or_folder_layout(tmp_path):
    (tmp_path / "Shinedown").mkdir()
    (tmp_path / "Shinedown" / "45.mp3").write_bytes(b"not really an mp3")
    (tmp_path / ".hidden").mkdir()
    (tmp_path / ".hidden" / "x.mp3").write_bytes(b"")
    (tmp_path / "download_report.json").write_text(json.dumps(
        {"tracks": [{"number": 1, "title": "Second Chance", "artist": "Shinedown", "status": "failed"}]}))
    profile = scan_library(tmp_path)
    assert [(s.artist, s.title) for s in profile.songs] == [("Shinedown", "45")]
    assert profile.owns("Shinedown", "45")
    assert profile.owns("Shinedown", "Second Chance")  # on the song list, still downloading


def test_profile_ownership_ignores_case_credits_and_remasters():
    p = _profile(("Juice WRLD & YoungBoy Never Broke Again", "Bandit"), ("Creed", "One Last Breath"))
    assert p.owns("Juice WRLD", "Bandit (feat. YoungBoy Never Broke Again)")
    assert p.owns("CREED", "One Last Breath (2004 Remaster)")
    assert p.owns("Creed", "One Last Breath - Remastered 2011")
    assert not p.owns("Creed", "My Sacrifice")
    assert core_title("Youth of the Nation (Live)") != core_title("Youth of the Nation")


def test_profile_weights_full_credit_and_collaborators():
    p = _profile(("Florence and the Machine", "Dog Days"), ("Jessie Murph & Jelly Roll", "Wild Ones"),
                 ("Jelly Roll", "Save Me"))
    weights = dict(p.top_artists(10))
    assert weights["Florence and the Machine"] == 1.0
    assert weights["Jelly Roll"] == 1.5  # own song + collaboration
    assert p.knows_artist("jelly roll")


# ------------------------------------------------------------------ recommendations


def _track(tid, title, artist, rank=500000, duration=200, version=""):
    return {"id": tid, "title": title, "title_version": version, "duration": duration, "rank": rank,
            "explicit_lyrics": False, "artist": {"id": hash(artist) % 10000, "name": artist},
            "album": {"title": f"{title} - Single"}}


FAKE_DEEZER = {
    "/search/artist?limit=5&q=Shinedown": {"data": [{"id": 1, "name": "Shinedown"}]},
    "/search/artist?limit=5&q=Creed": {"data": [{"id": 2, "name": "Creed"}]},
    "/artist/1/related?limit=25": {"data": [{"id": 10, "name": "Breaking Benjamin"}, {"id": 11, "name": "Creed"}]},
    "/artist/2/related?limit=25": {"data": [{"id": 10, "name": "Breaking Benjamin"}, {"id": 12, "name": "Daughtry"}]},
    "/artist/1/top?limit=25": {"data": [
        _track(100, "45", "Shinedown"),  # owned
        _track(101, "Second Chance", "Shinedown"),
        _track(102, "Second Chance (Live)", "Shinedown"),  # different version
        _track(103, "Cut the Cord", "Shinedown"),
    ]},
    "/artist/2/top?limit=25": {"data": [_track(200, "My Sacrifice", "Creed"), _track(201, "Intro", "Creed", duration=40)]},
    "/artist/10/top?limit=10": {"data": [
        _track(300, "The Diary of Jane", "Breaking Benjamin"), _track(301, "So Cold", "Breaking Benjamin"),
        _track(302, "Breath", "Breaking Benjamin"), _track(303, "Dance with the Devil", "Breaking Benjamin")]},
    "/artist/12/top?limit=10": {"data": [_track(400, "Home", "Daughtry", version="(Acoustic)"),
                                         _track(401, "It's Not Over", "Daughtry")]},
}


@pytest.fixture
def fake_deezer(monkeypatch):
    calls = []

    def fake_get(self, path, **params):
        key = path + "?" + "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        calls.append(key)
        return FAKE_DEEZER.get(key, {"data": []})

    monkeypatch.setattr(Recommender, "_get", fake_get)
    return calls


def test_recommend_filters_and_explains(fake_deezer):
    profile = _profile(("Shinedown", "45"), ("Shinedown", "Sound of Madness"), ("Creed", "One Last Breath"))
    picks = Recommender(profile, dismissed={recommend.song_key("Breaking Benjamin", "Breath")}).recommend(25)
    titles = {(s.artist, s.title) for s in picks}
    assert ("Shinedown", "45") not in titles  # already owned
    assert ("Shinedown", "Second Chance (Live)") not in titles  # live version
    assert ("Daughtry", "Home") not in titles  # acoustic version
    assert ("Creed", "Intro") not in titles  # too short
    assert ("Breaking Benjamin", "Breath") not in titles  # dismissed
    assert ("Daughtry", "It's Not Over") in titles
    by_artist = [s for s in picks if s.artist == "Breaking Benjamin"]
    assert len(by_artist) <= 2  # at most two songs per artist
    assert by_artist[0].reason == "Similar to Shinedown & Creed"  # related to both favourites
    shinedown = next(s for s in picks if s.artist == "Shinedown")
    assert shinedown.reason == "You have 2 songs by Shinedown" and shinedown.kind == "known"
    assert picks == sorted(picks, key=lambda s: -s.score)
    assert picks[0].to_track(5).number == 5 and picks[0].duration == 200


def test_recommend_count_is_clamped(fake_deezer):
    profile = _profile(("Shinedown", "45"))
    assert len(Recommender(profile).recommend(500)) <= recommend.MAX_COUNT
    assert Recommender(_profile()).recommend(10) == []  # empty library: nothing to base suggestions on


# ------------------------------------------------------------------ previews


def test_preview_falls_back_to_deezer(monkeypatch):
    monkeypatch.setattr(recommend.catalog, "_get_json", lambda url, *a, **k: {"preview": "https://cdn/p.mp3"})
    pv = Previewer(finder=None, player="ffplay")
    src = pv.resolve(Suggestion(title="Last Resort", artist="Papa Roach", deezer_id=42))
    assert src.url == "https://cdn/p.mp3" and "Deezer" in src.label


def test_preview_uses_deezer_when_youtube_is_slow(monkeypatch):
    import threading

    release = threading.Event()

    class SlowFinder:
        sources = ["youtube"]
        throttled = 0

        def search(self, source, track):
            release.wait(5)
            return [type("C", (), {"url": "https://youtu.be/x", "title": "Song", "uploader": "Artist - Topic"})()]

        def stream_url(self, url):
            return "https://stream", {}

    monkeypatch.setattr(recommend.catalog, "_get_json", lambda url, *a, **k: {"preview": "https://cdn/p.mp3"})
    pv = Previewer(finder=SlowFinder(), player="ffplay", youtube_wait=0.1)
    song = Suggestion(title="Song", artist="Artist", deezer_id=1)
    assert "Deezer" in pv.resolve(song).label
    release.set()
    for _ in range(50):
        if song.key in pv._sources:
            break
        threading.Event().wait(0.05)
    assert pv.resolve(song).url == "https://stream"  # YouTube result is used next time


def test_preview_skips_youtube_while_rate_limited():
    class Finder:
        sources = ["youtube"]
        throttled = 0
        searches = 0

        def search(self, source, track):
            self.searches += 1
            self.throttled += 1
            return []

    finder = Finder()
    pv = Previewer(finder=finder, player="ffplay")
    song = Suggestion(title="Song", artist="Artist")
    assert pv._from_youtube(song) is None and finder.searches == 1
    assert pv._from_youtube(song) is None and finder.searches == 1  # cooling down: no new request


# ------------------------------------------------------------------ TUI


class FakePreviewer:
    available = True
    seconds = 30

    def __init__(self):
        self.played = []

    def play(self, song):
        self.played.append(song.key)
        return PreviewSource("Fake: test", "x")

    def is_playing(self):
        return False

    def stop(self, keep_token=False):
        pass


class FakeDownloader:
    finder = None

    def __init__(self):
        self.tracks = []

    def run(self, tracks):
        self.tracks += tracks
        t = tracks[0]
        return [Result(number=t.number, title=t.title, artist=t.artist, album=t.album, status="downloaded",
                       path=f"/music/{t.artist}/{t.title}.mp3", source="youtube", artwork=True, lyrics=True)]


def test_tui_preview_dismiss_and_download(tmp_path, monkeypatch):
    from cli_music_downloader import suggest_tui
    from textual.widgets import DataTable

    picks = [Suggestion(title=f"Song {i}", artist=f"Artist {i}", album="Album", duration=200,
                        reason="Similar to X", score=1 - i / 100) for i in range(30)]
    profile = _profile(("X", "Y"))
    monkeypatch.setattr(suggest_tui, "scan_library", lambda folder, progress=None: profile)
    monkeypatch.setattr(suggest_tui.Recommender, "recommend", lambda self, count, **kw: list(picks))
    downloader, previewer = FakeDownloader(), FakePreviewer()

    async def scenario():
        app = suggest_tui.SuggesterApp(tmp_path, downloader=downloader, previewer=previewer)
        async with app.run_test(size=(160, 45)) as pilot:
            for _ in range(50):
                await pilot.pause(0.05)
                if app.query_one(DataTable).row_count:
                    break
            table = app.query_one(DataTable)
            assert table.row_count == 30

            await pilot.press("p")
            await pilot.pause(0.2)
            assert previewer.played == [picks[0].key]

            await pilot.press("x")  # dismiss the first song
            await pilot.pause()
            assert table.row_count == 29 and picks[0].key in app.state.dismissed

            await pilot.press("space", "space")  # mark songs 1 and 2
            await pilot.press("D")
            for _ in range(50):
                await pilot.pause(0.05)
                if len(downloader.tracks) == 2 and app.status.get(picks[2].key) == "saved":
                    break
            assert [t.title for t in downloader.tracks] == ["Song 1", "Song 2"]
            assert app.status[picks[1].key] == "saved" and profile.owns("Artist 1", "Song 1")

            await pilot.press("a")  # download all: already saved songs are not queued again
            for _ in range(100):
                await pilot.pause(0.05)
                if len(downloader.tracks) == 29:
                    break
            assert len(downloader.tracks) == 29
            await pilot.press("q")

    asyncio.run(scenario())
