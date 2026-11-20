"""`omakodi --version` says the manifest's version (ticket 062)."""

import json
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class VersionTest(unittest.TestCase):
    def test_cli_version_is_the_manifests(self):
        with open(os.path.join(ROOT, "manifest.json")) as f:
            version = json.load(f)["version"]
        out = subprocess.run([sys.executable, "-I", os.path.join(ROOT, "bin", "omakodi"), "--version"],
                             capture_output=True, text=True, check=True).stdout
        self.assertEqual(out.strip(), f"omakodi {version}")


if __name__ == "__main__":
    unittest.main()
