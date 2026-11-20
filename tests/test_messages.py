"""What omakodi says, worded as the phone remote says it (ticket 048).

Every message names the box in use; the remote shows them, and the play
and queue keybindings' notifications use the same words.
"""

import os
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fakekodi import FakeKodi  # noqa: E402
from omakodi import cli, desktop, messages  # noqa: E402
from omakodi.config import Config  # noqa: E402
from omakodi.errors import AUTH, UNREACHABLE, OmakodiError  # noqa: E402
from omakodi.rpc import Kodi  # noqa: E402
from omakodi.share import Sender, make_sender  # noqa: E402
from omakodi.state import YoutubeHealth  # noqa: E402

BOX = "Living room"
VID = "dQw4w9WgXcQ"


class WordingTest(unittest.TestCase):
    def test_every_message(self):
        self.assertEqual(messages.playing(BOX), "Playing on Living room…")
        self.assertEqual(messages.playing(BOX, sure=True), "Playing on Living room")
        self.assertEqual(messages.playing(BOX, " with SendToKodi (the YouTube add-on failed recently)"),
                         "Playing on Living room with SendToKodi (the YouTube add-on failed recently)…")
        self.assertEqual(messages.playing(BOX, messages.FALLBACK_NOTE, sure=True),
                         "Playing on Living room with SendToKodi (the YouTube add-on couldn't play it)")
        self.assertEqual(messages.queued(BOX, "", 3), "Queued on Living room (3 in queue)")
        self.assertEqual(messages.queued(BOX, "", None), "Queued on Living room")
        self.assertEqual(messages.youtube_loading(BOX), "YouTube is still loading on Living room")
        self.assertEqual(messages.FALLBACK, "YouTube add-on couldn't play it, trying SendToKodi…")
        self.assertEqual(messages.no_sendtokodi(BOX), "SendToKodi isn't installed on Living room")
        self.assertEqual(messages.no_addon(BOX),
                         "Neither the YouTube add-on nor SendToKodi is installed on Living room")
        self.assertEqual(messages.wake_sent(BOX), "Wake-up sent to Living room")
        self.assertEqual(messages.soundbar_sent(BOX), "Soundbar wake-up sent to Living room")
        self.assertEqual(messages.cant_reach(BOX), "Can't reach Living room")
        self.assertEqual(messages.NOTHING_PLAYING, "Nothing is playing")

    def test_omakodis_extras_in_the_same_words(self):
        # 038: SendToKodi gave up, or is still at it; 039: the user's own stop.
        self.assertEqual(str(OmakodiError(messages.sendtokodi_failed(BOX), messages.SENDTOKODI_FAILED_WHY)),
                         "SendToKodi couldn't play it on Living room: the TV shows why")
        self.assertEqual(messages.sendtokodi_loading(BOX), "SendToKodi is still opening it on Living room")
        self.assertEqual(messages.stopped(BOX), "Stopped on Living room")

    def test_no_name_is_kodi(self):
        self.assertEqual(messages.cant_reach(""), "Can't reach Kodi")
        self.assertEqual(messages.playing(None), "Playing on Kodi…")

    def test_errors_for_the_user(self):
        unreachable = OmakodiError("not reachable", "no answer from kodi.example.lan:8080 (away from home?)",
                                   UNREACHABLE)
        self.assertEqual(messages.for_user(unreachable, BOX), "Can't reach Living room")
        wrong = OmakodiError("wrong username or password", "Kodi refused the login", AUTH)
        self.assertEqual(messages.for_user(wrong, BOX), "Wrong username or password for Living room")  # 053
        self.assertEqual(messages.for_user(OmakodiError(messages.NOTHING_PLAYING), BOX), "Nothing is playing")


