"""The YouTube verdict against scripted Kodi behaviour (short timings)."""

import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fakekodi import ROOT, FakeKodi, unused_port  # noqa: E402
from omakodi import links  # noqa: E402
from omakodi.rpc import Kodi  # noqa: E402
from omakodi.share import Sender  # noqa: E402
from omakodi.state import StopNote, YoutubeHealth  # noqa: E402
from omakodi.control import Controller  # noqa: E402
from omakodi.errors import OmakodiError  # noqa: E402
from omakodi.verdict import FAILED, PLAYING, UNDECIDED, SendToKodiTimings, SendToKodiWatch, Timings, Verdict  # noqa: E402

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
        self.queue = None  # the video queue's files, when it plays from one
        self.position = -1
        fake.results["Player.GetActivePlayers"] = self.active
        fake.results["Player.GetItem"] = self.get_item
        fake.results["Player.GetProperties"] = self.properties
        fake.results["Playlist.Insert"] = self.insert
        fake.results["Playlist.Remove"] = self.remove

    def set(self, item, seconds=0.0, step=0.0, position=None):
        with self.lock:
            self.item, self.seconds, self.step = item, seconds, step
            if position is not None:
                self.position = position

    def play_queue(self, files, position):
        with self.lock:
            self.queue = list(files)
        self.set((files[position], "Queued video"), seconds=100.0, step=1.0, position=position)

    # Kodi keeps the position of the playing item when the queue changes.
    def insert(self, params):
        with self.lock:
            self.queue.insert(params["position"], params["item"]["file"])
            if params["position"] <= self.position:
                self.position += 1
        return "OK"

    def remove(self, params):
        with self.lock:
            del self.queue[params["position"]]
            if params["position"] < self.position:
                self.position -= 1
        return "OK"

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
            queued = self.queue is not None
            position = self.position
        return {"time": {"hours": 0, "minutes": int(s // 60), "seconds": int(s % 60),
                         "milliseconds": int((s % 1) * 1000)},
                "playlistid": 1 if queued else -1, "position": position if queued else -1}


class Setup:
    """A fake Kodi with a scripted player; ``on_open(path)`` runs when Kodi opens an item."""

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
        item = params["item"]
        path = item["file"] if "file" in item else self.player.queue[item["position"]]
        if self.on_open:
            threading.Thread(target=self.on_open, args=(path,), daemon=True).start()
        return "OK"

    def sender(self, cfg=None):
        kodi = Kodi(cfg or self.fake.config())
        return Sender(kodi, "smart", self.health, verdict=Verdict(FAST))

    def opened_paths(self):
        return [p["item"]["file"] for m, p in self.fake.calls if m == "Player.Open" and "file" in p["item"]]

    def verdict(self, cfg=None):
        kodi = Kodi(cfg or self.fake.config())
        target = Sender(kodi, "smart", self.health).target(URL)
        return Verdict(FAST)(kodi, target)


class VerdictTest(Setup, unittest.TestCase):
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



QUEUE = ["http://media.example.lan/one.mkv", "http://media.example.lan/two.mkv",
         "http://media.example.lan/three.mkv"]


class QueueVerdictTest(Setup, unittest.TestCase):
    """``play`` while the queue plays (ticket 021): the new video goes in after
    the playing one and the rest of the queue stays."""

    def setUp(self):
        super().setUp()
        self.player.play_queue(QUEUE, 0)

    def opened_positions(self):
        return [p["item"].get("position") for m, p in self.fake.calls if m == "Player.Open"]

    def test_fallback_takes_the_failed_items_place(self):
        def script(path):
            if path != links.youtube_path(VID):
                return
            time.sleep(0.05)
            self.fake.push("Other.playback_failed", {"video_id": VID})
            # Kodi goes on to the next item in the queue.
            self.player.set((QUEUE[1], "Queued video"), seconds=0.0, step=1.0, position=2)

        self.on_open = script
        msg = self.sender().play(URL)
        self.assertIn("SendToKodi", msg)
        self.assertEqual(self.player.queue, [QUEUE[0], links.sendtokodi_path(URL)] + QUEUE[1:])
        self.assertEqual(self.opened_positions(), [1, 1])

    def test_fallback_goes_after_an_item_kodi_wont_remove(self):
        self.fake.errors["Playlist.Remove"] = "Invalid params."

        def script(path):
            if path == links.youtube_path(VID):
                self.player.set((path, "New video"), position=1)
                self.fake.push("Other.playback_failed", {"video_id": VID})

        self.on_open = script
        self.sender().play(URL)
        self.assertEqual(self.player.queue,
                         [QUEUE[0], links.youtube_path(VID), links.sendtokodi_path(URL)] + QUEUE[1:])
        self.assertEqual(self.opened_positions(), [1, 2])

    def test_new_video_at_its_place_is_playing(self):
        def script(path):
            time.sleep(0.05)
            self.player.set((path, "New video"), seconds=0.0, step=1.0, position=1)

        self.on_open = script
        self.assertEqual(self.sender().play(URL), "Playing on Kodi")
        self.assertEqual(self.player.queue, [QUEUE[0], links.youtube_path(VID)] + QUEUE[1:])

    def test_next_queued_video_playing_is_not_the_new_one(self):
        def script(path):
            time.sleep(0.05)
            # The new item failed without a word; Kodi plays the next one.
            self.player.set((QUEUE[1], "Queued video"), seconds=0.0, step=1.0, position=2)

        self.on_open = script
        self.assertIn("Still loading", self.sender().play(URL))


# ---- SendToKodi (ticket 038) ----------------------------------------------------

STK_FAST = SendToKodiTimings(limit=1.5, quiet=0.3, poll_every=0.05, event_wait=0.02, connect=1.0)
OTHER = "https://video.example.net/clip/7"


class SendToKodiSetup(Setup):
    def setUp(self):
        super().setUp()
        self.busy = False
        self.fake.results["XBMC.GetInfoBooleans"] = lambda p: {b: self.busy for b in p["booleans"]}
        self.steps = []

    def stk_sender(self, cfg=None):
        kodi = Kodi(cfg or self.fake.config())
        return Sender(kodi, "smart", self.health, verdict=Verdict(FAST), sendtokodi_watch=SendToKodiWatch(STK_FAST))

    def play(self, url=OTHER, cfg=None):
        return self.stk_sender(cfg).play(url, progress=self.steps.append)

    def busy_then(self, outcome):
        """SendToKodi's busy dialog, then ``outcome(path)``: what Kodi does."""
        def script(path):
            if not path.startswith("plugin://plugin.video.sendtokodi/"):
                return
            time.sleep(0.05)
            self.busy = True
            time.sleep(0.2)
            self.busy = False  # the dialog blinks off between steps
            time.sleep(0.1)
            self.busy = True
            time.sleep(0.1)
            self.busy = False
            outcome(path)
        return script


class SendToKodiTest(SendToKodiSetup, unittest.TestCase):
    def test_plays(self):
        self.on_open = self.busy_then(lambda path: self.player.set((path, "Clip"), seconds=0.0, step=1.0))
        self.assertEqual(self.play(), "Playing on Kodi")
        self.assertEqual(self.steps, ["SendToKodi is opening it…"])

    def test_picture_up_event_means_playing(self):
        def outcome(path):
            self.fake.push("Player.OnPlay", {"item": {"title": "Clip", "type": "movie"}})
            self.fake.push("Player.OnAVStart", {"item": {"title": "Clip", "type": "movie"}})

        self.on_open = self.busy_then(outcome)
        self.assertEqual(self.play(), "Playing on Kodi")

    def test_dialog_gone_and_nothing_plays_is_a_failure(self):
        self.on_open = self.busy_then(lambda path: None)
        with self.assertRaises(OmakodiError) as cm:
            self.play()
        self.assertEqual(str(cm.exception), "SendToKodi couldn't play it: Kodi shows why on the TV")

    def test_stopped_before_the_picture_is_a_failure(self):
        def outcome(path):
            self.fake.push("Player.OnPlay", {"item": {"title": "Clip", "type": "movie"}})
            self.fake.push("Player.OnStop", {"item": {"title": "Clip", "type": "movie"}, "end": False})

        self.on_open = self.busy_then(outcome)
        with self.assertRaises(OmakodiError):
            self.play()

    def test_still_busy_or_never_busy_is_undecided(self):
        self.busy = True
        self.assertEqual(self.play(), "Sent to Kodi; SendToKodi is still opening it")
        self.busy = False
        self.assertEqual(self.play(), "Sent to Kodi; SendToKodi is still opening it")

    def test_old_video_playing_on_is_not_the_new_one(self):
        self.player.set(("http://media.example.lan/old.mkv", "Old video"), seconds=100.0, step=1.0)
        self.on_open = self.busy_then(lambda path: None)
        with self.assertRaises(OmakodiError):
            self.play()

    def test_without_event_port_the_poll_decides(self):
        self.on_open = self.busy_then(lambda path: self.player.set((path, "Clip"), seconds=0.0, step=1.0))
        self.assertEqual(self.play(cfg=self.fake.config(tcp_port=unused_port())), "Playing on Kodi")

    def test_youtube_fallback_is_watched_too(self):
        def script(path):
            if path == links.youtube_path(VID):
                time.sleep(0.05)
                self.fake.push("Other.playback_failed", {"video_id": VID})
            else:
                self.busy_then(lambda p: None)(path)

        self.on_open = script
        with self.assertRaises(OmakodiError):
            self.play(URL)
        self.assertEqual(self.steps, ["The YouTube add-on couldn't play it, trying SendToKodi…",
                                      "SendToKodi is opening it…"])
        self.assertTrue(self.health.failed_recently())

    def test_without_a_watch_it_answers_at_once(self):
        self.assertEqual(self.sender().play(OTHER), "Playing on Kodi…")


class SendToKodiQueueTest(SendToKodiSetup, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.player.play_queue(QUEUE, 0)

    def test_new_item_at_its_place_is_playing(self):
        self.on_open = self.busy_then(lambda path: self.player.set((path, "Clip"), seconds=0.0, step=1.0,
                                                                   position=1))
        self.assertEqual(self.play(), "Playing on Kodi")

    def test_next_queued_video_playing_is_not_the_new_one(self):
        self.on_open = self.busy_then(lambda path: self.player.set((QUEUE[1], "Queued video"), seconds=0.0,
                                                                   step=1.0, position=2))
        with self.assertRaises(OmakodiError):
            self.play()

    def test_fallback_after_an_item_kodi_wont_remove_watches_that_place(self):
        self.fake.errors["Playlist.Remove"] = "Invalid params."

        def script(path):
            if path == links.youtube_path(VID):
                self.player.set((path, "New video"), position=1)
                self.fake.push("Other.playback_failed", {"video_id": VID})
            else:
                self.busy_then(lambda p: self.player.set((p, "Clip"), seconds=0.0, step=1.0, position=2))(path)

        self.on_open = script
        self.assertEqual(self.play(URL), "Playing on Kodi with SendToKodi (the YouTube add-on couldn't play it)")


# ---- a stop you send isn't a failure (ticket 039) ----------------------------------

class StopTest(SendToKodiSetup, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.stops = StopNote(self.tmp.name)
        self.fake.results["Player.Stop"] = self.stopped_by_kodi

    def stopped_by_kodi(self, params):
        item = self.player.item
        self.player.set(None)
        self.fake.push("Player.OnStop", {"item": {"title": item[1] if item else "", "type": "movie"}, "end": False})
        return "OK"

    def watching_sender(self):
        kodi = Kodi(self.fake.config())
        return Sender(kodi, "smart", self.health, verdict=Verdict(FAST, stops=self.stops),
                      sendtokodi_watch=SendToKodiWatch(STK_FAST, stops=self.stops))

    def user_stops(self, path, how):
        """The new video comes up (Kodi's OnPlay), then the user stops it."""
        time.sleep(0.05)
        self.fake.push("Player.OnPlay", {"item": {"title": "New video", "type": "movie"}})
        time.sleep(0.05)
        how()

    def stop_in_this_process(self):
        Controller(Kodi(self.fake.config()), stops=self.stops).run("stop")

    def test_stop_during_the_youtube_verdict(self):
        def script(path):
            self.player.set((path, "New video"))
            self.user_stops(path, self.stop_in_this_process)

        self.on_open = script
        self.assertEqual(self.watching_sender().play(URL), "Stopped")
        self.assertEqual(self.opened_paths(), [links.youtube_path(VID)])  # no SendToKodi
        self.assertFalse(self.health.failed_recently())

    def test_stop_from_another_process(self):
        cfg = os.path.join(self.tmp.name, "config.json")
        with open(cfg, "w") as f:
            json.dump(self.fake.config_json(), f)
        os.chmod(cfg, 0o600)
        env = dict(os.environ, OMAKODI_CONFIG=cfg, XDG_STATE_HOME=self.tmp.name)
        # the other process's StopNote: <XDG_STATE_HOME>/omakodi/stopped
        self.stops = StopNote(os.path.join(self.tmp.name, "omakodi"))

        def other_process():
            r = subprocess.run([os.path.join(ROOT, "bin", "omakodi"), "control", "stop"], env=env,
                               capture_output=True, text=True, timeout=10)
            self.assertEqual(r.returncode, 0, r.stderr)

        def script(path):
            self.player.set((path, "New video"))
            self.user_stops(path, other_process)

        self.on_open = script
        self.assertEqual(self.watching_sender().play(URL), "Stopped")
        self.assertEqual(self.opened_paths(), [links.youtube_path(VID)])

    def test_a_stop_before_the_play_doesnt_count(self):
        self.stops.record()
        time.sleep(0.02)

        def script(path):
            if path == links.youtube_path(VID):
                time.sleep(0.05)
                self.fake.push("Other.playback_failed", {"video_id": VID})
            else:
                self.busy_then(lambda p: self.player.set((p, "Clip"), seconds=0.0, step=1.0))(path)

        self.on_open = script
        self.assertIn("SendToKodi", self.watching_sender().play(URL))
        self.assertTrue(self.health.failed_recently())

    def test_stop_while_sendtokodi_opens_it(self):
        def script(path):
            self.busy = True
            time.sleep(0.1)
            try:
                self.stop_in_this_process()
            except OmakodiError:
                pass  # nothing plays yet: Kodi says "nothing playing"; the stop is noted all the same

        self.on_open = script
        self.assertEqual(self.watching_sender().play(OTHER), "Stopped")


if __name__ == "__main__":
    unittest.main()
