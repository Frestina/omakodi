"""Small fixes from the backlog (ticket 064).

- The bar widget's tooltip says Kodi's error as the remote's top bar does
  (BarTip.js under node, with the daemon's own wording from messages.py).
- The keyboard key with a keyboard it found without the event port asks
  Kodi again (KodiInput.js, and Panel.qml's key functions cut out and run
  under node); the daemon's side is in test_daemon.py.
- install.sh --uninstall and the README list the same leftovers.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "lib"))

from omakodi import messages  # noqa: E402
from omakodi.errors import AUTH, FAILED, OmakodiError  # noqa: E402

BOX = "Living room"
WORDS = {"idle": "Kodi: nothing playing", "paused": "Paused", "click": "Click for the remote"}
BOXES = {"current": "b2", "list": [{"id": "b1", "name": "Bedroom", "host": "bedroom.example.lan"},
                                   {"id": "b2", "name": BOX, "host": "kodi.example.lan"}]}

EVAL_RUNNER = r"""
const fs = require("fs"), vm = require("vm")
const src = fs.readFileSync(process.argv[1], "utf8").replace(/^\.pragma library\s*$/m, "")
const ctx = {}
vm.runInNewContext(src, ctx)
process.stdout.write(JSON.stringify(vm.runInContext(process.argv[2], ctx)))
"""


def state_error(kind, detail, code):
    """The state's `error` as the daemon builds it."""
    return messages.with_fix(OmakodiError(kind, detail, code=code, box=BOX), BOX)


