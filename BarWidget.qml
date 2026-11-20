import QtQuick
import qs.Commons
import qs.Commons as Commons
import qs.Ui
import "Format.js" as Format
import "BarTip.js" as BarTip

// Kodi in the bar (SPEC "Bar widget"): hidden while Kodi doesn't answer, an
// icon while idle, icon and title while playing. All state comes from the
// service; this instance (one per monitor) only displays it.
BarWidget {
  id: root
  moduleName: "io.github.frestina.omakodi"

  readonly property string kodiGlyph: String.fromCodePoint(0xF0314)   // nf-md-kodi
  readonly property string pauseGlyph: String.fromCodePoint(0xF03E4)  // nf-md-pause

  // The service is created by the shell, possibly after this widget; look it
  // up until it appears. A destroyed service reads back as null.
  property var service: null
  function findService() {
    var s = bar && bar.shell && typeof bar.shell.serviceFor === "function"
      ? bar.shell.serviceFor(moduleName) : null
    if (s !== service) service = s
  }
  onBarChanged: findService()
  Timer {
    interval: 1000
    repeat: true
    running: root.service === null
    triggeredOnStart: true
    onTriggered: root.findService()
  }

  readonly property bool shown: service !== null && service.ready === true && service.reachable === true
  readonly property var playing: shown ? service.playing : null
  readonly property bool paused: playing !== null && playing.paused === true
  readonly property string problem: shown ? String(service.error || "") : ""
  readonly property int maxTitle: Math.max(0, Math.min(200, Number(setting("maxTitleLength", 0)) || 0))

  readonly property string label: {
    if (!shown) return ""
    if (vertical || playing === null) return kodiGlyph
    var title = Format.elide(playing.title, maxTitle)
    return kodiGlyph + (paused ? " " + pauseGlyph : "") + (title ? " " + title : "")
  }

  readonly property string tooltip: shown
    ? BarTip.lines({ error: problem, playing: playing, paused: paused, boxes: service.boxes },
                   Format.progress(playing),
                   { idle: strings.t("bar.idle"), paused: strings.t("bar.paused"), click: strings.t("bar.click") })
        .join("\n")
    : ""

  Commons.Translations { id: strings; directory: Qt.resolvedUrl("i18n") }

  visible: shown
  implicitWidth: shown ? button.implicitWidth : 0
  implicitHeight: shown ? button.implicitHeight : 0

  WidgetButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: root.label
    tooltipText: root.tooltip
    active: root.problem !== ""
    dimmed: root.vertical && root.paused

    onPressed: function(mouseButton) {
      if (mouseButton === Qt.LeftButton && root.service) root.service.toggleRemote()
    }
  }
}
