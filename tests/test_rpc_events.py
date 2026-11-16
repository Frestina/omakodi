import json
import os
import sys
import threading
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fakekodi import FakeKodi, unused_port  # noqa: E402
from omakodi import events  # noqa: E402
from omakodi.errors import AUTH, UNREACHABLE, OmakodiError  # noqa: E402
from omakodi.rpc import Kodi, KodiCallError  # noqa: E402


class RpcTest(unittest.TestCase):
    def setUp(self):
        self.fake = FakeKodi().start()
        self.kodi = Kodi(self.fake.config())

    def tearDown(self):
        self.fake.stop()

    def assertNoSecret(self, err):
        for text in (str(err), repr(err), err.detail):
            self.assertNotIn(self.fake.password, text)

    def test_call_returns_result_and_sends_params(self):
        self.fake.results["Player.GetActivePlayers"] = [{"playerid": 1, "type": "video"}]
        self.assertEqual(self.kodi.call("Player.GetActivePlayers"), [{"playerid": 1, "type": "video"}])
        self.kodi.call("Input.ExecuteAction", {"action": "stepback"})
        self.assertEqual(self.fake.calls[-1], ("Input.ExecuteAction", {"action": "stepback"}))

    def test_wrong_password(self):
        kodi = Kodi(self.fake.config(password="wrong-one"))
        with self.assertRaises(OmakodiError) as cm:
            kodi.call("JSONRPC.Ping")
        self.assertEqual((cm.exception.kind, cm.exception.code), ("wrong username or password", AUTH))
        self.assertNoSecret(cm.exception)

    def test_no_login_sends_no_header(self):
        self.fake.username = self.fake.password = ""
        Kodi(self.fake.config(username="", password="")).call("JSONRPC.Ping")
        self.assertIsNone(self.fake.auth_headers[-1])

    def test_other_http_status(self):
        self.fake.http_status = 500
        with self.assertRaises(OmakodiError) as cm:
            self.kodi.call("JSONRPC.Ping")
        self.assertEqual(cm.exception.kind, "http 500")

    def test_not_json(self):
        self.fake.raw_reply = b"<html>hello</html>"
        with self.assertRaises(OmakodiError) as cm:
            self.kodi.call("JSONRPC.Ping")
        self.assertEqual(cm.exception.kind, "bad response")

    def test_jsonrpc_error(self):
        self.fake.errors["Player.PlayPause"] = "Failed to execute method."
        with self.assertRaises(KodiCallError) as cm:
            self.kodi.call("Player.PlayPause", {"playerid": 1})
        self.assertEqual(cm.exception.kind, "kodi error")
        self.assertIn("Failed to execute method.", str(cm.exception))

    def test_unreachable(self):
        cfg = self.fake.config(http_port=unused_port())
        with self.assertRaises(OmakodiError) as cm:
            Kodi(cfg).call("JSONRPC.Ping")
        self.assertEqual((cm.exception.kind, cm.exception.code), ("not reachable", UNREACHABLE))
        self.assertNoSecret(cm.exception)

    def test_slow_answer_is_unreachable(self):
        self.fake.delay = 0.5
        with self.assertRaises(OmakodiError) as cm:
            self.kodi.call("JSONRPC.Ping", read_timeout=0.1)
        self.assertEqual(cm.exception.code, UNREACHABLE)


class SplitterTest(unittest.TestCase):
    def test_two_objects_in_one_read(self):
        s = events.JsonSplitter()
        self.assertEqual(s.feed('{"a":1}{"b":2}'), ['{"a":1}', '{"b":2}'])

    def test_object_across_reads(self):
        s = events.JsonSplitter()
        self.assertEqual(s.feed('{"a":{"b"'), [])
        self.assertEqual(s.feed(':1}}  {"c"'), ['{"a":{"b":1}}'])
        self.assertEqual(s.feed(":2}"), ['{"c":2}'])

    def test_braces_and_quotes_in_strings(self):
        s = events.JsonSplitter()
        raw = '{"t":"a } { \\" }"}'
        self.assertEqual(s.feed(raw), [raw])
        self.assertEqual(json.loads(raw)["t"], 'a } { " }')


class EventTest(unittest.TestCase):
    def setUp(self):
        self.fake = FakeKodi().start()
        self.cfg = self.fake.config()

    def tearDown(self):
        self.fake.stop()

    def test_notifications_and_replies(self):
        with events.EventConnection(self.cfg.host, self.cfg.tcp_port) as conn:
            self.assertTrue(self.fake.wait_for_event_client())
            self.fake.push_raw(b'{"id":"ping","jsonrpc":"2.0","result":"pong"}')
            self.fake.push("Player.OnPlay", {"item": {"title": "Example"}})
            got = []
            end = time.monotonic() + 2
            while not got and time.monotonic() < end:
                got = conn.poll(0.1)
            self.assertEqual(got, [("Player.OnPlay", {"item": {"title": "Example"}})])

    def test_ping_when_idle(self):
        now = [0.0]
        with events.EventConnection(self.cfg.host, self.cfg.tcp_port, clock=lambda: now[0]) as conn:
            now[0] = 31.0
            for _ in range(20):
                conn.poll(0.05)
                if self.fake.pings:
                    break
            self.assertEqual(self.fake.pings, 1)

    def test_lost_when_ping_unanswered(self):
        self.fake.answer_pings = False
        now = [0.0]
        with events.EventConnection(self.cfg.host, self.cfg.tcp_port, clock=lambda: now[0]) as conn:
            now[0] = 31.0
            conn.poll(0.01)  # sends the ping
            now[0] = 42.0
            with self.assertRaises(events.ConnectionLost):
                conn.poll(0.01)

    def test_follow_reconnects(self):
        stop = threading.Event()
        states = []
        received = []

        def run():
            for event in events.follow(self.cfg, stop.is_set, states.append, poll_timeout=0.05,
                                       backoff_start=0.05):
                received.append(event)

        t = threading.Thread(target=run, daemon=True)
        t.start()
        self.assertTrue(self.fake.wait_for_event_client(1))
        self.fake.drop_event_clients()
        self.assertTrue(self.fake.wait_for_event_client(1))
        self.fake.push("Player.OnStop", {"end": True})
        end = time.monotonic() + 2
        while not received and time.monotonic() < end:
            time.sleep(0.02)
        stop.set()
        t.join(2)
        self.assertEqual(received, [("Player.OnStop", {"end": True})])
        self.assertEqual(states[:3], [True, False, True])


if __name__ == "__main__":
    unittest.main()