@unittest.skipUnless(shutil.which("node"), "node is needed to run the JS files")
class TooltipTest(unittest.TestCase):
    def tip(self, **s):
        expr = "lines(%s, %s, %s)" % (json.dumps(s), json.dumps("6:33 / 50:09"), json.dumps(WORDS))
        r = subprocess.run(["node", "-e", EVAL_RUNNER, os.path.join(ROOT, "BarTip.js"), expr],
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_kodis_errors_in_the_phone_remotes_words(self):
        cases = [
            (("wrong username or password", "Kodi refused the login; check username and password", AUTH),
             "Wrong username or password for Living room", "Kodi refused the login; check username and password"),
            (("http 500", "Kodi's web server failed", FAILED), "Living room answered HTTP 500",
             "Kodi's web server failed"),
            (("bad response", "not JSON-RPC", FAILED), "Unexpected reply from Living room", "not JSON-RPC"),
        ]
        for (kind, detail, code), message, fix in cases:
            with self.subTest(kind=kind):
                lines = self.tip(error=state_error(kind, detail, code))
                self.assertEqual(lines, [message, fix, "Click for the remote"])
                self.assertFalse(any(line.startswith("Kodi: ") for line in lines))

    def test_an_error_with_no_message_of_its_own_is_shown_as_it_is(self):
        error = state_error("kodi error: Invalid params.", "", FAILED)
        self.assertEqual(error, "kodi error: Invalid params.")
        self.assertEqual(self.tip(error=error), [error, "Click for the remote"])

    def test_the_box_with_several(self):
        # Named by its id (054); not again when the message names it.
        error = state_error("wrong username or password", "check it", AUTH)
        self.assertEqual(self.tip(error=error, boxes=BOXES),
                         ["Wrong username or password for Living room", "check it", "Click for the remote"])
        self.assertEqual(self.tip(error="kodi error: Invalid params.", boxes=BOXES),
                         [BOX, "kodi error: Invalid params.", "Click for the remote"])
        self.assertEqual(self.tip(playing=None, boxes=BOXES), [BOX, WORDS["idle"], "Click for the remote"])
        nameless = {"current": "b1", "list": [{"id": "b1", "name": "", "host": "kodi.example.lan"},
                                              {"id": "b2", "name": "Bedroom", "host": "bedroom.example.lan"}]}
        self.assertEqual(self.tip(playing=None, boxes=nameless)[0], "kodi.example.lan")
        one = {"current": "b2", "list": BOXES["list"][1:]}
        self.assertEqual(self.tip(playing=None, boxes=one), [WORDS["idle"], "Click for the remote"])

    def test_what_plays(self):
        playing = {"title": "Example Movie", "subtitle": "Part one"}
        self.assertEqual(self.tip(playing=playing), ["Example Movie", "Part one", "6:33 / 50:09",
                                                     "Click for the remote"])
        self.assertEqual(self.tip(playing=playing, paused=True)[2], "6:33 / 50:09 · Paused")

    def test_the_widget_uses_it(self):
        with open(os.path.join(ROOT, "BarWidget.qml"), encoding="utf-8") as f:
            widget = f.read()
        self.assertIn('import "BarTip.js" as BarTip', widget)
        self.assertIn("BarTip.lines(", widget)
        with open(os.path.join(ROOT, "i18n", "en.json"), encoding="utf-8") as f:
            self.assertNotIn("bar.error", json.load(f))  # "Kodi: %1" is gone


# Panel.qml's keyboard key and its answer, cut out, with stubs.
KEY_RUNNER = r"""
const fs = require("fs"), vm = require("vm")
const root = process.argv[1], fns = JSON.parse(process.argv[2]), input = JSON.parse(process.argv[3])
const steps = JSON.parse(process.argv[4])
const lib = n => { const c = {}; vm.runInNewContext(fs.readFileSync(root + "/" + n, "utf8").replace(/^\.pragma library\s*$/m, ""), c); return c }
const log = { sent: 0, shown: 0, said: [] }
const ctx = {
  KodiInput: lib("KodiInput.js"), connected: true, kodiInput: input, root: { opened: true },
  refusedOffline: () => false, hush: () => {}, say: (t, e) => log.said.push(t),
  service: { openKeyboard: () => { log.sent++; return "" } },
  kodiTextDialog: { show: () => { log.shown++ } },
}
vm.createContext(ctx)
for (const f of fns) vm.runInContext(f, ctx)
for (const s of steps) vm.runInContext(s, ctx)
process.stdout.write(JSON.stringify(log))
"""


def panel_function(name):
    with open(os.path.join(ROOT, "Panel.qml"), encoding="utf-8") as f:
        source = f.read()
    start = source.index("  function %s(" % name)
    return source[start:source.index("\n  }\n", start) + 4]


@unittest.skipUnless(shutil.which("node"), "node is needed to run the JS files")
class KeyboardKeyTest(unittest.TestCase):
    FOUND = {"type": "keyboard", "title": "", "value": "", "hidden": False, "recheck": True}
    HEARD = {"type": "keyboard", "title": "Search", "value": "", "hidden": False, "recheck": False}

    def run_steps(self, input, steps):
        fns = [panel_function("openKeyboard"), panel_function("keyboardAnswered")]
        r = subprocess.run(["node", "-e", KEY_RUNNER, ROOT, json.dumps(fns), json.dumps(input), json.dumps(steps)],
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_a_keyboard_kodi_announced_opens_at_once(self):
        self.assertEqual(self.run_steps(self.HEARD, ["openKeyboard()"]), {"sent": 0, "shown": 1, "said": []})

    def test_one_found_without_the_event_port_is_asked_about_again(self):
        # Still open: the daemon answers "" and the dialog opens then.
        got = self.run_steps(self.FOUND, ["openKeyboard()",
                                          'keyboardAnswered({cmd: "keyboard", ok: true, text: ""})'])
        self.assertEqual(got, {"sent": 1, "shown": 1, "said": []})
        # Gone: the daemon says so (shown as any result) and nothing opens;
        # its next state has no input, so the key isn't marked.
        got = self.run_steps(self.FOUND, [
            "openKeyboard()",
            'keyboardAnswered({cmd: "keyboard", ok: true, text: "Kodi isn\'t asking for text right now"})',
            "kodiInput = null"])
        self.assertEqual(got, {"sent": 1, "shown": 0, "said": []})

    def test_nothing_opens_while_the_remote_is_closed_or_nothing_asks(self):
        got = self.run_steps(self.FOUND, ["root.opened = false",
                                          'keyboardAnswered({cmd: "keyboard", ok: true, text: ""})'])
        self.assertEqual(got["shown"], 0)
        got = self.run_steps(None, ['keyboardAnswered({cmd: "keyboard", ok: true, text: ""})'])
        self.assertEqual(got["shown"], 0)
        got = self.run_steps(self.FOUND, ['keyboardAnswered({cmd: "keyboard", ok: false, text: "Can\'t reach Kodi"})'])
        self.assertEqual(got["shown"], 0)

    def test_keyboard_key(self):
        def key(input):
            expr = "keyboardKey(%s)" % json.dumps(input)
            r = subprocess.run(["node", "-e", EVAL_RUNNER, os.path.join(ROOT, "KodiInput.js"), expr],
                               capture_output=True, text=True, timeout=60)
            self.assertEqual(r.returncode, 0, r.stderr)
            return json.loads(r.stdout)
        self.assertEqual(key(None), "ask")
        self.assertEqual(key(self.HEARD), "open")
        self.assertEqual(key(self.FOUND), "ask")

    def test_the_panel_routes_the_answer(self):
        with open(os.path.join(ROOT, "Panel.qml"), encoding="utf-8") as f:
            source = f.read()
        self.assertRegex(source, r'r\.cmd === "keyboard"\) \{\s*root\.keyboardAnswered\(r\)')


# ---- what removal leaves ---------------------------------------------------------

PATH = re.compile(r"~/[\w./-]+")


def readme_leftovers():
    with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as f:
        text = f.read()
    part = text[text.index("Removing the plugin leaves:"):]
    part = part[:part.index("\n## ")]
    return [PATH.findall(item)[0] for item in re.split(r"\n- ", part)[1:]]


class RemovalListTest(unittest.TestCase):
    def test_install_sh_and_the_readme_agree(self):
        readme = readme_leftovers()
        self.assertEqual(readme, ["~/.config/omakodi/", "~/.local/state/omakodi/", "~/.cache/omakodi/",
                                  "~/.config/hypr/bindings.lua", "~/.local/bin/omakodi"])
        with tempfile.TemporaryDirectory() as home:  # never the real HOME
            r = subprocess.run(["bash", os.path.join(ROOT, "install.sh"), "--uninstall"],
                               env={"HOME": home, "PATH": "/usr/bin:/bin"}, capture_output=True, text=True,
                               timeout=30)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(os.listdir(home), [])  # it only told
        listed = r.stdout[r.stdout.index("Still there"):]
        rows = [line for line in listed.splitlines()[1:] if line.startswith("  ~/") or line.startswith("  the ")]
        # Every row is one of the README's, in its order; the link install.sh
        # has just removed is the only one it leaves out.
        self.assertEqual([PATH.findall(row)[0] for row in rows], readme[:-1])
        self.assertIn("password", listed)
        for words in ("box in use", "MAC address", "shortcut buttons", "queued", "posters"):
            self.assertIn(words, listed)


if __name__ == "__main__":
    unittest.main()
