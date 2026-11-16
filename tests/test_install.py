"""install.sh with a throwaway HOME (ticket 011)."""

import os
import subprocess
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "install.sh")
SRC = os.path.join(ROOT, "bin", "omakodi")


def tree(top):
    """Every path under top, with link targets, so before/after can be compared."""
    out = set()
    for dirpath, dirnames, filenames in os.walk(top):
        for name in dirnames + filenames:
            p = os.path.join(dirpath, name)
            out.add((os.path.relpath(p, top), os.readlink(p) if os.path.islink(p) else None))
    return out


class InstallTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = self.tmp.name
        self.bin = os.path.join(self.home, ".local", "bin")
        self.dest = os.path.join(self.bin, "omakodi")

    def run_script(self, *args):
        env = {"HOME": self.home, "PATH": self.bin + ":/usr/bin:/bin"}
        return subprocess.run(["bash", SCRIPT, *args], env=env, capture_output=True, text=True, timeout=30)

    def test_install_then_uninstall_leaves_nothing(self):
        os.makedirs(self.bin)
        before = tree(self.home)

        r = self.run_script()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(os.path.realpath(self.dest), os.path.realpath(SRC))
        self.assertIn("omakodi init", r.stdout)
        self.assertIn('"host": "kodi.example.lan"', r.stdout)
        self.assertIn("toggleRemote", r.stdout)
        self.assertIn("omakodi play --clipboard --notify", r.stdout)
        self.assertIn("omakodi queue --clipboard --notify", r.stdout)
        self.assertNotIn("not on", r.stdout)

        again = self.run_script()
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertIn("already links", again.stdout)

        r = self.run_script("--uninstall")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("~/.config/omakodi/", r.stdout)
        self.assertEqual(tree(self.home), before)

    def test_linked_command_runs(self):
        os.makedirs(self.bin)
        self.assertEqual(self.run_script().returncode, 0)
        env = {"HOME": self.home, "PATH": self.bin + ":/usr/bin:/bin"}
        r = subprocess.run(["omakodi", "init"], env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        path = os.path.join(self.home, ".config", "omakodi", "config.json")
        self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)
        r = subprocess.run(["omakodi", "config"], env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('"password": "not set"', r.stdout)

    def test_never_touches_a_file_that_isnt_its_link(self):
        os.makedirs(self.bin)
        with open(self.dest, "w") as f:
            f.write("someone else's omakodi\n")
        for args in ((), ("--uninstall",)):
            r = self.run_script(*args)
            self.assertEqual(r.returncode, 1)
            self.assertIn("leaving it alone", r.stderr)
            with open(self.dest) as f:
                self.assertEqual(f.read(), "someone else's omakodi\n")

    def test_leaves_a_link_to_something_else(self):
        os.makedirs(self.bin)
        other = os.path.join(self.home, "other")
        open(other, "w").close()
        os.symlink(other, self.dest)
        for args in ((), ("--uninstall",)):
            self.assertEqual(self.run_script(*args).returncode, 1)
            self.assertEqual(os.readlink(self.dest), other)

    def test_replaces_a_broken_link(self):
        os.makedirs(self.bin)
        os.symlink(os.path.join(self.home, "gone"), self.dest)
        r = self.run_script()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(os.path.realpath(self.dest), os.path.realpath(SRC))

    def test_does_not_create_local_bin(self):
        r = self.run_script()
        self.assertEqual(r.returncode, 1)
        self.assertIn("mkdir -p ~/.local/bin", r.stderr)
        self.assertEqual(os.listdir(self.home), [])

    def test_uninstall_with_nothing_installed(self):
        r = self.run_script("--uninstall")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(os.listdir(self.home), [])

    def test_bad_argument(self):
        self.assertEqual(self.run_script("--frobnicate").returncode, 2)


if __name__ == "__main__":
    unittest.main()
