"""Tests for the song-list downloader: parsing, name completion, matching, paths and tagging."""

import shutil
import subprocess
from pathlib import Path

import pytest

from cli_music_downloader import catalog
from cli_music_downloader.catalog import CatalogInfo, base_title, split_artists
from cli_music_downloader.library import LibraryDownloader, safe_name, track_path
from cli_music_downloader.songlist import Track, parse_duration, parse_text, select_tracks
from cli_music_downloader.sources import score_candidate
from cli_music_downloader.tagger import TagData, prepare_artwork, read_summary, write_tags

MUSIC_PDF = Path(__file__).resolve().parent.parent / "Music.pdf"


# ------------------------------------------------------------------ song list


def test_parse_duration():
    assert parse_duration("3:45") == 225
    assert parse_duration("10:43") == 643
    assert parse_duration("1:02:03") == 3723
    assert parse_duration("") is None
    assert parse_duration("abc") is None


def test_parse_text(tmp_path):
    f = tmp_path / "songs.txt"
    f.write_text("# my list\nEvanescence - Bring Me to Life\n\nJust A Title\n")
    tracks = parse_text(f)
    assert [(t.artist, t.title) for t in tracks] == [("Evanescence", "Bring Me to Life"), ("", "Just A Title")]


def test_select_tracks():
    tracks = [Track(number=i, title=str(i), artist="a") for i in range(1, 11)]
    assert [t.number for t in select_tracks(tracks, "1-3,7")] == [1, 2, 3, 7]
    assert select_tracks(tracks, None) == tracks


@pytest.mark.skipif(not MUSIC_PDF.exists(), reason="Music.pdf not present")
def test_parse_music_pdf():
    from cli_music_downloader.songlist import parse_pdf

    tracks = parse_pdf(MUSIC_PDF)
    by_number = {t.number: t for t in tracks}
    assert len(tracks) == 303
    assert sorted(by_number) == list(range(1, 304))

    first = by_number[1]
    assert (first.title, first.artist, first.album, first.duration) == ("Dare You to Move", "Adam Doleac", "about: TIME", 225)
    # Ligatures (fi/fl) survive extraction
    assert by_number[257].title == "Bullet with Butterfly Wings"
    assert by_number[259].artist == "Sofia Camara & Fernando Daniel"
    # Album and artist rendered in one PDF span are still split into columns
    assert by_number[233].album.startswith("I Do What I Want (Outlaw Country")
    assert by_number[233].artist == "Outlaw Country Rap"
    # Cut-off values are flagged
    assert by_number[149].artist == "Juice WRLD & YoungBoy Never" and by_number[149].artist_truncated
    assert by_number[48].title_truncated
    assert not by_number[1].title_truncated
    # Row without album/artist
    assert by_number[303].artist == "" and by_number[303].duration == 189


# ------------------------------------------------------------ name completion


def test_complete_names_only_fills_truncated_values():
    listed = Track(number=149, title="Bandit", artist="Juice WRLD & YoungBoy Never", album="Bandit - Single",
                   artist_truncated=True)
    info = CatalogInfo(source="itunes", title="Bandit", artist="Juice WRLD & YoungBoy Never Broke Again",
                       album="Bandit - Single")
    done = catalog.complete_names(listed, info)
    assert done.artist == "Juice WRLD & YoungBoy Never Broke Again"
    assert done.title == "Bandit"


def test_complete_names_keeps_listed_text_when_not_truncated():
    listed = Track(number=1, title="Dare You to Move", artist="Adam Doleac", album="about: TIME")
    info = CatalogInfo(source="itunes", title="Dare You To Move (Remix)", artist="Adam Doleac & Someone",
                       album="about: TIME (Deluxe)")
    done = catalog.complete_names(listed, info)
    assert (done.title, done.artist, done.album) == ("Dare You to Move", "Adam Doleac", "about: TIME")


def test_complete_names_ignores_non_prefix_catalog_values():
    listed = Track(number=1, title="Until We Meet Again (feat. Ronnie", artist="Dennis Ellis", title_truncated=True)
    info = CatalogInfo(source="itunes", title="Something Else", artist="Dennis Ellis")
    assert catalog.complete_names(listed, info).title == listed.title


def test_text_helpers():
    assert base_title("Wasted (feat. Lil Uzi Vert)") == "Wasted"
    assert base_title("Holy Forever (Live) [feat. CeCe Wi") == "Holy Forever (Live)"
    assert split_artists("mgk, YUNGBLUD & Travis Barker") == ["mgk", "YUNGBLUD", "Travis Barker"]


# ---------------------------------------------------------- candidate scoring


def _t(**kw):
    base = dict(number=1, title="It Ends Tonight", artist="The All-American Rejects",
                album="Move Along (Deluxe Edition)", duration=244)
    base.update(kw)
    return Track(**base)


