import QtQuick
import Quickshell
import Quickshell.Hyprland
import Quickshell.Wayland
import qs.Commons
import qs.Commons as Commons
import qs.Ui
import "Format.js" as Format
import "RemoteKeys.js" as RemoteKeys

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
    if (detailsOpen) { queueOpen = false; audioOpen = false }
  }

  function toggleWholePlot() {
    if (!playing) return
    if (!detailsOpen) { toggleDetails(); wholePlot = true; return }
    wholePlot = !wholePlot
  }

  // "English · AC3 5.1": name, else language, else "Track N"; then the
  // sound unless the name already says it.
  function trackName(at) {
    if (!audio || at < 0 || at >= audio.tracks.length) return ""
    var t = audio.tracks[at]
    var name = t.name || t.language || strings.t("remote.track").arg(at + 1)
    var sound = [t.codec, t.channels].filter(function(x) { return x !== "" }).join(" ")
    return sound && t.name.indexOf(sound) < 0 ? name + " · " + sound : name
  }

  function toggleAudioList() {
    if (!reachable || !playing) return
    if (!audio) { note = strings.t("remote.noAudioTrack"); return }
    if (audio.tracks.length < 2) { note = strings.t("remote.oneAudioTrack"); return }
    audioOpen = !audioOpen
    if (audioOpen) {
      detailsOpen = false
      queueOpen = false
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
    if (queueOpen) {
      detailsOpen = false
      audioOpen = false
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

          // ---- header ----------------------------------------------------
          Item {
            width: parent.width
            height: closeButton.implicitHeight
            Text {
              anchors.verticalCenter: parent.verticalCenter
              textFormat: Text.PlainText
              text: String.fromCodePoint(0xF0314) + "  " + strings.t("remote.title")
              color: Commons.Color.popups.text
              font.family: Style.font.family
              font.pixelSize: Style.font.title
            }
            Button {
              id: closeButton
              anchors.right: parent.right
              iconText: String.fromCodePoint(0xF0156)
              tooltipText: strings.t("remote.close")
              onClicked: root.dismiss()
            }
          }

          // ---- now playing, or why there is nothing ------------------------
          Column {
            width: parent.width
            spacing: Style.spacing.sm
            Item {
              width: parent.width
              height: Math.max(artImage.visible ? artImage.height : 0, about.implicitHeight)
              // The poster or thumbnail, from the daemon's cache (never a URL).
              Image {
                id: artImage
                anchors.left: parent.left
                anchors.top: parent.top
                width: Style.space(96)
                height: Style.space(64)
                visible: root.artPath !== "" && status === Image.Ready
                source: root.artPath !== "" ? "file://" + root.artPath : ""
                fillMode: Image.PreserveAspectFit
                horizontalAlignment: Image.AlignLeft
                asynchronous: true
                cache: false
                sourceSize.width: width * 2
                sourceSize.height: height * 2
              }
              Column {
                id: about
                anchors.left: artImage.visible ? artImage.right : parent.left
                anchors.leftMargin: artImage.visible ? Style.spacing.md : 0
                anchors.right: parent.right
                spacing: Style.spacing.xs
                Text {
                  width: parent.width
                  textFormat: Text.PlainText
                  elide: Text.ElideRight
                  font.family: Style.font.family
                  font.pixelSize: Style.font.body
                  font.bold: true
                  color: Commons.Color.popups.text
                  text: !root.connected ? strings.t("remote.connecting")
                    : !root.reachable ? strings.t("remote.unreachable")
                    : root.playing ? (root.playing.title || strings.t("remote.nothingPlaying"))
                    : strings.t("remote.nothingPlaying")
                }
                Text {
                  width: parent.width
                  textFormat: Text.PlainText
                  wrapMode: Text.Wrap
                  maximumLineCount: 5
                  elide: Text.ElideRight
                  font.family: Style.font.family
                  font.pixelSize: Style.font.bodySmall
                  color: Commons.Color.popups.text
                  opacity: 0.7
                  visible: text !== ""
                  text: {
                    if (!root.connected) return ""
                    if (!root.reachable) {
                      var why = root.service.daemonError || root.service.error
                      return why ? why + "\n" + strings.t("remote.unreachableFix") : strings.t("remote.unreachableFix")
                    }
                    var parts = []
                    if (root.playing && root.playing.subtitle) parts.push(root.playing.subtitle)
                    if (root.playing) {
                      var p = root.playing
                      var when = p.durationSec > 0
                        ? Format.time(root.livePosition) + " / " + Format.time(p.durationSec)
                        : Format.time(root.livePosition)
                      if (p.durationSec > 0)
                        when += " · " + strings.t("remote.endsAt").arg(
                          Format.endsAt(p.durationSec - root.livePosition, root.nowMs))
                      if (p.paused) when += " · " + strings.t("remote.paused")
                      else if (root.speed > 1) when += " · " + strings.t("remote.forward").arg(root.speed)
                      else if (root.speed < 0) when += " · " + strings.t("remote.backward").arg(-root.speed)
                      parts.push(when)
                    }
                    if (root.service.muted) parts.push(strings.t("remote.muted"))
                    else if (root.service.volume >= 0) parts.push(strings.t("remote.volume").arg(root.service.volume))
                    return parts.join("  ·  ")
                  }
                }
              }
            }
            // ---- rewind, seek bar, fast-forward ---------------------------
            Item {
              width: parent.width
              height: rewindButton.implicitHeight
              visible: root.playing !== null
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

          // ---- buttons (the same actions as the keys) ----------------------
          Grid {
            id: pad
            anchors.horizontalCenter: parent.horizontalCenter
            columns: 3
            spacing: Style.spacing.sm
            enabled: root.reachable
            opacity: enabled ? 1 : 0.4

            Repeater {
              model: [
                ["home", 0xF02DC], ["up", 0xF0143], ["info", 0xF02FD],
                ["left", 0xF0141], ["select", 0], ["right", 0xF0142],
                ["back", 0xF006E], ["down", 0xF0140], ["context", 0xF035C],
                ["previous", 0xF04AE], ["playpause", 0xF040E], ["next", 0xF04AD],
                ["stop", 0xF04DB], ["osd", 0xF01D8], ["fullscreen", 0xF0293],
                ["voldown", 0xF075E], ["mute", 0xF0581], ["volup", 0xF075D]
              ]
              delegate: Button {
                required property var modelData
                width: Style.space(72)
                bordered: true
                text: modelData[1] === 0 ? "OK" : ""
                iconText: modelData[1] === 0 ? "" : String.fromCodePoint(modelData[1])
                tooltipText: strings.t("key." + modelData[0])
                onClicked: root.send(modelData[0], false)
              }
            }
          }

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

          // ---- details, queue, audio track and player info -------------------
          Flow {
            width: parent.width
            spacing: Style.spacing.sm
            visible: root.playing !== null
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
            Button {
              bordered: true
              iconText: String.fromCodePoint(0xF0A07)
              tooltipText: strings.t("key.playerinfo")
              onClicked: root.send("playerinfo", false)
            }
            Button {
              bordered: true
              visible: root.audio !== null && root.audio.tracks.length > 1
              width: Math.min(implicitWidth, parent.width)
              iconText: String.fromCodePoint(0xF057E)
              text: root.audio ? (root.trackName(root.audioAt) || "?") + " · "
                + (root.audioAt + 1 || "?") + "/" + root.audio.tracks.length : ""
              tooltipText: strings.t("key.audioList")
              onClicked: root.toggleAudioList()
            }
          }

          // ---- the audio track list ----------------------------------------------
          Column {
            width: parent.width
            spacing: Style.spacing.xs
            visible: root.audioOpen && root.audio !== null
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
              height: Math.min(count, 6) * rowHeight
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
            visible: root.detailsOpen && root.playing !== null
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
            visible: root.queue !== null && root.queueOpen
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
              height: Math.min(count, 6) * rowHeight
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
