"""What omakodi says, worded as the phone remote says it (SPEC "Messages").

Every message names the box in use (its ``name``, which is its ``host``
when it has none). The remote shows them as a short message, the
keybindings as a notification; both get these words.
"""

import re

from .errors import CONFIG, UNREACHABLE

NOTHING_PLAYING = "Nothing is playing"
NO_LINK = "No link found"  # the kind stays "no link found" (SPEC "Errors")
NOTHING_TO_SEND = "Nothing to send"  # an empty clipboard, or text with nothing in it
FALLBACK = "YouTube add-on couldn't play it, trying SendToKodi…"
FALLBACK_NOTE = " with SendToKodi (the YouTube add-on couldn't play it)"
DEFAULT_BOX = "Kodi"  # when no box name is known


def _box(box):
    return box or DEFAULT_BOX


def playing(box, how="", sure=False):
    """'Playing on <box>…' while it opens; without the dots once it is known to play."""
    return f"Playing on {_box(box)}{how}" + ("" if sure else "…")


def queued(box, how="", size=None):
    count = f" ({size} in queue)" if isinstance(size, int) else ""
    return f"Queued on {_box(box)}{how}{count}"


def youtube_loading(box):
    return f"YouTube is still loading on {_box(box)}"


def no_sendtokodi(box):
    return f"SendToKodi isn't installed on {_box(box)}"


def no_addon(box):
    return f"Neither the YouTube add-on nor SendToKodi is installed on {_box(box)}"


# omakodi's own, in the same words (SPEC "Sending a link" step 6 and the stop).
def sendtokodi_failed(box):
    return f"SendToKodi couldn't play it on {_box(box)}"


SENDTOKODI_FAILED_WHY = "the TV shows why"


def sendtokodi_loading(box):
    return f"SendToKodi is still opening it on {_box(box)}"


def stopped(box):
    return f"Stopped on {_box(box)}"


def wake_sent(box):
    return f"Wake-up sent to {_box(box)}"


def soundbar_sent(box):
    return f"Soundbar wake-up sent to {_box(box)}"


def cant_reach(box):
    return f"Can't reach {_box(box)}"


# Waking (SPEC "Wake-on-LAN").
def no_mac(box):
    return f"No MAC address saved for {_box(box)}. Connect once while it's on, or add it in the box's settings."


def bad_mac(box):
    return f"Invalid MAC address for {_box(box)}"


# The soundbar's packet couldn't be sent (SPEC "The soundbar over HDMI-CEC").
def soundbar_unreachable(box, why):
    return f"Couldn't reach {_box(box)}: {why}" if why else f"Couldn't reach {_box(box)}"


# Kodi's errors (SPEC "Errors").
def wrong_login(box):
    return f"Wrong username or password for {_box(box)}"


def answered_http(box, status):
    return f"{_box(box)} answered HTTP {status}"


def bad_address(box):
    return f"Bad address for {_box(box)}"


def bad_reply(box):
    return f"Unexpected reply from {_box(box)}"


_HTTP = re.compile(r"http (\d{3})")


def explain(error, box=None):
    """An error as the user sees it: (the message, the fix under it, or "").

    The phone remote's words for the errors it has; the others keep their
    wording, with nothing under it. ``box`` is the box in use's name; without
    it, the one the error names (``error.box``)."""
    box = box or getattr(error, "box", None)
    kind = getattr(error, "kind", None)
    code = getattr(error, "code", None)
    detail = getattr(error, "detail", "") or ""
    if kind == "not reachable" and code == UNREACHABLE:
        return cant_reach(box), detail
    if kind == "bad address" and code == CONFIG:  # the editor's "bad address" is its own
        return bad_address(box), detail
    if kind == "wrong username or password":
        return wrong_login(box), detail
    status = _HTTP.fullmatch(kind) if isinstance(kind, str) else None
    if status:
        return answered_http(box, status.group(1)), detail
    if kind == "bad response":
        return bad_reply(box), detail
    if kind == "can't reach Kodi's EventServer":
        return soundbar_unreachable(box, getattr(error, "why", "")), ""
    if kind == "no link found":
        return NO_LINK, detail
    if kind == NOTHING_TO_SEND:
        return NOTHING_TO_SEND, detail
    return str(error), ""


def for_user(error, box=None):
    """An error as the remote and the notifications say it: the message
    alone (see ``explain``)."""
    return explain(error, box)[0]


def with_fix(error, box=None):
    """The message, and the fix on the line under it: as the top bar (the
    state's ``error``) and the terminal show an error."""
    message, fix = explain(error, box)
    return f"{message}\n{fix}" if fix else message
