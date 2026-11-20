"""Keys while Kodi doesn't answer, like the phone remote (ticket 060).

TopBar.keyRefusal() and RemoteKeys.needsKodi() are checked on their own;
then the remote's own key functions, cut out of Panel.qml, run under node
against a stub service that records what would be sent, so "a message,
nothing sent" is checked on the code the remote runs.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "lib"))

from omakodi.control import ACTIONS  # noqa: E402

CANT_REACH = "Can't reach Living room"
FIX = "no answer from kodi.example.lan:8080 (away from home?)"

# The functions a key goes through, by name, from Panel.qml.
FUNCTIONS = ["refusedOffline", "send", "openKeyboard", "openStripButton", "openSendLink", "sendLink",
             "toggleAudioList", "sendClipboard", "wakeKodi", "sendPower"]

# Loads the JS libraries and the Panel functions into one context with
# stubs, sets the state from argv[3], runs the presses (argv[4]) one after
# another and prints what was said and sent.
RUNNER = r"""
const fs = require("fs"), vm = require("vm")
const root = process.argv[1], fns = JSON.parse(process.argv[2])
const state = JSON.parse(process.argv[3]), presses = JSON.parse(process.argv[4])
const lib = n => { const c = {}; vm.runInNewContext(fs.readFileSync(root + "/" + n, "utf8").replace(/^\.pragma library\s*$/m, ""), c); return c }
const log = { said: [], sent: [], hushed: 0, pages: [] }
const words = JSON.parse(fs.readFileSync(root + "/i18n/en.json", "utf8"))
String.prototype.arg = function(v) { return this.replace("%1", v) }
const ctx = {
  RemoteKeys: lib("RemoteKeys.js"), TopBar: lib("TopBar.js"), NowPlaying: lib("NowPlaying.js"),
  KodiInput: lib("KodiInput.js"), Protocol: lib("Protocol.js"), Toast: lib("Toast.js"),
  strings: { t: k => words[k] },
  Qt: { callLater: () => {} },
  Quickshell: { clipboardText: "look: https://www.example.org/watch?v=x" },
  service: {
    key: (a, r) => { log.sent.push(["control", a, r]); return "" },
    openKeyboard: () => { log.sent.push(["keyboard"]); return "" },
    openShortcut: s => { log.sent.push(["shortcut", s]); return "" },
    play: t => { log.sent.push(["play", t]); return "" },
    queue: t => { log.sent.push(["queue", t]); return "" },
    wake: () => { log.sent.push(["wake"]); return "" },
  },
  say: (t, e) => log.said.push([t, e === true]),
  hush: () => { log.hushed++ },
  closeOthers: () => {}, closePowerMenu: () => {},
  closeStripPage: () => { log.pages.push("closed"); ctx.stripPage = "" },
  sendField: { text: "", forceActiveFocus: () => {}, cursorPosition: 0 },
  audioList: { positionViewAtIndex: () => {} },
  stripButtons: [{ sendLink: true }, { sendLink: false }],
  audioOpen: false, audioAt: -1, audioSelected: -1, stripPage: "", sendText: "", kodiInput: null,
  wakeOnLan: true, playing: null, audio: null,
}
Object.assign(ctx, state)
vm.createContext(ctx)
for (const f of fns) vm.runInContext(f, ctx)
// The binding in Panel.qml, as it is written there.
ctx.topStatus = ctx.TopBar.status(state.kodi)
ctx.offlineRefusal = ctx.TopBar.keyRefusal(ctx.topStatus, ctx.reachable,
  ctx.strings.t("remote.cantReach").arg(ctx.topTitle !== "" ? ctx.topTitle : "Kodi"))
