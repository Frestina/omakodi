"""The dialog for Kodi's keyboard (Panel.qml KodiTextDialog, ticket 047) in a real Qt.

Runs the component from Panel.qml under qmltestrunner (offscreen), with
stand-ins for the host's Button and TextField and for qs.Commons: it opens
when Kodi asks for text, titled with Kodi's prompt; typing sends nothing;
Send or Enter sends the whole text once (submitted) and closes it; Cancel,
Esc or a click beside it sends nothing and only closes it; the keyboard key
opens it again; Paste puts the clipboard in place of the selection; a
password shows dots and starts empty. Skipped where Qt's test runner isn't
installed.
"""

import os
import shutil
import subprocess
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNNER = shutil.which("qmltestrunner") or shutil.which("qmltestrunner6") or (
    "/usr/lib/qt6/bin/qmltestrunner" if os.access("/usr/lib/qt6/bin/qmltestrunner", os.X_OK) else None)

FAKE_BUTTON = """import QtQuick
Rectangle {
  id: button
  signal clicked()
  property string text: ""
  property string iconText: ""
  property string tooltipText: ""
  property bool bordered: false
  property color foreground: "white"
  implicitWidth: 60
  implicitHeight: 24
  MouseArea { anchors.fill: parent; onClicked: button.clicked() }
}
"""

FAKE_TEXT_FIELD = """import QtQuick
import QtQuick.Controls
TextField {
  property color foreground: "white"
  property bool password: false
  echoMode: password ? TextInput.Password : TextInput.Normal
  height: 30
}
"""

QMLDIR = """module qs.Commons
singleton Color 1.0 Color.qml
singleton Style 1.0 Style.qml
"""

COLOR = """pragma Singleton
import QtQuick
QtObject {
  property QtObject popups: QtObject { property color text: "white" }
}
"""

STYLE = """pragma Singleton
import QtQuick
QtObject {
  property QtObject spacing: QtObject { property real sm: 4; property real lg: 12 }
  property QtObject font: QtObject { property string family: ""; property real title: 16 }
}
"""

TEST = """import QtQuick
import QtTest
import qs.Commons
import qs.Commons as Commons
import "KodiInput.js" as KodiInput
Item {
  id: root
  width: 400; height: 400
  property bool opened: true
  property var sent: []
  property int closed: 0
  property string refuse: ""
  property string clipText: ""
  function sendKodiText(text) { if (refuse) return false; sent.push(text); return true }
  function kodiTextClosed() { closed++ }
  function clipboardText() { return clipText }
  QtObject { id: strings; function t(k) { return k } }
  Rectangle { id: card; property real padding: 10; radius: 4; color: "black" }
  TextInput { id: elsewhere; width: 10; height: 10 }
  KodiTextDialog { id: dialog; anchors.fill: parent }
%COMPONENT%
  TestCase {
    name: "KodiTextDialog"
    when: windowShown
    function field() { return findChild(dialog, "kodiTextField") }
    function titleText() { return findChild(dialog, "kodiTextTitle").text }
    function click(name) { var b = findChild(dialog, name); mouseClick(b, 5, 5) }
    function init() { dialog.request = null; sent = []; closed = 0; refuse = ""; clipText = "" }
    function typed(s) { for (var i = 0; i < s.length; i++) keyClick(s[i]) }

    function test_closed_without_a_request() {
      verify(!dialog.visible)
      dialog.show(false)  // the keyboard key while Kodi isn't asking: nothing
      verify(!dialog.visible)
    }
    function test_opens_with_kodis_prompt_and_text() {
      dialog.request = { type: "keyboard", title: "Search", value: "the w", hidden: false }
      verify(dialog.visible)
      compare(titleText(), "Search")
      compare(field().text, "the w")
      compare(field().echoMode, TextInput.Normal)
      verify(dialog.fieldFocused)
    }
    function test_typing_sends_nothing_enter_sends_it_once() {
      dialog.request = { type: "keyboard", title: "Search", value: "the w", hidden: false }
      typed("ire")
      wait(300)
      compare(sent.length, 0)
      keyClick(Qt.Key_Return)
      compare(sent, ["the wire"])
      verify(!dialog.visible)
      compare(field().text, "")
      compare(closed, 1)
      keyClick(Qt.Key_Return)  // closed: nothing more
      compare(sent.length, 1)
    }
    function test_send_button() {
      dialog.request = { type: "keyboard", title: "", value: "", hidden: false }
      compare(titleText(), "kodiText.title")  // "Send text to Kodi"
      typed("dune")
      click("kodiTextSend")
      compare(sent, ["dune"])
      verify(!dialog.visible)
    }
    function test_escape_only_closes_it_and_the_key_opens_it_again() {
      dialog.request = { type: "keyboard", title: "Search", value: "", hidden: false }
      typed("abc")
      keyClick(Qt.Key_Escape)
      compare(sent.length, 0)
      verify(!dialog.visible)
      compare(closed, 1)
      verify(dialog.request !== null)  // Kodi's keyboard stays on the TV
      compare(KodiInput.keyboardKey(dialog.request), "open")
      dialog.show(false)  // the keyboard key
      verify(dialog.visible)
      compare(field().text, "")  // what was typed is forgotten
      verify(dialog.fieldFocused)
    }
    function test_cancel_button_and_a_click_beside_it() {
      dialog.request = { type: "keyboard", title: "Search", value: "x", hidden: false }
      click("kodiTextCancel")
      verify(!dialog.visible)
      dialog.show(false)
      mouseClick(dialog, 3, 3)  // beside the dialog
      verify(!dialog.visible)
      compare(sent.length, 0)
      compare(closed, 2)
    }
    function test_a_password_shows_dots_and_starts_empty() {
      dialog.request = { type: "password", title: "Login", value: "example-secret", hidden: true }
      compare(field().echoMode, TextInput.Password)
      compare(field().text, "")
      typed("pw")
      keyClick(Qt.Key_Enter)
      compare(sent, ["pw"])
      compare(field().text, "")
    }
    function test_paste_replaces_the_selection() {
      dialog.request = { type: "keyboard", title: "Search", value: "the wire", hidden: false }
      clipText = "big\\nsleep"
      field().select(4, 8)
      click("kodiTextPaste")
      compare(field().text, "the big sleep")
      compare(field().cursorPosition, 13)
      verify(dialog.fieldFocused)
      compare(sent.length, 0)
    }
    function test_a_refused_send_keeps_it_open() {
      dialog.request = { type: "keyboard", title: "Search", value: "abc", hidden: false }
      refuse = "the daemon isn't running"
      keyClick(Qt.Key_Return)
      verify(dialog.visible)
      compare(field().text, "abc")
      compare(closed, 0)
    }
    function test_kodi_closing_its_keyboard_closes_it() {
      dialog.request = { type: "keyboard", title: "Search", value: "", hidden: false }
      typed("abc")
      dialog.request = null
      verify(!dialog.visible)
      compare(field().text, "")
      compare(sent.length, 0)
      compare(closed, 1)  // the keys go back to the remote
    }
    function test_a_new_request_starts_afresh() {
      dialog.request = { type: "keyboard", title: "Search", value: "", hidden: false }
      typed("abc")
      dialog.request = { type: "keyboard", title: "Rename", value: "Old name", hidden: false }
      verify(dialog.visible)
      compare(titleText(), "Rename")
      compare(field().text, "Old name")
    }
    function test_the_key_while_open_keeps_the_text() {
      dialog.request = { type: "keyboard", title: "Search", value: "", hidden: false }
      typed("abc")
      elsewhere.forceActiveFocus()
      dialog.show(false)
      compare(field().text, "abc")
      verify(dialog.fieldFocused)
    }
    function test_nothing_takes_the_keyboard_while_the_remote_is_closed() {
      opened = false
      elsewhere.forceActiveFocus()
      dialog.request = { type: "keyboard", title: "Search", value: "", hidden: false }
      verify(!dialog.fieldFocused)
      opened = true
    }
  }
}
"""


