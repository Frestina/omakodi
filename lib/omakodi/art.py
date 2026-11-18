"""Artwork for the remote (SPEC "Artwork").

Kodi serves art through ``/image/``, which needs the login, so the daemon
fetches it and the shell only gets a local file path. Files are named by a
hash of the art URL: the URL itself (it can carry a media server's API key)
is never written down or shown.
"""

import hashlib
import os
import tempfile

from .errors import OmakodiError

MAX_BYTES = 4 * 1024 * 1024
MAX_FILES = 30
MAX_URL = 4096
# Kodi's art keys, best first: a poster, then the item's own thumbnail.
ART_KEYS = ("poster", "tvshow.poster", "thumb", "album.thumb", "icon")


def default_dir():
    base = os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache")
    return os.path.join(base, "omakodi", "art")


def source(item):
    """The ``image://…`` URL of the best art for a Player.GetItem item, or ""."""
    art = item.get("art") if isinstance(item.get("art"), dict) else {}
    for value in [art.get(k) for k in ART_KEYS] + [item.get("thumbnail")]:
        if isinstance(value, str) and value.startswith("image://") and len(value) <= MAX_URL:
            return value
    return ""


def kind(data):
    """The file extension for image bytes, by their first bytes, or None."""
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


class ArtCache:
    def __init__(self, directory=None, max_files=MAX_FILES, max_bytes=MAX_BYTES):
        self.directory = directory or default_dir()
        self.max_files = max_files
        self.max_bytes = max_bytes

    def _name(self, src):
        return hashlib.sha256(src.encode("utf-8")).hexdigest()[:32]

    def cached(self, src):
        """The local file for ``src`` if it is already here, else ""."""
        name = self._name(src)
        for ext in ("jpg", "png", "webp"):
            path = os.path.join(self.directory, f"{name}.{ext}")
            if os.path.isfile(path) and not os.path.islink(path):
                try:
                    os.utime(path)  # recently used: pruned last
                except OSError:
                    pass
                return path
        return ""

    def fetch(self, kodi, src):
        """The local file for ``src``, downloaded if needed; "" when Kodi has
        no usable image for it. Raises OmakodiError when Kodi can't be asked."""
        if not src:
            return ""
        path = self.cached(src)
        if path:
            return path
        try:
            data = kodi.image(src, self.max_bytes)
        except OmakodiError as e:
            if e.kind.startswith("http ") or e.kind == "image too large":
                return ""  # Kodi has nothing (usable) for it
            raise
        ext = kind(data)
        if ext is None:
            return ""
        self._ensure_dir()
        path = os.path.join(self.directory, f"{self._name(src)}.{ext}")
        fd, tmp = tempfile.mkstemp(dir=self.directory, prefix=".art-")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
            os.chmod(tmp, 0o600)
            os.replace(tmp, path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
        self.prune(keep=path)
        return path

    def _ensure_dir(self):
        os.makedirs(self.directory, mode=0o700, exist_ok=True)
        for d in (os.path.dirname(self.directory), self.directory):
            try:
                os.chmod(d, 0o700)
            except OSError:
                pass

    def prune(self, keep=None):
        """Keeps the ``max_files`` most recently used images."""
        try:
            names = os.listdir(self.directory)
        except OSError:
            return
        files = []
        for n in names:
            p = os.path.join(self.directory, n)
            if n.startswith(".art-") or not n.endswith((".jpg", ".png", ".webp")):
                continue
            try:
                files.append((os.lstat(p).st_mtime, p))
            except OSError:
                pass
        files.sort(reverse=True)
        for _, p in files[self.max_files:]:
            if p != keep:
                try:
                    os.unlink(p)
                except OSError:
                    pass
