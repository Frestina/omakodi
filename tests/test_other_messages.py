"""The phone remote's other messages (ticket 053): the words, and when they show.

Waking without a usable MAC address, a soundbar packet that can't be sent,
a link that isn't there or nothing to send, Kodi's own errors (with the fix
under them in the top bar and the terminal), and the remote's own notes.
"""

import io
import os
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fakekodi import FakeKodi  # noqa: E402
from omakodi import cli, desktop, eventserver, messages  # noqa: E402
from omakodi.config import Config  # noqa: E402
from omakodi.control import Controller  # noqa: E402
from omakodi.errors import AUTH, CONFIG, UNREACHABLE, USAGE, OmakodiError  # noqa: E402
from omakodi.rpc import Kodi, is_address  # noqa: E402
from omakodi.share import Sender  # noqa: E402
from omakodi.state import YoutubeHealth  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOX = "Living room"
VID = "dQw4w9WgXcQ"


class WordsTest(unittest.TestCase):
    def test_the_words(self):
        self.assertEqual(messages.no_mac(BOX), "No MAC address saved for Living room. Connect once while it's on, "
                                               "or add it in the box's settings.")
        self.assertEqual(messages.bad_mac(BOX), "Invalid MAC address for Living room")
        self.assertEqual(messages.soundbar_unreachable(BOX, "Network is unreachable"),
                         "Couldn't reach Living room: Network is unreachable")
        self.assertEqual(messages.NO_LINK, "No link found")
        self.assertEqual(messages.NOTHING_TO_SEND, "Nothing to send")
        self.assertEqual(messages.wrong_login(BOX), "Wrong username or password for Living room")
        self.assertEqual(messages.answered_http(BOX, 503), "Living room answered HTTP 503")
        self.assertEqual(messages.bad_address(BOX), "Bad address for Living room")
        self.assertEqual(messages.bad_reply(BOX), "Unexpected reply from Living room")
        self.assertEqual(messages.wrong_login(""), "Wrong username or password for Kodi")

    def test_each_error_in_the_phones_words_with_its_fix(self):
        cases = [
            (OmakodiError("wrong username or password", "Kodi refused the login; check username and password in "
                          "(fake)", AUTH), "Wrong username or password for Living room"),
            (OmakodiError("http 500", "from Kodi for JSONRPC.Ping"), "Living room answered HTTP 500"),
            (OmakodiError("bad response", "Kodi's answer to JSONRPC.Ping is not JSON"),
             "Unexpected reply from Living room"),
            (OmakodiError("bad address", "'kodi..lan' isn't an IP address or a hostname", CONFIG),
             "Bad address for Living room"),
            (OmakodiError("not reachable", "no answer from kodi.example.lan:8080 (away from home?)", UNREACHABLE),
             "Can't reach Living room"),
            (OmakodiError("no link found", "the text has no http(s) link", USAGE), "No link found"),
            (OmakodiError("Nothing to send", "the clipboard is empty", USAGE), "Nothing to send"),
        ]
        for error, said in cases:
            with self.subTest(error.kind):
                self.assertEqual(messages.explain(error, BOX), (said, error.detail))
                self.assertEqual(messages.for_user(error, BOX), said)
                self.assertEqual(messages.with_fix(error, BOX), said + "\n" + error.detail)
        # The editor's "bad address" (a field it can't save) keeps its words.
        editor = OmakodiError("bad address", "give the box's IP address or hostname (no http://, no port)", USAGE)
        self.assertEqual(messages.for_user(editor, BOX), str(editor))
        # Not the phone remote's: as they are, nothing under them.
        other = OmakodiError("kodi error", "Failed to execute method. (Player.Open)")
        self.assertEqual(messages.explain(other, BOX), ("kodi error: Failed to execute method. (Player.Open)", ""))
        self.assertEqual(messages.with_fix(other, BOX), "kodi error: Failed to execute method. (Player.Open)")

    def test_the_error_names_its_box(self):
        # Without the box in use's name (the terminal), the one the error came from.
        error = OmakodiError("http 401", "", box="Bedroom")
        self.assertEqual(messages.for_user(error), "Bedroom answered HTTP 401")
        self.assertEqual(messages.for_user(error, BOX), "Living room answered HTTP 401")
        self.assertEqual(messages.for_user(OmakodiError("bad response")), "Unexpected reply from Kodi")


