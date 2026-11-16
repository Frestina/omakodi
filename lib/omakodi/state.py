"""Small durable state in ~/.local/state/omakodi/."""

import os
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
