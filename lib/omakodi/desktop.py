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


def notify_args(message, error=False, replace=None):
    """notify-send's arguments. ``replace`` is the id of the notification
    this one updates (the play's first message), so a play shows one
    notification whose words change, as the phone remote's message does."""
    body = html.escape(message[:500], quote=False)
    args = ["notify-send", "--app-name=omakodi", "--icon=kodi", "--print-id"]
    if isinstance(replace, int) and replace > 0:
        args.append(f"--replace-id={replace}")
    if error:
        args.append("--urgency=normal")
    args += ["omakodi", body]
    return args


def notify(message, error=False, replace=None):
    """A desktop notification. Text from Kodi is untrusted, so markup is
    escaped. Returns its id (to update it), or ``replace`` when there is none."""
    try:
        r = subprocess.run(notify_args(message, error, replace), capture_output=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return replace  # no notification daemon: the message is on stdout/stderr anyway
    got = r.stdout.decode("ascii", "replace").strip()
    return int(got) if r.returncode == 0 and got.isdigit() else replace
