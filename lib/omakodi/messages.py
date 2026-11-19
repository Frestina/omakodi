"""What omakodi says, worded as the phone remote says it (SPEC "Messages").

Every message names the box in use (its ``name``, which is its ``host``
when it has none). The remote shows them as a short message, the
keybindings as a notification; both get these words.
"""

from .errors import UNREACHABLE

NOTHING_PLAYING = "Nothing is playing"
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


def for_user(error, box):
    """An error as the remote and the notifications say it: Kodi not
    answering is "Can't reach <box>"; the others keep their wording."""
    if getattr(error, "kind", None) == "not reachable" and getattr(error, "code", None) == UNREACHABLE:
        return cant_reach(box)
    return str(error)
