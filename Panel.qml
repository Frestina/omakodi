import QtQuick
import QtQuick.Effects
import Quickshell
import Quickshell.Hyprland
import Quickshell.Wayland
import qs.Commons
import qs.Commons as Commons
import qs.Ui
import "Format.js" as Format
import "RemoteKeys.js" as RemoteKeys
import "PowerMenu.js" as PowerMenu

// The remote (SPEC "Remote panel"). Opens on the focused monitor below the
// bar, keeps the keyboard while open; Esc, the close button or a click
// outside the card dismisses it. All Kodi state and commands go through the
// service.
Item {
  id: root
  property string omarchyPath: ""
  property var shell: null
  property var manifest: null
  property var service: null            // injected by the host

  readonly property string pluginId: "io.github.frestina.omakodi"

  property bool opened: false
  property var targetScreen: null
  property bool focusPrimed: false
  property string note: ""              // a local message (empty clipboard)

  readonly property bool connected: service !== null && service.ready === true
  readonly property bool reachable: connected && service.reachable === true && !service.daemonError
  readonly property var playing: reachable ? service.playing : null
  // The daemon reads the position every 5 s while something plays; between
  // reads the remote counts on from the last one at the play speed.
  property real positionBase: 0
  property real positionAt: 0
  property real nowMs: Date.now()
  readonly property int speed: playing ? playing.speed : 0
  readonly property real livePosition: playing
    ? Format.livePosition(positionBase, nowMs - positionAt, speed, playing.durationSec) : 0
  readonly property bool canSeek: playing !== null && playing.durationSec > 0
  readonly property string artPath: playing ? playing.art : ""
  // The queue section: open with u; while open it has the arrows.
  readonly property var queue: reachable ? service.queue : null
  property bool queueOpen: false
  property int queueSelected: -1        // a queue position (0 is the first)
  onQueueChanged: {
    if (!queue) { queueOpen = false; return }
    var last = queue.start + queue.items.length - 1
    if (queueSelected > last) queueSelected = last
    if (queueSelected < queue.start) queueSelected = queue.start
  }
  // Keys: the volume and action rows, and the bigger D-pad.
  readonly property real keySize: Style.space(40)
  readonly property real padSize: Style.space(56)
  readonly property color keyFill: Qt.rgba(Commons.Color.popups.text.r, Commons.Color.popups.text.g,
                                           Commons.Color.popups.text.b, 0.08)
  // Now playing shows more (seek bar, previous, details, queue) after a
  // click on it or n; the lists open in there.
  property bool moreOpen: false

  // Power: what Kodi allows, and whether it is on, off or restarting (the
  // latter two come with reachable false, so this doesn't wait for it).
  readonly property var power: connected ? service.power : null
  property bool powerOpen: false
  property int powerSelected: 0
  property string powerArmed: ""        // "reboot"/"shutdown" after the first press
  readonly property var powerItems: PowerMenu.items(power).map(function(action) {
    return { action: action, label: strings.t(action === "powermenu" ? "remote.powerMenu" : "remote." + action) }
  })
  onReachableChanged: if (!reachable) closePowerMenu()

  // Under the title: the volume, or why Kodi can't be reached and the fix.
  readonly property string headerStatus: {
    if (!service) return ""
    if (!connected) return strings.t("remote.connecting")
    if (!reachable && power && power.state === "off") return strings.t("remote.off")
    if (!reachable && power && power.state === "restarting") return strings.t("remote.restarting")
    if (!reachable) {
      var why = service.daemonError || service.error
      return strings.t("remote.unreachable") + "\n" + (why ? why + "\n" : "") + strings.t("remote.unreachableFix")
    }
    var parts = []
    if (!playing) parts.push(strings.t("remote.nothingPlaying"))
    if (service.muted) parts.push(strings.t("remote.muted"))
    else if (service.volume >= 0) parts.push(strings.t("remote.volume").arg(service.volume))
    return parts.join("  ·  ")
  }

  // "6:33 / 50:09 · ends 21:40 · Fast-forward 2×"
  readonly property string timeLine: {
    if (!playing) return ""
    var when = playing.durationSec > 0
      ? Format.time(livePosition) + " / " + Format.time(playing.durationSec)
      : Format.time(livePosition)
    if (playing.durationSec > 0)
      when += " · " + strings.t("remote.endsAt").arg(Format.endsAt(playing.durationSec - livePosition, nowMs))
    if (playing.paused) when += " · " + strings.t("remote.paused")
    else if (speed > 1) when += " · " + strings.t("remote.forward").arg(speed)
    else if (speed < 0) when += " · " + strings.t("remote.backward").arg(-speed)
    return when
  }

  // The details card: open with d; the plot shows 4 lines until D.
  readonly property var details: reachable ? service.details : null
  property bool detailsOpen: false
  property bool wholePlot: false
  property string shownPlot: ""
  onDetailsChanged: {  // a new plot starts cut again
    var plot = details ? details.plot : ""
    if (plot !== shownPlot) { shownPlot = plot; wholePlot = false }
  }
  // The audio tracks: a opens their list while there are two or more; while
  // open it has the arrows.
  readonly property var audio: reachable ? service.audio : null
  property bool audioOpen: false
  property int audioSelected: -1        // a place in audio.tracks
  onAudioChanged: {
    if (!audio || audio.tracks.length < 2) { audioOpen = false; return }
    audioSelected = Math.max(0, Math.min(audio.tracks.length - 1, audioSelected))
  }
  readonly property int audioAt: {  // where the playing track is in the list
    if (!audio) return -1
    for (var i = 0; i < audio.tracks.length; i++) if (audio.tracks[i].index === audio.current) return i
    return -1
  }
  onPlayingChanged: {
    nowMs = Date.now()
    positionBase = playing ? playing.positionSec : 0
    positionAt = nowMs
  }
  readonly property var lastResult: service ? service.lastResult : null
  // Kodi's on-screen keyboard while it is open: the text field shows.
  readonly property var kodiInput: reachable ? service.input : null
  readonly property string inputKey: kodiInput
    ? kodiInput.type + "\n" + kodiInput.title + "\n" + kodiInput.value : ""
  property string lastSentText: ""

  readonly property string statusText: {
    if (!service) return ""
    if (note) return note
    if (service.progressText) return service.progressText
    return lastResult ? lastResult.text : ""
  }
  readonly property bool statusIsError: !note && !(service && service.progressText)
    && lastResult !== null && lastResult.ok === false

  function focusedScreen() {
    var monitor = Hyprland.focusedMonitor
    var name = monitor ? monitor.name : ""
    for (var i = 0; i < Quickshell.screens.length; i++)
      if (Quickshell.screens[i].name === name) return Quickshell.screens[i]
    return Quickshell.screens.length > 0 ? Quickshell.screens[0] : null
  }

  function open(payloadJson) {
    // No payload fields are used; it is ignored rather than parsed.
    if (!root.opened) root.targetScreen = focusedScreen()
    root.note = ""
    root.opened = true
    root.focusPrimed = false
    focusPrimeTimer.restart()
    Qt.callLater(root.focusKeys)
  }

  // The text field while Kodi asks for text, the remote's keys otherwise.
  function focusKeys() {
    if (!root.opened) return
    if (root.kodiInput) field.forceActiveFocus()
    else keys.forceActiveFocus()
  }

  // A new keyboard on the TV: start from Kodi's text.
  onInputKeyChanged: {
    typingTimer.stop()
    field.text = kodiInput ? kodiInput.value : ""
    lastSentText = field.text
    focusKeys()
  }

  // Sends what is typed, unless Kodi already has it; `done` submits it.
  function sendTyped(done) {
    if (!kodiInput) return
    var t = field.text
    if (!done && t === lastSentText) return
    lastSentText = t
    note = ""
    var refused = service.sendText(t, done)
    if (refused) note = refused
  }

  function close() {
    typingTimer.stop()
    root.opened = false
    root.focusPrimed = false
    focusPrimeTimer.stop()
    root.note = ""
  }

  // Esc and the close button go through the host so its open state agrees.
  function dismiss() {
    if (shell && typeof shell.hide === "function" && shell.hide(pluginId)) return
    close()
  }

  function send(action, isRepeat) {
    if (!reachable) return
    note = ""
    service.key(action, isRepeat === true)
  }

  function seekTo(seconds) {
    if (!reachable || !canSeek) return
    var s = Math.max(0, Math.min(playing.durationSec, Math.round(seconds)))
    note = ""
    var refused = service.seek(s)
    if (refused) { note = refused; return }
    nowMs = Date.now()  // show it there now; the next state confirms it
    positionBase = s
    positionAt = nowMs
  }

  // Only one of the details card, the queue list and the track list is
  // open, so the remote stays short.
  function toggleDetails() {
    if (!playing) return
    detailsOpen = !detailsOpen
    closePowerMenu()
    if (detailsOpen) { queueOpen = false; audioOpen = false; moreOpen = true }
  }

  // The power menu: reboot and shut down only on a second press of the same
  // row within 5 s; moving, closing or waiting cancels it.
  function togglePowerMenu() {
    if (!reachable) return
    if (powerOpen) { closePowerMenu(); return }
    detailsOpen = false
    queueOpen = false
    audioOpen = false
    powerOpen = true
    powerSelected = 0
    powerArmed = ""
  }

  function closePowerMenu() {
    powerOpen = false
    powerArmed = ""
    armTimer.stop()
  }

  function movePowerSelection(step) {
    powerSelected = Math.max(0, Math.min(powerItems.length - 1, powerSelected + step))
    powerArmed = ""
    armTimer.stop()
  }

  function pickPower(at) {
    if (!reachable || at < 0 || at >= powerItems.length) return
    powerSelected = at
    var next = PowerMenu.pick(powerItems[at].action, powerArmed)
    if (next.send) {
      closePowerMenu()
      send(next.send, false)
      return
    }
    powerArmed = next.armed
    armTimer.restart()
  }

  // Shows more or less of what plays; less also closes the lists.
  function toggleMore() {
    if (!playing) return
    moreOpen = !moreOpen
    if (!moreOpen) { detailsOpen = false; queueOpen = false; audioOpen = false }
  }

  function toggleWholePlot() {
    if (!playing) return
    if (!detailsOpen) { toggleDetails(); wholePlot = true; return }
    wholePlot = !wholePlot
  }

  // "English · Commentary · AC3 5.1": language, name, then the sound unless
  // the name already says it; no part twice; "Track N" when there is none.
  function trackName(at) {
    if (!audio || at < 0 || at >= audio.tracks.length) return ""
    var t = audio.tracks[at]
    var sound = [t.codec, t.channels].filter(function(x) { return x !== "" }).join(" ")
    var parts = []
    var candidates = [t.language, t.name, t.name.indexOf(sound) < 0 ? sound : ""]
    for (var i = 0; i < candidates.length; i++) {
      var p = candidates[i]
      var seen = parts.some(function(q) { return q.toLowerCase() === p.toLowerCase() })
      if (p && !seen) parts.push(p)
    }
    return parts.length ? parts.join(" · ") : strings.t("remote.track").arg(at + 1)
  }

  function toggleAudioList() {
    if (!reachable || !playing) return
    if (!audio) { note = strings.t("remote.noAudioTrack"); return }
    if (audio.tracks.length < 2) { note = strings.t("remote.oneAudioTrack"); return }
    audioOpen = !audioOpen
    closePowerMenu()
    if (audioOpen) {
      detailsOpen = false
      queueOpen = false
      moreOpen = true
      audioSelected = Math.max(0, audioAt)
      Qt.callLater(function() { audioList.positionViewAtIndex(audioSelected, ListView.Center) })
    }
  }

  function moveAudioSelection(step) {
    if (!audio) return
    audioSelected = Math.max(0, Math.min(audio.tracks.length - 1, audioSelected + step))
    audioList.positionViewAtIndex(audioSelected, ListView.Contain)
  }

  function pickAudioTrack(at) {
    if (!reachable || !audio || at < 0 || at >= audio.tracks.length) return
    audioOpen = false
    if (at === audioAt) return
    note = ""
    var refused = service.setAudioTrack(audio.tracks[at].index)
    if (refused) note = refused
  }

  function toggleQueue() {
    if (!queue) return
    queueOpen = !queueOpen
    closePowerMenu()
    if (queueOpen) {
      detailsOpen = false
      audioOpen = false
      moreOpen = true
      queueSelected = queue.position
      Qt.callLater(function() { queueList.positionViewAtIndex(queueSelected - queue.start, ListView.Center) })
    }
  }

  function moveQueueSelection(step) {
    if (!queue || queue.items.length === 0) return
    var first = queue.start, last = queue.start + queue.items.length - 1
    queueSelected = Math.max(first, Math.min(last, queueSelected + step))
    queueList.positionViewAtIndex(queueSelected - first, ListView.Contain)
  }

  function playQueueEntry(position) {
    if (!reachable) return
    note = ""
    var refused = service.playQueueEntry(position)
    if (refused) note = refused
  }

  function removeQueueEntry(position) {
    if (!reachable || !queue || position === queue.position) return
    note = ""
    var refused = service.removeQueueEntry(position)
    if (refused) note = refused
  }

  function sendClipboard(cmd) {
    if (!reachable) return
    var text = String(Quickshell.clipboardText || "")
    if (text.trim() === "") { note = strings.t("remote.clipboardEmpty"); return }
    note = ""
    var refused = cmd === "queue" ? service.queue(text) : service.play(text)
    if (refused) note = refused
  }

  Commons.Translations { id: strings; directory: Qt.resolvedUrl("i18n") }

  Timer {
    interval: 1000
    repeat: true
    running: root.opened && root.playing !== null
    onTriggered: root.nowMs = Date.now()
  }

  Timer {
    id: armTimer
    interval: 5000
    onTriggered: root.powerArmed = ""
  }

  // While typing, Kodi gets the text at most every 150 ms, not per letter.
  Timer {
    id: typingTimer
    interval: 150
    onTriggered: root.sendTyped(false)
  }

  // A short exclusive grab makes the compositor give the new surface the
  // keyboard. OnDemand afterwards, because a long Exclusive sends every
  // pointer event on every monitor to this surface.
  Timer {
    id: focusPrimeTimer
    interval: 250
    onTriggered: if (root.opened) root.focusPrimed = true
  }

  // Like Omarchy's KeyboardPanel, the surface covers the monitor and the card
  // sits inside it. The pointer is then over this surface wherever it is on
  // the monitor, so Hyprland's focus-follows-mouse leaves the keyboard here;
  // a press outside the card closes the remote.
  PanelWindow {
    id: window
    screen: root.targetScreen
    visible: root.opened && root.targetScreen !== null
    anchors { top: true; bottom: true; left: true; right: true }
    color: "transparent"
    // Normal: stay clear of the bar's exclusive zone instead of covering it,
    // so the bar (and its omakodi icon) still gets its own clicks.
    exclusionMode: ExclusionMode.Normal
    WlrLayershell.namespace: "io-github-frestina-omakodi"
    WlrLayershell.layer: WlrLayer.Top
    WlrLayershell.keyboardFocus: !root.opened ? WlrKeyboardFocus.None
      : (root.focusPrimed ? WlrKeyboardFocus.OnDemand : WlrKeyboardFocus.Exclusive)

    MouseArea {
      id: outside
      anchors.fill: parent
      enabled: root.opened
      acceptedButtons: Qt.AllButtons
      onPressed: root.dismiss()
      onWheel: function(wheel) { wheel.accepted = true }
    }

    BorderSurface {
      id: card
      x: Math.round((window.width - width) / 2)
      y: Style.gapsOut
      // Opaque: the compositor blurs Omarchy's own panels behind a
      // translucent theme colour, but not a plugin's layer surface.
      readonly property color themed: Commons.Color.popups.background
      color: Qt.rgba(themed.r, themed.g, themed.b, 1)
      radius: Style.cornerRadius
      borderSpec: Border.surfaceSpec("popups", "border", Commons.Color.popups.border, 1)
      padding: Style.spacing.panelPadding
      implicitWidth: Style.space(300) + padding * 2
      implicitHeight: content.implicitHeight + padding * 2

      // The art of what plays behind everything, blurred and darkened so the
      // text keeps its contrast; the theme colour without art. One effect
      // that always exists and is only shown or hidden: a layer made and
      // dropped as the art comes and goes crashed the shell when the window
      // was mapped on a scaled screen.
      Image {
        id: posterImage
        anchors.fill: parent
        source: root.artPath !== "" ? "file://" + root.artPath : ""
        fillMode: Image.PreserveAspectCrop
        asynchronous: true
        cache: false
        sourceSize.width: 256
        visible: false
      }
      Rectangle {
        id: posterMask
        anchors.fill: parent
        radius: card.radius
        visible: false
        layer.enabled: true
      }
      MultiEffect {
        id: poster
        anchors.fill: parent
        visible: root.artPath !== "" && posterImage.status === Image.Ready
        source: posterImage
        autoPaddingEnabled: false
        blurEnabled: true
        blur: 1.0
        blurMax: 40
        maskEnabled: true
        maskSource: posterMask
      }
      Rectangle {
        anchors.fill: parent
        visible: poster.visible
        radius: card.radius
        color: card.color
        opacity: 0.65
      }

      // Presses on the card itself (between buttons) don't reach `outside`.
      MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.AllButtons
        onWheel: function(wheel) { wheel.accepted = true }
      }

      Item {
        id: keys
        anchors.fill: parent
        focus: true
        Keys.onPressed: function(event) {
          if (field.activeFocus) return  // keys the text field leaves aren't remote keys
          if (root.powerOpen && !(event.modifiers & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier))) {
            var pk = event.key
            if (pk === Qt.Key_Up || pk === Qt.Key_Down) {
              event.accepted = true
              root.movePowerSelection(pk === Qt.Key_Up ? -1 : 1)
              return
            }
            if ((pk === Qt.Key_Return || pk === Qt.Key_Enter) && !event.isAutoRepeat) {
              event.accepted = true
              root.pickPower(root.powerSelected)
              return
            }
            if (pk === Qt.Key_Escape) {  // closes the menu, not the remote
              event.accepted = true
              root.closePowerMenu()
              return
            }
          }
          if (root.audioOpen && !(event.modifiers & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier))) {
            var a = event.key
            if (a === Qt.Key_Up || a === Qt.Key_Down) {
              event.accepted = true
              root.moveAudioSelection(a === Qt.Key_Up ? -1 : 1)
              return
            }
            if ((a === Qt.Key_Return || a === Qt.Key_Enter) && !event.isAutoRepeat) {
              event.accepted = true
              root.pickAudioTrack(root.audioSelected)
              return
            }
            if (a === Qt.Key_Escape) {  // closes the list, not the remote
              event.accepted = true
              root.audioOpen = false
              return
            }
          }
          if (root.queueOpen && !(event.modifiers & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier))) {
            var k = event.key
            if (k === Qt.Key_Up || k === Qt.Key_Down) {
              event.accepted = true
              root.moveQueueSelection(k === Qt.Key_Up ? -1 : 1)
              return
            }
            if ((k === Qt.Key_Return || k === Qt.Key_Enter) && !event.isAutoRepeat) {
              event.accepted = true
              root.playQueueEntry(root.queueSelected)
              return
            }
            if (k === Qt.Key_Delete && !event.isAutoRepeat) {
              event.accepted = true
              root.removeQueueEntry(root.queueSelected)
              return
            }
            if (k === Qt.Key_Escape) {  // closes the queue, not the remote
              event.accepted = true
              root.queueOpen = false
              return
            }
          }
          var hit = RemoteKeys.lookup(Util.readingKey(event), event.text, event.modifiers)
          if (!hit) return
          event.accepted = true
          if (hit.queueList) { if (!event.isAutoRepeat) root.toggleQueue() }
          else if (hit.details) { if (!event.isAutoRepeat) root.toggleDetails() }
          else if (hit.wholePlot) { if (!event.isAutoRepeat) root.toggleWholePlot() }
          else if (hit.audioList) { if (!event.isAutoRepeat) root.toggleAudioList() }
          else if (hit.more) { if (!event.isAutoRepeat) root.toggleMore() }
          else if (hit.powerMenu) { if (!event.isAutoRepeat) root.togglePowerMenu() }
          else if (hit.close) root.dismiss()
          else if (hit.control) root.send(hit.control, event.isAutoRepeat)
          else if (hit.link && !event.isAutoRepeat) root.sendClipboard(hit.link)
        }

        Column {
          id: content
          x: card.padding
          y: card.padding
          width: card.width - card.padding * 2
          spacing: Style.spacing.md

          // ---- header: the title, the volume or what's wrong, close --------
          Item {
            width: parent.width
            height: Math.max(closeButton.implicitHeight, headerText.implicitHeight)
            Column {
              id: headerText
              anchors.left: parent.left
              anchors.right: powerButton.left
              anchors.rightMargin: Style.spacing.sm
              anchors.verticalCenter: parent.verticalCenter
              spacing: Style.spacing.xs
              Text {
                width: parent.width
                textFormat: Text.PlainText
                elide: Text.ElideRight
                text: String.fromCodePoint(0xF0314) + "  " + strings.t("remote.title")
                color: Commons.Color.popups.text
                font.family: Style.font.family
                font.pixelSize: Style.font.title
              }
              Text {
                width: parent.width
                visible: text !== ""
                textFormat: Text.PlainText
                wrapMode: Text.Wrap
                maximumLineCount: 4
                elide: Text.ElideRight
                font.family: Style.font.family
                font.pixelSize: Style.font.bodySmall
                color: Commons.Color.popups.text
                opacity: 0.7
                text: root.headerStatus
              }
            }
            Button {
              id: powerButton
              anchors.right: closeButton.left
              anchors.top: parent.top
              enabled: root.reachable
              opacity: enabled ? 1 : 0.4
              selected: root.powerOpen
              iconText: String.fromCodePoint(0xF0425)
              tooltipText: strings.t("key.power")
              onClicked: root.togglePowerMenu()
            }
            Button {
              id: closeButton
              anchors.right: parent.right
              anchors.top: parent.top
              iconText: String.fromCodePoint(0xF0156)
              tooltipText: strings.t("remote.close")
              onClicked: root.dismiss()
            }
          }

          // ---- the power menu --------------------------------------------------
          Column {
            width: parent.width
            spacing: Style.spacing.xs
            visible: root.powerOpen
            Text {
              width: parent.width
              textFormat: Text.PlainText
              elide: Text.ElideRight
              font.family: Style.font.family
              font.pixelSize: Style.font.bodySmall
              color: Commons.Color.popups.text
              opacity: 0.7
              text: strings.t("remote.powerHint")
            }
            Repeater {
              model: root.powerItems
              delegate: Item {
                id: powerRow
                required property var modelData
                required property int index
                readonly property bool armed: root.powerArmed === modelData.action
                width: parent.width
                height: Style.space(30)
                Rectangle {
                  anchors.fill: parent
                  radius: Style.cornerRadius
                  color: powerRow.armed ? Commons.Color.urgent : Commons.Color.popups.text
                  opacity: powerRow.armed ? 0.25
                    : powerRow.index === root.powerSelected ? 0.15 : (powerMouse.containsMouse ? 0.07 : 0)
                }
                MouseArea {
                  id: powerMouse
                  anchors.fill: parent
                  hoverEnabled: true
                  cursorShape: Qt.PointingHandCursor
                  onClicked: {
                    if (root.powerSelected !== powerRow.index) root.movePowerSelection(powerRow.index - root.powerSelected)
                    root.pickPower(powerRow.index)
                  }
                }
                Text {
                  anchors.left: parent.left
                  anchors.leftMargin: Style.spacing.sm
                  anchors.right: parent.right
                  anchors.rightMargin: Style.spacing.sm
                  anchors.verticalCenter: parent.verticalCenter
                  textFormat: Text.PlainText
                  elide: Text.ElideRight
                  font.family: Style.font.family
                  font.pixelSize: Style.font.bodySmall
                  font.bold: powerRow.armed
                  color: powerRow.armed ? Commons.Color.urgent : Commons.Color.popups.text
                  text: powerRow.armed
                    ? strings.t(powerRow.modelData.action === "reboot" ? "remote.rebootAgain" : "remote.shutdownAgain")
                    : powerRow.modelData.label
                }
              }
            }
          }

          // ---- Kodi's on-screen keyboard -----------------------------------
          Column {
            width: parent.width
            spacing: Style.spacing.xs
            visible: root.kodiInput !== null
            Text {
              width: parent.width
              textFormat: Text.PlainText
              elide: Text.ElideRight
              font.family: Style.font.family
              font.pixelSize: Style.font.bodySmall
              color: Commons.Color.popups.text
              text: root.kodiInput && root.kodiInput.title ? root.kodiInput.title : strings.t("remote.input")
            }
            TextField {
              id: field
              width: parent.width
              foreground: Commons.Color.popups.text
              password: root.kodiInput !== null && root.kodiInput.hidden === true
              maximumLength: 300
              placeholderText: strings.t("remote.inputHint")
              onTextEdited: if (!typingTimer.running) typingTimer.start()
              Keys.onPressed: function(event) {
                if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                  event.accepted = true
                  typingTimer.stop()
                  root.sendTyped(true)
                } else if (event.key === Qt.Key_Escape) {
                  event.accepted = true
                  typingTimer.stop()
                  root.send("back", false)  // Kodi closes its keyboard
                }
              }
            }
          }

          // ---- links -------------------------------------------------------
          Row {
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: Style.spacing.sm
            enabled: root.reachable
            opacity: enabled ? 1 : 0.4
            Button {
              bordered: true
              iconText: String.fromCodePoint(0xF040A)
              text: strings.t("remote.playClipboard")
              tooltipText: strings.t("key.play")
              onClicked: root.sendClipboard("play")
            }
            Button {
              bordered: true
              iconText: String.fromCodePoint(0xF0412)
              text: strings.t("remote.queueClipboard")
              tooltipText: strings.t("key.queue")
              onClicked: root.sendClipboard("queue")
            }
          }

          // ---- volume --------------------------------------------------------
          Row {
            id: volumeRow
            width: parent.width
            spacing: Style.spacing.sm
            enabled: root.reachable
            opacity: enabled ? 1 : 0.4
            Repeater {
              model: [["voldown", 0xF075E], ["mute", 0xF0581], ["volup", 0xF075D]]
              delegate: Button {
                required property var modelData
                width: (volumeRow.width - volumeRow.spacing * 2) / 3
                height: root.keySize
                background: root.keyFill
                foreground: Commons.Color.popups.text
                iconText: String.fromCodePoint(modelData[1])
                tooltipText: strings.t("key." + modelData[0])
                onClicked: root.send(modelData[0], false)
              }
            }
          }

          // ---- actions -------------------------------------------------------
          Row {
            id: actionRow
            width: parent.width
            spacing: Style.spacing.sm
            enabled: root.reachable
            opacity: enabled ? 1 : 0.4
            readonly property real keyWidth: (width - spacing * 5) / 6
            Button {
              width: actionRow.keyWidth
              height: root.keySize
              background: root.keyFill
              foreground: Commons.Color.popups.text
              opacity: root.audio !== null && root.audio.tracks.length > 1 ? 1 : 0.4
              selected: root.audioOpen
              iconText: String.fromCodePoint(0xF057E)
              tooltipText: root.audio !== null && root.audio.tracks.length > 1
                ? strings.t("key.audioList") + "\n" + root.trackName(root.audioAt) + " · "
                  + (root.audioAt + 1 || "?") + "/" + root.audio.tracks.length
                : strings.t("key.audioList")
              onClicked: root.toggleAudioList()
            }
            Repeater {
              model: [["fullscreen", 0xF0293], ["info", 0xF02FD], ["home", 0xF02DC],
                      ["context", 0xF035C], ["playerinfo", 0xF0A07]]
              delegate: Button {
                required property var modelData
                width: actionRow.keyWidth
                height: root.keySize
                background: root.keyFill
                foreground: Commons.Color.popups.text
                iconText: String.fromCodePoint(modelData[1])
                tooltipText: strings.t("key." + modelData[0])
                onClicked: root.send(modelData[0], false)
              }
            }
          }

          // ---- the D-pad -------------------------------------------------------
          Grid {
            anchors.horizontalCenter: parent.horizontalCenter
            columns: 3
            spacing: Style.spacing.sm
            enabled: root.reachable
            opacity: enabled ? 1 : 0.4
            Repeater {
              // ["", 0] keeps a corner empty (invisible items would close the gap).
              model: [["", 0], ["up", 0xF0143], ["", 0],
                      ["left", 0xF0141], ["select", 0], ["right", 0xF0142],
                      ["back", 0xF006E], ["down", 0xF0140], ["osd", 0xF01D8]]
              delegate: Button {
                required property var modelData
                readonly property bool arrow: ["up", "down", "left", "right"].indexOf(modelData[0]) >= 0
                width: root.padSize
                height: root.padSize
                opacity: modelData[0] === "" ? 0 : 1
                enabled: modelData[0] !== ""
                background: root.keyFill
                foreground: arrow ? Commons.Color.accent : Commons.Color.popups.text
                iconSize: arrow ? Style.font.icon * 1.5 : Style.font.icon
                fontSize: Style.font.title
                text: modelData[0] === "select" ? "OK" : ""
                iconText: modelData[1] === 0 ? "" : String.fromCodePoint(modelData[1])
                tooltipText: modelData[0] === "select" ? strings.t("key.selectOk")
                  : modelData[0] ? strings.t("key." + modelData[0]) : ""
                onClicked: if (modelData[0]) root.send(modelData[0], false)
                onRightClicked: if (modelData[0] === "select") root.send("context", false)
              }
            }
          }

          // ---- now playing: a bar that shows more on a click or n ----------
          Column {
            width: parent.width
            spacing: Style.spacing.xs
            visible: root.playing !== null
            // How far it is.
            Rectangle {
              width: parent.width
              height: 2
              radius: 1
              visible: root.canSeek
              color: Qt.rgba(Commons.Color.popups.text.r, Commons.Color.popups.text.g,
                             Commons.Color.popups.text.b, 0.2)
              Rectangle {
                height: parent.height
                radius: 1
                width: root.canSeek ? parent.width * Math.min(1, root.livePosition / root.playing.durationSec) : 0
                color: Commons.Color.accent
              }
            }
            Item {
              width: parent.width
              height: Math.max(artImage.visible ? artImage.height : 0, about.implicitHeight, transport.implicitHeight)
              MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: root.toggleMore()
              }
              // The poster or thumbnail, from the daemon's cache (never a URL).
              Image {
                id: artImage
                anchors.left: parent.left
                anchors.verticalCenter: parent.verticalCenter
                // As wide as the picture at this height (a poster is narrow), at most
                // 96. The decoded size depends on the height only: tying it to the
                // width as well is a binding loop, and that one crashed the shell.
                width: status === Image.Ready && implicitHeight > 0
                  ? Math.min(Style.space(96), height * implicitWidth / implicitHeight) : Style.space(96)
                height: Style.space(64)
                visible: root.artPath !== "" && status === Image.Ready
                source: root.artPath !== "" ? "file://" + root.artPath : ""
                fillMode: Image.PreserveAspectFit
                horizontalAlignment: Image.AlignLeft
                asynchronous: true
                cache: false
                sourceSize.height: Style.space(64) * 2
              }
              Column {
                id: about
                anchors.left: artImage.visible ? artImage.right : parent.left
                anchors.leftMargin: artImage.visible ? Style.spacing.sm : 0
                anchors.right: transport.left
                anchors.rightMargin: Style.spacing.xs
                anchors.verticalCenter: parent.verticalCenter
                spacing: Style.spacing.xs
                Text {
                  width: parent.width
                  textFormat: Text.PlainText
                  elide: Text.ElideRight
                  font.family: Style.font.family
                  font.pixelSize: Style.font.body
                  font.bold: true
                  color: Commons.Color.popups.text
                  text: root.playing ? (root.playing.title || strings.t("remote.nothingPlaying")) : ""
                }
                Text {
                  width: parent.width
                  visible: text !== ""
                  textFormat: Text.PlainText
                  elide: Text.ElideRight
                  font.family: Style.font.family
                  font.pixelSize: Style.font.bodySmall
                  color: Commons.Color.popups.text
                  opacity: 0.7
                  text: root.playing ? root.playing.subtitle : ""
                }
                Text {
                  width: parent.width
                  textFormat: Text.PlainText
                  elide: Text.ElideRight
                  font.family: Style.font.family
                  font.pixelSize: Style.font.bodySmall
                  color: Commons.Color.popups.text
                  opacity: 0.7
                  text: root.playing ? Format.progress({ positionSec: root.livePosition,
                    durationSec: root.playing.durationSec })
                    + (root.playing.paused ? " · " + strings.t("remote.paused") : "") : ""
                }
              }
              Row {
                id: transport
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                enabled: root.reachable
                Button {
                  iconText: String.fromCodePoint(root.playing && root.playing.paused ? 0xF040A : 0xF03E4)
                  tooltipText: strings.t("key.playpause")
                  onClicked: root.send("playpause", false)
                }
                Button {
                  iconText: String.fromCodePoint(0xF04AD)
                  tooltipText: strings.t("key.next")
                  onClicked: root.send("next", false)
                }
                Button {
                  iconText: String.fromCodePoint(0xF04DB)
                  tooltipText: strings.t("key.stop")
                  onClicked: root.send("stop", false)
                }
              }
            }
          }

          // ---- more of what plays: seek bar, time, previous, details, queue --
          Column {
            width: parent.width
            spacing: Style.spacing.sm
            visible: root.moreOpen && root.playing !== null
            Item {
              width: parent.width
              height: rewindButton.implicitHeight
              Button {
                id: rewindButton
                anchors.left: parent.left
                iconText: String.fromCodePoint(0xF045F)
                tooltipText: strings.t("key.rewind")
                onClicked: root.send("rewind", false)
              }
              PanelSlider {
                id: seekBar
                anchors.left: rewindButton.right
                anchors.right: forwardButton.left
                anchors.margins: Style.spacing.sm
                anchors.verticalCenter: parent.verticalCenter
                visible: root.canSeek
                minimum: 0
                maximum: root.canSeek ? root.playing.durationSec : 1
                value: root.livePosition
                step: 10  // the wheel: 10 s a notch
                trackColor: Qt.rgba(Commons.Color.popups.text.r, Commons.Color.popups.text.g,
                                    Commons.Color.popups.text.b, 0.2)
                fillColor: Commons.Color.popups.text
                knobColor: Commons.Color.popups.text
                onReleased: function(value) { root.seekTo(value) }
                PanelToolTip { text: strings.t("key.seek"); visible: seekBar._hot && !seekBar.dragging }
              }
              Button {
                id: forwardButton
                anchors.right: parent.right
                iconText: String.fromCodePoint(0xF0211)
                tooltipText: strings.t("key.fastforward")
                onClicked: root.send("fastforward", false)
              }
            }
            Text {
              width: parent.width
              textFormat: Text.PlainText
              wrapMode: Text.Wrap
              font.family: Style.font.family
              font.pixelSize: Style.font.bodySmall
              color: Commons.Color.popups.text
              opacity: 0.7
              text: root.timeLine
            }
            Flow {
              width: parent.width
              spacing: Style.spacing.sm
              Button {
                bordered: true
                iconText: String.fromCodePoint(0xF04AE)
                tooltipText: strings.t("key.previous")
                onClicked: root.send("previous", false)
              }
              Button {
                bordered: true
                iconText: String.fromCodePoint(root.detailsOpen ? 0xF0140 : 0xF0142)
                text: strings.t("remote.details")
                tooltipText: strings.t("key.details")
                onClicked: root.toggleDetails()
              }
              Button {
                bordered: true
                visible: root.queue !== null
                iconText: String.fromCodePoint(root.queueOpen ? 0xF0140 : 0xF0142)
                text: root.queue ? strings.t("remote.queue").arg(root.queue.total) : ""
                tooltipText: strings.t("key.queueList")
                onClicked: root.toggleQueue()
              }
            }
          }

          // ---- the audio track list ----------------------------------------------
          Column {
            width: parent.width
            spacing: Style.spacing.xs
            visible: root.moreOpen && root.audioOpen && root.audio !== null
            Text {
              width: parent.width
              textFormat: Text.PlainText
              elide: Text.ElideRight
              font.family: Style.font.family
              font.pixelSize: Style.font.bodySmall
              color: Commons.Color.popups.text
              opacity: 0.7
              text: strings.t("remote.audioHint")
            }
            ListView {
              id: audioList
              width: parent.width
              readonly property real rowHeight: Style.space(30)
              height: Math.min(count, 5) * rowHeight
              clip: true
              boundsBehavior: Flickable.StopAtBounds
              model: root.audio ? root.audio.tracks : []
              delegate: Item {
                id: track
                required property var modelData
                required property int index
                readonly property bool isPlaying: track.index === root.audioAt
                readonly property bool isSelected: track.index === root.audioSelected
                width: ListView.view.width
                height: audioList.rowHeight
                Rectangle {
                  anchors.fill: parent
                  radius: Style.cornerRadius
                  color: Commons.Color.popups.text
                  opacity: track.isSelected ? 0.15 : (trackMouse.containsMouse ? 0.07 : 0)
                }
                MouseArea {
                  id: trackMouse
                  anchors.fill: parent
                  hoverEnabled: true
                  onClicked: { root.audioSelected = track.index; root.pickAudioTrack(track.index) }
                }
                Text {
                  anchors.left: parent.left
                  anchors.leftMargin: Style.spacing.sm
                  anchors.right: parent.right
                  anchors.rightMargin: Style.spacing.sm
                  anchors.verticalCenter: parent.verticalCenter
                  textFormat: Text.PlainText
                  elide: Text.ElideRight
                  font.family: Style.font.family
                  font.pixelSize: Style.font.bodySmall
                  font.bold: track.isPlaying
                  color: Commons.Color.popups.text
                  text: (track.isPlaying ? "▶ " : (track.index + 1) + "  ") + root.trackName(track.index)
                }
              }
            }
          }
          // ---- the details card ------------------------------------------------
          Rectangle {
            id: detailsCard
            width: parent.width
            visible: root.moreOpen && root.detailsOpen && root.playing !== null
            height: detailsColumn.implicitHeight + Style.spacing.md * 2
            radius: Style.cornerRadius
            color: Qt.rgba(Commons.Color.popups.text.r, Commons.Color.popups.text.g,
                           Commons.Color.popups.text.b, 0.06)
            Column {
              id: detailsColumn
              x: Style.spacing.md
              y: Style.spacing.md
              width: parent.width - Style.spacing.md * 2
              spacing: Style.spacing.sm
              Text {
                width: parent.width
                visible: root.details === null
                textFormat: Text.PlainText
                wrapMode: Text.Wrap
                font.family: Style.font.family
                font.pixelSize: Style.font.bodySmall
                color: Commons.Color.popups.text
                opacity: 0.7
                text: strings.t("remote.noDetails")
              }
              // year · genres · studio · ★ rating
              Text {
                width: parent.width
                visible: text !== ""
                textFormat: Text.PlainText
                wrapMode: Text.Wrap
                maximumLineCount: 2
                elide: Text.ElideRight
                font.family: Style.font.family
                font.pixelSize: Style.font.bodySmall
                font.bold: true
                color: Commons.Color.popups.text
                text: {
                  var d = root.details
                  if (!d) return ""
                  var parts = []
                  if (d.year) parts.push(String(d.year))
                  if (d.genres.length) parts.push(d.genres.join(", "))
                  if (d.studio) parts.push(d.studio)
                  if (d.rating) parts.push(strings.t("remote.rating").arg(d.rating))
                  return parts.join("  ·  ")
                }
              }
              Flow {
                width: parent.width
                spacing: Style.spacing.xs
                visible: root.details !== null && root.details.badges.length > 0
                Repeater {
                  model: root.details ? root.details.badges : []
                  delegate: Rectangle {
                    required property var modelData
                    width: badgeText.implicitWidth + Style.spacing.sm * 2
                    height: badgeText.implicitHeight + Style.spacing.xs * 2
                    radius: Style.cornerRadius
                    color: "transparent"
                    border.width: 1
                    border.color: Qt.rgba(Commons.Color.popups.text.r, Commons.Color.popups.text.g,
                                          Commons.Color.popups.text.b, 0.4)
                    Text {
                      id: badgeText
                      anchors.centerIn: parent
                      textFormat: Text.PlainText
                      font.family: Style.font.family
                      font.pixelSize: Style.font.bodySmall
                      color: Commons.Color.popups.text
                      text: parent.modelData
                    }
                  }
                }
              }
              // The plot: 4 lines, or all of it (D), scrolling past about 12.
              Flickable {
                id: plotView
                width: parent.width
                visible: root.details !== null && root.details.plot !== ""
                readonly property real maxHeight: Math.ceil(plotText.font.pixelSize * 1.35 * 12)
                height: root.wholePlot ? Math.min(plotText.implicitHeight, maxHeight) : plotText.implicitHeight
                contentWidth: width
                contentHeight: plotText.implicitHeight
                clip: true
                interactive: contentHeight > height
                boundsBehavior: Flickable.StopAtBounds
                onVisibleChanged: contentY = 0
                Connections {
                  target: root
                  function onWholePlotChanged() { plotView.contentY = 0 }
                }
                Text {
                  id: plotText
                  width: plotView.width
                  textFormat: Text.PlainText
                  wrapMode: Text.Wrap
                  maximumLineCount: root.wholePlot ? 1000 : 4
                  elide: Text.ElideRight
                  font.family: Style.font.family
                  font.pixelSize: Style.font.bodySmall
                  color: Commons.Color.popups.text
                  text: root.details ? root.details.plot : ""
                  TapHandler { onTapped: root.toggleWholePlot() }
                }
              }
              Button {
                visible: plotView.visible && (plotText.truncated || root.wholePlot)
                text: strings.t(root.wholePlot ? "remote.plotLess" : "remote.plotMore")
                fontSize: Style.font.bodySmall
                tooltipText: strings.t("key.wholePlot")
                onClicked: root.toggleWholePlot()
              }
              Text {
                width: parent.width
                visible: text !== ""
                textFormat: Text.PlainText
                wrapMode: Text.Wrap
                maximumLineCount: 2
                elide: Text.ElideRight
                font.family: Style.font.family
                font.pixelSize: Style.font.bodySmall
                color: Commons.Color.popups.text
                opacity: 0.7
                text: root.details && root.details.cast.length > 0
                  ? strings.t("remote.cast").arg(root.details.cast.join(", ")) : ""
              }
            }
          }
          // ---- the queue ------------------------------------------------------
          Column {
            width: parent.width
            spacing: Style.spacing.xs
            visible: root.moreOpen && root.queue !== null && root.queueOpen
            Text {
              width: parent.width
              visible: root.queueOpen
              textFormat: Text.PlainText
              elide: Text.ElideRight
              font.family: Style.font.family
              font.pixelSize: Style.font.bodySmall
              color: Commons.Color.popups.text
              opacity: 0.7
              text: strings.t("remote.queueHint")
            }
            ListView {
              id: queueList
              width: parent.width
              visible: root.queueOpen
              readonly property real rowHeight: Style.space(30)
              height: Math.min(count, 5) * rowHeight
              clip: true
              boundsBehavior: Flickable.StopAtBounds
              model: root.queue ? root.queue.items : []
              delegate: Item {
                id: entry
                required property var modelData
                required property int index
                readonly property int position: root.queue ? root.queue.start + index : index
                readonly property bool isPlaying: root.queue !== null && position === root.queue.position
                readonly property bool isSelected: position === root.queueSelected
                width: ListView.view.width
                height: queueList.rowHeight
                Rectangle {
                  anchors.fill: parent
                  radius: Style.cornerRadius
                  color: Commons.Color.popups.text
                  opacity: entry.isSelected ? 0.15 : (rowMouse.containsMouse ? 0.07 : 0)
                }
                MouseArea {
                  id: rowMouse
                  anchors.fill: parent
                  hoverEnabled: true
                  onClicked: { root.queueSelected = entry.position; root.playQueueEntry(entry.position) }
                }
                Text {
                  anchors.left: parent.left
                  anchors.leftMargin: Style.spacing.sm
                  anchors.right: removeButton.left
                  anchors.verticalCenter: parent.verticalCenter
                  textFormat: Text.PlainText
                  elide: Text.ElideRight
                  font.family: Style.font.family
                  font.pixelSize: Style.font.bodySmall
                  font.bold: entry.isPlaying
                  color: Commons.Color.popups.text
                  text: (entry.isPlaying ? "▶ " : (entry.position + 1) + "  ")
                    + (entry.modelData.title || "?")
                    + (entry.modelData.subtitle ? " · " + entry.modelData.subtitle : "")
                }
                Button {
                  id: removeButton
                  anchors.right: parent.right
                  anchors.verticalCenter: parent.verticalCenter
                  visible: !entry.isPlaying && (entry.isSelected || rowMouse.containsMouse || removeButton.hot)
                  iconText: String.fromCodePoint(0xF0156)
                  tooltipText: strings.t("key.queueRemove")
                  onClicked: root.removeQueueEntry(entry.position)
                }
              }
            }
          }
          // ---- the last result, progress or error ---------------------------
          Text {
            width: parent.width
            visible: text !== ""
            textFormat: Text.PlainText
            wrapMode: Text.Wrap
            maximumLineCount: 4
            elide: Text.ElideRight
            font.family: Style.font.family
            font.pixelSize: Style.font.bodySmall
            color: root.statusIsError ? Commons.Color.urgent : Commons.Color.popups.text
            text: root.statusText
          }
        }
      }
    }
  }
}