for (const p of presses) vm.runInContext(p, ctx)
log.audioOpen = ctx.audioOpen
log.stripPage = ctx.stripPage
process.stdout.write(JSON.stringify(log))
"""

EVAL_RUNNER = r"""
const fs = require("fs"), vm = require("vm")
const src = fs.readFileSync(process.argv[1], "utf8").replace(/^\.pragma library\s*$/m, "")
const ctx = {}
vm.runInNewContext(src, ctx)
process.stdout.write(JSON.stringify(vm.runInContext(process.argv[2], ctx)))
"""


def panel():
    with open(os.path.join(ROOT, "Panel.qml"), encoding="utf-8") as f:
        return f.read()


def function(source, name):
    start = source.index("  function %s(" % name)
    return source[start:source.index("\n  }\n", start) + 4]


# The daemon's states, as the service holds them.
UNREACHABLE = {"ready": True, "reachable": False, "error": CANT_REACH + "\n" + FIX, "power": {"state": "on"}}
OFF = {"ready": True, "reachable": False, "error": "", "power": {"state": "off"}}
RESTARTING = {"ready": True, "reachable": False, "error": "", "power": {"state": "restarting"}}
BAD_ADDRESS = {"ready": True, "reachable": False, "error": "Bad address for Living room\nnot an address"}
DAEMON = {"ready": True, "reachable": False, "error": "", "daemonError": "omakodi daemon keeps stopping"}
WRONG_PASSWORD = {"ready": True, "reachable": True, "error": "Wrong username or password for Living room\ncheck it"}
CONNECTED = {"ready": True, "reachable": True, "error": "", "power": {"state": "on"}}
CONNECTING = {"ready": True, "reachable": False, "connecting": True, "error": ""}


@unittest.skipUnless(shutil.which("node"), "node is needed to run the JS files")
class OfflineKeysTest(unittest.TestCase):
    def js(self, name, expr):
        r = subprocess.run(["node", "-e", EVAL_RUNNER, os.path.join(ROOT, name), expr],
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def press(self, service, presses, **extra):
        source = panel()
        state = {"kodi": service, "connected": service.get("ready") is True,
                 "reachable": service.get("ready") is True and service.get("reachable") is True
                 and not service.get("daemonError"), "topTitle": "Living room"}
        state.update(extra)
        r = subprocess.run(["node", "-e", RUNNER, ROOT, json.dumps([function(source, f) for f in FUNCTIONS]),
                            json.dumps(state), json.dumps(presses)],
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    # ---- the pure parts ------------------------------------------------------------

    def refusal(self, service, reachable=None):
        if reachable is None:
            reachable = service.get("reachable") is True and not service.get("daemonError")
        return self.js("TopBar.js", "keyRefusal(status(%s), %s, %s)" % (
            json.dumps(service), json.dumps(reachable), json.dumps(CANT_REACH)))

    def test_what_a_key_says_while_offline(self):
        self.assertEqual(self.refusal(UNREACHABLE), CANT_REACH)  # the message alone, not the fix
        self.assertEqual(self.refusal(BAD_ADDRESS), "Bad address for Living room")
        self.assertEqual(self.refusal(OFF), CANT_REACH)  # no error of its own: the phone's words
        self.assertEqual(self.refusal(RESTARTING), CANT_REACH)
        self.assertEqual(self.refusal(DAEMON), "omakodi daemon keeps stopping")
        # Sent: Kodi answers (a wrong password answers each key itself), or Connecting….
        self.assertEqual(self.refusal(CONNECTED), "")
        self.assertEqual(self.refusal(WRONG_PASSWORD), "")
        self.assertEqual(self.refusal(CONNECTING), "")
        self.assertEqual(self.refusal({"ready": False}), "")
        self.assertEqual(self.js("TopBar.js", "keyRefusal(status(null), false, 'x')"), "")

    def test_only_the_soundbar_wake_up_goes_without_kodi(self):
        got = self.js("RemoteKeys.js", "%s.map(needsKodi)" % json.dumps(ACTIONS))
        self.assertEqual([a for a, needs in zip(ACTIONS, got) if not needs], ["soundbaron"])

    def test_the_wording(self):
        with open(os.path.join(ROOT, "i18n", "en.json"), encoding="utf-8") as f:
            self.assertEqual(json.load(f)["remote.cantReach"], "Can't reach %1")
        self.assertIn('strings.t("remote.cantReach").arg(topTitle !== "" ? topTitle : "Kodi")', panel())

    # ---- each kind of key while Offline: the message, nothing sent ------------------

    def test_every_key_that_needs_kodi_says_the_error_and_sends_nothing(self):
        presses = (["send(%s, false)" % json.dumps(a) for a in ACTIONS if a != "soundbaron"]
                   + ["openKeyboard()", "openStripButton(1)", "toggleAudioList()", "sendClipboard('play')",
                      "sendClipboard('queue')"])
        for service, said in ((UNREACHABLE, CANT_REACH), (OFF, CANT_REACH), (RESTARTING, CANT_REACH),
                              (DAEMON, "omakodi daemon keeps stopping")):
            for p in presses:
                with self.subTest(state=service, press=p):
                    log = self.press(service, [p])
                    self.assertEqual(log["sent"], [])
                    self.assertEqual(log["said"], [[said, True]])  # an error: stays until the next key
                    self.assertFalse(log["audioOpen"])

    def test_a_held_key_says_it_once(self):
        log = self.press(UNREACHABLE, ["send('up', false)", "send('up', true)", "send('up', true)",
                                       "send('volup', false)", "send('volup', true)"])
        self.assertEqual(log["sent"], [])
        self.assertEqual(log["said"], [[CANT_REACH, True], [CANT_REACH, True]])

    def test_send_a_link_opens_and_its_play_says_the_error(self):
        log = self.press(UNREACHABLE, ["openStripButton(0)"])
        self.assertEqual((log["sent"], log["said"], log["stripPage"]), ([], [], "send"))
        log = self.press(UNREACHABLE, ["sendLink(false)", "sendLink(true)"], stripPage="send",
                         sendText="https://www.example.org/watch?v=x")
        self.assertEqual(log["sent"], [])
        self.assertEqual(log["said"], [[CANT_REACH, True], [CANT_REACH, True]])
        self.assertEqual((log["pages"][0], log["stripPage"]), ("closed", ""))

    # ---- keys that don't need Kodi still work ------------------------------------------

    def test_wake_up_and_the_soundbar_still_go(self):
        for service in (UNREACHABLE, OFF, DAEMON):
            with self.subTest(state=service):
                log = self.press(service, ["wakeKodi()", "send('soundbaron', false)", "sendPower('soundbaron')",
                                           "sendPower('wake')"])
                self.assertEqual(log["sent"], [["wake"], ["control", "soundbaron", False],
                                               ["control", "soundbaron", False], ["wake"]])
                self.assertEqual(log["said"], [])

    def test_kodis_power_menu_goes_to_the_daemon_which_answers(self):
        log = self.press(UNREACHABLE, ["sendPower('powermenu')"])
        self.assertEqual(log["sent"], [["control", "powermenu", False]])

    def test_the_pages_open_without_kodi(self):
        # The ☰ menu, Settings, Kodi boxes, the power menu and a strip button's
        # page ask only `connected`, never whether Kodi answers.
        source = panel()
        for name in ("toggleMenu", "toggleSettings", "toggleBoxes", "togglePowerMenu", "editStrip",
                     "openSendLink", "wakeKodi", "pickMenuRow", "pickPower"):
            with self.subTest(function=name):
                body = function(source, name)
                self.assertNotIn("reachable", body)
                self.assertNotIn("refusedOffline", body)

    # ---- back to normal when the box answers --------------------------------------------

    def test_keys_go_once_kodi_answers(self):
        presses = ["send('up', false)", "send('up', true)", "send('mute', false)", "openKeyboard()",
                   "openStripButton(1)", "sendClipboard('play')"]
        log = self.press(CONNECTED, presses)
        self.assertEqual(log["said"], [])
        self.assertEqual(log["sent"], [["control", "up", False], ["control", "up", True], ["control", "mute", False],
                                       ["keyboard"], ["shortcut", 1],
                                       ["play", "look: https://www.example.org/watch?v=x"]])
        # A wrong password: the keys go, and Kodi answers each with it.
        self.assertEqual(len(self.press(WRONG_PASSWORD, presses)["sent"]), 6)
        # Connecting…: the keys go to the daemon, which answers.
        self.assertEqual(len(self.press(CONNECTING, presses)["sent"]), 6)

    def test_the_audio_key_with_kodi_back_says_nothing_is_playing(self):
        log = self.press(CONNECTED, ["toggleAudioList()"])
        self.assertEqual((log["sent"], log["said"]), ([], [["Nothing is playing", True]]))

    # ---- no row is dimmed ------------------------------------------------------------------

    def test_no_row_of_keys_is_dimmed(self):
        source = panel()
        self.assertNotIn("opacity: root.reachable", source)
        rows = source[source.index("// ---- the shortcut strip: five buttons"):source.index("// ---- the audio track list")]
        self.assertNotIn("reachable", rows)
        self.assertIsNone(re.search(r"opacity: enabled \? 1 : 0\.4", rows))


if __name__ == "__main__":
    unittest.main()
