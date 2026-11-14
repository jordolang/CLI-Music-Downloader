"""Settings, playlists, play counts and loved songs, kept in one JSON file."""

import json
import logging
import threading
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional

from ..recommend import cache_dir
from ..sources import DEFAULT_SOURCES

logger = logging.getLogger(__name__)

DEFAULT_SETTINGS = {
    "library": str(Path("~/Music").expanduser()),
    "sources": list(DEFAULT_SOURCES),
    "lyrics": True,
    "quality": "0",
    "cookies_from_browser": "",
    "organize_on_edit": True,
    "workers": 2,
}


def state_path() -> Path:
    return cache_dir() / "gui_state.json"


class AppState:
    def __init__(self, path: Optional[Path] = None):
        self.path = path or state_path()
        self._lock = threading.RLock()
        self.settings: Dict = dict(DEFAULT_SETTINGS)
        self.playlists: List[Dict] = []
        self.plays: Dict[str, Dict] = {}  # song id -> {"count": n, "last": ts}
        self.loved: List[str] = []
        self._load()

    def _load(self) -> None:
        try:
            data = json.loads(self.path.read_text())
        except Exception:
            return
        self.settings.update({k: v for k, v in (data.get("settings") or {}).items() if k in DEFAULT_SETTINGS})
        self.playlists = data.get("playlists") or []
        self.plays = data.get("plays") or {}
        self.loved = data.get("loved") or []

    def save(self) -> None:
        with self._lock:
            data = {"settings": self.settings, "playlists": self.playlists, "plays": self.plays,
                    "loved": self.loved}
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                tmp = self.path.with_suffix(".tmp")
                tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False))
                tmp.replace(self.path)
            except OSError as exc:
                logger.warning("Could not save GUI state: %s", exc)

    def to_dict(self) -> Dict:
        with self._lock:
            return {"settings": self.settings, "playlists": self.playlists, "plays": self.plays,
                    "loved": self.loved}

    # ------------------------------------------------------------- settings

    def update_settings(self, changes: Dict) -> Dict:
        with self._lock:
            for key, value in changes.items():
                if key not in DEFAULT_SETTINGS:
                    continue
                if key == "sources":
                    value = [s for s in value if s in DEFAULT_SOURCES] or list(DEFAULT_SOURCES)
                if key == "workers":
                    value = max(1, min(4, int(value)))
                if key == "library":
                    value = str(Path(value).expanduser())
                self.settings[key] = value
            self.save()
            return dict(self.settings)

    # ------------------------------------------------------------- playlists

    def playlist(self, pid: str) -> Optional[Dict]:
        return next((p for p in self.playlists if p["id"] == pid), None)

    def create_playlist(self, name: str, songs: Optional[List[str]] = None) -> Dict:
        with self._lock:
            pl = {"id": uuid.uuid4().hex[:10], "name": name.strip() or "Untitled Playlist",
                  "songs": list(dict.fromkeys(songs or [])), "created": time.time()}
            self.playlists.append(pl)
            self.save()
            return pl

    def update_playlist(self, pid: str, name: Optional[str] = None, songs: Optional[List[str]] = None,
                        add: Optional[List[str]] = None, remove: Optional[List[str]] = None) -> Dict:
        with self._lock:
            pl = self.playlist(pid)
            if not pl:
                raise KeyError(pid)
            if name is not None:
                pl["name"] = name.strip() or pl["name"]
            if songs is not None:
                pl["songs"] = list(dict.fromkeys(songs))
            if add:
                pl["songs"] = list(dict.fromkeys(pl["songs"] + list(add)))
            if remove:
                drop = set(remove)
                pl["songs"] = [s for s in pl["songs"] if s not in drop]
            self.save()
            return pl

    def delete_playlist(self, pid: str) -> None:
        with self._lock:
            self.playlists = [p for p in self.playlists if p["id"] != pid]
            self.save()

    def rename_song(self, old_id: str, new_id: str) -> None:
        """Keep playlists, plays and loves when a file is moved (its id follows its path)."""
        if old_id == new_id:
            return
        with self._lock:
            for pl in self.playlists:
                pl["songs"] = [new_id if s == old_id else s for s in pl["songs"]]
            if old_id in self.plays:
                self.plays[new_id] = self.plays.pop(old_id)
            self.loved = [new_id if s == old_id else s for s in self.loved]
            self.save()

    # ------------------------------------------------------------- listening

    def record_play(self, sid: str) -> Dict:
        with self._lock:
            entry = self.plays.setdefault(sid, {"count": 0, "last": 0})
            entry["count"] += 1
            entry["last"] = time.time()
            self.save()
            return entry

    def set_loved(self, sid: str, loved: bool) -> List[str]:
        with self._lock:
            if loved and sid not in self.loved:
                self.loved.append(sid)
            if not loved:
                self.loved = [s for s in self.loved if s != sid]
            self.save()
            return self.loved
