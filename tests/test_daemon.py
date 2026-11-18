import json
import os
import queue
import subprocess
import sys
import tempfile
import threading
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fakekodi import ROOT, FakeKodi  # noqa: E402
from omakodi import daemon  # noqa: E402
from omakodi.art import ArtCache  # noqa: E402
from omakodi.titles import TitleStore  # noqa: E402
from omakodi.control import FULLSCREEN_CHECK  # noqa: E402
from omakodi.rpc import Kodi  # noqa: E402
from omakodi.share import Sender  # noqa: E402
from omakodi.state import HostValue, YoutubeHealth  # noqa: E402
from omakodi.wol import MacStore, magic_packet  # noqa: E402
from omakodi.eventserver import action_packet  # noqa: E402

SECRET_FILE = "http://media.example.lan/stream/42?api_key=fake-api-key-123"
PLAYING = {
    "Player.GetActivePlayers": [{"playerid": 1, "type": "video"}],
    "Player.GetItem": {"item": {"label": "Example Movie", "title": "Example Movie", "type": "movie",
                                "file": SECRET_FILE}},
    "Player.GetProperties": {"time": {"hours": 0, "minutes": 6, "seconds": 33},
                             "totaltime": {"hours": 0, "minutes": 50, "seconds": 9}, "speed": 1},
}


PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32

class Lines:
    """Reads the daemon's stdout in the background."""

    def __init__(self, f):
        self.q = queue.Queue()
        self.raw = []
        self.f = f
        self.thread = threading.Thread(target=self._read, args=(f,), daemon=True)
        self.thread.start()

    def close(self):
        self.thread.join(2)
        self.f.close()

    def _read(self, f):
        for line in iter(f.readline, b""):
            self.raw.append(line)
            self.q.put(json.loads(line))
        self.q.put(None)

    def next(self, timeout=3.0):
        try:
            return self.q.get(timeout=timeout)
        except queue.Empty:
            raise AssertionError("no output from the daemon") from None

    def none_within(self, seconds):
        try:
            got = self.q.get(timeout=seconds)
        except queue.Empty:
            return True
        raise AssertionError(f"unexpected output: {got}")

    def result(self, rid, timeout=3.0):
        """Skip state and progress lines up to the result for ``rid``."""
        end = time.monotonic() + timeout
        while True:
            msg = self.next(max(0.01, end - time.monotonic()))
            if msg and msg.get("type") == "result" and msg.get("id") == rid:
                return msg


