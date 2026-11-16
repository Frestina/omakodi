"""The YouTube verdict against scripted Kodi behaviour (short timings)."""

import os
import sys
import tempfile
import threading
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fakekodi import FakeKodi, unused_port  # noqa: E402
from omakodi import links  # noqa: E402
from omakodi.rpc import Kodi  # noqa: E402
from omakodi.share import Sender  # noqa: E402
from omakodi.state import YoutubeHealth  # noqa: E402
from omakodi.verdict import FAILED, PLAYING, UNDECIDED, Timings, Verdict  # noqa: E402

VID = "dQw4w9WgXcQ"
URL = f"https://youtu.be/{VID}"
FAST = Timings(decision=1.5, stall=0.4, min_progress=3.0, poll_every=0.05, event_wait=0.02, connect=1.0)


class Player:
    """A scripted Kodi player: what plays, and how its time moves."""

    def __init__(self, fake):
        self.lock = threading.Lock()
        self.item = None  # (file, label) or None when nothing plays
        self.seconds = 0.0
        self.step = 0.0  # added to the time on every read
        fake.results["Player.GetActivePlayers"] = self.active
        fake.results["Player.GetItem"] = self.get_item
        fake.results["Player.GetProperties"] = self.properties

    def set(self, item, seconds=0.0, step=0.0):
        with self.lock:
            self.item, self.seconds, self.step = item, seconds, step

    def active(self, params):
        with self.lock:
            return [{"playerid": 1, "type": "video"}] if self.item else []

    def get_item(self, params):
        with self.lock:
            if not self.item:
                return {"item": {"label": ""}}
            return {"item": {"file": self.item[0], "label": self.item[1]}}

    def properties(self, params):
        with self.lock:
            self.seconds += self.step
            s = self.seconds
        return {"time": {"hours": 0, "minutes": int(s // 60), "seconds": int(s % 60),
                         "milliseconds": int((s % 1) * 1000)}}


class VerdictTest(unittest.TestCase):
    def setUp(self):
        self.fake = FakeKodi().start()
        self.player = Player(self.fake)
        self.on_open = None
        self.fake.results["Player.Open"] = self.opened
        self.fake.results["Addons.GetAddonDetails"] = lambda p: {"addon": {"enabled": True}}
        self.tmp = tempfile.TemporaryDirectory()
        self.health = YoutubeHealth(self.tmp.name)

    def tearDown(self):
        self.fake.stop()
        self.tmp.cleanup()

    def opened(self, params):
        if self.on_open:
            threading.Thread(target=self.on_open, args=(params["item"]["file"],), daemon=True).start()
        return "OK"

    def sender(self, cfg=None):
        kodi = Kodi(cfg or self.fake.config())
        return Sender(kodi, "smart", self.health, verdict=Verdict(FAST))

    def opened_paths(self):
        return [p["item"]["file"] for m, p in self.fake.calls if m == "Player.Open"]

    def verdict(self, cfg=None):
        kodi = Kodi(cfg or self.fake.config())
        target = Sender(kodi, "smart", self.health).target(URL)
        return Verdict(FAST)(kodi, target)

    def test_addon_reports_failure_then_fallback(self):
        def script(path):
            time.sleep(0.05)
            self.fake.push("Other.playback_failed", {"video_id": VID})

        self.on_open = script
        msg = self.sender().play(URL)
        self.assertEqual(self.opened_paths(), [links.youtube_path(VID), links.sendtokodi_path(URL)])
        self.assertTrue(self.health.failed_recently())
        self.assertIn("SendToKodi", msg)

    def test_failure_for_another_video_is_ignored(self):
        def script(path):
            time.sleep(0.05)
            self.fake.push("Other.playback_failed", {"video_id": "AAAAAAAAAAA"})

        self.on_open = script
        self.assertEqual(self.verdict(), UNDECIDED)

    def test_stopped_before_playing(self):
        def script(path):
            time.sleep(0.05)
            self.fake.push("Player.OnPlay", {"item": {"title": "New video"}})
            time.sleep(0.05)
            self.fake.push("Player.OnStop", {"item": {"title": "New video"}, "end": False})

        self.on_open = script
        self.assertEqual(self.verdict(), FAILED)

    def test_picture_up_but_time_frozen(self):
        def script(path):
            self.player.set((path, "New video"), seconds=0.0, step=0.0)
            self.fake.push("Player.OnPlay", {"item": {"title": "New video"}})
            self.fake.push("Player.OnAVStart", {"item": {"title": "New video"}})

        self.on_open = script
        self.assertEqual(self.verdict(), FAILED)

    def test_time_moves_means_playing_and_clears_memory(self):
        self.health.record_failure()
        sender = Sender(Kodi(self.fake.config()), "youtube-first", self.health, verdict=Verdict(FAST))

        def script(path):
            time.sleep(0.05)
            self.player.set((path, "New video"), seconds=0.0, step=1.0)

        self.on_open = script
        self.assertEqual(sender.play(URL), "Playing on Kodi")
        self.assertEqual(self.opened_paths(), [links.youtube_path(VID)])
        self.assertFalse(self.health.failed_recently())

    def test_viewer_pauses_new_video(self):
        def script(path):
            self.fake.push("Player.OnPlay", {"item": {"title": "New video"}})
            time.sleep(0.05)
            self.fake.push("Player.OnPause", {"item": {"title": "New video"}})

        self.on_open = script
        self.assertEqual(self.verdict(), PLAYING)

    def test_nothing_happens_is_undecided_without_fallback(self):
        msg = self.sender().play(URL)
        self.assertEqual(self.opened_paths(), [links.youtube_path(VID)])
        self.assertIn("Still loading", msg)
        self.assertFalse(self.health.failed_recently())

    def test_old_video_playing_on_is_not_the_new_one(self):
        self.player.set(("http://media.example.lan/old.mkv", "Old video"), seconds=100.0, step=1.0)
        self.assertEqual(self.verdict(), UNDECIDED)

    def test_old_video_replaced(self):
        self.player.set(("http://media.example.lan/old.mkv", "Old video"), seconds=100.0, step=1.0)

        def script(path):
            time.sleep(0.1)
            # Kodi first reports the new item with the old time, then restarts.
            self.player.set((path, "New video"), seconds=101.0, step=0.0)
            time.sleep(0.15)
            self.player.set((path, "New video"), seconds=0.0, step=1.0)

        self.on_open = script
        self.assertEqual(self.verdict(), PLAYING)

    def test_without_event_port_the_poll_decides(self):
        cfg = self.fake.config(tcp_port=unused_port())

        def script(path):
            self.player.set((path, "New video"), seconds=0.0, step=1.0)

        self.on_open = script
        self.assertEqual(self.verdict(cfg), PLAYING)


if __name__ == "__main__":
    unittest.main()