class KodiErrorsTest(unittest.TestCase):
    """Kodi's errors, from a fake Kodi: the phone remote's words, naming the
    box, never the password."""

    def setUp(self):
        self.fake = FakeKodi().start()
        self.cfg = self.fake.config(name=BOX)

    def tearDown(self):
        self.fake.stop()

    def said(self, cfg=None):
        with self.assertRaises(OmakodiError) as cm:
            Kodi(cfg or self.cfg).call("JSONRPC.Ping")
        e = cm.exception
        self.assertNotIn(self.fake.password, messages.with_fix(e) + str(e))
        return e, messages.for_user(e), messages.with_fix(e)

    def test_wrong_password(self):
        self.fake.password = "changed-on-kodi"
        e, said, shown = self.said()
        self.assertEqual((said, e.code), ("Wrong username or password for Living room", AUTH))
        self.assertEqual(shown, "Wrong username or password for Living room\n"
                                "Kodi refused the login; check username and password in (fake)")

    def test_another_http_status(self):
        self.fake.http_status = 503
        self.assertEqual(self.said()[1], "Living room answered HTTP 503")

    def test_an_unexpected_reply(self):
        self.fake.raw_reply = b"<html>hello</html>"
        self.assertEqual(self.said()[1], "Unexpected reply from Living room")

    def test_a_bad_address_is_never_tried(self):
        for host in ("kodi..lan", "kodi.example.lan:8080", "-kodi", "a" * 64 + ".lan"):
            with self.subTest(host):
                e, said, shown = self.said(self.fake.config(host=host, name=BOX))
                self.assertEqual((e.kind, e.code, said), ("bad address", CONFIG, "Bad address for Living room"))
                self.assertEqual(shown, f"Bad address for Living room\n{host!r} isn't an IP address or a hostname; "
                                        "fix it in the box's settings or (fake)")
        self.assertEqual(self.fake.calls, [])

    def test_good_addresses(self):
        for host in ("kodi.example.lan", "kodi", "kodi.example.lan.", "192.0.2.10", "2001:db8::10", "media_box"):
            with self.subTest(host):
                self.assertTrue(is_address(host))

    def test_an_unknown_name_cant_be_reached(self):
        # As on the phone: a name that doesn't resolve is "Can't reach"; the fix says why.
        e, said, shown = self.said(self.fake.config(host="no-such-host.invalid", name=BOX))
        self.assertEqual(said, "Can't reach Living room")
        self.assertIn("ssh alias", shown.split("\n", 1)[1])

    def test_the_terminal_puts_the_fix_under_it(self):
        self.fake.password = "changed-on-kodi"
        err = io.StringIO()
        with mock.patch.object(cli.config, "load", return_value=self.cfg), mock.patch("sys.stderr", err):
            code = cli.main(["control", "playpause"])
        self.assertEqual(code, AUTH)
        self.assertEqual(err.getvalue(), "omakodi: Wrong username or password for Living room\n"
                                         "  Kodi refused the login; check username and password in (fake)\n")


class Unreachable:
    """A socket whose packets can't leave."""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def sendto(self, data, address):
        raise OSError(101, "Network is unreachable")


class SoundbarTest(unittest.TestCase):
    def test_the_packet_cant_be_sent(self):
        def send(host, port, packet):
            eventserver.send_packet(host, port, packet, make_socket=Unreachable)

        cfg = Config("(fake)", "kodi.example.lan", name=BOX)  # nothing reaches it: the socket is a stand-in
        with self.assertRaises(OmakodiError) as cm:
            Controller(Kodi(cfg), event_send=send).run("soundbaron")
        self.assertEqual(messages.for_user(cm.exception), "Couldn't reach Living room: Network is unreachable")
        self.assertEqual(messages.with_fix(cm.exception), "Couldn't reach Living room: Network is unreachable")
        self.assertEqual(cm.exception.code, UNREACHABLE)
        # The error itself keeps the address.
        self.assertEqual(str(cm.exception),
                         "can't reach Kodi's EventServer: kodi.example.lan:9777 (Network is unreachable)")

    def test_a_bad_address(self):
        sent = []
        cfg = Config("(fake)", "kodi..lan", name=BOX)
        with self.assertRaises(OmakodiError) as cm:
            Controller(Kodi(cfg), event_send=lambda *a: sent.append(a)).run("soundbaron")
        self.assertEqual((messages.for_user(cm.exception), sent), ("Bad address for Living room", []))


