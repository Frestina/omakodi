"""Kodi boxes known by an id (SPEC "Kodi boxes"): each saved box's settings
and state are kept under an id of its own, not under its address.

``migrate`` gives the boxes of a config from before ids one each, and moves
their per-box state from their host to it. ``forget`` clears a deleted
box's. Both hold a lock file in the state folder, so two omakodi processes
never move the same files at once.

The move is safe to stop at any point: the state is copied to the new ids
first (the host's entry stays), then the config is written (atomically,
mode 600, everything in it kept, the passwords too), and only then are the
hosts' entries dropped. Until the config holds the ids, a box without one
goes by its host, so the old files keep working.
"""

import fcntl
import os
import uuid

from . import config as configmod
from .errors import OmakodiError
from .state import ChosenBox, _write_json, read_box_map

# The per-box files: (name, the value's key in omakodi 0.2's one-box form,
# the largest file the store reads).
PER_BOX_FILES = (
    ("mac.json", "mac", 16 * 1024),
    ("volume.json", "keys", 16 * 1024),
    ("youtube-mode.json", "mode", 16 * 1024),
    ("youtube-failed.json", None, 16 * 1024),
    ("shortcuts.json", None, 256 * 1024),
)
LOCK = ".boxes.lock"


def new_id():
    """A new box's id: a random UUID, as a phone remote makes one."""
    return str(uuid.uuid4())


class _Lock:
    """An exclusive lock on DIR/.boxes.lock, across processes."""

    def __init__(self, directory):
        self.directory = directory
        self.fd = None

    def __enter__(self):
        os.makedirs(self.directory, mode=0o700, exist_ok=True)
        self.fd = os.open(os.path.join(self.directory, LOCK), os.O_RDWR | os.O_CREAT | os.O_CLOEXEC, 0o600)
        fcntl.flock(self.fd, fcntl.LOCK_EX)
        return self

    def __exit__(self, *exc):
        os.close(self.fd)  # lets go of the lock
        return False


def _remap(path, key, limit, copies=None, drop=()):
    """Rewrite one per-box file: each ``copies`` host's value also under its
    new ids, then the ``drop`` keys taken out. Writes (atomically, mode 600)
    only when something changes; a missing, unreadable or foreign file is
    left as it is. Raises OSError when it can't write."""
    old = read_box_map(path, key, limit)
    if old is None:
        return False
    new = dict(old)
    for host, ids in (copies or {}).items():
        if host in old:
            for box_id in ids:
                new[box_id] = old[host]
    for k in drop:
        new.pop(k, None)
    if new == old:
        return False
    _write_json(path, {"boxes": new})
    return True


def _with_ids(data):
    """(the config's JSON with an id for each box that has none, {host: [the
    new ids of the boxes at it]})."""
    copies = {}

    def give(box):
        if "id" in box:
            return box
        box_id = new_id()
        copies.setdefault(box["host"], []).append(box_id)
        return {"id": box_id, **box}

    if "boxes" in data:
        return {**data, "boxes": [give(b) for b in data["boxes"]]}, copies
    return give(data), copies


def migrate(config_path, directory):
    """Give every box in the config at ``config_path`` an id, moving its
    state in ``directory`` from its host to it. Returns whether it changed
    the config. Does nothing to a config that doesn't parse or isn't the
    user's, or whose boxes all have ids. Raises OSError when a file can't
    be written: the config is then as it was, unless it was the last step."""
    with _Lock(directory):
        try:
            data, st = configmod.read_file(config_path)
            if st.st_uid != os.getuid():
                return False
            boxes = configmod.parse(data, config_path, st, unique=False)  # not one readable by others
            if all(b.saved_id for b in boxes):
                return False
            moved, copies = _with_ids(data)
            boxes = configmod.parse(moved, config_path)  # never write what omakodi wouldn't read
        except OmakodiError:
            return False
        # 1. The state, copied to the new ids (each host's entry stays).
        for name, key, limit in PER_BOX_FILES:
            _remap(os.path.join(directory, name), key, limit, copies)
        # 2. The config, with the ids.
        configmod.write_file(config_path, moved)
        # 3. The hosts' entries go, and box.json names the box by its id.
        ids = {b.id for b in boxes}
        drop = set(copies) - ids
        for name, key, limit in PER_BOX_FILES:
            try:
                _remap(os.path.join(directory, name), key, limit, drop=drop)
            except OSError:
                pass  # left over, they harm nothing
        chosen = ChosenBox(directory)
        was = chosen.read()
        if was is not None and was not in ids and was in copies:
            try:
                chosen.save(copies[was][0])
            except OSError:
                pass  # still read: the box in use is found by its host
        return True


def forget(directory, box_id):
    """Take a deleted box's settings and state out of every per-box file.
    Raises OSError when one can't be written."""
    with _Lock(directory):
        for name, key, limit in PER_BOX_FILES:
            _remap(os.path.join(directory, name), key, limit, drop={box_id})
