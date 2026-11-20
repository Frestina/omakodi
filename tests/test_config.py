import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "lib"))

from omakodi import config  # noqa: E402
from omakodi.errors import CONFIG, OmakodiError  # noqa: E402

SECRET = "s3cret-example-pw"


class ConfigTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "config.json")

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, data, mode=0o600):
        with open(self.path, "w") as f:
            f.write(data if isinstance(data, str) else json.dumps(data))
        os.chmod(self.path, mode)

    def assertConfigError(self, kind):
        with self.assertRaises(OmakodiError) as cm:
            config.load(self.path)
        self.assertEqual(cm.exception.kind, kind)
        self.assertEqual(cm.exception.code, CONFIG)
        self.assertNotIn(SECRET, str(cm.exception))
        self.assertNotIn(SECRET, repr(cm.exception))
        return cm.exception

    def test_missing(self):
        self.assertConfigError("not configured")

    def test_defaults(self):
        self.write({"host": "kodi.example.lan"}, 0o644)
        c = config.load(self.path)
        self.assertEqual((c.host, c.http_port, c.tcp_port, c.youtube_mode),
                         ("kodi.example.lan", 8080, 9090, "smart"))
        self.assertFalse(c.has_login)
        self.assertEqual((c.mac, c.wake_on_lan, c.event_port), ("", True, 9777))

    def test_wake_on_lan(self):
        self.write({"host": "kodi.example.lan", "mac": "02-1A-2B-3C-4D-5E", "wakeOnLan": False})
        c = config.load(self.path)
        self.assertEqual((c.mac, c.wake_on_lan), ("02:1a:2b:3c:4d:5e", False))
        self.assertEqual((c.public()["mac"], c.public()["wakeOnLan"]), ("02:1a:2b:3c:4d:5e", False))

    def test_bad_json(self):
        self.write("{nope")
        self.assertConfigError("bad config")

    def test_not_object(self):
        self.write("[1]")
        self.assertConfigError("bad config")

    def test_bad_values(self):
        for data in (
            {},
            {"host": ""},
            {"host": "kodi.example.lan/x"},
            {"host": "user@kodi.example.lan"},
            {"host": "kodi example"},
            {"host": "kodi.example.lan", "httpPort": "8080"},
            {"host": "kodi.example.lan", "httpPort": True},
            {"host": "kodi.example.lan", "tcpPort": 70000},
            {"host": "kodi.example.lan", "username": 5},
            {"host": "kodi.example.lan", "password": ["x"]},
            {"host": "kodi.example.lan", "youtubeMode": "fast"},
            {"host": "kodi.example.lan", "mac": 5},  # text that isn't a MAC address loads (ticket 057)
            {"host": "kodi.example.lan", "mac": None},
            {"host": "kodi.example.lan", "wakeOnLan": "no"},
            {"host": "kodi.example.lan", "wakeOnLan": 0},
            {"host": "kodi.example.lan", "eventPort": 0},
            {"host": "kodi.example.lan", "eventPort": "9777"},
        ):
            with self.subTest(data=data):
                self.write(data)
                self.assertConfigError("bad config")

    def test_password_needs_private_file(self):
        for mode in (0o640, 0o604, 0o660, 0o644):
            with self.subTest(mode=oct(mode)):
                self.write({"host": "kodi.example.lan", "password": SECRET}, mode)
                e = self.assertConfigError("config readable by others")
                self.assertIn("chmod 600", e.detail)

    def test_password_private_ok(self):
        self.write({"host": "kodi.example.lan", "username": "kodi", "password": SECRET}, 0o600)
        c = config.load(self.path)
        self.assertEqual(c.password, SECRET)
        self.assertNotIn(SECRET, repr(c))
        self.assertNotIn(SECRET, json.dumps(c.public()))

    def test_template(self):
        path = config.write_template(os.path.join(self.tmp.name, "sub", "config.json"))
        self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)
        with self.assertRaises(OmakodiError):
            config.write_template(path)


class CommandTest(unittest.TestCase):
    def run_omakodi(self, exe, *args, env_config=None):
        env = dict(os.environ, XDG_CONFIG_HOME=os.path.dirname(env_config or exe))  # not the real shell.json
        if env_config:
            env["OMAKODI_CONFIG"] = env_config
        return subprocess.run([exe, *args], capture_output=True, text=True, env=env, timeout=10)

    def test_through_symlink(self):
        with tempfile.TemporaryDirectory() as d:
            link = os.path.join(d, "omakodi")
            os.symlink(os.path.join(ROOT, "bin", "omakodi"), link)
            cfg = os.path.join(d, "config.json")
            with open(cfg, "w") as f:
                json.dump({"host": "kodi.example.lan", "password": SECRET}, f)
            os.chmod(cfg, 0o600)
            r = self.run_omakodi(link, "config", env_config=cfg)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("kodi.example.lan", r.stdout)
            self.assertNotIn(SECRET, r.stdout + r.stderr)

    def test_not_configured_exit_code(self):
        with tempfile.TemporaryDirectory() as d:
            r = self.run_omakodi(os.path.join(ROOT, "bin", "omakodi"), "config",
                                 env_config=os.path.join(d, "none.json"))
            self.assertEqual(r.returncode, 3)
            self.assertIn("not configured", r.stderr)

    def test_usage_exit_code(self):
        r = self.run_omakodi(os.path.join(ROOT, "bin", "omakodi"), "frobnicate")
        self.assertEqual(r.returncode, 2)


if __name__ == "__main__":
    unittest.main()