class SenderNamesTheBoxTest(unittest.TestCase):
    def setUp(self):
        self.fake = FakeKodi().start()
        self.installed = {"plugin.video.youtube", "plugin.video.sendtokodi"}
        self.fake.results["Addons.GetAddonDetails"] = lambda p: {
            "addon": {"addonid": p["addonid"], "enabled": p["addonid"] in self.installed}}
        self.fake.results["Player.GetActivePlayers"] = []
        self.fake.results["Playlist.GetProperties"] = {"size": 3}
        self.tmp = tempfile.TemporaryDirectory()
        self.sender = Sender(Kodi(self.fake.config()), "smart", YoutubeHealth(self.tmp.name), box=BOX)
        self.steps = []

    def tearDown(self):
        self.fake.stop()
        self.tmp.cleanup()

    def test_play_says_it_at_once(self):
        msg = self.sender.play("https://vimeo.com/123456", progress=self.steps.append)
        self.assertEqual(self.steps, ["Playing on Living room…"])
        self.assertEqual(msg, "Playing on Living room…")

    def test_queue(self):
        self.fake.results["Player.GetActivePlayers"] = [{"playerid": 1, "type": "video"}]
        self.assertEqual(self.sender.queue(f"https://youtu.be/{VID}", progress=self.steps.append),
                         "Queued on Living room (3 in queue)")
        self.assertEqual(self.steps, [])

    def test_missing_addons(self):
        self.installed = {"plugin.video.youtube"}
        with self.assertRaises(OmakodiError) as cm:
            self.sender.play("https://vimeo.com/123456")
        self.assertEqual(str(cm.exception), "SendToKodi isn't installed on Living room")
        self.installed = set()
        with self.assertRaises(OmakodiError) as cm:
            self.sender.play(f"https://youtu.be/{VID}")
        self.assertEqual(str(cm.exception), "Neither the YouTube add-on nor SendToKodi is installed on Living room")

    def test_make_sender_uses_the_box_name(self):
        self.assertEqual(make_sender(self.fake.config(name=BOX)).box, BOX)
        self.assertEqual(make_sender(self.fake.config()).box, "127.0.0.1")  # no name: its address


class NotificationTest(unittest.TestCase):
    def test_one_notification_updated(self):
        self.assertEqual(desktop.notify_args("Playing on Living room…"),
                         ["notify-send", "--app-name=omakodi", "--icon=kodi", "--print-id", "omakodi",
                          "Playing on Living room…"])
        self.assertEqual(desktop.notify_args("Can't reach Living room", error=True, replace=17),
                         ["notify-send", "--app-name=omakodi", "--icon=kodi", "--print-id", "--replace-id=17",
                          "--urgency=normal", "omakodi", "Can't reach Living room"])
        self.assertEqual(desktop.notify_args("<b>x</b>")[-1], "&lt;b&gt;x&lt;/b&gt;")

    def test_notify_returns_the_id(self):
        done = SimpleNamespace(returncode=0, stdout=b"42\n")
        with mock.patch.object(desktop.subprocess, "run", return_value=done):
            self.assertEqual(desktop.notify("Playing on Living room…"), 42)
        with mock.patch.object(desktop.subprocess, "run", side_effect=OSError):
            self.assertEqual(desktop.notify("x", replace=42), 42)

    def notified(self, outcome):
        """The notifications a play --notify shows, and their replace ids."""
        shown = []

        def notify(message, error=False, replace=None):
            shown.append((message, error, replace))
            return 7

        class FakeSender:
            def play(self, text, progress=None):
                progress("Playing on Living room…")
                return outcome()

        cfg = Config("(fake)", "kodi.example.lan", name=BOX)  # nothing is sent to it
        with mock.patch.object(cli.config, "load", return_value=cfg), \
                mock.patch.object(cli, "make_sender", return_value=FakeSender()), \
                mock.patch.object(cli.desktop, "notify", side_effect=notify), \
                mock.patch("sys.stdout"), mock.patch("sys.stderr"):
            code = cli.main(["play", "--notify", "https://vimeo.com/123456"])
        return code, shown

    def test_play_notifications_use_the_remotes_words(self):
        code, shown = self.notified(lambda: "Playing on Living room")
        self.assertEqual(code, 0)
        self.assertEqual(shown, [("Playing on Living room…", False, None), ("Playing on Living room", False, 7)])

    def test_unreachable_notification(self):
        def fail():
            raise OmakodiError("not reachable", "no answer from kodi.example.lan:8080 (away from home?)",
                               UNREACHABLE)
        code, shown = self.notified(fail)
        self.assertEqual(code, UNREACHABLE)
        self.assertEqual(shown[-1], ("Can't reach Living room", True, 7))


if __name__ == "__main__":
    unittest.main()
