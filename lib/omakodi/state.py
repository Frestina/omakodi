"""Small durable state in ~/.local/state/omakodi/."""

import json
import os
import tempfile
import threading
import time

AVOID_SECONDS = 30 * 60


def state_dir():
    base = os.environ.get("XDG_STATE_HOME") or os.path.join(os.path.expanduser("~"), ".local", "state")
    return os.path.join(base, "omakodi")


class YoutubeHealth:
    """When the YouTube add-on last failed, for ``smart`` mode."""

    def __init__(self, directory=None, now=time.time):
        self.path = os.path.join(directory or state_dir(), "youtube-failed")
        self.now = now

    def failed_at(self):
        try:
            with open(self.path) as f:
                return float(f.read(64).strip())
        except (OSError, ValueError):
            return None

    def failed_recently(self):
        t = self.failed_at()
        # A time slightly in the future (clock adjusted) still counts; one far
        # in the future is junk and is ignored.
        return t is not None and -60 <= self.now() - t < AVOID_SECONDS

    def record_failure(self):
        os.makedirs(os.path.dirname(self.path), mode=0o700, exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w") as f:
            f.write(f"{self.now():.3f}\n")
        os.replace(tmp, self.path)

    def clear(self):
        try:
            os.remove(self.path)
        except FileNotFoundError:
            pass


class HostValue:
    """One small fact about a Kodi box, kept for its host in DIR/NAME.json
    (mode 600): ``{"host": "kodi.example.lan", KEY: value}``. ``allowed``
    lists the values it keeps; anything else reads as None."""

    MAX_FILE = 4 * 1024

    def __init__(self, name, key, allowed, directory=None):
        self.path = os.path.join(directory or state_dir(), name + ".json")
        self.key = key
        self.allowed = tuple(allowed)
        self._lock = threading.Lock()

    def read(self, host):
        try:
            with open(self.path, "rb") as f:
                raw = f.read(self.MAX_FILE + 1)
            data = json.loads(raw.decode("utf-8")) if len(raw) <= self.MAX_FILE else None
        except (OSError, UnicodeDecodeError, ValueError):
            return None
        if not isinstance(data, dict) or data.get("host") != host:
            return None
        value = data.get(self.key)
        return value if isinstance(value, str) and value in self.allowed else None

    def save(self, host, value):
        """Keep ``value`` for ``host``; writes only when it changes."""
        if value not in self.allowed:
            raise ValueError(f"not one of {self.allowed}")
        with self._lock:
            if self.read(host) == value:
                return False
            directory = os.path.dirname(self.path)
            os.makedirs(directory, mode=0o700, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=directory, prefix="." + os.path.basename(self.path) + ".")
            try:
                with os.fdopen(fd, "w") as f:
                    json.dump({"host": host, self.key: value}, f)
                    f.write("\n")
                os.replace(tmp, self.path)
            except BaseException:
                try:
                    os.remove(tmp)
                except OSError:
                    pass
                raise
        return True
