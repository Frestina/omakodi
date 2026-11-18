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


MAX_HOSTS = 32  # boxes a per-box file keeps, the most recently changed


def _write_json(path, data):
    """Write ``data`` to ``path`` atomically, mode 600 (folder 700)."""
    directory = os.path.dirname(path)
    os.makedirs(directory, mode=0o700, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, prefix="." + os.path.basename(path) + ".")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f)
            f.write("\n")
        os.replace(tmp, path)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


class HostMap:
    """Small facts about Kodi boxes, one per host, in DIR/NAME.json (mode
    600): ``{"hosts": {"kodi.example.lan": value, ...}}``, the 32 most
    recently changed. Reads the single-box form ``{"host": h, KEY: value}``
    of omakodi 0.2 too (``key``). ``valid(value)`` returns the value to keep,
    or None for one it doesn't take."""

    MAX_FILE = 16 * 1024

    def __init__(self, name, valid, key=None, directory=None):
        self.path = os.path.join(directory or state_dir(), name + ".json")
        self.valid = valid
        self.key = key
        self._lock = threading.Lock()

    def _all(self):
        try:
            with open(self.path, "rb") as f:
                raw = f.read(self.MAX_FILE + 1)
            data = json.loads(raw.decode("utf-8")) if len(raw) <= self.MAX_FILE else None
        except (OSError, UnicodeDecodeError, ValueError):
            return {}
        if not isinstance(data, dict):
            return {}
        hosts = data.get("hosts")
        if isinstance(hosts, dict):
            return {h: v for h, v in hosts.items() if isinstance(h, str)}
        if self.key is not None and isinstance(data.get("host"), str):  # the single-box form
            return {data["host"]: data.get(self.key)}
        return {}

    def read(self, host):
        value = self._all().get(host)
        return None if value is None else self.valid(value)

    def save(self, host, value):
        """Keep ``value`` for ``host``; writes only when it changes. Returns
        whether it wrote. A value ``valid`` refuses raises ValueError."""
        value = self.valid(value)
        if value is None:
            raise ValueError("not a value this file keeps")
        with self._lock:
            hosts = self._all()
            if hosts.get(host) == value:
                return False
            hosts.pop(host, None)
            hosts[host] = value  # the most recent last
            kept = dict(list(hosts.items())[-MAX_HOSTS:])
            _write_json(self.path, {"hosts": kept})
        return True

    def forget(self, host):
        with self._lock:
            hosts = self._all()
            if host not in hosts:
                return False
            del hosts[host]
            _write_json(self.path, {"hosts": hosts})
        return True


class YoutubeHealth:
    """When the YouTube add-on last failed, for ``smart`` mode, per box (the
    add-on is the box's): youtube-failed.json, ``{"hosts": {host: time}}``."""

    def __init__(self, directory=None, now=time.time, host=""):
        self.directory = directory
        self.now = now
        self.host = host
        self._map = HostMap("youtube-failed", _a_time, directory=directory)
        self.path = self._map.path

    def for_host(self, host):
        """The same record, for another box."""
        return YoutubeHealth(self.directory, self.now, host)

    def failed_at(self):
        return self._map.read(self.host)

    def failed_recently(self):
        t = self.failed_at()
        # A time slightly in the future (clock adjusted) still counts; one far
        # in the future is junk and is ignored.
        return t is not None and -60 <= self.now() - t < AVOID_SECONDS

    def record_failure(self):
        self._map.save(self.host, round(self.now(), 3))

    def clear(self):
        self._map.forget(self.host)


def _a_time(value):
    return float(value) if type(value) in (int, float) and value >= 0 else None


class HostValue:
    """One small fact about each Kodi box, kept per host in DIR/NAME.json
    (mode 600, see HostMap; omakodi 0.2 wrote ``{"host": h, KEY: value}``).
    ``allowed`` lists the values it keeps; anything else reads as None."""

    def __init__(self, name, key, allowed, directory=None):
        self.key = key
        self.allowed = tuple(allowed)
        self._map = HostMap(name, lambda v: v if isinstance(v, str) and v in self.allowed else None,
                            key=key, directory=directory)
        self.path = self._map.path

    def read(self, host):
        return self._map.read(host)

    def save(self, host, value):
        """Keep ``value`` for ``host``; writes only when it changes."""
        if value not in self.allowed:
            raise ValueError(f"not one of {self.allowed}")
        return self._map.save(host, value)


class StopNote:
    """When a stop last went to Kodi through omakodi (SPEC "Sending a link"
    step 5): a play's watch, maybe in another process, reads it to tell the
    user's stop from a failure. Wall-clock time, since processes share it."""

    def __init__(self, directory=None, now=time.time):
        self.path = os.path.join(directory or state_dir(), "stopped")
        self.now = now

    def record(self, host=""):
        """Note a stop now, for the box ``host`` it goes to."""
        os.makedirs(os.path.dirname(self.path), mode=0o700, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(self.path), prefix=".stopped.")
        try:
            with os.fdopen(fd, "w") as f:
                f.write(f"{self.now():.3f} {host[:253]}\n")
            os.replace(tmp, self.path)
        except BaseException:
            try:
                os.remove(tmp)
            except OSError:
                pass
            raise

    def since(self, t, host=None):
        """Whether a stop was noted at or after ``t`` (and not in the
        future), for ``host`` when given: a stop sent to another box doesn't
        count. A note without a host (omakodi 0.2) counts for any box."""
        try:
            with open(self.path) as f:
                parts = f.read(512).split(None, 1)
            noted = float(parts[0])
        except (OSError, ValueError, IndexError):
            return False
        noted_host = parts[1].strip() if len(parts) > 1 else ""
        if host is not None and noted_host and noted_host != host:
            return False
        return t <= noted <= self.now() + 60


class ChosenBox:
    """The Kodi box in use, when the config lists several: box.json,
    ``{"host": "kodi.example.lan"}`` (mode 600). Every omakodi process reads
    it, so the bar, the remote, the keybindings and the CLI follow one box."""

    MAX_FILE = 4 * 1024

    def __init__(self, directory=None):
        self.path = os.path.join(directory or state_dir(), "box.json")
        self._lock = threading.Lock()

    def read(self):
        """The chosen box's host, or None."""
        try:
            with open(self.path, "rb") as f:
                raw = f.read(self.MAX_FILE + 1)
            data = json.loads(raw.decode("utf-8")) if len(raw) <= self.MAX_FILE else None
        except (OSError, UnicodeDecodeError, ValueError):
            return None
        host = data.get("host") if isinstance(data, dict) else None
        return host if isinstance(host, str) and 0 < len(host) <= 253 else None

    def save(self, host):
        with self._lock:
            if self.read() == host:
                return False
            _write_json(self.path, {"host": host})
        return True

    def stat_key(self):
        """Changes whenever the file does (for watchers)."""
        try:
            st = os.stat(self.path)
            return (st.st_ino, st.st_mtime_ns, st.st_size)
        except OSError:
            return None


def chosen_box(directory=None):
    return ChosenBox(directory)
