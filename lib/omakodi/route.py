"""Which add-on plays a YouTube link (SPEC "Sending a link" step 3)."""

from typing import NamedTuple, Optional

NOTE_FAILED_RECENTLY = "the YouTube add-on failed recently"
NOTE_NO_SENDTOKODI = "SendToKodi isn't installed"
NOTE_NO_YOUTUBE = "the YouTube add-on isn't installed"


class Route(NamedTuple):
    youtube_addon: bool  # True: YouTube add-on; False: SendToKodi
    fallback: bool  # with the YouTube add-on: try SendToKodi if it fails
    note: Optional[str] = None  # why the usual add-on wasn't used


SENDTOKODI = Route(youtube_addon=False, fallback=False)


def choose(mode, has_youtube, has_sendtokodi, failed_recently):
    """The route for a YouTube link, or None when neither add-on is installed.

    A missing YouTube add-on is common, so in ``smart`` and ``youtube-first``
    SendToKodi is used without a note. The explicit modes say when they
    couldn't do what was asked.
    """
    if not has_youtube and not has_sendtokodi:
        return None
    if mode == "sendtokodi-only":
        if has_sendtokodi:
            return SENDTOKODI
        return Route(True, False, NOTE_NO_SENDTOKODI)
    if mode == "youtube-only":
        if has_youtube:
            return Route(True, False)
        return SENDTOKODI._replace(note=NOTE_NO_YOUTUBE)
    if not has_youtube:
        return SENDTOKODI
    if mode == "smart" and failed_recently and has_sendtokodi:
        return SENDTOKODI._replace(note=NOTE_FAILED_RECENTLY)
    return Route(True, fallback=has_sendtokodi)