class DaemonTest(unittest.TestCase):
    def setUp(self):
        self.fake = FakeKodi().start()
        self.fake.results["Application.GetProperties"] = {"volume": 80, "muted": False}
        self.fake.results["Player.GetActivePlayers"] = []
        self.fake.results["XBMC.GetInfoBooleans"] = {k: False for k in FULLSCREEN_CHECK}
        self.fake.results["Addons.GetAddonDetails"] = {"addon": {"enabled": True}}
        self.fake.results["System.GetProperties"] = lambda p: {
            k: k == "canreboot" for k in p["properties"]}
        self.state_dir = tempfile.TemporaryDirectory()
        self.now = [1000.0]
        self.cfg = self.fake.config()
        self.macs = MacStore(self.state_dir.name)
        self.woken = []
        self.events = []
        self.volume_keys = HostValue("volume", "keys", daemon.VOLUME_KEYS, self.state_dir.name)
        self.d = daemon.Daemon(
            lambda: self.cfg, clock=lambda: self.now[0], macs=self.macs, wake_send=self.woken.append,
            event_send=lambda host, port, packet: self.events.append((host, port, packet)),
            volume_keys=self.volume_keys,
            sender_for=lambda c: Sender(Kodi(c), c.youtube_mode, YoutubeHealth(self.state_dir.name)),
            art_cache=ArtCache(os.path.join(self.state_dir.name, "art")),
            titles=TitleStore(self.state_dir.name))
        in_r, self.in_w = os.pipe()
        out_r, out_w = os.pipe()
        self.inp = os.fdopen(in_r, "rb")
        self.out = os.fdopen(out_w, "wb")
        self.lines = Lines(os.fdopen(out_r, "rb"))
        self.thread = threading.Thread(target=self.d.run, args=(self.inp, self.out), daemon=True)
        self.thread.start()

    def tearDown(self):
        self.close_stdin()
        self.thread.join(2)
        self.inp.close()
        self.out.close()
        self.lines.close()
        self.fake.stop()
        self.state_dir.cleanup()
        for line in self.lines.raw:
            self.assertNotIn(self.fake.password.encode(), line)
            self.assertNotIn(b"api_key", line)

    def send(self, obj):
        raw = obj if isinstance(obj, bytes) else json.dumps(obj).encode()
        os.write(self.in_w, raw + b"\n")

    def close_stdin(self):
        if self.in_w is not None:
            os.close(self.in_w)
            self.in_w = None

    def test_state_on_connect_on_play_and_after_kodi_goes_away(self):
        first = self.lines.next()
        self.assertEqual(first, {"type": "state", "reachable": True, "error": "", "playing": None,
                                 "volume": 80, "muted": False, "queue": None, "details": None, "audio": None,
                                 "power": {"state": "on", "reboot": True, "shutdown": False},
                                 "wake": False, "volumeKeys": "unknown", "input": None})
        self.assertTrue(self.fake.wait_for_event_client())

        self.fake.results.update(PLAYING)
        self.fake.push("Player.OnPlay", {"item": {"title": "Example Movie", "type": "movie"}})
        state = self.lines.next()
        self.assertEqual(state["playing"], {"title": "Example Movie", "subtitle": "", "kind": "movie",
                                            "paused": False, "speed": 1, "positionSec": 393, "durationSec": 3009,
                                            "art": ""})

        # Kodi goes away: nothing changes for 45 s of failure, then it's gone.
        self.fake.stop()
        self.lines.none_within(0.6)
        self.now[0] += 44
        self.lines.none_within(0.6)
        self.now[0] += 6  # the next 5 s retry, past 45 s
        gone = self.lines.next()
        self.assertEqual((gone["reachable"], gone["playing"], gone["volume"]), (False, None, None))
        self.assertTrue(gone["error"].startswith("not reachable"), gone["error"])

    def test_polls_while_playing(self):
        self.fake.results.update(PLAYING)
        self.assertEqual(self.lines.next()["playing"]["positionSec"], 393)
        self.fake.results["Player.GetProperties"] = dict(PLAYING["Player.GetProperties"],
                                                         time={"minutes": 6, "seconds": 38})
        self.lines.none_within(0.4)
        self.now[0] += 5
        self.assertEqual(self.lines.next()["playing"]["positionSec"], 398)

    def test_key_answered_before_a_pending_play(self):
        self.lines.next()
        gate = threading.Event()
        self.fake.results["Player.Open"] = lambda params: (gate.wait(5), "OK")[1]
        self.send({"id": 1, "cmd": "play", "text": "look: https://video.example.net/clip/7"})
        time.sleep(0.2)
        self.send({"id": 2, "cmd": "control", "action": "up"})
        self.assertEqual(self.lines.result(2), {"type": "result", "id": 2, "ok": True, "message": ""})
        gate.set()
        self.assertEqual(self.lines.result(1), {"type": "result", "id": 1, "ok": True,
                                                "message": "Playing on Kodi…"})

    def test_keys_run_in_order_and_stale_ones_are_skipped(self):
        self.lines.next()
        gate = threading.Event()
        self.fake.results["Input.Up"] = lambda params: (gate.wait(5), "OK")[1]
        self.send({"id": 1, "cmd": "control", "action": "up"})
        self.send({"id": 2, "cmd": "control", "action": "down"})
        self.send({"id": 3, "cmd": "control", "action": "left"})
        time.sleep(0.2)
        self.now[0] += 10  # Kodi took 10 s over the first key
        self.send({"id": 4, "cmd": "control", "action": "right"})
        gate.set()
        self.assertTrue(self.lines.result(1)["ok"])
        for rid in (2, 3):
            self.assertEqual(self.lines.result(rid)["error"], "skipped: Kodi was busy with the previous key")
        self.assertTrue(self.lines.result(4)["ok"])
        sent = [m for m in self.fake.methods() if m.startswith("Input.")]
        self.assertEqual(sent, ["Input.Up", "Input.Right"])

    def test_held_arrow_in_fullscreen_video(self):
        self.lines.next()
        self.fake.results["XBMC.GetInfoBooleans"] = {k: k == FULLSCREEN_CHECK[0] for k in FULLSCREEN_CHECK}
        self.send({"id": 1, "cmd": "control", "action": "right"})
        self.send({"id": 2, "cmd": "control", "action": "right", "repeat": True})
        self.send({"id": 3, "cmd": "control", "action": "right", "repeat": "yes"})  # not true: a press
        for rid in (1, 2, 3):
            self.assertEqual(self.lines.result(rid), {"type": "result", "id": rid, "ok": True, "message": ""})
        sent = [p for m, p in self.fake.calls if m == "Input.ExecuteAction"]
        self.assertEqual(sent, [{"action": "stepforward"}] * 2)

    def test_kodi_keyboard_sets_and_clears_input(self):
        self.lines.next()
        self.assertTrue(self.fake.wait_for_event_client())
        self.fake.push("Input.OnInputRequested", {"type": "keyboard", "title": "Search", "value": "the w"})
        self.assertEqual(self.lines.next()["input"], {"type": "keyboard", "title": "Search", "value": "the w"})
        self.fake.push("Input.OnInputFinished")
        self.assertIsNone(self.lines.next()["input"])

    def test_hidden_input_never_carries_its_value(self):
        self.lines.next()
        self.assertTrue(self.fake.wait_for_event_client())
        for kind, shown in (("password", "password"), ("numericpassword", "numericpassword"),
                            ("something-new", "keyboard")):
            with self.subTest(kind=kind):
                self.fake.push("Input.OnInputRequested", {"type": kind, "title": "Login", "value": "example-secret"})
                state = self.lines.next()
                self.assertEqual(state["input"], {"type": shown, "title": "Login", "value": ""})
                self.assertNotIn("example-secret", json.dumps(state))
                self.fake.push("Input.OnInputFinished")
                self.lines.next()

    def test_input_cleared_when_the_event_port_drops(self):
        self.lines.next()
        self.assertTrue(self.fake.wait_for_event_client())
        self.fake.push("Input.OnInputRequested", {"type": "keyboard", "title": "Search", "value": ""})
        self.assertIsNotNone(self.lines.next()["input"])
        self.fake.drop_event_clients()
        self.assertIsNone(self.lines.next()["input"])

    def test_text_is_sent_to_kodi(self):
        self.lines.next()
        self.send({"id": 1, "cmd": "text", "text": "the wi"})
        self.send({"id": 2, "cmd": "text", "text": "the wire", "done": True})
        self.send({"id": 3, "cmd": "text", "text": "x", "done": "yes"})  # not true: not done
        for rid in (1, 2, 3):
            self.assertEqual(self.lines.result(rid), {"type": "result", "id": rid, "ok": True, "message": ""})
        sent = [p for m, p in self.fake.calls if m == "Input.SendText"]
        self.assertEqual(sent, [{"text": "the wi", "done": False}, {"text": "the wire", "done": True},
                                {"text": "x", "done": False}])
        self.send({"id": 4, "cmd": "text", "text": "x" * 301})
        self.send({"id": 5, "cmd": "text"})
        for rid in (4, 5):
            self.assertTrue(self.lines.result(rid)["error"].startswith('bad request: "text" must be text'))

    def test_seek(self):
        self.lines.next()
        self.fake.results["Player.GetActivePlayers"] = [{"playerid": 1, "type": "video"}]
        self.send({"id": 1, "cmd": "seek", "seconds": 754})
        self.assertEqual(self.lines.result(1), {"type": "result", "id": 1, "ok": True, "message": ""})
        seeks = [p for m, p in self.fake.calls if m == "Player.Seek"]
        self.assertEqual(seeks, [{"playerid": 1, "value": {"time": {
            "hours": 0, "minutes": 12, "seconds": 34, "milliseconds": 0}}}])
        for rid, seconds in ((2, -1), (3, "754"), (4, 1.5), (5, True), (6, None), (7, 10 ** 9)):
            self.send({"id": rid, "cmd": "seek", "seconds": seconds} if seconds is not None
                      else {"id": rid, "cmd": "seek"})
            self.assertTrue(self.lines.result(rid)["error"].startswith('bad request: "seconds"'), rid)
        self.assertEqual(len([m for m in self.fake.methods() if m == "Player.Seek"]), 1)

    def test_audio_tracks_in_the_state_and_switching(self):
        self.lines.next()
        streams = [{"index": 0, "name": "Stereo", "language": "eng", "codec": "aac", "channels": 2},
                   {"index": 1, "name": "[B]Commentary[/B]", "language": "nor", "codec": "ac3", "channels": 6}]
        current = [0]
        self.fake.results["Player.GetActivePlayers"] = [{"playerid": 1, "type": "video"}]
        self.fake.results["Player.GetProperties"] = lambda p: {
            "speed": 1, "audiostreams": streams, "currentaudiostream": streams[current[0]]}

        def set_stream(p):
            current[0] = p["stream"]
            return "OK"
        self.fake.results["Player.SetAudioStream"] = set_stream
        state = self.next_state(lambda m: m.get("audio"))
        self.assertEqual(state["audio"], {"current": 0, "tracks": [
            {"index": 0, "name": "Stereo", "language": "English", "codec": "AAC", "channels": "Stereo"},
            {"index": 1, "name": "Commentary", "language": "Norwegian", "codec": "AC3", "channels": "5.1"}]})
        self.send({"id": 1, "cmd": "audio", "index": 1})
        self.assertEqual(self.lines.result(1), {"type": "result", "id": 1, "ok": True, "message": ""})
        self.assertEqual(self.next_state(lambda m: (m.get("audio") or {}).get("current") == 1)["audio"]["current"], 1)
        self.send({"id": 2, "cmd": "audio", "index": 5})
        self.assertEqual(self.lines.result(2)["error"], "no such audio track: it changed; look again")
        for rid, index in ((3, -1), (4, "1"), (5, 1.5), (6, True), (7, None), (8, 1000)):
            self.send({"id": rid, "cmd": "audio", "index": index} if index is not None else {"id": rid, "cmd": "audio"})
            self.assertTrue(self.lines.result(rid)["error"].startswith('bad request: "index"'), rid)
        self.assertEqual(self.fake.methods().count("Player.SetAudioStream"), 1)
        self.fake.results["Player.GetActivePlayers"] = []
        self.assertIsNone(self.next_state(lambda m: m.get("playing") is None)["audio"])

    def test_shutdown_says_off_at_once(self):
        self.lines.next()
        # Read when Kodi answered; the shut down asks Kodi again itself.
        self.fake.results["System.GetProperties"] = lambda p: {k: True for k in p["properties"]}
        self.send({"id": 1, "cmd": "control", "action": "shutdown"})
        self.assertEqual(self.lines.result(1)["ok"], True)
        off = self.next_state(lambda m: (m.get("power") or {}).get("state") == "off")
        self.assertEqual((off["reachable"], off["error"], off["playing"]), (False, "", None))
        self.assertIn("System.Shutdown", self.fake.methods())
        # Kodi still answers as it closes: that isn't it being back.
        self.now[0] += 5
        self.send({"id": 2, "cmd": "refresh"})
        self.lines.result(2)
        self.assertEqual(self.d._state["power"]["state"], "off")
        # Gone: still "off", not "not reachable", however long it takes.
        self.fake.stop()
        self.now[0] += 600
        state = self.next_state(lambda m: True)
        self.assertEqual((state["power"]["state"], state["reachable"], state["error"]), ("off", False, ""))

    def test_back_after_a_reboot(self):
        self.lines.next()
        self.assertTrue(self.fake.wait_for_event_client())
        self.fake.push("System.OnQuit", {"exitcode": 66})
        state = self.next_state(lambda m: (m.get("power") or {}).get("state") == "restarting")
        self.assertFalse(state["reachable"])
        reads = self.fake.methods().count("System.GetProperties")
        self.now[0] += 20  # answering again after the quiet time: it's back
        state = self.next_state(lambda m: m.get("reachable"))
        self.assertEqual(state["power"]["state"], "on")
        self.assertEqual(self.fake.methods().count("System.GetProperties"), reads + 1)  # read again

    def test_quit_codes_and_a_reboot_that_never_comes_back(self):
        self.lines.next()
        self.assertTrue(self.fake.wait_for_event_client())
        self.fake.push("System.OnQuit", {"exitcode": 64})
        self.next_state(lambda m: (m.get("power") or {}).get("state") == "off")
        self.fake.stop()
        self.d._going("restarting")
        self.next_state(lambda m: (m.get("power") or {}).get("state") == "restarting")
        self.now[0] += 181  # no answer for 3 minutes: plain "not reachable"
        state = self.next_state(lambda m: m.get("error"))
        self.assertTrue(state["error"].startswith("not reachable"), state["error"])
        self.assertIsNone(state["power"])

    def volume_box(self, volume, cec):
        """Kodi's own volume; volume keys move it unless they go over CEC."""
        level = [volume]

        def set_volume(p):
            v = p["volume"]
            if isinstance(v, int):
                level[0] = v
            elif not cec:
                level[0] = max(0, min(100, level[0] + (5 if v == "increment" else -5)))
            return level[0]
        self.fake.results["Application.GetProperties"] = lambda p: {"volume": level[0], "muted": False}
        self.fake.results["Application.SetVolume"] = set_volume
        return level

    def volume_key(self, rid, action):
        self.send({"id": rid, "cmd": "control", "action": action})
        self.assertTrue(self.lines.result(rid)["ok"])

    def test_volume_keys_that_go_to_the_tv(self):
        self.volume_box(80, cec=True)
        self.send({"id": 1, "cmd": "refresh"})
        self.lines.result(1)
        self.volume_key(2, "soundbarup")
        self.assertEqual(self.d._state["volumeKeys"], "unknown")  # not yet: Kodi may still apply it
        self.now[0] += 1.1
        state = self.next_state(lambda m: m.get("volumeKeys") != "unknown")
        self.assertEqual((state["volumeKeys"], state["volume"]), ("tv", 80))
        self.assertEqual(self.volume_keys.read(self.cfg.host), "tv")

    def test_volume_keys_that_move_kodis_volume(self):
        self.volume_keys.save(self.cfg.host, "tv")  # an old finding: Kodi now says otherwise
        self.volume_box(80, cec=False)
        self.assertEqual(self.lines.next()["volumeKeys"], "tv")
        self.send({"id": 1, "cmd": "refresh"})
        self.lines.result(1)
        self.volume_key(2, "soundbardown")
        state = self.next_state(lambda m: m.get("volumeKeys") == "kodi")
        self.assertEqual(state["volume"], 75)
        self.assertEqual(self.volume_keys.read(self.cfg.host), "kodi")

    def test_volume_keys_at_the_limit_learn_nothing(self):
        self.volume_box(100, cec=True)
        self.send({"id": 1, "cmd": "refresh"})
        self.lines.result(1)
        self.volume_key(2, "soundbarup")
        self.now[0] += 1.1
        self.send({"id": 3, "cmd": "refresh"})
        self.lines.result(3)
        self.assertEqual(self.d._state["volumeKeys"], "unknown")
        self.assertIsNone(self.d._vol_probe)
        self.assertIsNone(self.volume_keys.read(self.cfg.host))

    def test_plus_and_minus_never_teach_where_the_keys_go(self):
        level = self.volume_box(80, cec=True)
        self.send({"id": 1, "cmd": "refresh"})
        self.lines.result(1)
        self.volume_key(2, "volup")  # Kodi's own volume: moves it, says nothing about CEC
        self.assertEqual(level[0], 85)
        self.now[0] += 1.1
        self.send({"id": 3, "cmd": "refresh"})
        self.lines.result(3)
        self.assertEqual((self.d._state["volume"], self.d._state["volumeKeys"]), (85, "unknown"))

    def test_kodis_own_volume(self):
        level = self.volume_box(100, cec=True)
        self.lines.next()
        self.send({"id": 1, "cmd": "volume", "level": 60})
        self.assertEqual(self.lines.result(1), {"type": "result", "id": 1, "ok": True, "message": ""})
        self.assertEqual(level[0], 60)
        self.assertEqual(self.next_state(lambda m: m.get("volume") == 60)["volumeKeys"], "unknown")
        for bad in (101, -1, 50.5, "60", True, None):
            self.send({"id": 2, "cmd": "volume", "level": bad})
            self.assertIn('"level" must be a whole number from 0 to 100', self.lines.result(2)["error"])
        self.assertEqual(level[0], 60)

    def test_soundbar_on_goes_to_the_event_server(self):
        self.lines.next()
        self.send({"id": 1, "cmd": "control", "action": "soundbaron"})
        self.assertEqual(self.lines.result(1), {"type": "result", "id": 1, "ok": True,
                                                "message": "Asked Kodi to turn on the soundbar"})
        self.assertEqual(self.events, [(self.cfg.host, 9777, action_packet("CECActivateSource"))])

    def test_mac_is_read_saved_and_wakes(self):
        answers = iter(["Busy", "Busy", "02-1A-2B-3C-4D-5E"])
        self.fake.results["XBMC.GetInfoLabels"] = lambda p: (
            {"Network.MacAddress": next(answers, "02:00:00:00:00:09")}
            if p == {"labels": ["Network.MacAddress"]} else {})
        self.assertFalse(self.lines.next()["wake"])
        self.send({"id": 1, "cmd": "wake"})
        self.assertIn("no MAC address known yet", self.lines.result(1)["error"])
        for rid in (2, 3):  # Kodi says Busy while it looks it up: asked again
            self.send({"id": rid, "cmd": "refresh"})
            self.lines.result(rid)
        self.assertTrue(self.d._state["wake"])
        self.assertEqual(self.macs.read(self.cfg.host), "02:1a:2b:3c:4d:5e")
        self.send({"id": 4, "cmd": "refresh"})
        self.lines.result(4)
        self.assertEqual(self.fake.methods().count("XBMC.GetInfoLabels"), 3)  # not again once known

        self.fake.stop()  # off: the remote offers to wake it
        self.d._going("off")
        state = self.next_state(lambda m: (m.get("power") or {}).get("state") == "off")
        self.assertTrue(state["wake"])
        self.send({"id": 5, "cmd": "wake"})
        self.assertEqual(self.lines.result(5), {"type": "result", "id": 5, "ok": True,
                                                "message": "Wake-up sent; Kodi takes a minute to start"})
        self.assertEqual(self.woken, [magic_packet("02:1a:2b:3c:4d:5e")])

    def test_mac_is_given_up_on_and_read_again_when_kodi_is_back(self):
        self.fake.results["XBMC.GetInfoLabels"] = {"Network.MacAddress": "Busy"}
        self.lines.next()
        for rid in range(1, 8):
            self.send({"id": rid, "cmd": "refresh"})
            self.lines.result(rid)
        self.assertEqual(self.fake.methods().count("XBMC.GetInfoLabels"), daemon.MAC_TRIES)
        self.assertFalse(self.d._state["wake"])
        self.assertTrue(self.fake.wait_for_event_client())
        self.fake.push("System.OnQuit", {"exitcode": 66})
        self.next_state(lambda m: (m.get("power") or {}).get("state") == "restarting")
        self.fake.results["XBMC.GetInfoLabels"] = {"Network.MacAddress": "02:1a:2b:3c:4d:5e"}
        self.now[0] += 20
        self.assertTrue(self.next_state(lambda m: m.get("reachable"))["wake"])
        self.assertEqual(self.fake.methods().count("XBMC.GetInfoLabels"), daemon.MAC_TRIES + 1)

    def test_wake_on_lan_off_and_the_configs_mac(self):
        self.lines.next()
        self.fake.results["XBMC.GetInfoLabels"] = {"Network.MacAddress": "02:1a:2b:3c:4d:5e"}
        self.fake.clear_calls()
        self.cfg = self.fake.config(wake_on_lan=False, mac="02:00:00:00:00:01")
        self.send({"id": 1, "cmd": "refresh"})
        self.assertFalse(self.next_state(lambda m: True)["wake"])
        self.lines.result(1)
        self.send({"id": 2, "cmd": "wake"})
        self.assertIn('"wakeOnLan" is false', self.lines.result(2)["error"])
        self.assertNotIn("XBMC.GetInfoLabels", self.fake.methods())
        self.cfg = self.fake.config(mac="02:00:00:00:00:01")  # set by hand: not read from Kodi
        self.send({"id": 3, "cmd": "refresh"})
        self.assertTrue(self.next_state(lambda m: True)["wake"])
        self.send({"id": 4, "cmd": "wake"})
        self.assertTrue(self.lines.result(4)["ok"])
        self.assertEqual(self.woken, [magic_packet("02:00:00:00:00:01")])
        self.assertNotIn("XBMC.GetInfoLabels", self.fake.methods())
        self.assertIsNone(self.macs.read(self.cfg.host))

    def test_art_is_fetched_and_only_its_path_is_shown(self):
        url = "image://http%3a%2f%2fmedia.example.lan%2fposter.png%3fapi_key%3dsecret123/"
        self.fake.images[url] = PNG
        self.fake.results["Player.GetActivePlayers"] = [{"playerid": 1, "type": "video"}]
        self.fake.results["Player.GetItem"] = {"item": {"type": "movie", "title": "Example Movie",
                                                        "art": {"poster": url}}}
        self.fake.results["Player.GetProperties"] = {"speed": 1}
        seen = []

        def has_art(msg):
            seen.append(json.dumps(msg))
            return bool((msg.get("playing") or {}).get("art"))

        path = self.next_state(has_art)["playing"]["art"]
        self.assertTrue(path.startswith(os.path.join(self.state_dir.name, "art") + os.sep), path)
        self.assertTrue(path.endswith(".png"))
        with open(path, "rb") as f:
            self.assertEqual(f.read(), PNG)
        self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)
        self.assertEqual(self.fake.image_requests, [url])
        self.assertFalse(any("secret123" in line or "media.example.lan" in line for line in seen))

    def queue_playing(self, titles, position):
        """A fake video queue playing ``titles[position]``."""
        items = [{"label": t, "title": t, "type": "unknown", "file": f"plugin://example/{i}?token=hidden"}
                 for i, t in enumerate(titles)]
        self.fake.results["Player.GetActivePlayers"] = [{"playerid": 1, "type": "video"}]
        self.fake.results["Player.GetItem"] = {"item": {"type": "unknown", "title": titles[position]}}
        self.fake.results["Player.GetProperties"] = {"speed": 1, "playlistid": 1, "position": position}
        self.fake.results["Playlist.GetProperties"] = lambda p: {"size": len(items)}
        self.fake.results["Playlist.GetItems"] = lambda p: {
            "items": items[p["limits"]["start"]:p["limits"]["end"]],
            "limits": {"start": p["limits"]["start"], "end": p["limits"]["end"], "total": len(items)}}
        return items

    def next_state(self, test, timeout=3.0):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            try:
                msg = self.lines.next(0.3)
            except AssertionError:  # nothing within 0.3 s: ask for the state
                self.send({"id": "r", "cmd": "refresh"})
                continue
            if msg.get("type") == "state" and test(msg):
                return msg
        self.fail("no such state")

    def test_queue_in_the_state(self):
        self.lines.next()
        items = self.queue_playing(["Harbour Lights", "Night Ferry", "The Tide Clock"], 1)
        state = self.next_state(lambda m: m.get("queue"))
        self.assertEqual(state["queue"], {"position": 1, "start": 0, "total": 3, "items": [
            {"title": "Harbour Lights", "subtitle": ""}, {"title": "Night Ferry", "subtitle": ""},
            {"title": "The Tide Clock", "subtitle": ""}]})
        self.assertNotIn("token=hidden", json.dumps(state))
        # The file is asked for (to look up stored titles) but never shown.
        self.assertNotIn("plugin://example", json.dumps(state))
        reads = self.fake.methods().count("Playlist.GetItems")
        self.send({"id": 1, "cmd": "refresh"})
        self.lines.result(1)
        self.assertEqual(self.fake.methods().count("Playlist.GetItems"), reads)  # unchanged: not read again
        items.append({"label": "Fourth", "title": "Fourth"})  # queued
        state = self.next_state(lambda m: m.get("queue") and m["queue"]["total"] == 4)
        self.assertEqual(state["queue"]["items"][-1]["title"], "Fourth")
        self.fake.results["Player.GetProperties"] = {"speed": 1, "playlistid": -1, "position": -1}
        self.assertIsNone(self.next_state(lambda m: m.get("queue") is None)["queue"])

    def test_stored_title_for_an_entry_kodi_has_none_for(self):
        self.lines.next()
        items = self.queue_playing(["Harbour Lights", "Night Ferry"], 0)
        queued = "plugin://plugin.video.youtube/play/?video_id=aqz-KE-bpKQ"
        TitleStore(self.state_dir.name).put(queued, "Highland Cow Gets a Bath")
        items.append({"label": "play", "title": "", "type": "unknown", "file": queued})
        state = self.next_state(lambda m: m.get("queue") and m["queue"]["total"] == 3)
        self.assertEqual([i["title"] for i in state["queue"]["items"]],
                         ["Harbour Lights", "Night Ferry", "Highland Cow Gets a Bath"])
        self.assertNotIn("video_id", json.dumps(state))
        # Kodi's own title wins once it has one (the entry played).
        items[2] = {"label": "Highland Cow", "title": "Highland Cow", "type": "unknown", "file": queued}
        TitleStore(self.state_dir.name).put("plugin://other", "x")  # any change makes it look again
        state = self.next_state(lambda m: m.get("queue") and m["queue"]["items"][2]["title"] == "Highland Cow")

    def details_playing(self, title, streams):
        """A fake library movie ``title``; ``streams`` the playing streams
        (a dict, so the test can change it)."""
        self.fake.results["Player.GetActivePlayers"] = [{"playerid": 1, "type": "video"}]
        movie = {"plot": "[B]A lighthouse keeper[/B][CR]finds a map.", "genre": ["Drama", "Mystery"],
                 "year": 2019, "studio": ["Northlight Pictures"], "rating": 7.84,
                 "cast": [{"name": "Ada Example", "role": "Keeper", "order": 0}],
                 "streamdetails": {"video": [{"width": 3840, "height": 1600, "hdrtype": "dolbyvision"}],
                                   "audio": [{"channels": 8, "codec": "truehd_atmos"}]}}
        self.fake.results["Player.GetItem"] = lambda p: {"item": {
            "type": "movie", "id": 7, "label": title[0], "title": title[0], "file": SECRET_FILE,
            **(movie if "plot" in p["properties"] else {})}}
        self.fake.results["Player.GetProperties"] = lambda p: (
            dict(streams) if "currentvideostream" in p["properties"] else {"speed": 1})

    def detail_reads(self):
        return sum(1 for m, p in list(self.fake.calls)
                   if m == "Player.GetItem" and "plot" in (p or {}).get("properties", []))

    def test_details_read_once_per_item(self):
        self.lines.next()
        self.assertTrue(self.fake.wait_for_event_client())
        title = ["Harbour Lights"]
        streams = {"currentvideostream": {"width": 3840, "height": 1600, "codec": "hevc"},
                   "currentaudiostream": {"channels": 8, "codec": "truehd"}}
        self.details_playing(title, streams)
        state = self.next_state(lambda m: m.get("details"))
        self.assertEqual(state["details"], {
            "plot": "A lighthouse keeper\nfinds a map.", "genres": ["Drama", "Mystery"], "year": 2019,
            "studio": "Northlight Pictures", "rating": "7.8", "cast": ["Ada Example"],
            "badges": ["4K", "Dolby Vision", "7.1", "TrueHD"]})
        for rid in (1, 2, 3):  # more polls of the same item: not read again
            self.send({"id": rid, "cmd": "refresh"})
            self.lines.result(rid)
        self.assertEqual(self.detail_reads(), 1)
        self.fake.push("Player.OnAVStart", {"item": {"type": "movie"}})  # streams were known: no read
        self.send({"id": 4, "cmd": "refresh"})
        self.lines.result(4)
        self.assertEqual(self.detail_reads(), 1)

        # A new item that has only just started: no streams yet, so it is
        # read once more when the picture comes up.
        streams.clear()
        title[0] = "Night Ferry"
        state = self.next_state(lambda m: (m.get("playing") or {}).get("title") == "Night Ferry")
        self.assertEqual(state["details"]["badges"], ["4K", "Dolby Vision", "7.1", "TrueHD Atmos"])
        self.assertEqual(self.detail_reads(), 2)
        streams.update({"currentvideostream": {"width": 1920, "height": 1080},
                        "currentaudiostream": {"channels": 2, "codec": "aac"}})
        self.fake.push("Player.OnAVStart", {"item": {"type": "movie"}})
        state = self.next_state(lambda m: (m.get("details") or {}).get("badges", [""])[0] == "1080p")
        self.assertEqual(state["details"]["badges"], ["1080p", "Dolby Vision", "Stereo", "AAC"])
        self.assertEqual(self.detail_reads(), 3)
        self.fake.push("Player.OnAVStart", {"item": {"type": "movie"}})
        self.send({"id": 5, "cmd": "refresh"})
        self.lines.result(5)
        self.assertEqual(self.detail_reads(), 3)

        self.fake.results["Player.GetActivePlayers"] = []
        self.assertIsNone(self.next_state(lambda m: m.get("playing") is None)["details"])

    def test_details_bounded_from_junk(self):
        self.lines.next()
        self.details_playing(["Harbour Lights"], {})
        self.fake.results["Player.GetItem"] = lambda p: (
            {"item": {"type": "movie", "title": "Harbour Lights"}} if "plot" not in p["properties"]
            else {"item": {"type": "movie", "plot": "x" * 5000, "cast": "not a list", "genre": [1, None]}})
        state = self.next_state(lambda m: m.get("details"))
        self.assertEqual(set(state["details"]), {"plot"})
        self.assertEqual(len(state["details"]["plot"]), 3000)
        self.assertTrue(state["details"]["plot"].endswith("…"))

    def test_goto_and_remove(self):
        self.lines.next()
        self.queue_playing(["One", "Two", "Three"], 1)
        self.send({"id": 1, "cmd": "goto", "position": 2})
        self.assertEqual(self.lines.result(1)["ok"], True)
        self.send({"id": 2, "cmd": "remove", "position": 0})
        self.assertEqual(self.lines.result(2)["ok"], True)
        self.send({"id": 3, "cmd": "remove", "position": 1})
        self.assertEqual(self.lines.result(3)["error"], "that one is playing: stop it or skip it first")
        self.send({"id": 4, "cmd": "goto", "position": 3})
        self.assertEqual(self.lines.result(4)["error"], "not in the queue: it changed; look again")
        for rid, pos in ((5, -1), (6, "2"), (7, True), (8, None)):
            self.send({"id": rid, "cmd": "goto", "position": pos})
            self.assertTrue(self.lines.result(rid)["error"].startswith('bad request: "position"'), rid)
        calls = [(m, p) for m, p in self.fake.calls if m in ("Player.GoTo", "Playlist.Remove")]
        self.assertEqual(calls, [("Player.GoTo", {"playerid": 1, "to": 2}),
                                 ("Playlist.Remove", {"playlistid": 1, "position": 0})])
        self.fake.results["Player.GetProperties"] = {"speed": 1, "playlistid": -1, "position": -1}
        self.send({"id": 9, "cmd": "goto", "position": 0})
        self.assertEqual(self.lines.result(9)["error"], "not playing the queue")

    def test_errors_are_results(self):
        self.lines.next()
        self.send({"id": "a", "cmd": "control", "action": "stop"})
        self.assertEqual(self.lines.result("a"), {"type": "result", "id": "a", "ok": False,
                                                  "error": "nothing playing"})
        self.send({"id": 5, "cmd": "queue", "text": "no link here"})
        self.assertEqual(self.lines.result(5)["error"], "no link found: the text has no http(s) link")

    def test_bad_lines_are_answered(self):
        self.lines.next()
        cases = [
            (b"not json", None, "bad request: not JSON"),
            (b"\xff\xfe", None, "bad request: not JSON"),
            (b"[1, 2]", None, "bad request: not a JSON object"),
            (b'{"cmd": "refresh"}', None, 'bad request: "id" must be a number or short text'),
            (b'{"id": true, "cmd": "refresh"}', None, 'bad request: "id" must be a number or short text'),
            (b'{"id": 1, "cmd": "dance"}', 1, "bad request: unknown command"),
            (b'{"id": 2, "cmd": "control", "action": "dance"}', 2, "bad request: unknown action"),
            (b'{"id": 3, "cmd": "play", "text": 7}', 3, 'bad request: "text" must be text'),
            (b"x" * (daemon.MAX_LINE + 10), None, "bad request: line too long"),
        ]
        for raw, rid, error in cases:
            with self.subTest(raw=raw[:40]):
                self.send(raw)
                msg = self.lines.next()
                self.assertEqual((msg["type"], msg["id"], msg["ok"]), ("result", rid, False))
                self.assertTrue(msg["error"].startswith(error), msg["error"])
        self.send(b"")  # blank lines are ignored
        self.send({"id": 9, "cmd": "refresh"})
        self.assertEqual(self.lines.next()["type"], "state")  # refresh always pushes the state
        self.assertEqual(self.lines.next(), {"type": "result", "id": 9, "ok": True, "message": ""})

    def test_wrong_password_shows_at_once(self):
        self.lines.next()
        self.fake.password = "changed-on-kodi"
        self.send({"id": 1, "cmd": "refresh"})
        state = self.lines.next()
        self.assertEqual((state["reachable"], state["playing"]), (True, None))
        self.assertTrue(state["error"].startswith("wrong username or password"))

    def test_close_stdin_stops(self):
        self.lines.next()
        self.close_stdin()
        self.thread.join(1)
        self.assertFalse(self.thread.is_alive())
        for t in self.d._threads:
            self.assertFalse(t.is_alive())


