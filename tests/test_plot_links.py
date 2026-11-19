"""Links in the Details dialog's plot (PlotLinks.js and Panel.qml DetailsPlot,
ticket 049).

PlotLinks.js runs under node: the plot's http(s) links are found (several,
at the end of a line, with punctuation after them, none), the rest stays
text, no other scheme is a link, and the markup escapes everything but the
links it builds. DetailsPlot runs under qmltestrunner (offscreen): what it
shows is exactly the plot, a click on a link asks to open that link, Tab
marks the links in turn and Enter opens the marked one, and it never takes
the keyboard. Each part is skipped where node or Qt's test runner isn't
installed.
"""

import json
import os
import shutil
import subprocess
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNNER = shutil.which("qmltestrunner") or shutil.which("qmltestrunner6") or (
    "/usr/lib/qt6/bin/qmltestrunner" if os.access("/usr/lib/qt6/bin/qmltestrunner", os.X_OK) else None)

# Loads PlotLinks.js and prints the JSON of each expression in the JSON array
# on stdin; `arg` in an expression is the matching value of the array in argv.
EVAL = r"""
const fs = require("fs"), vm = require("vm")
const src = fs.readFileSync(process.argv[1], "utf8").replace(/^\.pragma library\s*$/m, "")
const ctx = {}
vm.runInNewContext(src, ctx)
const jobs = JSON.parse(fs.readFileSync(0, "utf8"))
process.stdout.write(JSON.stringify(jobs.map(j => { ctx.arg = j[1]; return vm.runInContext(j[0], ctx) })))
"""


