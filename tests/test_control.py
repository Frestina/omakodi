import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fakekodi import ROOT, FakeKodi  # noqa: E402
from omakodi.control import FULLSCREEN_CHECK, Controller  # noqa: E402
from omakodi.errors import OmakodiError  # noqa: E402
from omakodi.nowplaying import now_playing  # noqa: E402
from omakodi.rpc import Kodi  # noqa: E402

VIDEO_PLAYER = [{"playerid": 1, "type": "video"}]


def booleans(fullscreen=False, osd=False, dialog=False):
    return {FULLSCREEN_CHECK[0]: fullscreen, FULLSCREEN_CHECK[1]: osd, FULLSCREEN_CHECK[2]: dialog}


class ControlTest(unittest.TestCase):
    def setUp(self):
        self.fake = FakeKodi().start()
        self.fake.results["XBMC.GetInfoBooleans"] = booleans()
        self.ctl = Controller(Kodi(self.fake.config()))

    def tearDown(self):
        self.fake.stop()

    def last_call(self):
        return self.fake.calls[-1]

    def test_menu_actions(self):
        table = {
            "up": ("Input.Up", None), "down": ("Input.Down", None),
            "left": ("Input.Left", None), "right": ("Input.Right", None),
            "select": ("Input.Select", None), "back": ("Input.Back", None),
            "info": ("Input.Info", None), "context": ("Input.ContextMenu", None),
            "osd": ("Input.ShowOSD", None), "home": ("GUI.ActivateWindow", {"window": "home"}),
            "volup": ("Application.SetVolume", {"volume": "increment"}),
            "voldown": ("Application.SetVolume", {"volume": "decrement"}),
            "mute": ("Application.SetMute", {"mute": "toggle"}),
            "fullscreen": ("GUI.SetFullscreen", {"fullscreen": "toggle"}),
        }
        for action, expected in table.items():
            with self.subTest(action=action):
                self.ctl.run(action)
                self.assertEqual(self.last_call(), expected)

    def test_arrows_in_fullscreen_video(self):
        self.fake.results["XBMC.GetInfoBooleans"] = booleans(fullscreen=True)
        table = {"up": "chapterorbigstepforward", "down": "chapterorbigstepback",
                 "left": "stepback", "right": "stepforward"}
        for action, video_action in table.items():
            with self.subTest(action=action):
                self.ctl.run(action)
                self.assertEqual(self.last_call(), ("Input.ExecuteAction", {"action": video_action}))
        self.ctl.run("select")
        self.assertEqual(self.last_call(), ("Input.ShowOSD", None))

    def test_held_arrow_skips_once_in_fullscreen_video(self):
        self.fake.results["XBMC.GetInfoBooleans"] = booleans(fullscreen=True)
        for action in ("up", "down", "left", "right"):
            with self.subTest(action=action):
                self.fake.clear_calls()
                self.assertIsNone(self.ctl.run(action, repeat=True))
                self.assertEqual(self.fake.methods(), ["XBMC.GetInfoBooleans"])
                self.ctl.run(action)  # a press still skips
                self.assertEqual(self.last_call()[0], "Input.ExecuteAction")

    def test_held_key_repeats_elsewhere(self):
        self.ctl.run("down", repeat=True)  # a menu: scrolls
        self.assertEqual(self.last_call(), ("Input.Down", None))
        self.fake.results["XBMC.GetInfoBooleans"] = booleans(fullscreen=True, osd=True)
        self.ctl.run("right", repeat=True)  # the OSD: moves along it
        self.assertEqual(self.last_call(), ("Input.Right", None))
        self.fake.results["XBMC.GetInfoBooleans"] = booleans(fullscreen=True)
        self.ctl.run("select", repeat=True)  # repeat means nothing for select
        self.assertEqual(self.last_call(), ("Input.ShowOSD", None))
        self.ctl.run("volup", repeat=True)
        self.assertEqual(self.last_call(), ("Application.SetVolume", {"volume": "increment"}))

    def test_osd_or_dialog_means_normal_navigation(self):
        for flags in (dict(osd=True), dict(dialog=True)):
            with self.subTest(**flags):
                self.fake.results["XBMC.GetInfoBooleans"] = booleans(fullscreen=True, **flags)
                self.ctl.run("left")
                self.assertEqual(self.last_call(), ("Input.Left", None))

    def test_fullscreen_check_is_cached_for_arrows_only(self):
        now = [0.0]
        ctl = Controller(Kodi(self.fake.config()), fullscreen_ttl=1.0, clock=lambda: now[0])
        ctl.run("up")
        ctl.run("up")
        self.assertEqual(self.fake.methods().count("XBMC.GetInfoBooleans"), 1)
        ctl.run("select")  # never from the cache
        self.assertEqual(self.fake.methods().count("XBMC.GetInfoBooleans"), 2)

    def test_player_actions(self):
        self.fake.results["Player.GetActivePlayers"] = [{"playerid": 0, "type": "audio"}] + VIDEO_PLAYER
        self.ctl.run("playpause")
        self.assertEqual(self.last_call(), ("Player.PlayPause", {"playerid": 1}))
        self.ctl.run("stop")
        self.assertEqual(self.last_call(), ("Player.Stop", {"playerid": 1}))
        self.ctl.run("next")
        self.assertEqual(self.last_call(), ("Player.GoTo", {"playerid": 1, "to": "next"}))
        self.ctl.run("previous")
        self.assertEqual(self.last_call(), ("Player.GoTo", {"playerid": 1, "to": "previous"}))

    def test_nothing_playing(self):
        self.fake.results["Player.GetActivePlayers"] = []
        for action in ("playpause", "next", "previous"):
            with self.subTest(action=action), self.assertRaises(OmakodiError) as cm:
                self.ctl.run(action)
            self.assertEqual((cm.exception.kind, cm.exception.code), ("nothing playing", 1))
        self.assertNotIn("Player.GoTo", self.fake.methods())


