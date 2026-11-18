"""Did the YouTube add-on start the video? (SPEC "Sending a link" step 5)

Opens the item while listening to Kodi's events, and decides:

- "failed": the add-on reported playback_failed for this video, or Kodi
  stopped the new item before it played, or the picture came up but the play
  time stood still;
- "playing": the new item's play time moved forward, or the viewer paused,
  resumed or seeked it;
- "undecided": no answer in time. Kodi shows its own error if it fails later.

The video that was playing before keeps playing while the add-on looks up the
new one, so progress only counts once Kodi shows a different item, or the
same item restarted. When the new item was put in the queue (``slot``), only
the item at that queue position counts: if it fails, Kodi moves on to the
next one in the queue, which must not read as the new video playing.
"""

import time

from .control import active_player
from .errors import UNREACHABLE, OmakodiError
from .events import ConnectionLost, EventConnection

PLAYING, FAILED, UNDECIDED = "playing", "failed", "undecided"
WATCHED_BY_VIEWER = ("Player.OnPause", "Player.OnResume", "Player.OnSeek", "Player.OnSpeedChanged")


class Timings:
    def __init__(self, decision=30.0, stall=12.0, min_progress=3.0, poll_every=1.0, event_wait=0.25,
                 connect=2.0):
        self.decision = decision
        self.stall = stall
        self.min_progress = min_progress
        self.poll_every = poll_every
        self.event_wait = event_wait
        self.connect = connect


def _time_seconds(t):
    if not isinstance(t, dict):
        return 0.0
    try:
        return (int(t.get("hours", 0)) * 3600 + int(t.get("minutes", 0)) * 60 + int(t.get("seconds", 0))
                + int(t.get("milliseconds", 0)) / 1000.0)
    except (TypeError, ValueError):
        return 0.0


def _item_key(kodi, player):
    """'file|label' of what a player plays. Internal only: never shown or logged."""
    got = kodi.call("Player.GetItem", {"playerid": player, "properties": ["file"]})
    item = got.get("item") if isinstance(got, dict) else None
    item = item if isinstance(item, dict) else {}
    return f"{item.get('file', '')}|{item.get('label', '')}"


def _swallow_player_change(fn):
    """Kodi answers "Failed to execute method" while players change; that is
    not an error here. Being unreachable is."""
    try:
        return fn()
    except OmakodiError as e:
        if e.code == UNREACHABLE or e.kind == "wrong username or password":
            raise
        return None


def current_item(kodi):
    player = _swallow_player_change(lambda: active_player(kodi))
    if player is None:
        return None
    return _swallow_player_change(lambda: _item_key(kodi, player))


class ProgressCheck:
    def __init__(self, before, min_progress, slot=None):
        self.before = before
        self.min_progress = min_progress
        self.slot = slot
        self.started = False
        self.previous = None
        self.tracked = None
        self.base = 0.0

    def poll(self, kodi):
        player = _swallow_player_change(lambda: active_player(kodi))
        if player is None:
            self.previous = None  # normal while the stream opens
            return False

        def read():
            key = _item_key(kodi, player)
            props = kodi.call("Player.GetProperties", {"playerid": player, "properties": ["time", "position"]})
            props = props if isinstance(props, dict) else {}
            return key, _time_seconds(props.get("time")), props.get("position")

        got = _swallow_player_change(read)
        if got is None:
            return False
        key, seconds, position = got
        if self.slot is not None and position != self.slot:
            self.previous = None  # another item in the queue: not ours
            return False
        jumped_back = self.previous is not None and seconds < self.previous - 1
        self.previous = seconds
        if not self.started and (key != self.before or jumped_back):
            self.started = True
        if not self.started or seconds <= 0:
            return False
        # A new item can first report the old one's time, then drop to 0:
        # anything below the baseline starts the count again.
        if key != self.tracked or jumped_back or seconds < self.base:
            self.tracked = key
            self.base = seconds
            return False
        return seconds - self.base >= self.min_progress


class Verdict:
    def __init__(self, timings=None, clock=time.monotonic, sleep=time.sleep):
        self.t = timings or Timings()
        self.clock = clock
        self.sleep = sleep

    def __call__(self, kodi, target, open_item=None, slot=None):
        """``open_item()`` opens the target (default ``Player.Open`` of its
        path); ``slot`` is its queue position when it was put in the queue."""
        cfg = kodi.cfg
        conn = EventConnection(cfg.host, cfg.tcp_port, connect_timeout=self.t.connect)
        try:
            conn.open()  # listen before opening, so no event is missed
        except ConnectionLost:
            conn = None  # the play time alone decides
        try:
            progress = ProgressCheck(current_item(kodi), self.t.min_progress, slot)
            if open_item is None:
                kodi.call("Player.Open", {"item": {"file": target.path}})
            else:
                open_item()
            return self._watch(kodi, conn, progress, target.video_id)
        finally:
            if conn is not None:
                conn.close()

    def _watch(self, kodi, conn, progress, video_id):
        start = self.clock()
        new_title = None  # set by Player.OnPlay: Kodi found the new video
        av_start = None
        last_poll = None
        while True:
            now = self.clock()
            if av_start is not None and now - av_start > self.t.stall:
                return FAILED
            if now - start > self.t.decision:
                return UNDECIDED
            events = []
            if conn is not None:
                try:
                    events = conn.poll(self.t.event_wait)
                except ConnectionLost:
                    conn.close()
                    conn = None
            else:
                self.sleep(self.t.event_wait)
            for method, data in events:
                data = data or {}
                item = data.get("item") if isinstance(data.get("item"), dict) else {}
                title = str(item.get("title", ""))
                if method == "Other.playback_failed":
                    if data.get("video_id") == video_id:
                        return FAILED
                elif method == "Player.OnPlay":
                    if new_title is None:
                        new_title = title
                elif method == "Player.OnAVStart":
                    if new_title is not None and av_start is None:
                        av_start = self.clock()
                elif method in WATCHED_BY_VIEWER:
                    # Kodi can send OnResume for the old video just before
                    # OnPlay; the title check skips that.
                    if new_title is not None and title == new_title:
                        return PLAYING
                elif method == "Player.OnStop":
                    if new_title is not None and title == new_title and data.get("end") is not True:
                        return FAILED
            if events:
                continue
            now = self.clock()
            if last_poll is None or now - last_poll >= self.t.poll_every:
                last_poll = now
                if progress.poll(kodi):
                    return PLAYING