@unittest.skipUnless(shutil.which("node"), "node is needed to run PlotLinks.js")
class PlotLinksTest(unittest.TestCase):
    def run_js(self, jobs):
        r = subprocess.run(["node", "-e", EVAL, os.path.join(ROOT, "PlotLinks.js")],
                           input=json.dumps(jobs), capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def links(self, *plots):
        return self.run_js([["links(parts(arg))", p] for p in plots])

    def parts(self, plot):
        return self.run_js([["parts(arg)", plot]])[0]

    def test_several_links(self):
        plot = ("Watch the trailer: https://www.example.com/trailer and the making of "
                "http://video.example.org/making?id=42&t=3 or HTTPS://EXAMPLE.NET/A")
        self.assertEqual(self.links(plot), [[
            "https://www.example.com/trailer",
            "http://video.example.org/making?id=42&t=3",
            "HTTPS://EXAMPLE.NET/A",
        ]])

    def test_a_link_at_the_end_of_a_line(self):
        plot = "Follow us\nhttps://social.example.com/@channel\nMore below\nhttps://example.org"
        self.assertEqual(self.links(plot), [["https://social.example.com/@channel", "https://example.org"]])
        parts = self.parts(plot)
        self.assertEqual(parts[1], {"text": "https://social.example.com/@channel",
                                    "url": "https://social.example.com/@channel"})
        self.assertEqual(parts[2], {"text": "\nMore below\n", "url": ""})

    def test_punctuation_after_a_link(self):
        got = self.links(
            "Read https://example.com/a.",
            "See https://example.com/b, then https://example.com/c; https://example.com/d!",
            "Is it https://example.com/e? Yes: https://example.com/f…",
            "(see https://example.com/g)",
            "The film https://en.example.org/wiki/Big_Sleep_(film) is old.",
            "[https://example.com/h] and {https://example.com/i}",
            "**https://example.com/j**",
            "Quoted \"https://example.com/k\" and 'https://example.com/l' and <https://example.com/m>",
        )
        self.assertEqual(got, [
            ["https://example.com/a"],
            ["https://example.com/b", "https://example.com/c", "https://example.com/d"],
            ["https://example.com/e", "https://example.com/f"],
            ["https://example.com/g"],
            ["https://en.example.org/wiki/Big_Sleep_(film)"],
            ["https://example.com/h", "https://example.com/i"],
            ["https://example.com/j"],
            ["https://example.com/k", "https://example.com/l", "https://example.com/m"],
        ])
        # What was trimmed is text again.
        self.assertEqual(self.parts("(see https://example.com/g).")[-1], {"text": ").", "url": ""})

    def test_no_links(self):
        self.assertEqual(self.links("", "Just a plot.", "http", "https://", "https://.", "https:///path",
                                    "https://user@", "www.example.com", "example.com/path"),
                         [[]] * 9)
        self.assertEqual(self.parts("Just a plot."), [{"text": "Just a plot.", "url": ""}])
        self.assertEqual(self.parts(""), [])
        self.assertEqual(self.run_js([["parts(arg)", None], ["parts(arg)", 7]]), [[], []])

    def test_only_http_and_https(self):
        self.assertEqual(self.links(
            "ftp://example.org/file", "mailto:someone@example.org", "file:///etc/passwd",
            "javascript:alert(1)", "httpx://example.org", "data:text/html,hi", "plugin://plugin.video.example/",
            "http\u017f://example.org", "smb://kodi.example.lan/share",
        ), [[]] * 9)
        checks = self.run_js([["isWebLink(arg)", u] for u in (
            "https://example.com", "http://example.com/x?y=1#z", "HTTP://EXAMPLE.COM",
            "ftp://example.com", "javascript:alert(1)", "https://", "https://exa mple.com",
            "https://example.com/\n", "https://example.com/\x00", "https://example.com/<b>",
            "https://" + "a" * 4089, "https://" + "a" * 4088, " https://example.com", 42,
        )])
        self.assertEqual(checks, [True, True, True, False, False, False, False,
                                  False, False, False, False, True, False, False])
        self.assertEqual(self.run_js([["openCommand(arg)", u] for u in (
            "https://example.com/a b", "https://example.com/a?b=$(id)&c=`id`", "file:///etc/passwd")]),
            [None, ["xdg-open", "https://example.com/a?b=$(id)&c=`id`"], None])

    def test_the_other_text_stays_plain(self):
        plot = ("<b>Bold?</b> &amp; <img src=\"https://example.com/x.png\"> <a href='javascript:x'>y</a>\n"
                "[B]tags[/B] https://example.com/a?b=1&c=<2>")
        markup, links = self.run_js([["markup(parts(arg), -1, '#112233', '#ffffff')", plot],
                                     ["links(parts(arg))", plot]])
        self.assertEqual(links, ["https://example.com/x.png", "https://example.com/a?b=1&c="])
        body = markup.removeprefix('<div style="white-space:pre-wrap;line-height:120%">').removesuffix("</div>")
        # The only tags are the links and the line break the remote builds.
        tags = [t for t in body.split("<")[1:]]
        self.assertEqual([t.split(">")[0].split(" ")[0] for t in tags], ["a", "/a", "br", "a", "/a"])
        self.assertIn("&lt;b&gt;Bold?&lt;/b&gt; &amp;amp; &lt;img src=&quot;", body)
        self.assertIn("&lt;a href=&#39;javascript:x&#39;&gt;y&lt;/a&gt;", body)
        self.assertIn('<a href="1" style="color:#112233;text-decoration:underline">'
                      'https://example.com/a?b=1&amp;c=</a>&lt;2&gt;', body)
        self.assertNotIn("javascript:x'", body)

    def test_markup_marks_the_focused_link_and_checks_colours(self):
        plot = "a https://example.com/1 b https://example.com/2"
        focused, bad = self.run_js([
            ["markup(parts(arg), 1, '#112233', '#ffffff')", plot],
            ["markup(parts(arg), -1, 'red;background:url(x)', '#fff')", plot],
        ])
        self.assertIn('<a href="0" style="color:#112233;text-decoration:underline">', focused)
        self.assertIn('<a href="1" style="color:#ffffff;background-color:#112233;text-decoration:underline">',
                      focused)
        self.assertNotIn("url(x)", bad)
        self.assertIn("color:#3584e4", bad)

    def test_helpers(self):
        plot = "x\nhttps://example.com/1 yy https://example.com/22"
        got = self.run_js([
            ["offset(parts(arg), 0)", plot], ["offset(parts(arg), 1)", plot], ["offset(parts(arg), 2)", plot],
            ["[step(0, -1, 1), step(3, -1, 1), step(3, -1, -1), step(3, 2, 1), step(3, 0, -1), step(3, 1, 1)]", None],
            ["[linkIndex('0', 2), linkIndex('1', 2), linkIndex('2', 2), linkIndex('-1', 2), "
             "linkIndex('https://example.com', 2), linkIndex('1x', 2)]", None],
            ["css({r: 1, g: 0.5, b: 0})", None], ["css(null)", None],
        ])
        self.assertEqual(got, [2, 27, -1, [-1, 0, 2, 0, 2, 2], [0, 1, -1, -1, -1, -1], "#ff8000", "#000000"])


FAKE_COMMONS = {
    "qmldir": "module qs.Commons\nsingleton Color 1.0 Color.qml\nsingleton Style 1.0 Style.qml\n",
    "Color.qml": ("pragma Singleton\nimport QtQuick\nQtObject {\n"
                  "  property QtObject popups: QtObject { property color text: \"white\" }\n"
                  "  property color accent: \"#336699\"\n}\n"),
    "Style.qml": ("pragma Singleton\nimport QtQuick\nQtObject {\n"
                  "  property QtObject font: QtObject { property string family: \"\"; property real body: 14 }\n}\n"),
}

TEST = """import QtQuick
import QtTest
import qs.Commons
import qs.Commons as Commons
import "PlotLinks.js" as PlotLinks
Item {
  id: root
  width: 400; height: 600
  property var opened: []
  Item { id: keys; width: 10; height: 10; focus: true }
  DetailsPlot {
    id: plot
    y: 20
    width: 300
    linkColor: Commons.Color.accent
    focusedColor: "black"
    onOpenLink: function(url) { root.opened.push(url) }
  }
%COMPONENT%
  TestCase {
    name: "DetailsPlot"
    when: windowShown
    readonly property string sample: "Our <b>new</b> video & more.\\n\\nShop: https://shop.example.com/x?a=1&b=2.\\n"
      + "Chat (https://chat.example.org/room) or mailto:fan@example.com\\nhttps://example.net/end"
    function init() { opened = []; plot.plot = ""; keys.forceActiveFocus() }
    function shown() { return plot.getText(0, plot.length) }
    function linkPoint(i) {
      var r = plot.positionToRectangle(PlotLinks.offset(plot.parts, i) + 2)
      return Qt.point(r.x + 1, r.y + r.height / 2)
    }

    function test_shows_the_plot_as_it_is() {
      plot.plot = sample
      compare(shown(), sample.replace(/\\n/g, "\\u2028"))
      compare(plot.links, ["https://shop.example.com/x?a=1&b=2", "https://chat.example.org/room",
                           "https://example.net/end"])
    }
    function test_a_click_on_a_link_opens_it() {
      plot.plot = sample
      for (var i = 0; i < 3; i++) {
        var p = linkPoint(i)
        compare(plot.linkAt(p.x, p.y), String(i))
        mouseClick(plot, p.x, p.y)
      }
      compare(opened, plot.links)
      verify(keys.activeFocus)  // the remote keeps the keyboard
      verify(!plot.activeFocus)
    }
    function test_a_click_on_text_opens_nothing() {
      plot.plot = sample
      mouseClick(plot, 2, 2)
      compare(opened.length, 0)
    }
    function test_tab_marks_the_links_in_turn_and_enter_opens_it() {
      plot.plot = sample
      compare(plot.focusedLink, -1)
      verify(!plot.openFocused())
      var r = plot.moveFocus(1)
      compare(plot.focusedLink, 0)
      verify(r.height > 0)
      var r1 = plot.moveFocus(1)
      compare(plot.focusedLink, 1)
      verify(r1.y > r.y)
      plot.moveFocus(1)
      plot.moveFocus(1)  // round the end
      compare(plot.focusedLink, 0)
      plot.moveFocus(-1)
      compare(plot.focusedLink, 2)
      verify(plot.openFocused())
      compare(opened, ["https://example.net/end"])
      compare(shown(), sample.replace(/\\n/g, "\\u2028"))  // marking changes no text
    }
    function test_a_new_plot_marks_nothing() {
      plot.plot = sample
      plot.moveFocus(1)
      plot.plot = "Another plot, https://example.com"
      compare(plot.focusedLink, -1)
    }
    function test_without_links() {
      plot.plot = "No links here: www.example.com, ftp://example.com"
      compare(plot.links.length, 0)
      compare(plot.moveFocus(1), null)
      compare(plot.focusedLink, -1)
      verify(!plot.openFocused())
      mouseClick(plot, 5, 5)
      compare(opened.length, 0)
    }
    function test_keys_and_a_press_leave_the_keyboard_alone() {
      plot.plot = sample
      mouseClick(plot, 3, 3)
      verify(keys.activeFocus)
      verify(plot.readOnly)
    }
  }
}
"""


@unittest.skipUnless(RUNNER, "Qt's qmltestrunner is needed to run the QML")
class DetailsPlotTest(unittest.TestCase):
    def test_details_plot(self):
        with open(os.path.join(ROOT, "Panel.qml"), encoding="utf-8") as f:
            panel = f.read()
        start = panel.index("  component DetailsPlot: TextEdit {")
        end = panel.index("\n  // A heading in the Details dialog", start)
        component = panel[start:end]
        with tempfile.TemporaryDirectory() as d:
            shutil.copy(os.path.join(ROOT, "PlotLinks.js"), d)
            commons = os.path.join(d, "imports", "qs", "Commons")
            os.makedirs(commons)
            for name, text in FAKE_COMMONS.items():
                with open(os.path.join(commons, name), "w", encoding="utf-8") as f:
                    f.write(text)
            test = os.path.join(d, "tst_details_plot.qml")
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
