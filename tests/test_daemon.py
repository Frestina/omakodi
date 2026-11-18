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
from omakodi.control import FULLSCREEN_CHECK  # noqa: E402
from omakodi.rpc import Kodi  # noqa: E402
from omakodi.share import Sender  # noqa: E402
from omakodi.state import YoutubeHealth  # noqa: E402

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
        self.state_dir = tempfile.TemporaryDirectory()
        self.now = [1000.0]
        cfg = self.fake.config()
        self.d = daemon.Daemon(
            lambda: cfg, clock=lambda: self.now[0],
            sender_for=lambda c: Sender(Kodi(c), c.youtube_mode, YoutubeHealth(self.state_dir.name)),
            art_cache=ArtCache(os.path.join(self.state_dir.name, "art")))
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
                                 "volume": 80, "muted": False, "queue": None, "input": None})
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
        asked = [p for m, p in self.fake.calls if m == "Playlist.GetItems"][0]
        self.assertNotIn("file", asked["properties"])
        reads = self.fake.methods().count("Playlist.GetItems")
        self.send({"id": 1, "cmd": "refresh"})
        self.lines.result(1)
        self.assertEqual(self.fake.methods().count("Playlist.GetItems"), reads)  # unchanged: not read again
        items.append({"label": "Fourth", "title": "Fourth"})  # queued
        state = self.next_state(lambda m: m.get("queue") and m["queue"]["total"] == 4)
        self.assertEqual(state["queue"]["items"][-1]["title"], "Fourth")
        self.fake.results["Player.GetProperties"] = {"speed": 1, "playlistid": -1, "position": -1}
        self.assertIsNone(self.next_state(lambda m: m.get("queue") is None)["queue"])

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
