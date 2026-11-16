"""Clipboard and notifications on the Omarchy desktop."""

import html
import subprocess

from .errors import USAGE, OmakodiError

MAX_CLIPBOARD = 8192


def read_clipboard():
    try:
        r = subprocess.run(["wl-paste", "--no-newline", "--type", "text"], capture_output=True, timeout=3)
    except (OSError, subprocess.TimeoutExpired):
        raise OmakodiError("no link found", "can't read the clipboard (is wl-paste installed?)", USAGE) from None
    if r.returncode != 0 or not r.stdout:
        raise OmakodiError("no link found", "the clipboard is empty", USAGE)
    return r.stdout[:MAX_CLIPBOARD].decode("utf-8", "replace")


def notify(message, error=False):
    """A desktop notification. Text from Kodi is untrusted, so markup is escaped."""
    body = html.escape(message[:500], quote=False)
    args = ["notify-send", "--app-name=omakodi", "--icon=kodi"]
    if error:
        args.append("--urgency=normal")
    args += ["omakodi", body]
    try:
        subprocess.run(args, capture_output=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        pass  # no notification daemon: the message is on stdout/stderr anyway