class DaemonProcessTest(unittest.TestCase):
    """The real `omakodi daemon` over pipes."""

    def test_over_pipes(self):
        fake = FakeKodi().start()
        fake.results["Application.GetProperties"] = {"volume": 30, "muted": True}
        fake.results["Player.GetActivePlayers"] = []
        fake.results["XBMC.GetInfoBooleans"] = {k: False for k in FULLSCREEN_CHECK}
        try:
            with tempfile.TemporaryDirectory() as d:
                cfg = os.path.join(d, "config.json")
                fd = os.open(cfg, os.O_WRONLY | os.O_CREAT, 0o600)
                with os.fdopen(fd, "w") as f:
                    json.dump(fake.config_json(), f)
                env = dict(os.environ, OMAKODI_CONFIG=cfg, XDG_STATE_HOME=d)
                p = subprocess.Popen([os.path.join(ROOT, "bin", "omakodi"), "daemon"], stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
                lines = Lines(p.stdout)
                try:
                    state = lines.next(5)
                    self.assertEqual((state["type"], state["reachable"], state["volume"], state["muted"]),
                                     ("state", True, 30, True))
                    p.stdin.write(b'{"id": 1, "cmd": "control", "action": "select"}\n')
                    p.stdin.flush()
                    self.assertEqual(lines.result(1), {"type": "result", "id": 1, "ok": True, "message": ""})
                    self.assertIn("Input.Select", fake.methods())

                    start = time.monotonic()
                    p.stdin.close()
                    p.wait(1)
                    self.assertLess(time.monotonic() - start, 1.0)
                    self.assertEqual(p.returncode, 0)
                    self.assertEqual(p.stderr.read(), b"")
                    for line in lines.raw:
                        self.assertNotIn(fake.password.encode(), line)
                finally:
                    if p.poll() is None:
                        p.kill()
                        p.wait()
                    p.stdin.close()
                    p.stderr.close()
                    lines.close()
        finally:
            fake.stop()


if __name__ == "__main__":
    unittest.main()