@unittest.skipUnless(RUNNER, "Qt's qmltestrunner is needed to run the QML")
class KodiTextDialogTest(unittest.TestCase):
    def test_kodi_text_dialog(self):
        with open(os.path.join(ROOT, "Panel.qml"), encoding="utf-8") as f:
            panel = f.read()
        start = panel.index("  component KodiTextDialog: Item {")
        end = panel.index("\n  // ----", start + 1)
        component = panel[start:end]
        component = component.replace("          TextField {\n            id: kodiTextField",
                                      "          FakeTextField {\n            id: kodiTextField")
        component = component.replace("Button {", "FakeButton {")
        self.assertIn("FakeTextField {", component)
        self.assertEqual(component.count("FakeButton {"), 3)
        with tempfile.TemporaryDirectory() as d:
            shutil.copy(os.path.join(ROOT, "KodiInput.js"), d)
            commons = os.path.join(d, "imports", "qs", "Commons")
            os.makedirs(commons)
            for name, text in (("qmldir", QMLDIR), ("Color.qml", COLOR), ("Style.qml", STYLE)):
                with open(os.path.join(commons, name), "w", encoding="utf-8") as f:
                    f.write(text)
            for name, text in (("FakeButton.qml", FAKE_BUTTON), ("FakeTextField.qml", FAKE_TEXT_FIELD)):
                with open(os.path.join(d, name), "w", encoding="utf-8") as f:
                    f.write(text)
            test = os.path.join(d, "tst_kodi_text.qml")
            with open(test, "w", encoding="utf-8") as f:
                f.write(TEST.replace("%COMPONENT%", component))
            env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
            r = subprocess.run([RUNNER, "-import", os.path.join(d, "imports"), "-input", test],
                               capture_output=True, text=True, timeout=120, env=env, cwd=d)
        out = r.stdout[-4000:] + r.stderr[-3000:]
        self.assertEqual(r.returncode, 0, out)
        self.assertIn(" 0 failed", r.stdout)
        self.assertNotIn("ReferenceError", out)
        self.assertNotIn("TypeError", out)


if __name__ == "__main__":
    unittest.main()
