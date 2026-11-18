"""Reading ~/.config/omakodi/config.json (SPEC "Configuration and credentials")."""

import json
import os
import re
import stat

from .errors import CONFIG, OmakodiError
from .wol import parse_mac

YOUTUBE_MODES = ("smart", "youtube-first", "youtube-only", "sendtokodi-only")
MAX_BYTES = 64 * 1024
# A hostname, IPv4 address or bracket-less IPv6 address. Nothing that could
# change the meaning of the URL it is put into (no "/", "@", "?", "#", spaces).
HOST_RE = re.compile(r"^[A-Za-z0-9._:-]{1,253}$")


def default_path():
    override = os.environ.get("OMAKODI_CONFIG")
    if override:
        return override
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, "omakodi", "config.json")


class Config:
    """The settings omakodi needs. ``repr`` never shows the password."""

    __slots__ = ("path", "host", "http_port", "tcp_port", "username", "password", "youtube_mode",
                 "mac", "wake_on_lan")

    def __init__(self, path, host, http_port=8080, tcp_port=9090, username="", password="",
                 youtube_mode="smart", mac="", wake_on_lan=True):
        self.path = path
        self.host = host
        self.http_port = http_port
        self.tcp_port = tcp_port
        self.username = username
        self.password = password
        self.youtube_mode = youtube_mode
        self.mac = mac  # "" or a valid MAC address that overrides the saved one
        self.wake_on_lan = wake_on_lan

    @property
    def has_login(self):
        return bool(self.username or self.password)

    def public(self):
        """The settings as a dict for display, with the password replaced."""
        return {
            "path": self.path,
            "host": self.host,
            "httpPort": self.http_port,
            "tcpPort": self.tcp_port,
            "username": self.username,
            "password": "set" if self.password else "not set",
            "youtubeMode": self.youtube_mode,
            "mac": self.mac or "not set",
            "wakeOnLan": self.wake_on_lan,
        }

    def __repr__(self):
        return f"Config(host={self.host!r}, http_port={self.http_port}, tcp_port={self.tcp_port})"


def _bad(detail, path):
    return OmakodiError("bad config", f"{detail} in {path}", CONFIG)


def _port(data, key, default, path):
    value = data.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 65535:
        raise _bad(f'"{key}" must be a port number (1-65535)', path)
    return value


def _string(data, key, path):
    value = data.get(key, "")
    if not isinstance(value, str) or len(value) > 1024:
        raise _bad(f'"{key}" must be text', path)
    return value


def load(path=None):
    """Read and check the config. Raises OmakodiError with exit code 3."""
    path = path or default_path()
    try:
        with open(path, "rb") as f:
            st = os.fstat(f.fileno())
            raw = f.read(MAX_BYTES + 1)
    except FileNotFoundError:
        raise OmakodiError("not configured", f"{path} is missing; run `omakodi init`", CONFIG) from None
    except OSError as e:
        raise OmakodiError("bad config", f"can't read {path} ({e.strerror})", CONFIG) from None

    if not stat.S_ISREG(st.st_mode):
        raise _bad("not a regular file", path)
    if len(raw) > MAX_BYTES:
        raise _bad("file is too large", path)
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise _bad("not valid JSON", path) from None
    if not isinstance(data, dict):
        raise _bad("not a JSON object", path)

    host = data.get("host")
    if not isinstance(host, str) or not HOST_RE.match(host):
        raise _bad('"host" must be a hostname or IP address', path)
    username = _string(data, "username", path)
    password = _string(data, "password", path)
    mode = data.get("youtubeMode", "smart")
    if mode not in YOUTUBE_MODES:
        raise _bad('"youtubeMode" must be one of ' + ", ".join(YOUTUBE_MODES), path)

    mac = data.get("mac", "")
    if mac != "":
        mac = parse_mac(mac)
        if mac is None:
            raise _bad('"mac" must be a MAC address like aa:bb:cc:dd:ee:ff', path)
    wake_on_lan = data.get("wakeOnLan", True)
    if not isinstance(wake_on_lan, bool):
        raise _bad('"wakeOnLan" must be true or false', path)

    if password and (st.st_uid != os.getuid() or st.st_mode & 0o077):
        if st.st_uid != os.getuid():
            fix = "it must belong to you"
        else:
            fix = f"run `chmod 600 {path}`"
        raise OmakodiError("config readable by others", f"{path} holds a password; {fix}", CONFIG)

    return Config(
        path=path,
        host=host,
        http_port=_port(data, "httpPort", 8080, path),
        tcp_port=_port(data, "tcpPort", 9090, path),
        username=username,
        password=password,
        youtube_mode=mode,
        mac=mac,
        wake_on_lan=wake_on_lan,
    )


TEMPLATE = {
    "host": "kodi.example.lan",
    "httpPort": 8080,
    "tcpPort": 9090,
    "username": "kodi",
    "password": "",
    "youtubeMode": "smart",
}


def write_template(path=None):
    """Create a config template with mode 600. Refuses to overwrite."""
    path = path or default_path()
    os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raise OmakodiError("already configured", f"{path} exists; edit it instead", CONFIG) from None
    with os.fdopen(fd, "w") as f:
        json.dump(TEMPLATE, f, indent=2)
        f.write("\n")
    return path