class NowPlayingTest(unittest.TestCase):
    def setUp(self):
        self.fake = FakeKodi().start()
        self.fake.results["Application.GetProperties"] = {"volume": 80, "muted": False}

    def tearDown(self):
        self.fake.stop()

    def test_idle(self):
        self.fake.results["Player.GetActivePlayers"] = []
        self.assertEqual(now_playing(Kodi(self.fake.config())),
                         {"playing": None, "volume": 80, "muted": False})

    def test_episode_never_includes_file(self):
        self.fake.results["Player.GetActivePlayers"] = VIDEO_PLAYER
        self.fake.results["Player.GetItem"] = {"item": {
            "type": "episode", "label": "Pilot", "title": "Pilot\nPart one", "showtitle": "Example Show",
            "season": 1, "episode": 7, "file": "http://media.example.lan/Videos/x/stream?ApiKey=abc123"}}
        self.fake.results["Player.GetProperties"] = {
            "speed": 0, "time": {"hours": 0, "minutes": 6, "seconds": 33},
            "totaltime": {"hours": 0, "minutes": 50, "seconds": 9}}
        state = now_playing(Kodi(self.fake.config()))
        self.assertEqual(state["playing"], {
            "title": "Pilot Part one", "subtitle": "Example Show · S01E07", "kind": "episode",
            "paused": True, "positionSec": 393, "durationSec": 3009})
        self.assertNotIn("ApiKey", json.dumps(state))
        item_params = [p for m, p in self.fake.calls if m == "Player.GetItem"][0]
        self.assertNotIn("file", item_params["properties"])

    def test_song_and_long_title(self):
        self.fake.results["Player.GetActivePlayers"] = [{"playerid": 0, "type": "audio"}]
        self.fake.results["Player.GetItem"] = {"item": {
            "type": "song", "title": "x" * 1000, "artist": ["Example Band"], "album": "First Album",
            "season": -1, "episode": -1}}
        self.fake.results["Player.GetProperties"] = {"speed": 1}
        playing = now_playing(Kodi(self.fake.config()))["playing"]
        self.assertEqual(len(playing["title"]), 300)
        self.assertEqual(playing["subtitle"], "Example Band · First Album")
        self.assertFalse(playing["paused"])


class CommandTest(unittest.TestCase):
    def test_status_and_control_from_the_command(self):
        fake = FakeKodi().start()
        try:
            fake.results["Player.GetActivePlayers"] = []
            fake.results["Application.GetProperties"] = {"volume": 50, "muted": True}
            with tempfile.TemporaryDirectory() as d:
                cfg = os.path.join(d, "config.json")
                with open(cfg, "w") as f:
                    json.dump(fake.config_json(), f)
                os.chmod(cfg, 0o600)
                env = dict(os.environ, OMAKODI_CONFIG=cfg)
                exe = os.path.join(ROOT, "bin", "omakodi")
                r = subprocess.run([exe, "status"], capture_output=True, text=True, env=env, timeout=10)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertEqual(json.loads(r.stdout), {"playing": None, "volume": 50, "muted": True})
                r = subprocess.run([exe, "control", "stop"], capture_output=True, text=True, env=env, timeout=10)
                self.assertEqual(r.returncode, 1)
                self.assertIn("nothing playing", r.stderr)
                r = subprocess.run([exe, "control", "dance"], capture_output=True, text=True, env=env, timeout=10)
                self.assertEqual(r.returncode, 2)
        finally:
            fake.stop()


if __name__ == "__main__":
    unittest.main()
