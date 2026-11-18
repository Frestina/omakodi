"""youtubeMode from the bar widget's settings in shell.json (ticket 040)."""

import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "lib"))

from omakodi import shellconfig  # noqa: E402
from omakodi.config import Config  # noqa: E402
from omakodi.share import make_sender  # noqa: E402

ID = "io.github.frestina.omakodi"


def layout(entry):
    return {"version": 1, "bar": {"layout": {"left": [{"id": "omarchy.menu"}],
                                             "right": [{"id": "omarchy.clock"}, entry]}}}


class ShellConfigTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "omarchy", "shell.json")
        os.makedirs(os.path.dirname(self.path))
        self.cfg = Config("(test)", "kodi.example.lan", youtube_mode="youtube-first")

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, data):
        raw = data if isinstance(data, bytes) else (data if isinstance(data, str) else json.dumps(data)).encode()
        with open(self.path, "wb") as f:
            f.write(raw)

    def mode(self):
        return shellconfig.youtube_mode(self.cfg, self.path)

    def test_the_widget_setting_wins(self):
        self.write(layout({"id": ID, "maxTitleLength": 0, "youtubeMode": "sendtokodi-only"}))
        self.assertEqual(self.mode(), ("sendtokodi-only", "bar widget settings"))

    def test_found_wherever_the_layout_moves(self):
        self.write({"bars": [{"monitor": "eDP-1", "sections": {"centre": [[{"id": ID, "youtubeMode": "smart"}]]}}]})
        self.assertEqual(self.mode(), ("smart", "bar widget settings"))

    def test_otherwise_the_config_file(self):
        for data in (layout({"id": ID, "maxTitleLength": 0}),  # never chosen
                     layout({"id": ID, "youtubeMode": "fast"}),  # not a mode
                     layout({"id": ID, "youtubeMode": ["smart"]}),
                     layout({"id": "someone.else", "youtubeMode": "smart"}),
                     "{not json", b"\xff\xfe", "[]", "null",
                     " " * (shellconfig.MAX_BYTES + 1)):
            with self.subTest(data=str(data)[:60]):
                self.write(data)
                self.assertEqual(self.mode(), ("youtube-first", "config file"))
        os.remove(self.path)
        self.assertEqual(self.mode(), ("youtube-first", "config file"))

    def test_deep_nesting_is_not_a_crash(self):
        deep = {"id": ID, "youtubeMode": "smart"}
        for _ in range(5000):
            deep = [deep]
        self.write(json.dumps(deep))
        self.assertEqual(self.mode(), ("youtube-first", "config file"))

    def test_plays_and_queues_use_it(self):
        self.write(layout({"id": ID, "youtubeMode": "youtube-only"}))
        old = os.environ.get("XDG_CONFIG_HOME")
        os.environ["XDG_CONFIG_HOME"] = self.tmp.name
        try:
            self.assertEqual(shellconfig.shell_json_path(), self.path)
            self.assertEqual(make_sender(self.cfg).youtube_mode, "youtube-only")
            self.write(layout({"id": ID, "youtubeMode": "smart"}))  # changed in the settings: the next play follows
            self.assertEqual(make_sender(self.cfg).youtube_mode, "smart")
        finally:
            if old is None:
                os.environ.pop("XDG_CONFIG_HOME")
            else:
                os.environ["XDG_CONFIG_HOME"] = old

    def test_omakodi_config_says_where_it_came_from(self):
        cfg = os.path.join(self.tmp.name, "config.json")
        with open(cfg, "w") as f:
            json.dump({"host": "kodi.example.lan", "youtubeMode": "youtube-first"}, f)
        self.write(layout({"id": ID, "youtubeMode": "sendtokodi-only"}))
        env = dict(os.environ, OMAKODI_CONFIG=cfg, XDG_CONFIG_HOME=self.tmp.name)
        r = subprocess.run([os.path.join(ROOT, "bin", "omakodi"), "config"], capture_output=True, text=True,
                           env=env, timeout=10)
        self.assertEqual(r.returncode, 0, r.stderr)
        shown = json.loads(r.stdout)
        self.assertEqual((shown["youtubeMode"], shown["youtubeModeFrom"]), ("sendtokodi-only", "bar widget settings"))


class ManifestTest(unittest.TestCase):
    def test_the_setting_is_offered_but_not_a_default(self):
        with open(os.path.join(ROOT, "manifest.json")) as f:
            widget = json.load(f)["barWidget"]
        entry = next(e for e in widget["schema"] if e["key"] == "youtubeMode")
        self.assertEqual((entry["type"], entry["options"], entry["defaultValue"]),
                         ("enum", ["smart", "youtube-first", "youtube-only", "sendtokodi-only"], "smart"))
        self.assertNotIn("youtubeMode", widget["defaults"])  # never overrides the config file unasked


if __name__ == "__main__":
    unittest.main()