class SendingALinkTest(unittest.TestCase):
    def setUp(self):
        self.fake = FakeKodi().start()
        self.installed = {"plugin.video.youtube", "plugin.video.sendtokodi"}
        self.fake.results["Addons.GetAddonDetails"] = lambda p: {
            "addon": {"addonid": p["addonid"], "enabled": p["addonid"] in self.installed}}
        self.fake.results["Player.GetActivePlayers"] = []
        self.fake.results["Playlist.GetProperties"] = {"size": 3}
        self.tmp = tempfile.TemporaryDirectory()
        self.steps = []

    def tearDown(self):
        self.fake.stop()
        self.tmp.cleanup()

    def sender(self, mode="smart"):
        return Sender(Kodi(self.fake.config()), mode, YoutubeHealth(self.tmp.name), box=BOX)

    def refused(self, text, queue=False):
        s = self.sender()
        with self.assertRaises(OmakodiError) as cm:
            (s.queue if queue else s.play)(text, progress=self.steps.append)
        return cm.exception

    def test_no_link_found(self):
        for queue in (False, True):
            e = self.refused("have a look at this", queue)
            self.assertEqual((messages.for_user(e, BOX), e.code), ("No link found", USAGE))
        self.assertEqual(self.steps, [])
        self.assertNotIn("Player.Open", [m for m, _ in self.fake.calls])

    def test_nothing_to_send(self):
        for text in ("", "  \n\t"):
            e = self.refused(text)
            self.assertEqual((messages.for_user(e, BOX), e.code), ("Nothing to send", USAGE))
        self.assertEqual(self.fake.calls, [])  # Kodi isn't asked

    def test_with_the_addon_it_played_with(self):
        self.installed = {"plugin.video.youtube"}
        msg = self.sender("sendtokodi-only").play(f"https://youtu.be/{VID}", progress=self.steps.append)
        self.assertEqual(msg, "Playing on Living room with the YouTube add-on (SendToKodi isn't installed)…")
        self.installed = {"plugin.video.sendtokodi"}
        self.fake.results["Player.GetActivePlayers"] = [{"playerid": 1, "type": "video"}]
        msg = self.sender("youtube-only").queue(f"https://youtu.be/{VID}")
        self.assertEqual(msg, "Queued on Living room with SendToKodi (the YouTube add-on isn't installed) (3 in queue)")
        # The usual add-on: no note.
        self.installed = {"plugin.video.youtube", "plugin.video.sendtokodi"}
        self.assertEqual(self.sender("youtube-first").queue(f"https://youtu.be/{VID}"),
                         "Queued on Living room (3 in queue)")

    def test_neither_addon(self):
        self.installed = set()
        e = self.refused(f"https://youtu.be/{VID}")
        self.assertEqual(messages.for_user(e, BOX),
                         "Neither the YouTube add-on nor SendToKodi is installed on Living room")


class ClipboardTest(unittest.TestCase):
    def read(self, **run):
        with mock.patch.object(desktop.subprocess, "run", **run):
            return desktop.read_clipboard()

    def test_an_empty_clipboard_is_nothing_to_send(self):
        for got in (SimpleNamespace(returncode=1, stdout=b""), SimpleNamespace(returncode=0, stdout=b" \n")):
            with self.subTest(got.stdout):
                with self.assertRaises(OmakodiError) as cm:
                    self.read(return_value=got)
                self.assertEqual((str(cm.exception), cm.exception.code),
                                 ("Nothing to send: the clipboard is empty", USAGE))
                self.assertEqual(messages.for_user(cm.exception), "Nothing to send")

    def test_no_wl_paste(self):
        with self.assertRaises(OmakodiError) as cm:
            self.read(side_effect=OSError)
        self.assertEqual(str(cm.exception), "can't read the clipboard: is wl-paste installed?")

    def test_the_keybinding_says_it(self):
        # omakodi play --clipboard --notify with an empty clipboard: the
        # notification has the phone's words, the terminal the reason too.
        shown, err = [], io.StringIO()
        empty = SimpleNamespace(returncode=1, stdout=b"")

        def notify(message, error=False, replace=None):
            shown.append((message, error))
            return 7

        with mock.patch.object(desktop.subprocess, "run", return_value=empty), \
                mock.patch.object(cli.desktop, "notify", side_effect=notify), mock.patch("sys.stderr", err):
            code = cli.main(["play", "--clipboard", "--notify"])
        self.assertEqual(code, USAGE)
        self.assertEqual(shown, [("Nothing to send", True)])
        self.assertEqual(err.getvalue(), "omakodi: Nothing to send\n  the clipboard is empty\n")


class RemoteNotesTest(unittest.TestCase):
    """When the remote's own notes show (Panel.qml): an empty clipboard on
    p / q, no audio streams on a, and a link the service refused."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(ROOT, "Panel.qml"), encoding="utf-8") as f:
            cls.panel = f.read()

    def function(self, name):
        start = self.panel.index(f"  function {name}(")
        return self.panel[start:self.panel.index("\n  }\n", start)]

    def test_empty_clipboard_and_no_link(self):
        body = self.function("sendClipboard")
        self.assertIn('if (text.trim() === "") { say(strings.t("remote.clipboardEmpty"), false); return }', body)
        self.assertIn("say(Toast.refusal(refused), true)", body)
        self.assertIn("say(Toast.refusal(refused), true)", self.function("sendLink"))

    def test_no_audio_streams(self):
        self.assertIn('if (!audio) { say(strings.t("remote.noAudioTrack"), false); return }',
                      self.function("toggleAudioList"))

    def test_the_fix_under_the_top_bars_error(self):
        self.assertIn("readonly property string topFix: [topStatus.detail,", self.panel)


if __name__ == "__main__":
    unittest.main()