def test_score_prefers_official_matching_duration():
    t = _t()
    official = score_candidate(t, "It Ends Tonight", "The All-American Rejects - Topic", 245)
    live = score_candidate(t, "The All-American Rejects - It Ends Tonight (Live)", "Fan", 250)
    cover = score_candidate(t, "It Ends Tonight (Acoustic Cover)", "Someone", 244)
    assert official > 90
    assert official > live and official > cover
    assert cover < 0 and live < 0  # different versions are rejected outright


def test_score_rejects_wrong_song_and_wrong_length():
    t = _t()
    assert score_candidate(t, "Dirty Little Secret", "The All-American Rejects", 244) < 0
    assert score_candidate(t, "It Ends Tonight", "The All-American Rejects", 600) < 0


def test_score_allows_version_words_present_in_listing():
    t = _t(title="The Reason (Acoustic)", artist="Hoobastank", album="Summer Acoustic Hits", duration=234)
    assert score_candidate(t, "The Reason (Acoustic)", "Hoobastank - Topic", 234) > 90


def test_score_matches_censored_titles_and_rejects_clean_edits():
    t = _t(title="Ur Bill Is Big As F**k", artist="Jessie Murph", album="Sex Hysteria", duration=115)
    assert score_candidate(t, "Ur Bill Is Big As Fuck", "Jessie Murph - Topic", 115) > 90
    assert score_candidate(t, "(CLEAN) Jessie Murph - Ur Bill is Big as F##k", "Clean Music Only", 121) < 0


def test_score_rejects_fan_uploads_on_open_platforms():
    t = _t(title="45", artist="Shinedown", album="Leave a Whisper (Deluxe Edition)", duration=249)
    assert score_candidate(t, "45 - Shinedown", "Soft Assumptions", 249, source="soundcloud") < 0
    assert score_candidate(t, "45", "Shinedown", 249, source="soundcloud") > 70
    mgk = _t(title="9 lives", artist="mgk", album="mainstream sellout", duration=181)
    assert score_candidate(mgk, "9 Lives (MGK X LIL PEEP TYPE BEAT)", "mgk", 181, source="soundcloud") < 0


# ------------------------------------------------------------------- paths


def test_safe_name_keeps_text_except_illegal_characters():
    assert safe_name("cre$ce") == "cre$ce"
    assert safe_name("*NSYNC") == "*NSYNC"
    assert safe_name("Sixx:A.M.") == "Sixx-A.M."
    assert safe_name("Far Away (Live at Buffalo Chip, Sturgis, SD, 8/8/2006)") == \
        "Far Away (Live at Buffalo Chip, Sturgis, SD, 8-8-2006)"
    assert safe_name("") == "Untitled"
    assert safe_name("..hidden") == "hidden"


def test_track_path_layout(tmp_path):
    assert track_path(tmp_path, "Evanescence", "Bring Me to Life") == tmp_path / "Evanescence" / "Bring Me to Life.mp3"
    assert track_path(tmp_path, "", "x").parent.name == "Unknown Artist"


def test_duplicates_and_existing_files_are_skipped(tmp_path, monkeypatch):
    monkeypatch.setattr(catalog, "lookup", lambda track: None)
    existing = track_path(tmp_path, "Artist", "Song")
    existing.parent.mkdir(parents=True)
    existing.write_bytes(b"x")
    dl = LibraryDownloader(tmp_path, dry_run=True, workers=2, on_result=lambda *a: None)
    results = dl.run([
        Track(number=1, title="Song", artist="Artist"),
        Track(number=2, title="Song", artist="Artist"),
        Track(number=3, title="Other", artist="Artist"),
    ])
    assert [r.status for r in results] == ["exists", "duplicate", "planned"]
    assert "#1" in results[1].message


# ----------------------------------------------------------------- tagging


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")
def test_write_tags_roundtrip(tmp_path):
    mp3 = tmp_path / "t.mp3"
    subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
                    "-codec:a", "libmp3lame", "-q:a", "5", str(mp3)], check=True)
    from PIL import Image
    import io

    buf = io.BytesIO()
    Image.new("RGB", (1280, 720), (200, 20, 20)).save(buf, format="PNG")
    art = prepare_artwork(buf.getvalue())
    assert Image.open(io.BytesIO(art)).size == (720, 720)  # 16:9 thumbnail cropped square

    write_tags(mp3, TagData(title="Ur Bill Is Big As F**k", artist="Jessie Murph", album="Sex Hysteria",
                            genre="Pop", date="2025-01-01", track_number=15, track_count=23),
               artwork=art, lyrics="la la la")
    s = read_summary(mp3)
    assert s["title"] == "Ur Bill Is Big As F**k"
    assert s["artist"] == "Jessie Murph" and s["album_artist"] == "Jessie Murph"
    assert s["album"] == "Sex Hysteria" and s["genre"] == "Pop"
    assert s["track"] == "15/23" and s["date"].startswith("2025")
    assert s["has_artwork"] and s["has_lyrics"]
