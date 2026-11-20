import QtQuick
import QtQuick.Effects
import Quickshell
import Quickshell.Hyprland
import Quickshell.Io
import Quickshell.Wayland
import qs.Commons
import qs.Commons as Commons
import qs.Ui
import "Format.js" as Format
import "RemoteKeys.js" as RemoteKeys
import "PowerMenu.js" as PowerMenu
import "Protocol.js" as Protocol
import "Shortcuts.js" as Shortcuts
import "Boxes.js" as Boxes
import "TopBar.js" as TopBar
import "NowPlaying.js" as NowPlaying
import "KodiInput.js" as KodiInput
import "Toast.js" as Toast
import "PlotLinks.js" as PlotLinks

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
  // The short message at the bottom (SPEC "Remote panel"), as a phone
  // remote's: shown a few seconds and gone; an error stays until the next
  // action (hush). Results, progress and the remote's own notes all go here.
  property string toastText: ""
  property bool toastError: false
  property bool toastShown: false

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
    if (!queue) return  // the Queue dialog says it is empty
    var last = queue.start + queue.items.length - 1
    if (queueSelected > last) queueSelected = last
    if (queueSelected < queue.start) queueSelected = queue.start
  }
  // Keys: the volume and action rows, and the bigger D-pad.
  readonly property real keySize: Style.space(40)
  readonly property real padSize: Style.space(56)
  readonly property color keyFill: Qt.rgba(Commons.Color.popups.text.r, Commons.Color.popups.text.g,
                                           Commons.Color.popups.text.b, 0.08)
  // The now-playing page (a click on the now-playing bar, or n), over the
  // remote like Settings, as on a phone remote. It shows the last item for
  // a moment after playback stops, then closes. Its Queue and Details open
  // as dialogs over it.
  property bool nowOpen: false
  property var shownPlaying: null       // what the page shows: what plays, or the last item
  property real shownPosition: 0        // where that last item was when it stopped
  property bool queueLoading: false     // the Queue dialog waits for the daemon's fresh read
  readonly property real pagePosition: playing ? livePosition : shownPosition

  // Power: what Kodi allows, and whether it is on, off or restarting (the
  // latter two come with reachable false, so this doesn't wait for it).
  // The power menu is there while Kodi isn't answering too: Wake up is how
  // it comes back. Reboot and Shut down ask in a dialog first.
  readonly property var power: connected ? service.power : null
  readonly property bool wakeOnLan: connected && service.wakeOnLan !== false
  property bool powerOpen: false
  property int powerSelected: 0
  property var powerDialog: null        // {action, at}: "Reboot <box>?" while it asks
  readonly property var powerItems: PowerMenu.items(power, wakeOnLan)
  onPowerItemsChanged: {
    powerSelected = Math.max(0, Math.min(powerSelected, powerItems.length - 1))
    // Kodi no longer allows it (or stopped answering): the question goes.
    if (powerDialog && powerItems.indexOf(powerDialog.action) < 0) powerDialog = null
  }

  // The top bar (SPEC "Remote panel"): ☰, the box's name with Connected,
  // Offline or Connecting… under it, the power button, close.
  readonly property var topStatus: service ? TopBar.status({
    ready: service.ready === true, daemonError: service.daemonError, connecting: service.connecting === true,
    reachable: service.reachable === true, error: service.error, power: service.power }) : TopBar.status(null)
  readonly property string topTitle: connected ? TopBar.title(service.boxes) : ""
  // The ☰ menu: the saved boxes, Manage Kodi boxes, Settings, the version.
  property bool menuOpen: false
  property int menuSelected: 0
  readonly property var menuRows: TopBar.menuRows(connected ? service.boxes : null)
  onMenuRowsChanged: menuSelected = TopBar.menuMove(menuSelected, 0, menuRows.length)
  readonly property string version: manifest && manifest.version ? String(manifest.version) : ""
  // Connected is green, as on a phone remote: the theme's green (or color2),
  // read when the remote opens; the shell's own palette has none.
  property color okColor: "#5fa85f"
  FileView {
    id: themeColors
    path: Quickshell.env("HOME") + "/.local/state/omarchy/current/theme/colors.toml"
    watchChanges: false
    printErrors: false
    onLoaded: {
      var m = String(text() || "").match(/^\s*(?:green|color2)\s*=\s*["']?(#[0-9A-Fa-f]{6})/m)
      if (m) root.okColor = m[1]
    }
  }

  // Settings: a page over the remote, like a phone remote's Settings
  // (SPEC "Remote panel"). For now one section: which add-on plays YouTube
  // links, per box, with smart mode's wait after a failure.
  readonly property var youtube: connected ? service.youtube : null
  readonly property var youtubeModes: ["smart", "youtube-first", "sendtokodi-only", "youtube-only"]
  property bool settingsOpen: false
  property int settingsSelected: 0      // a mode's place, or 4: "Try the YouTube add-on again"
  property real settingsNow: Date.now()
  readonly property bool smartWaiting: youtube !== null && youtube.mode === "smart"
    && youtube.avoidUntil * 1000 > settingsNow
  readonly property int settingsRows: youtubeModes.length + (smartWaiting ? 1 : 0)
  onSmartWaitingChanged: if (settingsSelected >= settingsRows) settingsSelected = settingsRows - 1
  // The shortcut strip under the top bar (SPEC "Shortcut buttons"): five
  // buttons, each opening something on Kodi or the Send a link dialog. Its
  // pages cover the remote like Settings: "send" (Send a link), "edit" (one
  // button), "picker" (Choose from Kodi), "icons" (Change icon).
  readonly property var stripButtons: connected && service.shortcuts ? service.shortcuts.buttons : []
  property string stripPage: ""
  property int stripSlot: -1            // the button being changed
  property bool stripArmed: false       // after e: the next key, 1-5, picks the button to change
  readonly property var editButton: stripSlot >= 0 && stripSlot < stripButtons.length ? stripButtons[stripSlot] : null
  property int editSelected: 0
  property int editButtonAt: 0          // in the bottom row of the button page
  readonly property var editRows: {
    if (!editButton) return []
    var rows = ["choose"]
    if (!editButton.sendLink) rows.push("sendLink")
    rows.push("icon", "path", "buttons")
    return rows
  }
  readonly property var editButtons: editButton && editButton.custom ? ["reset", "cancel", "save"] : ["cancel", "save"]
  property string typedPath: ""         // the path field's text
  readonly property bool canSavePath: editButton !== null && typedPath !== editButton.typed
    && (typedPath.trim() === "" || Shortcuts.normalize(typedPath) !== "")
  readonly property var pickerView: service ? service.picker : null
  property bool pickerWaiting: false    // asked for a page the daemon hasn't shown yet
  property int pickerSelected: 0
  onPickerViewChanged: {
    pickerWaiting = false
    pickerSelected = Math.max(0, Math.min(pickerSelected, pickerRows.length - 1))
  }
  // The picker's rows: "Use this folder" on a folder, Kodi's rows once
  // listed, "Try again" when it couldn't list them.
  readonly property var pickerRows: {
    var v = pickerView
    if (!v || pickerWaiting) return []
    var rows = []
    if (v.folder) rows.push({ kind: "folder", label: strings.t("picker.useFolder"), detail: v.crumb, browse: false })
    if (v.status === "ready")
      for (var i = 0; i < v.items.length; i++)
        rows.push({ kind: "item", index: i, label: v.items[i].label, detail: v.items[i].detail, browse: v.items[i].browse })
    if (v.status === "failed") rows.push({ kind: "retry", label: strings.t("picker.tryAgain"), detail: "", browse: false })
    return rows
  }
  readonly property string pickerStatus: {
    var v = pickerView
    if (!v || pickerWaiting || v.status === "loading") return strings.t("picker.loading")
    if (v.status === "failed") return strings.t("picker.couldntLoad") + (v.error ? ": " + v.error : "")
    if (v.items.length === 0) return strings.t(v.folder ? "picker.noFolders" : "picker.nothing")
    return ""
  }
  readonly property var iconNames: Shortcuts.names()
  readonly property int iconColumns: 8
  property int iconSelected: 0          // 0: Kodi's icon (or automatic), then the built-in icons
  property string sendText: ""          // the Send a link field

  // The Kodi boxes (SPEC "Kodi boxes"): b or Manage Kodi boxes in the ☰ menu opens
  // the "Kodi boxes" page (saved boxes, boxes found on the network, Add
  // manually), like a phone remote's; "edit" is a box's editor. The
  // passwords stay in the daemon: the editor only says one is saved.
  readonly property var boxList: connected && service.boxes ? service.boxes.list : []
  readonly property string currentBox: connected && service.boxes ? service.boxes.current : ""
  // A box goes by its id (SPEC "Kodi boxes"), not its address: two can
  // share one, and a box keeps its settings when its address changes.
  function boxName(id) {
    for (var i = 0; i < boxList.length; i++) if (boxList[i].id === id) return boxList[i].name || boxList[i].host
    return ""
  }
  readonly property var foundView: service ? service.found : null
  readonly property var foundBoxes: foundView ? foundView.boxes : []
  property string boxPage: ""           // "list" or "edit"
  property int boxSelected: 0
  readonly property var boxRows: {
    var rows = []
    for (var i = 0; i < boxList.length; i++) rows.push({ kind: "saved", at: i })
    for (var j = 0; j < foundBoxes.length; j++) rows.push({ kind: "found", at: j })
    rows.push({ kind: "add", at: 0 })
    return rows
  }
  onBoxRowsChanged: boxSelected = Math.max(0, Math.min(boxSelected, boxRows.length - 1))
  // As a phone remote: "Searching…" until a box answers the search, "No
  // new boxes found" when all that answer are saved.
  readonly property string foundStatus: {
    var f = foundView
    if (f && f.status === "failed") return strings.t("boxes.searchFailed").arg(f.error)
    if (foundBoxes.length > 0) return ""
    if (!f || f.total === 0) return strings.t("boxes.searching")
    return strings.t("boxes.noNew")
  }
  property string editKey: ""           // the id of the box being changed; "" for a new one
  property bool editHasPassword: false
  property string editKnownMac: ""
  property bool passwordEdited: false
  property int editorRow: 0             // 0-6 the fields, 7 the buttons
  property int editorButtonAt: 0
  readonly property var editorButtons: editKey !== "" ? ["test", "delete", "save"] : ["test", "save"]
  readonly property string formProblem: boxPage === "edit" ? Boxes.problem(boxForm()) : ""
  property string testStatus: ""
  property bool testOk: false
  property bool testing: false
  property bool savingBox: false
  property string editorError: ""
  // Another box: what was open was the last box's.
  onCurrentBoxChanged: {
    stripPage = ""
    stripSlot = -1
    closeOthers()
  }

  // Volume (SPEC "Volume"): + - m are Kodi's own volume; the soundbar row
  // sends Kodi's volume keys (HDMI-CEC), hidden once they turn out to move
  // Kodi's own volume.
  readonly property bool showSoundbar: connected && service.volumeKeys !== "kodi"

  // Under the status: Kodi is off or restarting, or why Kodi can't be
  // reached (at most 2 lines) and the fix (always whole): the error's own
  // first, then "Is Kodi on…" when Kodi can't be reached.
  readonly property string topNote: topStatus.note === "off" ? strings.t("remote.off")
    : topStatus.note === "restarting" ? strings.t("remote.restarting") : ""
  readonly property string topFix: [topStatus.detail,
    topStatus.fix ? strings.t("remote.unreachableFix") : ""].filter(function(x) { return x !== "" }).join("\n")

  // The Details dialog (d): what Kodi knows about what plays, as a phone
  // remote's details screen. A new item starts it at the top again.
  readonly property var details: reachable ? service.details : null
  property bool detailsOpen: false
  readonly property string detailsTitle: details ? details.title : ""
  onDetailsTitleChanged: { detailsFlick.contentY = 0; castList.contentX = 0; detailsPlot.focusedLink = -1 }
  // The audio tracks: a opens their list while there is one or more, as on
  // the phone remote; while open it has the arrows.
  readonly property var audio: reachable ? service.audio : null
  property bool audioOpen: false
  property int audioSelected: -1        // a place in audio.tracks
  onAudioChanged: {
    if (!NowPlaying.audioListOpens(audio)) { audioOpen = false; return }
    audioSelected = Math.max(0, Math.min(audio.tracks.length - 1, audioSelected))
  }
  readonly property int audioAt: {  // where the playing track is in the list
    if (!audio) return -1
    for (var i = 0; i < audio.tracks.length; i++) if (audio.tracks[i].index === audio.current) return i
    return -1
  }
  onPlayingChanged: {
    var was = Date.now()
    if (!playing && shownPlaying)  // where it stopped, for the page's last moment
      shownPosition = Format.livePosition(positionBase, was - positionAt, shownPlaying.speed, shownPlaying.durationSec)
    nowMs = was
    positionBase = playing ? playing.positionSec : 0
    positionAt = nowMs
    if (playing) { shownPlaying = playing; nowCloseTimer.stop() }
    else if (nowOpen) nowCloseTimer.restart()
  }
  // Kodi's on-screen keyboard while it is open: its dialog opens over the
  // remote (KodiTextDialog).
  readonly property var kodiInput: reachable ? service.input : null
  onKodiInputChanged: if (kodiInput) closeNowPlaying()  // the dialog is over the remote

  // Shows `text`; it goes after a few seconds unless it is an error or
  // `sticky` (it waits for the next key: "Change which button?").
  function say(text, error, sticky) {
    var t = String(text || "")
    if (t === "") { hush(); return }
    toastText = t
    toastError = error === true
    toastShown = true
    var ms = sticky === true ? 0 : Toast.lasts(toastError)
    if (ms > 0) { toastTimer.interval = ms; toastTimer.restart() } else toastTimer.stop()
  }

  // The next action: the message goes, an error too.
  function hush() {
    toastTimer.stop()
    toastShown = false
  }

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
    themeColors.reload()
    root.hush()
    root.opened = true
    root.focusPrimed = false
    focusPrimeTimer.restart()
    if (root.kodiInput) kodiTextDialog.show(false)  // Kodi still asks for text
    Qt.callLater(root.focusKeys)
  }

  // The keyboard goes to the dialog for Kodi's keyboard while it is open,
  // else to the field of the page that has one, else to the remote's keys.
  function focusKeys() {
    if (!root.opened) return
    if (kodiTextDialog.shown) kodiTextDialog.take()
    else if (root.boxPage === "edit") root.focusEditorRow()
    else if (root.stripPage === "edit") root.focusEditRow()
    else if (root.stripPage === "send") sendField.forceActiveFocus()
    else keys.forceActiveFocus()
  }

  // The dialog's Send: the whole text, once, submitted (`done`). False when
  // the service refused it (the remote says why; the dialog stays).
  function sendKodiText(text) {
    if (!kodiInput) return false
    hush()
    var refused = service.sendText(text, true)
    if (refused) { say(refused, true); return false }
    return true
  }

  function kodiTextClosed() { focusKeys() }

  function clipboardText() { return String(Quickshell.clipboardText || "") }

  function close() {
    kodiTextDialog.hide()
    root.menuOpen = false
    root.powerOpen = false
    root.powerDialog = null
    root.boxPage = ""
    boxPassword.text = ""
    root.stripPage = ""
    root.stripSlot = -1
    root.stripArmed = false
    root.closeNowPlaying()
    root.opened = false
    root.focusPrimed = false
    focusPrimeTimer.stop()
    root.hush()
  }

  // Esc and the close button go through the host so its open state agrees.
  function dismiss() {
    if (shell && typeof shell.hide === "function" && shell.hide(pluginId)) return
    close()
  }

  function send(action, isRepeat) {
    if (!reachable) return
    if (isRepeat === true && RemoteKeys.oncePerPress(action)) return  // held: once per press
    hush()
    service.key(action, isRepeat === true)
  }

  // The keyboard key (Type text, k): the dialog again while Kodi asks for
  // text (after Cancel); the daemon asks Kodi when it hasn't seen its
  // keyboard open, or says Kodi isn't asking for text.
  function openKeyboard() {
    if (!reachable) return
    if (KodiInput.keyboardKey(kodiInput) === "open") { kodiTextDialog.show(false); return }
    hush()
    var refused = service.openKeyboard()
    if (refused) say(refused, true)
  }

  function seekTo(seconds) {
    if (!reachable || !canSeek) return
    var s = Math.max(0, Math.min(playing.durationSec, Math.round(seconds)))
    hush()
    var refused = service.seek(s)
    if (refused) { say(refused, true); return }
    nowMs = Date.now()  // show it there now; the next state confirms it
    positionBase = s
    positionAt = nowMs
  }

  // Details (d) is a dialog over the now-playing page; from the remote it
  // opens the page with it.
  function toggleDetails() {
    if (!nowOpen && !openNowPlaying()) return
    detailsOpen = !detailsOpen
    if (!detailsOpen) return
    queueOpen = false
    detailsFlick.contentY = 0
    castList.contentX = 0
    detailsPlot.focusedLink = -1
  }

  // Tab / Shift+Tab mark the plot's next or previous link and scroll it
  // into view; Enter opens the marked one (SPEC "Remote panel").
  function moveDetailsLink(dir) {
    var r = detailsPlot.moveFocus(dir)
    if (!r) return
    var margin = Style.space(24)
    var top = detailsPlot.y + r.y
    var bottom = top + r.height
    var y = detailsFlick.contentY
    if (top < y + margin) y = top - margin
    else if (bottom > y + detailsFlick.height - margin) y = bottom - detailsFlick.height + margin
    detailsFlick.contentY = Math.max(0, Math.min(y, Math.max(0, detailsFlick.contentHeight - detailsFlick.height)))
  }

  // A link in the plot, clicked or Enter: the default browser opens it
  // (xdg-open, the link its one argument, no shell; http and https only),
  // and the remote closes so the browser has the keyboard, as a phone
  // remote's tap leaves it for the browser.
  function openDetailsLink(url) {
    var command = PlotLinks.openCommand(url)
    if (!command) return
    Quickshell.execDetached(command)
    dismiss()
  }

  // Wake up (the power menu, or w): asks nothing first, since waking can't
  // harm. Without a known MAC address the daemon says how to get one.
  function wakeKodi() {
    if (!wakeOnLan) return
    hush()
    var refused = service.wake()
    if (refused) say(refused, true)
  }

  function toggleSettings() {
    if (settingsOpen) { closeSettings(); return }
    if (!connected) return
    closePowerMenu()
    closeNowPlaying()
    audioOpen = false
    settingsNow = Date.now()
    settingsSelected = youtube ? Math.max(0, youtubeModes.indexOf(youtube.mode)) : 0
    settingsOpen = true
  }

  function closeSettings() {
    settingsOpen = false
  }

  function moveSettingsSelection(step) {
    settingsSelected = Math.max(0, Math.min(settingsRows - 1, settingsSelected + step))
  }

  // A mode is saved at once, as a phone's radio buttons do.
  function pickSetting(at) {
    if (!connected || at < 0 || at >= settingsRows) return
    settingsSelected = at
    hush()
    var refused = at < youtubeModes.length ? service.setYoutubeMode(youtubeModes[at]) : service.youtubeRetry()
    if (refused) say(refused, true)
  }

  // ---- the shortcut strip -------------------------------------------------
  function closeOthers() {
    closeSettings()
    closePowerMenu()
    closeMenu()
    powerDialog = null
    audioOpen = false
    stripArmed = false
    closeNowPlaying()
  }

  function openStripButton(slot) {
    if (!reachable || slot < 0 || slot >= stripButtons.length) return
    hush()
    if (stripButtons[slot].sendLink) { openSendLink(); return }
    var refused = service.openShortcut(slot)
    if (refused) say(refused, true)
  }

  function openSendLink() {
    if (!reachable) return
    closeOthers()
    hush()
    // Starts with the clipboard's link, when it holds one.
    sendField.text = Protocol.extractLink(String(Quickshell.clipboardText || ""))
    sendText = sendField.text
    stripPage = "send"
    Qt.callLater(function() { sendField.forceActiveFocus(); sendField.cursorPosition = sendField.text.length })
  }

  function sendLink(queue) {
    if (!reachable || !Protocol.hasLink(sendText)) return
    var refused = queue ? service.queue(sendText) : service.play(sendText)
    closeStripPage()
    hush()
    if (refused) say(Toast.refusal(refused), true)
  }

  function pasteLink() {
    var clip = String(Quickshell.clipboardText || "")
    if (clip.trim() === "") return
    sendField.insert(sendField.cursorPosition, clip.slice(0, Protocol.MAX_LINK_TEXT))
    sendField.forceActiveFocus()
  }

  function clearLink() {
    sendField.text = ""
    sendText = ""
    sendField.forceActiveFocus()
  }

  // The page for changing button `slot`.
  function editStrip(slot) {
    if (!connected || slot < 0 || slot >= stripButtons.length) return
    closeOthers()
    hush()
    stripSlot = slot
    pathField.text = stripButtons[slot].typed
    typedPath = pathField.text
    editSelected = 0
    editButtonAt = editButtons.length - 1
    stripPage = "edit"
    Qt.callLater(focusEditRow)
  }

  function closeStripPage() {
    stripPage = ""
    stripSlot = -1
    focusKeys()
  }

  function focusEditRow() {
    if (stripPage !== "edit") return
    if (editRows[editSelected] === "path") pathField.forceActiveFocus()
    else keys.forceActiveFocus()
  }

  function moveEditSelection(step) {
    editSelected = Math.max(0, Math.min(editRows.length - 1, editSelected + step))
    focusEditRow()
  }

  // A change goes to the daemon, which keeps it for this box; the strip
  // shows it with the next state.
  function changeStrip(change) {
    if (stripSlot < 0) return
    var refused = service.setShortcut(stripSlot, change)
    closeStripPage()
    hush()
    if (refused) say(refused, true)
  }

  function savePath() {
    if (!canSavePath) return
    changeStrip(typedPath.trim() === "" ? { reset: true } : { path: typedPath })
  }

  function pickEditRow(at) {
    var row = editRows[at]
    editSelected = at
    if (row === "choose") openPicker()
    else if (row === "sendLink") changeStrip({ sendLink: true })
    else if (row === "icon") openIcons()
    else if (row === "path") savePath()
    else if (row === "buttons") pickEditButton(editButtons[editButtonAt])
  }

  function pickEditButton(what) {
    if (what === "reset") changeStrip({ reset: true })
    else if (what === "save") savePath()
    else closeStripPage()
  }

  function openPicker() {
    if (!connected) return
    pickerSelected = 0
    pickerWaiting = true
    stripPage = "picker"
    keys.forceActiveFocus()
    var refused = service.browse("root")
    if (refused) { pickerWaiting = false; say(refused, true) }
  }

  function pickerBack() {
    if (!pickerView || pickerView.depth <= 1) { stripPage = "edit"; Qt.callLater(focusEditRow); return }
    pickerSelected = 0
    pickerWaiting = true
    if (service.browse("back", pickerView.seq)) pickerWaiting = false
  }

  function movePickerSelection(step) {
    pickerSelected = Math.max(0, Math.min(pickerRows.length - 1, pickerSelected + step))
    pickerList.positionViewAtIndex(pickerSelected, ListView.Contain)
  }

  function pickPickerRow(at) {
    if (!pickerView || at < 0 || at >= pickerRows.length) return
    var row = pickerRows[at]
    pickerSelected = at
    if (row.kind === "folder") { changeStrip({ pick: { seq: pickerView.seq, index: -1 } }); return }
    if (row.kind === "retry") {
      pickerWaiting = true
      if (service.browse("reload", pickerView.seq)) pickerWaiting = false
      return
    }
    if (row.browse) {
      pickerSelected = 0
      pickerWaiting = true
      if (service.browse("open", pickerView.seq, row.index)) pickerWaiting = false
      return
    }
    changeStrip({ pick: { seq: pickerView.seq, index: row.index } })
  }

  function openIcons() {
    if (!editButton) return
    iconSelected = editButton.icon ? iconNames.indexOf(editButton.icon) + 1 : 0
    stripPage = "icons"
    keys.forceActiveFocus()
  }

  function pickIcon(at) {
    if (at < 0 || at > iconNames.length) return
    changeStrip({ icon: at === 0 ? "" : iconNames[at - 1] })
  }

  // The keys while a strip page is open; the text fields take their own.
  function stripKey(event) {
    var k = event.key
    var up = k === Qt.Key_Up, down = k === Qt.Key_Down
    var enter = (k === Qt.Key_Return || k === Qt.Key_Enter) && !event.isAutoRepeat
    if (stripPage === "send") {
      if (k === Qt.Key_Escape) closeStripPage()
      else if (enter) sendLink((event.modifiers & Qt.ShiftModifier) !== 0)
    } else if (stripPage === "edit") {
      if (k === Qt.Key_Escape) closeStripPage()
      else if (up || down) moveEditSelection(up ? -1 : 1)
      else if ((k === Qt.Key_Left || k === Qt.Key_Right) && editRows[editSelected] === "buttons")
        editButtonAt = Math.max(0, Math.min(editButtons.length - 1, editButtonAt + (k === Qt.Key_Left ? -1 : 1)))
      else if (enter) pickEditRow(editSelected)
    } else if (stripPage === "picker") {
      if (k === Qt.Key_Escape) { stripPage = "edit"; Qt.callLater(focusEditRow) }
      else if (up || down) movePickerSelection(up ? -1 : 1)
      else if (k === Qt.Key_Backspace || k === Qt.Key_Left) pickerBack()
      else if (enter || (k === Qt.Key_Right && pickerRows[pickerSelected] && pickerRows[pickerSelected].browse))
        pickPickerRow(pickerSelected)
    } else if (stripPage === "icons") {
      if (k === Qt.Key_Escape) { stripPage = "edit"; Qt.callLater(focusEditRow) }
      else if (enter) pickIcon(iconSelected)
      else if (up || down || k === Qt.Key_Left || k === Qt.Key_Right)
        iconSelected = Shortcuts.iconMove(iconSelected, k === Qt.Key_Left ? -1 : k === Qt.Key_Right ? 1 : 0,
                                          up ? -1 : down ? 1 : 0, iconColumns, iconNames.length)
    }
  }

  // ---- Kodi boxes --------------------------------------------------------------
  function boxIndex(id) {
    for (var i = 0; i < boxList.length; i++) if (boxList[i].id === id) return i
    return -1
  }

  function toggleBoxes() {
    if (boxPage !== "") { closeBoxPage(); return }
    if (!connected) return
    closeOthers()
    stripPage = ""
    stripSlot = -1
    hush()
    boxSelected = Math.max(0, boxIndex(currentBox))
    boxPage = "list"
    keys.forceActiveFocus()
    searchBoxes()
  }

  function closeBoxPage() {
    boxPage = ""
    boxPassword.text = ""
    focusKeys()
  }

  // Asks the network again, unless a search is running: the page keeps
  // looking while it is open, as a phone remote does.
  function searchBoxes() {
    if (foundView && foundView.status === "searching") return
    service.discover()
  }

  function moveBoxSelection(step) {
    boxSelected = Math.max(0, Math.min(boxRows.length - 1, boxSelected + step))
  }

  function pickBoxRow(at) {
    if (at < 0 || at >= boxRows.length) return
    var row = boxRows[at]
    boxSelected = at
    if (row.kind === "saved") useBox(boxList[row.at].id)
    else if (row.kind === "found") editBox(null, foundBoxes[row.at])
    else editBox(null, null)
  }

  // Picking a box switches to it and goes back to the remote.
  function useBox(id) {
    hush()
    if (id !== currentBox) {
      var refused = service.useBox(id)
      if (refused) { say(refused, true); return }
    }
    closeBoxPage()
  }

  // The editor, for a saved box, a found one (nothing sent to it yet), or a new one.
  function editBox(saved, found) {
    var b = saved || found || {}
    editKey = saved ? saved.id : ""
    editHasPassword = saved ? saved.hasPassword : false
    editKnownMac = saved ? saved.knownMac : ""
    boxName.text = b.name || ""
    boxHost.text = b.host || ""
    boxWeb.text = String(b.httpPort || 8080)
    boxLive.text = String(b.tcpPort || 9090)
    boxUser.text = saved ? saved.username : "kodi"
    boxPassword.text = ""
    passwordEdited = false
    boxMac.text = saved ? saved.mac : ""
    testStatus = ""
    testOk = false
    testing = false
    savingBox = false
    editorError = ""
    editorRow = 0
    editorButtonAt = editorButtons.length - 1
    boxPage = "edit"
    Qt.callLater(focusEditorRow)
  }

  function backToBoxList() {
    boxPassword.text = ""
    boxPage = "list"
    keys.forceActiveFocus()
  }

  function boxForm() {
    return { name: boxName.text, host: boxHost.text, httpPort: boxWeb.text, tcpPort: boxLive.text,
             username: boxUser.text, password: boxPassword.text, passwordEdited: passwordEdited, mac: boxMac.text }
  }

  function editorFields() { return [boxName, boxHost, boxWeb, boxLive, boxUser, boxPassword, boxMac] }

  function focusEditorRow() {
    if (boxPage !== "edit") return
    var fields = editorFields()
    if (editorRow < fields.length) fields[editorRow].take()
    else keys.forceActiveFocus()
  }

  function moveEditorRow(step) {
    editorRow = Math.max(0, Math.min(editorFields().length, editorRow + step))
    focusEditorRow()
  }

  function testBox() {
    if (formProblem !== "" || testing) return
    testing = true
    testOk = false
    testStatus = strings.t("boxes.testing")
    var refused = service.testBox(editKey, Boxes.fields(boxForm()))
    if (refused) { testing = false; testStatus = refused }
  }

  function saveBox() {
    if (formProblem !== "" || savingBox) return
    savingBox = true
    editorError = ""
    var refused = service.saveBox(editKey, Boxes.fields(boxForm()))
    if (refused) { savingBox = false; editorError = refused }
  }

  function deleteBox() {
    if (editKey === "" || savingBox) return
    savingBox = true
    editorError = ""
    var refused = service.deleteBox(editKey)
    if (refused) { savingBox = false; editorError = refused }
  }

  function pickEditorButton(what) {
    if (what === "test") testBox()
    else if (what === "delete") deleteBox()
    else saveBox()
  }

  // The keys while a box page is open; the editor's fields take their own.
  function boxKey(event) {
    var k = event.key
    var up = k === Qt.Key_Up, down = k === Qt.Key_Down
    var enter = (k === Qt.Key_Return || k === Qt.Key_Enter) && !event.isAutoRepeat
    if (boxPage === "list") {
      var row = boxRows[boxSelected]
      if (k === Qt.Key_Escape || event.text === "b") closeBoxPage()
      else if (up || down) moveBoxSelection(up ? -1 : 1)
      else if (enter) pickBoxRow(boxSelected)
      else if ((event.text === "e" || k === Qt.Key_Right) && row && row.kind === "saved") editBox(boxList[row.at], null)
    } else if (boxPage === "edit") {
      if (k === Qt.Key_Escape) backToBoxList()
      else if (up || down) moveEditorRow(up ? -1 : 1)
      else if (k === Qt.Key_Left || k === Qt.Key_Right)
        editorButtonAt = Math.max(0, Math.min(editorButtons.length - 1, editorButtonAt + (k === Qt.Key_Left ? -1 : 1)))
      else if (enter) pickEditorButton(editorButtons[editorButtonAt])
    }
  }

  // ---- the power menu and its dialog ------------------------------------------
  function togglePowerMenu() {
    if (!connected) return
    if (powerOpen) { closePowerMenu(); return }
    closeOthers()
    powerOpen = true
    powerSelected = 0
  }

  function closePowerMenu() {
    powerOpen = false
  }

  function movePowerSelection(step) {
    powerSelected = Math.max(0, Math.min(powerItems.length - 1, powerSelected + step))
  }

  // A pick closes the menu: Wake up, the soundbar and Kodi's power menu go
  // at once (the daemon answers when Kodi can't be reached), Reboot and
  // Shut down open the dialog.
  function pickPower(at) {
    if (!connected || at < 0 || at >= powerItems.length) return
    powerSelected = at
    var next = PowerMenu.pick(powerItems[at])
    closePowerMenu()
    if (next.ask) { powerDialog = PowerMenu.ask(next.ask); return }
    sendPower(next.send)
  }

  function sendPower(action) {
    if (!connected || action === "") return
    if (action === "wake") { wakeKodi(); return }
    hush()
    var refused = service.key(action, false)
    if (refused) say(refused, true)
  }

  // "left", "right", "tab", "enter", "escape", "cancel" or "confirm".
  function powerDialogKey(key) {
    var next = PowerMenu.dialogKey(powerDialog, key)
    powerDialog = next.dialog
    if (next.send) sendPower(next.send)
  }

  // ---- the ☰ menu ------------------------------------------------------------------
  function toggleMenu() {
    if (menuOpen) { closeMenu(); return }
    if (!connected) return
    closeOthers()
    hush()
    menuSelected = TopBar.menuStart(menuRows, currentBox)
    menuOpen = true
    keys.forceActiveFocus()
  }

  function closeMenu() {
    menuOpen = false
  }

  function moveMenuSelection(step) {
    menuSelected = TopBar.menuMove(menuSelected, step, menuRows.length)
  }

  // A box switches to it; Manage Kodi boxes and Settings open their pages.
  function pickMenuRow(at) {
    if (at < 0 || at >= menuRows.length) return
    var row = menuRows[at]
    menuSelected = at
    closeMenu()
    if (row.kind === "box") useBox(row.id)
    else if (row.kind === "manage") toggleBoxes()
    else if (row.kind === "settings") toggleSettings()
  }

  // The now-playing page, while something plays; it closes the remote's
  // lists and menus. Returns whether it is open.
  function openNowPlaying() {
    if (nowOpen) return true
    if (!playing) return false
    closeOthers()
    hush()
    shownPlaying = playing
    nowOpen = true
    return true
  }

  function closeNowPlaying() {
    nowCloseTimer.stop()
    nowOpen = false
    queueOpen = false
    queueLoading = false
    detailsOpen = false
  }

  function toggleNowPlaying() {
    if (nowOpen) closeNowPlaying()
    else openNowPlaying()
  }

  // The keys on the page (NowPlaying.pageKey): its buttons' actions, the
  // volume, d D u for its dialogs; Esc and n close a dialog, then the page.
  function nowPlayingKey(event) {
    var k = event.key
    if (queueOpen && !(event.modifiers & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier))) {
      if (k === Qt.Key_Up || k === Qt.Key_Down) { moveQueueSelection(k === Qt.Key_Up ? -1 : 1); return }
      if (k === Qt.Key_Return || k === Qt.Key_Enter) { if (!event.isAutoRepeat) pickQueueEntry(queueSelected); return }
      if (k === Qt.Key_Delete) { if (!event.isAutoRepeat) removeQueueEntry(queueSelected); return }
    }
    if (detailsOpen && !(event.modifiers & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier))) {
      if (k === Qt.Key_Tab || k === Qt.Key_Backtab) {
        moveDetailsLink(k === Qt.Key_Backtab || (event.modifiers & Qt.ShiftModifier) ? -1 : 1)
        return
      }
      if (k === Qt.Key_Return || k === Qt.Key_Enter) { if (!event.isAutoRepeat) detailsPlot.openFocused(); return }
      if (scrollDetails(k)) return
    }
    var hit = NowPlaying.pageKey(RemoteKeys.lookup(Util.readingKey(event), event.text, event.modifiers))
    if (!hit) return
    if (hit.close || hit.nowPlaying) {
      if (event.isAutoRepeat) return
      if (queueOpen || detailsOpen) { queueOpen = false; queueLoading = false; detailsOpen = false }
      else closeNowPlaying()
    }
    else if (hit.queueList) { if (!event.isAutoRepeat) toggleQueue() }
    else if (hit.details) { if (!event.isAutoRepeat) toggleDetails() }
    else if (hit.control) send(hit.control, event.isAutoRepeat)
  }

  // Up/Down (PgUp/PgDn a page, Home/End) scroll the Details dialog,
  // Left/Right its cast. Returns whether the key was one of those.
  function scrollDetails(k) {
    var step = Style.space(48)
    var page = Math.max(step, detailsFlick.height - step)
    var y = detailsFlick.contentY
    if (k === Qt.Key_Up) y -= step
    else if (k === Qt.Key_Down) y += step
    else if (k === Qt.Key_PageUp) y -= page
    else if (k === Qt.Key_PageDown) y += page
    else if (k === Qt.Key_Home) y = 0
    else if (k === Qt.Key_End) y = detailsFlick.contentHeight
    else if (k === Qt.Key_Left || k === Qt.Key_Right) {
      var x = castList.contentX + (k === Qt.Key_Left ? -1 : 1) * (castList.cardWidth + castList.spacing)
      castList.contentX = Math.max(0, Math.min(x, Math.max(0, castList.contentWidth - castList.width)))
      return true
    }
    else return false
    detailsFlick.contentY = Math.max(0, Math.min(y, Math.max(0, detailsFlick.contentHeight - detailsFlick.height)))
    return true
  }

  function toggleAudioList() {
    if (!reachable || !playing) return
    if (!NowPlaying.audioListOpens(audio)) { say(strings.t("remote.noAudioTrack"), false); return }
    audioOpen = !audioOpen
    closePowerMenu()
    if (audioOpen) {
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
    hush()
    var refused = service.setAudioTrack(audio.tracks[at].index)
    if (refused) say(refused, true)
  }

  // Queue (u) is a dialog over the now-playing page, there whether or not
  // what plays is from the queue. It reads the state again first and says
  // "Loading…" until the daemon has answered, as a phone remote asks Kodi.
  function toggleQueue() {
    if (!nowOpen && !openNowPlaying()) return
    queueOpen = !queueOpen
    queueLoading = false
    if (!queueOpen) return
    detailsOpen = false
    queueSelected = queue ? queue.position : -1
    if (service && service.refresh() === "") {
      queueLoading = true
      queueLoadingTimer.restart()
    } else showQueuePosition()
  }

  function showQueuePosition() {
    if (!queue || !queueOpen) return
    Qt.callLater(function() {
      if (root.queue) queueList.positionViewAtIndex(root.queueSelected - root.queue.start, ListView.Center)
    })
  }

  function queueLoaded() {
    if (!queueLoading) return
    queueLoading = false
    queueLoadingTimer.stop()
    showQueuePosition()
  }

  // A click or Enter plays the entry and closes the dialog, as on a phone remote.
  function pickQueueEntry(position) {
    if (!queue || position < queue.start || position >= queue.start + queue.items.length) return
    queueSelected = position
    queueOpen = false
    playQueueEntry(position)
  }

  function moveQueueSelection(step) {
    if (!queue || queue.items.length === 0) return
    var first = queue.start, last = queue.start + queue.items.length - 1
    queueSelected = Math.max(first, Math.min(last, queueSelected + step))
    queueList.positionViewAtIndex(queueSelected - first, ListView.Contain)
  }

  function playQueueEntry(position) {
    if (!reachable) return
    hush()
    var refused = service.playQueueEntry(position)
    if (refused) say(refused, true)
  }

  function removeQueueEntry(position) {
    if (!reachable || !queue || position === queue.position) return
    hush()
    var refused = service.removeQueueEntry(position)
    if (refused) say(refused, true)
  }

  function sendClipboard(cmd) {
    if (!reachable) return
    var text = String(Quickshell.clipboardText || "")
    if (text.trim() === "") { say(strings.t("remote.clipboardEmpty"), false); return }
    hush()
    var refused = cmd === "queue" ? service.queue(text) : service.play(text)
    if (refused) say(Toast.refusal(refused), true)
  }

  Commons.Translations { id: strings; directory: Qt.resolvedUrl("i18n") }

  // The editor follows the daemon's answers: a test's verdict (and what it
  // learnt: Kodi's name and MAC address fill empty fields, as on a phone
  // remote), and back to the boxes once saved or deleted.
  Connections {
    target: root.service
    function onResultArrived(r) {
      var shown = Toast.fromResult(r, root.savingBox)
      if (shown) root.say(shown.text, shown.error)
      if (r.cmd === "boxTest" && root.testing) {
        root.testing = false
        root.testOk = r.ok
        root.testStatus = r.text
      } else if ((r.cmd === "boxSave" || r.cmd === "boxDelete") && root.savingBox) {
        root.savingBox = false
        if (!r.ok) root.editorError = r.text
        else if (root.boxPage === "edit") root.backToBoxList()
      } else if (r.cmd === "refresh") {
        root.queueLoaded()  // the Queue dialog has the fresh state now
      }
    }
    function onProgressTextChanged() {  // a play's step, as a short message too
      if (root.service.progressText) root.say(root.service.progressText, false)
    }
    function onBoxTestedChanged() {
      var t = root.service ? root.service.boxTested : null
      if (!t || root.boxPage !== "edit" || !root.testing) return
      if (boxName.text.trim() === "" && t.name) boxName.text = t.name
      if (boxMac.text.trim() === "" && t.mac) boxMac.text = t.mac
    }
  }

  // The search runs again while the Kodi boxes page is open.
  Timer {
    interval: 15000
    repeat: true
    running: root.opened && root.boxPage === "list"
    onTriggered: root.searchBoxes()
  }

  // Smart mode's wait runs out by itself: the page follows the clock.
  Timer {
    interval: 1000
    repeat: true
    running: root.settingsOpen && root.smartWaiting
    onTriggered: root.settingsNow = Date.now()
  }

  Timer {
    interval: 1000
    repeat: true
    running: root.opened && root.playing !== null
    onTriggered: root.nowMs = Date.now()
  }

  // The now-playing page shows the last item a moment after playback stops,
  // as on a phone remote, then closes; something new playing keeps it open.
  // The short message goes by itself (an error waits for the next action).
  Timer {
    id: toastTimer
    interval: Toast.SHOW_MS
    onTriggered: root.toastShown = false
  }
  Timer {
    id: nowCloseTimer
    interval: 2500
    onTriggered: if (!root.playing) root.closeNowPlaying()
  }
  // The Queue dialog's "Loading…" never stays: a slow answer shows the queue
  // the remote has.
  Timer {
    id: queueLoadingTimer
    interval: 4000
    onTriggered: root.queueLoaded()
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
      implicitHeight: Math.max(content.implicitHeight,
                               root.settingsOpen ? settingsPage.implicitHeight : 0,
                               root.nowOpen ? nowPage.implicitHeight : 0,
                               root.stripPage !== "" ? stripPages.implicitHeight : 0,
                               root.boxPage !== "" ? boxPages.implicitHeight : 0,
                               root.menuOpen ? menuLayer.implicitHeight - padding * 2 : 0) + padding * 2

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
          if (kodiTextDialog.shown) {  // Kodi's keyboard: nothing else until it closes
            if (kodiTextDialog.fieldFocused) return  // keys its field leaves aren't remote keys
            event.accepted = true
            if (event.key === Qt.Key_Escape) kodiTextDialog.act("cancel")
            else if ((event.key === Qt.Key_Return || event.key === Qt.Key_Enter) && !event.isAutoRepeat) kodiTextDialog.act("send")
            else kodiTextDialog.take()
            return
          }
          if (root.powerDialog !== null) {  // "Reboot <box>?": nothing else until it is answered
            event.accepted = true
            if (event.isAutoRepeat) return
            var dk = event.key
            if (dk === Qt.Key_Left || dk === Qt.Key_Right) {
              var lk = Util.readingKey(event)
              root.powerDialogKey(lk === Qt.Key_Left ? "left" : "right")
            }
            else if (dk === Qt.Key_Tab || dk === Qt.Key_Backtab) root.powerDialogKey("tab")
            else if (dk === Qt.Key_Return || dk === Qt.Key_Enter) root.powerDialogKey("enter")
            else if (dk === Qt.Key_Escape) root.powerDialogKey("escape")
            return
          }
          if (root.menuOpen) {  // the ☰ menu has the keys while open
            event.accepted = true
            var mk = event.key
            if (mk === Qt.Key_Up || mk === Qt.Key_Down) root.moveMenuSelection(mk === Qt.Key_Up ? -1 : 1)
            else if ((mk === Qt.Key_Return || mk === Qt.Key_Enter) && !event.isAutoRepeat) root.pickMenuRow(root.menuSelected)
            else if (mk === Qt.Key_Escape || event.text === "M") root.closeMenu()
            return
          }
          if (root.boxPage !== "") {  // a page of its own: the remote's keys wait
            event.accepted = true
            root.boxKey(event)
            return
          }
          if (root.stripPage !== "") {  // a page of its own: the remote's keys wait
            event.accepted = true
            root.stripKey(event)
            return
          }
          if (root.stripArmed) {  // e, then 1-5: change that button
            event.accepted = true
            if (event.key === Qt.Key_Shift || event.key === Qt.Key_Control || event.key === Qt.Key_Alt) return
            root.stripArmed = false
            root.hush()
            var slot = RemoteKeys.stripSlot(event.text)
            if (slot >= 0) root.editStrip(slot)
            return
          }
          if (root.settingsOpen) {  // a page of its own: the remote's keys wait
            event.accepted = true
            var sk = event.key
            if (sk === Qt.Key_Up || sk === Qt.Key_Down) root.moveSettingsSelection(sk === Qt.Key_Up ? -1 : 1)
            else if ((sk === Qt.Key_Return || sk === Qt.Key_Enter) && !event.isAutoRepeat) root.pickSetting(root.settingsSelected)
            else if (sk === Qt.Key_Escape || sk === Qt.Key_Backspace || event.text === "S") root.closeSettings()
            return
          }
          if (root.nowOpen) {  // the now-playing page: its own keys, and its dialogs
            event.accepted = true
            root.nowPlayingKey(event)
            return
          }
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
          var hit = RemoteKeys.lookup(Util.readingKey(event), event.text, event.modifiers)
          if (!hit) return
          event.accepted = true
          if (hit.queueList) { if (!event.isAutoRepeat) root.toggleQueue() }
          else if (hit.details) { if (!event.isAutoRepeat) root.toggleDetails() }
          else if (hit.audioList) { if (!event.isAutoRepeat) root.toggleAudioList() }
          else if (hit.nowPlaying) { if (!event.isAutoRepeat) root.toggleNowPlaying() }
          else if (hit.powerMenu) { if (!event.isAutoRepeat) root.togglePowerMenu() }
          else if (hit.wake) { if (!event.isAutoRepeat) root.wakeKodi() }
          else if (hit.settings) { if (!event.isAutoRepeat) root.toggleSettings() }
          else if (hit.boxes) { if (!event.isAutoRepeat) root.toggleBoxes() }
          else if (hit.menu) { if (!event.isAutoRepeat) root.toggleMenu() }
          else if (hit.keyboard) { if (!event.isAutoRepeat) root.openKeyboard() }
          else if (hit.shortcut !== undefined) { if (!event.isAutoRepeat) root.openStripButton(hit.shortcut) }
          else if (hit.editStrip) {
            if (!event.isAutoRepeat && root.connected) { root.closeOthers(); root.stripArmed = true; root.say(strings.t("strip.which"), false, true) }
          }
          else if (hit.close) root.dismiss()
          else if (hit.control) root.send(hit.control, event.isAutoRepeat)
          else if (hit.link && !event.isAutoRepeat) root.sendClipboard(hit.link)
        }

        // ---- the now-playing page: over the remote, like a phone remote's ------
        Item {
          id: nowPage
          z: 9
          x: card.padding
          y: card.padding
          width: card.width - card.padding * 2
          height: card.height - card.padding * 2
          // The artwork takes the room the remote leaves; at least this much.
          implicitHeight: nowTop.height + Style.space(180) + nowSeek.implicitHeight + nowControls.height
            + Style.spacing.md * 3
          visible: root.nowOpen && root.shownPlaying !== null
          readonly property var item: root.shownPlaying
          readonly property real length: item ? item.durationSec : 0
          Rectangle {  // covers the remote, its poster included
            x: -card.padding
            y: -card.padding
            width: card.width
            height: card.height
            radius: card.radius
            color: card.color
          }
          MouseArea {  // clicks and the wheel stay on the page
            anchors.fill: parent
            acceptedButtons: Qt.AllButtons
            onWheel: function(wheel) { wheel.accepted = true }
          }
          // The top bar: close, the title and subtitle, Details, Queue.
          Item {
            id: nowTop
            width: parent.width
            height: Math.max(nowClose.implicitHeight, nowTitles.implicitHeight)
            Button {
              id: nowClose
              anchors.left: parent.left
              anchors.verticalCenter: parent.verticalCenter
              iconText: String.fromCodePoint(0xF0140)
              tooltipText: strings.t("nowPlaying.close")
              onClicked: root.closeNowPlaying()
            }
            Column {
              id: nowTitles
              anchors.left: nowClose.right
              anchors.leftMargin: Style.spacing.xs
              anchors.right: nowDetails.left
              anchors.rightMargin: Style.spacing.xs
              anchors.verticalCenter: parent.verticalCenter
              Text {
                width: parent.width
                textFormat: Text.PlainText
                elide: Text.ElideRight
                font.family: Style.font.family
                font.pixelSize: Style.font.heading
                color: Commons.Color.popups.text
                text: nowPage.item ? (nowPage.item.title || strings.t("remote.nothingPlaying")) : ""
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
                text: nowPage.item ? nowPage.item.subtitle : ""
              }
            }
            Button {
              id: nowDetails
              anchors.right: nowQueue.left
              anchors.verticalCenter: parent.verticalCenter
              iconText: String.fromCodePoint(0xF02FD)
              tooltipText: strings.t("key.details")
              onClicked: root.toggleDetails()
            }
            Button {
              id: nowQueue
              anchors.right: parent.right
              anchors.verticalCenter: parent.verticalCenter
              iconText: String.fromCodePoint(0xF0411)
              tooltipText: strings.t("key.queueList")
              onClicked: root.toggleQueue()
            }
          }
          // The artwork, large and cropped, fading into the page at the
          // bottom; a film icon without art. Fixed decoding size only: an
          // image sized from its own picture was a binding loop that crashed
          // the shell.
          Item {
            id: nowArt
            anchors.top: nowTop.bottom
            anchors.topMargin: Style.spacing.md
            anchors.bottom: nowSeek.top
            anchors.bottomMargin: Style.spacing.md
            width: parent.width
            clip: true
            Image {
              id: nowArtImage
              anchors.fill: parent
              visible: status === Image.Ready
              source: root.nowOpen && nowPage.item && nowPage.item.art !== "" ? "file://" + nowPage.item.art : ""
              fillMode: Image.PreserveAspectCrop
              asynchronous: true
              cache: false
              sourceSize.width: 600
            }
            Rectangle {
              anchors.left: parent.left
              anchors.right: parent.right
              anchors.bottom: parent.bottom
              height: parent.height / 4
              visible: nowArtImage.visible
              gradient: Gradient {
                GradientStop { position: 0; color: Qt.rgba(card.color.r, card.color.g, card.color.b, 0) }
                GradientStop { position: 1; color: card.color }
              }
            }
            Text {
              anchors.centerIn: parent
              visible: !nowArtImage.visible
              textFormat: Text.PlainText
              text: String.fromCodePoint(0xF0DCE)
              color: Commons.Color.popups.text
              opacity: 0.25
              font.family: Style.font.family
              font.pixelSize: Style.space(120)
            }
          }
          // The seek bar, and under it the elapsed time (in the accent colour
          // while dragging), Paused or the speed, the length and when it ends.
          Column {
            id: nowSeek
            anchors.bottom: nowControls.top
            anchors.bottomMargin: Style.spacing.md
            width: parent.width
            spacing: Style.spacing.xs
            PanelSlider {
              id: nowSlider
              width: parent.width
              enabled: root.canSeek
              opacity: enabled ? 1 : 0.4
              minimum: 0
              maximum: nowPage.length > 0 ? nowPage.length : 1
              value: nowPage.length > 0 ? root.pagePosition : 0
              step: 10  // the wheel: 10 s a notch
              trackColor: Qt.rgba(Commons.Color.popups.text.r, Commons.Color.popups.text.g,
                                  Commons.Color.popups.text.b, 0.2)
              fillColor: Commons.Color.accent
              knobColor: Commons.Color.accent
              onReleased: function(value) { root.seekTo(value) }
              PanelToolTip { text: strings.t("key.seek"); visible: nowSlider._hot && !nowSlider.dragging }
            }
            Item {
              width: parent.width
              height: nowElapsed.implicitHeight
              Text {
                id: nowElapsed
                anchors.left: parent.left
                textFormat: Text.PlainText
                font.family: Style.font.family
                font.pixelSize: Style.font.bodySmall
                font.bold: nowSlider.dragging
                color: nowSlider.dragging ? Commons.Color.accent : Commons.Color.popups.text
                text: Format.clock(nowSlider.dragging ? nowSlider.liveValue : root.pagePosition, nowPage.length)
              }
              Text {
                anchors.left: nowElapsed.right
                anchors.right: nowEnds.left
                anchors.margins: Style.spacing.xs
                horizontalAlignment: Text.AlignHCenter
                textFormat: Text.PlainText
                elide: Text.ElideRight
                font.family: Style.font.family
                font.pixelSize: Style.font.bodySmall
                color: Commons.Color.popups.text
                opacity: 0.7
                text: Format.speedLine(nowPage.item, strings.t("nowPlaying.paused"), strings.t("nowPlaying.speed"))
              }
              Text {
                id: nowEnds
                anchors.right: parent.right
                textFormat: Text.PlainText
                font.family: Style.font.family
                font.pixelSize: Style.font.bodySmall
                color: Commons.Color.popups.text
                opacity: 0.7
                text: Format.endLine(root.pagePosition, nowPage.length, root.nowMs, strings.t("nowPlaying.ends"))
              }
            }
          }
          // Previous, rewind, play/pause (large), fast-forward, next.
          Item {
            id: nowControls
            anchors.bottom: parent.bottom
            width: parent.width
            height: Style.space(64)
            enabled: root.reachable && root.playing !== null
            Row {
              anchors.centerIn: parent
              spacing: Style.spacing.sm
              Button {
                anchors.verticalCenter: parent.verticalCenter
                iconText: String.fromCodePoint(0xF04AE)
                iconSize: Style.font.icon * 1.3
                tooltipText: strings.t("key.previous")
                onClicked: root.send("previous", false)
              }
              Button {
                anchors.verticalCenter: parent.verticalCenter
                iconText: String.fromCodePoint(0xF045F)
                iconSize: Style.font.icon * 1.3
                tooltipText: strings.t("key.rewind")
                onClicked: root.send("rewind", false)
              }
              Rectangle {
                id: nowPlayKey
                anchors.verticalCenter: parent.verticalCenter
                width: Style.space(60)
                height: Style.space(60)
                radius: width / 2
                color: Qt.rgba(Commons.Color.popups.text.r, Commons.Color.popups.text.g,
                               Commons.Color.popups.text.b, nowPlayMouse.containsMouse ? 0.16 : 0.08)
                opacity: nowControls.enabled ? 1 : 0.4
                Text {
                  anchors.centerIn: parent
                  textFormat: Text.PlainText
                  text: String.fromCodePoint(NowPlaying.showsPause(root.playing) ? 0xF03E4 : 0xF040A)
                  color: Commons.Color.popups.text
                  font.family: Style.font.family
                  font.pixelSize: Style.space(30)
                }
                MouseArea {
                  id: nowPlayMouse
                  anchors.fill: parent
                  hoverEnabled: true
                  cursorShape: Qt.PointingHandCursor
                  onClicked: root.send("playpause", false)
                }
                PanelToolTip { text: strings.t("key.playpause"); visible: nowPlayMouse.containsMouse }
              }
              Button {
                anchors.verticalCenter: parent.verticalCenter
                iconText: String.fromCodePoint(0xF0211)
                iconSize: Style.font.icon * 1.3
                tooltipText: strings.t("key.fastforward")
                onClicked: root.send("fastforward", false)
              }
              Button {
                anchors.verticalCenter: parent.verticalCenter
                iconText: String.fromCodePoint(0xF04AD)
                iconSize: Style.font.icon * 1.3
                tooltipText: strings.t("key.next")
                onClicked: root.send("next", false)
              }
            }
          }

          // ---- a dialog over the page: Queue or Details, with Close -----------
          Item {
            z: 5
            anchors.fill: parent
            visible: root.queueOpen || root.detailsOpen
            Rectangle {
              x: -card.padding
              y: -card.padding
              width: card.width
              height: card.height
              radius: card.radius
              color: "black"
              opacity: 0.45
            }
            MouseArea {  // a click beside the dialog closes it
              anchors.fill: parent
              acceptedButtons: Qt.AllButtons
              onPressed: { root.queueOpen = false; root.queueLoading = false; root.detailsOpen = false }
              onWheel: function(wheel) { wheel.accepted = true }
            }
            Rectangle {
              anchors.centerIn: parent
              width: parent.width
              height: Math.min(parent.height, (root.detailsOpen ? detailsPane.naturalHeight
                : nowDialogColumn.implicitHeight) + card.padding * 2)
              radius: card.radius
              color: card.color
              clip: true
              border.width: 1
              border.color: Qt.rgba(Commons.Color.popups.text.r, Commons.Color.popups.text.g, Commons.Color.popups.text.b, 0.2)
              MouseArea {
                anchors.fill: parent
                acceptedButtons: Qt.AllButtons
                onWheel: function(wheel) { wheel.accepted = true }
              }
              Column {
                id: nowDialogColumn
                visible: root.queueOpen
                x: card.padding
                y: card.padding
                width: parent.width - card.padding * 2
                spacing: Style.spacing.md
                readonly property string queueStatus: NowPlaying.queueStatus(root.queue, root.queueLoading)
                Text {
                  width: parent.width
                  textFormat: Text.PlainText
                  elide: Text.ElideRight
                  text: strings.t("queue.title")
                  color: Commons.Color.popups.text
                  font.family: Style.font.family
                  font.pixelSize: Style.font.title
                }
                // The queue: Loading…, empty, or its entries.
                Text {
                  width: parent.width
                  visible: root.queueOpen && nowDialogColumn.queueStatus !== "ready"
                  textFormat: Text.PlainText
                  wrapMode: Text.Wrap
                  font.family: Style.font.family
                  font.pixelSize: Style.font.body
                  color: Commons.Color.popups.text
                  opacity: 0.7
                  text: strings.t(nowDialogColumn.queueStatus === "loading" ? "queue.loading" : "queue.empty")
                }
                ListView {
                  id: queueList
                  width: parent.width
                  visible: root.queueOpen && nowDialogColumn.queueStatus === "ready"
                  readonly property real rowHeight: Style.space(44)
                  height: Math.min(count, 7) * rowHeight
                  clip: true
                  boundsBehavior: Flickable.StopAtBounds
                  model: root.queueOpen ? NowPlaying.queueRows(root.queue) : []
                  delegate: Item {
                    id: entry
                    required property var modelData
                    readonly property bool isSelected: modelData.position === root.queueSelected
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
                      cursorShape: Qt.PointingHandCursor
                      onClicked: root.pickQueueEntry(entry.modelData.position)
                    }
                    Column {
                      anchors.left: parent.left
                      anchors.leftMargin: Style.spacing.sm
                      anchors.right: removeButton.left
                      anchors.verticalCenter: parent.verticalCenter
                      Text {
                        width: parent.width
                        textFormat: Text.PlainText
                        elide: Text.ElideRight
                        font.family: Style.font.family
                        font.pixelSize: Style.font.body
                        font.bold: entry.modelData.playing
                        color: entry.modelData.playing ? Commons.Color.accent : Commons.Color.popups.text
                        text: entry.modelData.label
                      }
                      Text {
                        width: parent.width
                        visible: text !== ""
                        textFormat: Text.PlainText
                        elide: Text.ElideRight
                        font.family: Style.font.family
                        font.pixelSize: Style.font.bodySmall
                        color: Commons.Color.popups.text
                        opacity: 0.6
                        text: entry.modelData.detail
                      }
                    }
                    Button {
                      id: removeButton
                      anchors.right: parent.right
                      anchors.verticalCenter: parent.verticalCenter
                      visible: entry.modelData.removable && (entry.isSelected || rowMouse.containsMouse || removeButton.hot)
                      iconText: String.fromCodePoint(0xF0156)
                      tooltipText: strings.t("key.queueRemove")
                      onClicked: root.removeQueueEntry(entry.modelData.position)
                    }
                  }
                }
                PageHint {
                  visible: queueList.visible
                  text: strings.t("remote.queueHint")
                }
                Item {
                  width: parent.width
                  height: nowDialogClose.implicitHeight
                  Button {
                    id: nowDialogClose
                    anchors.right: parent.right
                    text: strings.t("dialog.close")
                    onClicked: { root.queueOpen = false; root.queueLoading = false; root.detailsOpen = false }
                  }
                }
              }
              // Details, as a phone remote's: the title and subtitle, Overview
              // (the whole plot), the badges, Info (a row per field, with its
              // icon), Cast (cards with photo, name and role); all of it
              // scrolls, Close stays at the bottom. Fields Kodi doesn't have
              // are left out.
              Item {
                id: detailsPane
                visible: root.detailsOpen
                x: card.padding
                y: card.padding
                width: parent.width - card.padding * 2
                height: parent.height - card.padding * 2
                readonly property var d: root.details
                readonly property real naturalHeight: detailsContent.implicitHeight + Style.spacing.md
                  + detailsClose.implicitHeight
                Flickable {
                  id: detailsFlick
                  width: parent.width
                  height: Math.max(0, parent.height - detailsClose.implicitHeight - Style.spacing.md)
                  contentWidth: width
                  contentHeight: detailsContent.implicitHeight
                  clip: true
                  interactive: contentHeight > height
                  boundsBehavior: Flickable.StopAtBounds
                  Column {
                    id: detailsContent
                    width: detailsFlick.width
                    spacing: Style.spacing.xs
                    Text {
                      width: parent.width
                      textFormat: Text.PlainText
                      wrapMode: Text.Wrap
                      font.family: Style.font.family
                      font.pixelSize: Style.font.title
                      color: Commons.Color.popups.text
                      text: detailsPane.d && detailsPane.d.title ? detailsPane.d.title
                        : (nowPage.item ? (nowPage.item.title || strings.t("remote.nothingPlaying")) : "")
                    }
                    Text {
                      width: parent.width
                      visible: text !== ""
                      textFormat: Text.PlainText
                      wrapMode: Text.Wrap
                      font.family: Style.font.family
                      font.pixelSize: Style.font.bodySmall
                      color: Commons.Color.popups.text
                      opacity: 0.7
                      text: detailsPane.d ? detailsPane.d.subtitle : (nowPage.item ? nowPage.item.subtitle : "")
                    }
                    Text {
                      width: parent.width
                      visible: detailsPane.d === null
                      topPadding: Style.spacing.md
                      textFormat: Text.PlainText
                      wrapMode: Text.Wrap
                      font.family: Style.font.family
                      font.pixelSize: Style.font.bodySmall
                      color: Commons.Color.popups.text
                      opacity: 0.7
                      text: strings.t("remote.noDetails")
                    }
                    DetailsHeading {
                      visible: detailsPane.d !== null && detailsPane.d.plot !== ""
                      text: strings.t("details.overview")
                    }
                    DetailsPlot {
                      id: detailsPlot
                      width: parent.width
                      visible: detailsPane.d !== null && detailsPane.d.plot !== ""
                      plot: detailsPane.d ? detailsPane.d.plot : ""
                      styles: detailsPane.d ? detailsPane.d.plotStyles : []
                      linkColor: Commons.Color.accent
                      focusedColor: card.color
                      onOpenLink: function(url) { root.openDetailsLink(url) }
                    }
                    // The badges, centred: a Flow as wide as they are in a row
                    // (measured by a hidden Row), at most the dialog's width.
                    Item {
                      width: parent.width
                      visible: detailsPane.d !== null && detailsPane.d.badges.length > 0
                      height: badgeFlow.height + Style.spacing.md
                      Row {
                        id: badgeMeasure
                        visible: false
                        spacing: Style.spacing.sm
                        Repeater {
                          model: detailsPane.d ? detailsPane.d.badges : []
                          delegate: DetailsBadge { required property var modelData; label: modelData }
                        }
                      }
                      Flow {
                        id: badgeFlow
                        y: Style.spacing.md
                        anchors.horizontalCenter: parent.horizontalCenter
                        width: Math.min(parent.width, badgeMeasure.implicitWidth)
                        spacing: Style.spacing.sm
                        Repeater {
                          model: detailsPane.d ? detailsPane.d.badges : []
                          delegate: DetailsBadge { required property var modelData; label: modelData }
                        }
                      }
                    }
                    DetailsHeading {
                      visible: detailsPane.d !== null && detailsPane.d.info.length > 0
                      text: strings.t("details.info")
                    }
                    Repeater {
                      model: detailsPane.d ? detailsPane.d.info : []
                      delegate: Item {
                        id: infoRow
                        required property var modelData
                        width: detailsContent.width
                        height: Math.max(infoText.implicitHeight, infoIcon.implicitHeight) + Style.spacing.md * 2
                        Text {
                          id: infoIcon
                          anchors.left: parent.left
                          anchors.verticalCenter: parent.verticalCenter
                          width: Style.space(28)
                          textFormat: Text.PlainText
                          font.family: Style.font.family
                          font.pixelSize: Style.font.title
                          color: Commons.Color.accent
                          text: String.fromCodePoint(NowPlaying.infoIcon(infoRow.modelData.kind))
                        }
                        Text {
                          id: infoText
                          anchors.left: infoIcon.right
                          anchors.leftMargin: Style.spacing.md
                          anchors.right: parent.right
                          anchors.verticalCenter: parent.verticalCenter
                          textFormat: Text.PlainText
                          wrapMode: Text.Wrap
                          font.family: Style.font.family
                          font.pixelSize: Style.font.body
                          color: Commons.Color.popups.text
                          text: infoRow.modelData.text
                        }
                        Rectangle {  // the divider under the text, as on the phone
                          anchors.left: infoText.left
                          anchors.right: parent.right
                          anchors.bottom: parent.bottom
                          height: 1
                          color: Commons.Color.popups.text
                          opacity: 0.12
                        }
                      }
                    }
                    DetailsHeading {
                      visible: castList.count > 0
                      text: strings.t("details.cast")
                    }
                    // The cast: a row of cards, photo (a person icon without
                    // one), the name and role over a dark fade. Fixed card and
                    // decoding sizes: no size comes from the picture.
                    ListView {
                      id: castList
                      readonly property real cardWidth: Style.space(96)
                      width: parent.width
                      height: count > 0 ? Style.space(136) : 0
                      visible: count > 0
                      orientation: ListView.Horizontal
                      spacing: Style.spacing.sm
                      clip: true
                      boundsBehavior: Flickable.StopAtBounds
                      model: detailsPane.d ? detailsPane.d.cast : []
                      delegate: Rectangle {
                        id: castCard
                        required property var modelData
                        width: castList.cardWidth
                        height: castList.height
                        radius: Style.cornerRadius
                        clip: true
                        color: Qt.rgba(Commons.Color.popups.text.r, Commons.Color.popups.text.g,
                                       Commons.Color.popups.text.b, 0.08)
                        Image {
                          id: castPhoto
                          anchors.fill: parent
                          visible: status === Image.Ready
                          source: castCard.modelData.photo !== "" ? "file://" + castCard.modelData.photo : ""
                          fillMode: Image.PreserveAspectCrop
                          asynchronous: true
                          cache: false
                          sourceSize.width: 192
                          sourceSize.height: 272
                        }
                        Text {
                          anchors.horizontalCenter: parent.horizontalCenter
                          y: Math.round(parent.height * 0.22)
                          visible: !castPhoto.visible
                          textFormat: Text.PlainText
                          font.family: Style.font.family
                          font.pixelSize: Style.space(48)
                          color: Commons.Color.popups.text
                          opacity: 0.35
                          text: String.fromCodePoint(0xF0013)
                        }
                        Rectangle {
                          anchors.left: parent.left
                          anchors.right: parent.right
                          anchors.bottom: parent.bottom
                          height: castNames.implicitHeight + Style.spacing.md * 2
                          gradient: Gradient {
                            GradientStop { position: 0; color: Qt.rgba(0.06, 0.06, 0.08, 0) }
                            GradientStop { position: 1; color: Qt.rgba(0.06, 0.06, 0.08, 0.9) }
                          }
                        }
                        Column {
                          id: castNames
                          anchors.left: parent.left
                          anchors.right: parent.right
                          anchors.bottom: parent.bottom
                          anchors.margins: Style.spacing.sm
                          Text {
                            width: parent.width
                            textFormat: Text.PlainText
                            elide: Text.ElideRight
                            font.family: Style.font.family
                            font.pixelSize: Style.font.bodySmall
                            color: "white"
                            text: castCard.modelData.name
                          }
                          Text {
                            width: parent.width
                            visible: text !== ""
                            textFormat: Text.PlainText
                            elide: Text.ElideRight
                            font.family: Style.font.family
                            font.pixelSize: Math.max(1, Style.font.bodySmall - 1)
                            color: Qt.rgba(0.79, 0.77, 0.82, 1)
                            text: castCard.modelData.role
                          }
                        }
                      }
                    }
                  }
                }
                Button {
                  id: detailsClose
                  anchors.right: parent.right
                  anchors.bottom: parent.bottom
                  text: strings.t("dialog.close")
                  onClicked: root.detailsOpen = false
                }
              }
            }
          }
        }

        // ---- Settings: a page over the remote (S) -----------------------------
        Item {
          id: settingsPage
          z: 10
          x: card.padding
          y: card.padding
          width: card.width - card.padding * 2
          height: card.height - card.padding * 2
          implicitHeight: settingsColumn.implicitHeight
          visible: root.settingsOpen
          Rectangle {  // covers the remote, its poster included
            x: -card.padding
            y: -card.padding
            width: card.width
            height: card.height
            radius: card.radius
            color: card.color
          }
          MouseArea {  // clicks and the wheel stay on the page
            anchors.fill: parent
            acceptedButtons: Qt.AllButtons
            onWheel: function(wheel) { wheel.accepted = true }
          }
          Column {
            id: settingsColumn
            width: parent.width
            spacing: Style.spacing.md
            Row {
              spacing: Style.spacing.sm
              Button {
                id: settingsBack
                iconText: String.fromCodePoint(0xF004D)
                tooltipText: strings.t("settings.back")
                onClicked: root.closeSettings()
              }
              Text {
                anchors.verticalCenter: settingsBack.verticalCenter
                textFormat: Text.PlainText
                text: strings.t("settings.title")
                color: Commons.Color.popups.text
                font.family: Style.font.family
                font.pixelSize: Style.font.heading
              }
            }
            Rectangle {  // the "Sharing" card
              width: parent.width
              radius: Style.cornerRadius
              color: root.keyFill
              height: sharing.implicitHeight + Style.spacing.md * 2
              Column {
                id: sharing
                x: Style.spacing.md
                y: Style.spacing.md
                width: parent.width - Style.spacing.md * 2
                spacing: Style.spacing.xs
                Text {
                  width: parent.width
                  textFormat: Text.PlainText
                  text: strings.t("settings.sharing")
                  color: Commons.Color.accent
                  font.family: Style.font.family
                  font.pixelSize: Style.font.subtitle
                  font.bold: true
                  bottomPadding: Style.spacing.sm
                }
                Text {
                  width: parent.width
                  textFormat: Text.PlainText
                  text: strings.t("settings.youtubeLinks")
                  color: Commons.Color.popups.text
                  font.family: Style.font.family
                  font.pixelSize: Style.font.title
                  font.bold: true
                }
                Text {
                  width: parent.width
                  textFormat: Text.PlainText
                  wrapMode: Text.Wrap
                  text: strings.t("settings.youtubeWhich").arg(root.youtube && root.boxName(root.youtube.box) || "Kodi")
                  color: Commons.Color.popups.text
                  opacity: 0.7
                  font.family: Style.font.family
                  font.pixelSize: Style.font.bodySmall
                  bottomPadding: Style.spacing.sm
                }
                Repeater {
                  model: root.youtubeModes
                  delegate: Item {
                    id: modeRow
                    required property string modelData
                    required property int index
                    readonly property bool chosen: root.youtube !== null && root.youtube.mode === modelData
                    width: sharing.width
                    height: modeText.implicitHeight + Style.spacing.sm * 2
                    Rectangle {
                      anchors.fill: parent
                      radius: Style.cornerRadius
                      color: Commons.Color.popups.text
                      opacity: modeRow.index === root.settingsSelected ? 0.12 : (modeMouse.containsMouse ? 0.06 : 0)
                    }
                    MouseArea {
                      id: modeMouse
                      anchors.fill: parent
                      hoverEnabled: true
                      cursorShape: Qt.PointingHandCursor
                      onClicked: root.pickSetting(modeRow.index)
                    }
                    Text {  // the radio button
                      id: modeRadio
                      x: Style.spacing.sm
                      y: Style.spacing.sm
                      textFormat: Text.PlainText
                      text: String.fromCodePoint(modeRow.chosen ? 0xF043E : 0xF043D)
                      color: modeRow.chosen ? Commons.Color.accent : Commons.Color.popups.text
                      font.family: Style.font.family
                      font.pixelSize: Style.font.iconLarge
                    }
                    Column {
                      id: modeText
                      x: modeRadio.x + modeRadio.implicitWidth + Style.spacing.sm
                      y: Style.spacing.sm
                      width: modeRow.width - x - Style.spacing.sm
                      Text {
                        width: modeText.width
                        textFormat: Text.PlainText
                        text: strings.t("settings.mode." + modeRow.modelData)
                        color: Commons.Color.popups.text
                        font.family: Style.font.family
                        font.pixelSize: Style.font.body
                      }
                      Text {
                        width: modeText.width
                        textFormat: Text.PlainText
                        wrapMode: Text.Wrap
                        text: strings.t("settings.mode." + modeRow.modelData + ".about")
                        color: Commons.Color.popups.text
                        opacity: 0.7
                        font.family: Style.font.family
                        font.pixelSize: Style.font.bodySmall
                      }
                    }
                  }
                }
                Rectangle {  // smart mode's wait after a failure
                  width: sharing.width
                  visible: root.smartWaiting
                  radius: Style.cornerRadius
                  color: root.keyFill
                  height: visible ? waitColumn.implicitHeight + Style.spacing.sm * 2 : 0
                  Column {
                    id: waitColumn
                    x: Style.spacing.sm
                    y: Style.spacing.sm
                    width: parent.width - Style.spacing.sm * 2
                    spacing: Style.spacing.xs
                    Text {
                      width: waitColumn.width
                      textFormat: Text.PlainText
                      wrapMode: Text.Wrap
                      text: root.youtube ? strings.t("settings.smartWaiting").arg(
                        Format.endsAt((root.youtube.avoidUntil * 1000 - root.settingsNow) / 1000, root.settingsNow)) : ""
                      color: Commons.Color.popups.text
                      font.family: Style.font.family
                      font.pixelSize: Style.font.bodySmall
                    }
                    Item {
                      width: waitColumn.width
                      height: tryAgain.implicitHeight
                      Button {
                        id: tryAgain
                        anchors.right: parent.right
                        bordered: true
                        selected: root.settingsSelected === root.youtubeModes.length
                        text: strings.t("settings.tryAgain")
                        onClicked: root.pickSetting(root.youtubeModes.length)
                      }
                    }
                  }
                }
              }
            }
            Text {
              width: parent.width
              textFormat: Text.PlainText
              elide: Text.ElideRight
              text: strings.t("settings.hint")
              color: Commons.Color.popups.text
              opacity: 0.5
              font.family: Style.font.family
              font.pixelSize: Style.font.bodySmall
            }
          }
        }

        // ---- the strip's pages: Send a link, a button, the picker, icons ------
        Item {
          id: stripPages
          z: 10
          x: card.padding
          y: card.padding
          width: card.width - card.padding * 2
          height: card.height - card.padding * 2
          implicitHeight: root.stripPage === "send" ? sendColumn.implicitHeight
            : root.stripPage === "edit" ? editColumn.implicitHeight
            : root.stripPage === "picker" ? pickerColumn.implicitHeight
            : root.stripPage === "icons" ? iconsColumn.implicitHeight : 0
          visible: root.stripPage !== ""
          Rectangle {  // covers the remote, its poster included
            x: -card.padding
            y: -card.padding
            width: card.width
            height: card.height
            radius: card.radius
            color: card.color
          }
          MouseArea {  // clicks and the wheel stay on the page
            anchors.fill: parent
            acceptedButtons: Qt.AllButtons
            onWheel: function(wheel) { wheel.accepted = true }
          }

          // Send a link: type or paste one, then play or queue it.
          Column {
            id: sendColumn
            width: parent.width
            spacing: Style.spacing.md
            visible: root.stripPage === "send"
            PageTitle {
              text: strings.t("send.title")
              backTooltip: strings.t("strip.backTooltip")
              onBack: root.closeStripPage()
            }
            Item {
              width: parent.width
              height: sendField.implicitHeight
              TextField {
                id: sendField
                anchors.left: parent.left
                anchors.right: sendTool.left
                anchors.rightMargin: Style.spacing.xs
                foreground: Commons.Color.popups.text
                maximumLength: Protocol.MAX_LINK_TEXT
                placeholderText: strings.t("send.placeholder")
                onTextChanged: root.sendText = text
                Keys.onPressed: function(event) {
                  if ((event.key === Qt.Key_Return || event.key === Qt.Key_Enter) && !event.isAutoRepeat) {
                    event.accepted = true
                    root.sendLink((event.modifiers & Qt.ShiftModifier) !== 0)
                  } else if (event.key === Qt.Key_Escape) {
                    event.accepted = true
                    root.closeStripPage()
                  }
                }
              }
              Button {  // Clear while there is text, Paste while there is none
                id: sendTool
                anchors.right: parent.right
                anchors.verticalCenter: sendField.verticalCenter
                iconText: String.fromCodePoint(root.sendText !== "" ? 0xF0156 : 0xF0192)
                tooltipText: strings.t(root.sendText !== "" ? "send.clear" : "send.paste")
                onClicked: root.sendText !== "" ? root.clearLink() : root.pasteLink()
              }
            }
            Row {
              anchors.right: parent.right
              spacing: Style.spacing.sm
              Button {
                bordered: true
                text: strings.t("strip.cancel")
                onClicked: root.closeStripPage()
              }
              Button {
                bordered: true
                enabled: Protocol.hasLink(root.sendText)
                opacity: enabled ? 1 : 0.4
                iconText: String.fromCodePoint(0xF0412)
                text: strings.t("send.queue")
                tooltipText: strings.t("send.queueKey")
                onClicked: root.sendLink(true)
              }
              Button {
                bordered: true
                enabled: Protocol.hasLink(root.sendText)
                opacity: enabled ? 1 : 0.4
                iconText: String.fromCodePoint(0xF040A)
                text: strings.t("send.play")
                tooltipText: strings.t("send.playKey")
                onClicked: root.sendLink(false)
              }
            }
            PageHint { text: strings.t("send.hint") }
          }

          // One button: choose from Kodi, Send a link, its icon, a typed path.
          Column {
            id: editColumn
            width: parent.width
            spacing: Style.spacing.sm
            visible: root.stripPage === "edit"
            PageTitle {
              text: strings.t("edit.title").arg(root.stripSlot + 1)
              backTooltip: strings.t("strip.backTooltip")
              onBack: root.closeStripPage()
            }
            Row {
              width: parent.width
              spacing: Style.spacing.md
              Rectangle {
                width: Style.space(44)
                height: Style.space(44)
                radius: Style.cornerRadius
                color: root.keyFill
                ButtonFace {
                  anchors.centerIn: parent
                  width: Style.space(28)
                  height: Style.space(28)
                  button: root.editButton
                }
              }
              Text {
                width: parent.width - Style.space(44) - Style.spacing.md
                anchors.verticalCenter: parent.verticalCenter
                textFormat: Text.PlainText
                wrapMode: Text.Wrap
                maximumLineCount: 2
                elide: Text.ElideRight
                color: Commons.Color.popups.text
                font.family: Style.font.family
                font.pixelSize: Style.font.body
                text: !root.editButton ? ""
                  : root.editButton.custom ? root.editButton.label : strings.t("edit.default").arg(root.editButton.label)
              }
            }
            Repeater {
              model: root.editRows.filter(function(r) { return r !== "path" && r !== "buttons" })
              delegate: PageRow {
                required property string modelData
                required property int index
                width: editColumn.width
                selected: root.editRows[root.editSelected] === modelData
                accent: modelData === "choose"
                label: modelData === "choose" ? strings.t("edit.choose")
                  : modelData === "sendLink" ? strings.t("edit.useSendLink") : strings.t("edit.changeIcon")
                glyph: String.fromCodePoint(modelData === "choose" ? 0xF0256
                  : modelData === "sendLink" ? 0xF0C94 : 0xF02E9)
                onPicked: root.pickEditRow(root.editRows.indexOf(modelData))
              }
            }
            Text {
              width: parent.width
              topPadding: Style.spacing.xs
              textFormat: Text.PlainText
              wrapMode: Text.Wrap
              color: Commons.Color.popups.text
              opacity: 0.7
              font.family: Style.font.family
              font.pixelSize: Style.font.bodySmall
              text: strings.t("edit.typeHint")
            }
            TextField {
              id: pathField
              width: parent.width
              foreground: Commons.Color.popups.text
              maximumLength: 2048
              placeholderText: "plugin://plugin.video.youtube"
              hasCursor: root.editRows[root.editSelected] === "path"
              onTextChanged: root.typedPath = text
              onActiveFocusChanged: if (activeFocus && root.stripPage === "edit") root.editSelected = root.editRows.indexOf("path")
              Keys.onPressed: function(event) {
                var k = event.key
                if (k === Qt.Key_Up || k === Qt.Key_Down) {
                  event.accepted = true
                  root.moveEditSelection(k === Qt.Key_Up ? -1 : 1)
                } else if ((k === Qt.Key_Return || k === Qt.Key_Enter) && !event.isAutoRepeat) {
                  event.accepted = true
                  root.savePath()
                } else if (k === Qt.Key_Escape) {
                  event.accepted = true
                  root.closeStripPage()
                }
              }
            }
            Text {
              width: parent.width
              visible: root.typedPath.trim() !== "" && Shortcuts.normalize(root.typedPath) === ""
              textFormat: Text.PlainText
              wrapMode: Text.Wrap
              color: Commons.Color.urgent
              font.family: Style.font.family
              font.pixelSize: Style.font.bodySmall
              text: strings.t("edit.notAPath")
            }
            Row {
              anchors.right: parent.right
              spacing: Style.spacing.sm
              Repeater {
                model: root.editButtons
                delegate: Button {
                  required property string modelData
                  required property int index
                  bordered: true
                  hasCursor: root.editRows[root.editSelected] === "buttons" && root.editButtonAt === index
                  enabled: modelData !== "save" || root.canSavePath
                  opacity: enabled ? 1 : 0.4
                  text: strings.t("strip." + modelData)
                  onClicked: root.pickEditButton(modelData)
                }
              }
            }
            PageHint { text: strings.t("edit.hint") }
          }

          // Choose from Kodi: a list per level, live from the box.
          Column {
            id: pickerColumn
            width: parent.width
            spacing: Style.spacing.sm
            visible: root.stripPage === "picker"
            PageTitle {
              text: root.pickerView && !root.pickerWaiting ? root.pickerView.title : strings.t("picker.title")
              detail: root.pickerView && !root.pickerWaiting && root.pickerView.crumb !== root.pickerView.title
                ? root.pickerView.crumb : ""
              backTooltip: strings.t("picker.back")
              onBack: root.pickerBack()
              closable: true
              closeTooltip: strings.t("picker.close")
              onClosed: { root.stripPage = "edit"; Qt.callLater(root.focusEditRow) }
            }
            ListView {
              id: pickerList
              width: parent.width
              readonly property real rowHeight: Style.space(38)
              height: Math.min(count, 10) * rowHeight
              visible: count > 0
              clip: true
              boundsBehavior: Flickable.StopAtBounds
              model: root.pickerRows
              delegate: PageRow {
                required property var modelData
                required property int index
                width: ListView.view.width
                height: pickerList.rowHeight
                selected: index === root.pickerSelected
                accent: modelData.kind !== "item"
                label: modelData.label
                detail: modelData.detail
                glyph: modelData.kind === "folder" ? String.fromCodePoint(0xF012C)
                  : modelData.kind === "retry" ? String.fromCodePoint(0xF0450) : ""
                chevron: modelData.browse
                onPicked: root.pickPickerRow(index)
              }
            }
            Text {
              width: parent.width
              visible: text !== ""
              topPadding: Style.spacing.sm
              bottomPadding: Style.spacing.sm
              textFormat: Text.PlainText
              wrapMode: Text.Wrap
              maximumLineCount: 4
              elide: Text.ElideRight
              color: root.pickerView && !root.pickerWaiting && root.pickerView.status === "failed"
                ? Commons.Color.urgent : Commons.Color.popups.text
              opacity: 0.8
              font.family: Style.font.family
              font.pixelSize: Style.font.bodySmall
              text: root.pickerStatus
            }
            PageHint { text: strings.t("picker.hint") }
          }

          // Change icon: Kodi's artwork (or the automatic one), or a built-in.
          Column {
            id: iconsColumn
            width: parent.width
            spacing: Style.spacing.sm
            visible: root.stripPage === "icons"
            readonly property real tile: Math.floor((width - Style.spacing.xs * (root.iconColumns - 1)) / root.iconColumns)
            readonly property bool hasArt: root.editButton !== null && root.editButton.art !== ""
            PageTitle {
              text: strings.t("icons.title")
              backTooltip: strings.t("strip.backTooltip")
              onBack: { root.stripPage = "edit"; Qt.callLater(root.focusEditRow) }
            }
            Row {
              spacing: Style.spacing.md
              IconTile {
                id: kodiTile
                width: iconsColumn.tile
                height: iconsColumn.tile
                selected: root.iconSelected === 0
                chosen: root.editButton !== null && root.editButton.icon === ""
                onPicked: root.pickIcon(0)
                ButtonFace {
                  anchors.centerIn: parent
                  width: Math.round(iconsColumn.tile * 0.62)
                  height: Math.round(iconsColumn.tile * 0.62)
                  button: root.editButton ? { label: "", sendLink: false, icon: "", art: root.editButton.art,
                                              auto: root.editButton.auto } : null
                }
              }
              Column {
                anchors.verticalCenter: kodiTile.verticalCenter
                Text {
                  textFormat: Text.PlainText
                  color: Commons.Color.popups.text
                  font.family: Style.font.family
                  font.pixelSize: Style.font.body
                  text: strings.t(iconsColumn.hasArt ? "icons.kodi" : "icons.auto")
                }
                Text {
                  textFormat: Text.PlainText
                  color: Commons.Color.popups.text
                  opacity: 0.7
                  font.family: Style.font.family
                  font.pixelSize: Style.font.bodySmall
                  text: strings.t(iconsColumn.hasArt ? "icons.kodiAbout" : "icons.autoAbout")
                }
              }
            }
            Grid {
              columns: root.iconColumns
              spacing: Style.spacing.xs
              Repeater {
                model: root.iconNames
                delegate: IconTile {
                  required property string modelData
                  required property int index
                  width: iconsColumn.tile
                  height: iconsColumn.tile
                  selected: root.iconSelected === index + 1
                  chosen: root.editButton !== null && root.editButton.icon === modelData
                  tooltip: modelData.replace(/_/g, " ")
                  onPicked: root.pickIcon(index + 1)
                  Text {
                    anchors.centerIn: parent
                    textFormat: Text.PlainText
                    color: Commons.Color.popups.text
                    font.family: Style.font.family
                    font.pixelSize: Math.round(iconsColumn.tile * 0.5)
                    text: Shortcuts.glyph(parent.modelData)
                  }
                }
              }
            }
            PageHint { text: strings.t("icons.hint") }
          }
        }

        // ---- Kodi boxes: the saved ones, the found ones, the editor ------------
        Item {
          id: boxPages
          z: 10
          x: card.padding
          y: card.padding
          width: card.width - card.padding * 2
          height: card.height - card.padding * 2
          implicitHeight: root.boxPage === "list" ? boxListColumn.implicitHeight
            : root.boxPage === "edit" ? editorColumn.implicitHeight : 0
          visible: root.boxPage !== ""
          Rectangle {  // covers the remote, its poster included
            x: -card.padding
            y: -card.padding
            width: card.width
            height: card.height
            radius: card.radius
            color: card.color
          }
          MouseArea {  // clicks and the wheel stay on the page
            anchors.fill: parent
            acceptedButtons: Qt.AllButtons
            onWheel: function(wheel) { wheel.accepted = true }
          }

          // Kodi boxes: pick one to switch to it, edit one, add a found one.
          Column {
            id: boxListColumn
            width: parent.width
            spacing: Style.spacing.xs
            visible: root.boxPage === "list"
            PageTitle {
              text: strings.t("boxes.title")
              backTooltip: strings.t("boxes.back")
              onBack: root.closeBoxPage()
            }
            SectionLabel {
              visible: root.boxList.length > 0
              text: strings.t("boxes.saved")
            }
            Repeater {
              model: root.boxList
              delegate: Item {
                id: savedRow
                required property var modelData
                required property int index
                readonly property bool inUse: modelData.id === root.currentBox
                width: boxListColumn.width
                height: savedLine.implicitHeight
                PageRow {
                  id: savedLine
                  anchors.left: parent.left
                  anchors.right: savedEdit.left
                  anchors.rightMargin: Style.spacing.xs
                  selected: root.boxRows[root.boxSelected] !== undefined
                    && root.boxRows[root.boxSelected].kind === "saved" && root.boxRows[root.boxSelected].at === savedRow.index
                  accent: savedRow.inUse
                  glyph: String.fromCodePoint(savedRow.inUse ? 0xF043E : 0xF043D)
                  label: savedRow.modelData.name
                  detail: savedRow.modelData.host + ":" + savedRow.modelData.httpPort
                  onPicked: root.pickBoxRow(savedRow.index)
                }
                Button {
                  id: savedEdit
                  anchors.right: parent.right
                  anchors.verticalCenter: parent.verticalCenter
                  iconText: String.fromCodePoint(0xF03EB)
                  tooltipText: strings.t("boxes.edit").arg(savedRow.modelData.name)
                  onClicked: root.editBox(savedRow.modelData, null)
                }
              }
            }
            SectionLabel { text: strings.t("boxes.found") }
            Text {
              width: parent.width
              visible: text !== ""
              leftPadding: Style.spacing.sm
              topPadding: Style.spacing.xs
              bottomPadding: Style.spacing.xs
              textFormat: Text.PlainText
              wrapMode: Text.Wrap
              maximumLineCount: 3
              elide: Text.ElideRight
              color: root.foundView && root.foundView.status === "failed" ? Commons.Color.urgent : Commons.Color.popups.text
              opacity: 0.7
              font.family: Style.font.family
              font.pixelSize: Style.font.bodySmall
              text: root.foundStatus
            }
            Repeater {
              model: root.foundBoxes
              delegate: PageRow {
                required property var modelData
                required property int index
                width: boxListColumn.width
                selected: root.boxRows[root.boxSelected] !== undefined
                  && root.boxRows[root.boxSelected].kind === "found" && root.boxRows[root.boxSelected].at === index
                accent: true
                glyph: String.fromCodePoint(0xF05A9)
                label: modelData.name
                detail: modelData.host + ":" + modelData.httpPort
                chevron: true
                chevronGlyph: 0xF0415
                onPicked: root.editBox(null, modelData)
              }
            }
            Item { width: 1; height: Style.spacing.sm }
            Button {
              width: parent.width
              bordered: true
              hasCursor: root.boxRows[root.boxSelected] !== undefined && root.boxRows[root.boxSelected].kind === "add"
              iconText: String.fromCodePoint(0xF0415)
              text: strings.t("boxes.addManually")
              onClicked: root.editBox(null, null)
            }
            PageHint { text: strings.t("boxes.hint") }
          }

          // A box's editor: its settings, Test connection, Delete, Save.
          Column {
            id: editorColumn
            width: parent.width
            spacing: Style.spacing.sm
            visible: root.boxPage === "edit"
            PageTitle {
              text: root.editKey === "" ? strings.t("boxes.addTitle") : strings.t("boxes.editTitle").arg(
                root.boxName(root.editKey))
              backTooltip: strings.t("boxes.editorBack")
              onBack: root.backToBoxList()
            }
            BoxField {
              id: boxName
              width: parent.width
              label: strings.t("boxes.name")
              maximumLength: 100
              current: root.editorRow === 0
              onFocused: root.editorRow = 0
              onMoved: function(step) { root.moveEditorRow(step) }
              onEntered: root.saveBox()
              onEscaped: root.backToBoxList()
            }
            BoxField {
              id: boxHost
              width: parent.width
              label: strings.t("boxes.address")
              maximumLength: 253
              placeholder: "kodi.example.lan"
              current: root.editorRow === 1
              onFocused: root.editorRow = 1
              onMoved: function(step) { root.moveEditorRow(step) }
              onEntered: root.saveBox()
              onEscaped: root.backToBoxList()
            }
            Row {
              width: parent.width
              spacing: Style.spacing.sm
              BoxField {
                id: boxWeb
                width: (parent.width - parent.spacing) / 2
                label: strings.t("boxes.webPort")
                maximumLength: 5
                placeholder: "8080"
                current: root.editorRow === 2
                onFocused: root.editorRow = 2
                onMoved: function(step) { root.moveEditorRow(step) }
                onEntered: root.saveBox()
                onEscaped: root.backToBoxList()
              }
              BoxField {
                id: boxLive
                width: (parent.width - parent.spacing) / 2
                label: strings.t("boxes.livePort")
                maximumLength: 5
                placeholder: "9090"
                current: root.editorRow === 3
                onFocused: root.editorRow = 3
                onMoved: function(step) { root.moveEditorRow(step) }
                onEntered: root.saveBox()
                onEscaped: root.backToBoxList()
              }
            }
            BoxField {
              id: boxUser
              width: parent.width
              label: strings.t("boxes.username")
              maximumLength: 100
              current: root.editorRow === 4
              onFocused: root.editorRow = 4
              onMoved: function(step) { root.moveEditorRow(step) }
              onEntered: root.saveBox()
              onEscaped: root.backToBoxList()
            }
            BoxField {
              id: boxPassword
              width: parent.width
              label: strings.t("boxes.password")
              password: true
              maximumLength: 1024
              placeholder: root.editHasPassword && !root.passwordEdited ? strings.t("boxes.passwordSaved") : ""
              current: root.editorRow === 5
              onFocused: root.editorRow = 5
              onEdited: root.passwordEdited = true
              onMoved: function(step) { root.moveEditorRow(step) }
              onEntered: root.saveBox()
              onEscaped: root.backToBoxList()
            }
            BoxField {
              id: boxMac
              width: parent.width
              label: strings.t("boxes.mac")
              maximumLength: 17
              placeholder: root.editKnownMac ? strings.t("boxes.macKnown").arg(root.editKnownMac) : "aa:bb:cc:dd:ee:ff"
              current: root.editorRow === 6
              onFocused: root.editorRow = 6
              onMoved: function(step) { root.moveEditorRow(step) }
              onEntered: root.saveBox()
              onEscaped: root.backToBoxList()
            }
            Text {  // the Kodi setup help
              width: parent.width
              textFormat: Text.PlainText
              wrapMode: Text.Wrap
              color: Commons.Color.popups.text
              opacity: 0.7
              font.family: Style.font.family
              font.pixelSize: Style.font.bodySmall
              text: strings.t("boxes.help")
            }
            Text {  // what Save can't take yet
              width: parent.width
              visible: text !== ""
              textFormat: Text.PlainText
              wrapMode: Text.Wrap
              color: Commons.Color.urgent
              font.family: Style.font.family
              font.pixelSize: Style.font.bodySmall
              text: root.formProblem !== "" && boxHost.text !== "" ? strings.t("boxes.problem." + root.formProblem)
                : root.editorError
            }
            Item {
              width: parent.width
              height: Math.max(testButton.implicitHeight, testText.implicitHeight)
              Button {
                id: testButton
                anchors.left: parent.left
                anchors.verticalCenter: parent.verticalCenter
                bordered: true
                enabled: root.formProblem === "" && !root.testing
                opacity: enabled ? 1 : 0.4
                hasCursor: root.editorRow === 7 && root.editorButtons[root.editorButtonAt] === "test"
                text: strings.t("boxes.test")
                onClicked: root.testBox()
              }
              Text {
                id: testText
                anchors.left: testButton.right
                anchors.leftMargin: Style.spacing.sm
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                textFormat: Text.PlainText
                wrapMode: Text.Wrap
                maximumLineCount: 3
                elide: Text.ElideRight
                color: root.testOk ? Commons.Color.accent : Commons.Color.popups.text
                opacity: root.testOk ? 1 : 0.8
                font.family: Style.font.family
                font.pixelSize: Style.font.bodySmall
                text: root.testStatus
              }
            }
            Item {
              width: parent.width
              height: saveButton.implicitHeight
              Button {
                anchors.left: parent.left
                visible: root.editKey !== ""
                enabled: !root.savingBox
                foreground: Commons.Color.urgent
                hasCursor: root.editorRow === 7 && root.editorButtons[root.editorButtonAt] === "delete"
                text: strings.t("boxes.delete")
                onClicked: root.deleteBox()
              }
              Button {
                id: saveButton
                anchors.right: parent.right
                bordered: true
                enabled: root.formProblem === "" && !root.savingBox
                opacity: enabled ? 1 : 0.4
                hasCursor: root.editorRow === 7 && root.editorButtons[root.editorButtonAt] === "save"
                text: strings.t("boxes.save")
                onClicked: root.saveBox()
              }
            }
            PageHint { text: strings.t("boxes.editorHint") }
          }
        }

        Column {
          id: content
          x: card.padding
          y: card.padding
          width: card.width - card.padding * 2
          spacing: Style.spacing.md

          // ---- the top bar: ☰, the box and how it is, power, close ----------
          Item {
            id: topBar
            width: parent.width
            height: Math.max(closeButton.implicitHeight, topText.implicitHeight)
            Button {
              id: menuButton
              anchors.left: parent.left
              anchors.top: parent.top
              enabled: root.connected
              opacity: enabled ? 1 : 0.4
              selected: root.menuOpen
              iconText: String.fromCodePoint(0xF035C)
              tooltipText: strings.t("key.menu")
              onClicked: root.toggleMenu()
            }
            Column {
              id: topText
              anchors.left: menuButton.right
              anchors.leftMargin: Style.spacing.sm
              anchors.right: powerButton.left
              anchors.rightMargin: Style.spacing.sm
              anchors.verticalCenter: parent.verticalCenter
              spacing: 2
              Text {
                width: parent.width
                textFormat: Text.PlainText
                elide: Text.ElideRight
                text: root.topTitle !== "" ? root.topTitle : strings.t(root.connected ? "remote.noBox" : "remote.title")
                color: Commons.Color.popups.text
                font.family: Style.font.family
                font.pixelSize: Style.font.title
                // A click on the name opens the menu too, as on a phone remote.
                MouseArea {
                  anchors.fill: parent
                  enabled: root.connected
                  cursorShape: Qt.PointingHandCursor
                  onClicked: root.toggleMenu()
                }
              }
              Text {  // Connected, Offline or Connecting…
                width: parent.width
                visible: text !== ""
                textFormat: Text.PlainText
                elide: Text.ElideRight
                font.family: Style.font.family
                font.pixelSize: Style.font.bodySmall
                color: root.topStatus.word === "connected" ? root.okColor
                  : root.topStatus.word === "offline" ? Commons.Color.urgent : Commons.Color.popups.text
                opacity: root.topStatus.word === "connecting" ? 0.7 : 1
                text: root.topStatus.word !== "" ? strings.t("remote.status." + root.topStatus.word) : ""
              }
              Text {  // Kodi is off, or restarting
                width: parent.width
                visible: text !== ""
                textFormat: Text.PlainText
                elide: Text.ElideRight
                font.family: Style.font.family
                font.pixelSize: Style.font.bodySmall
                color: Commons.Color.popups.text
                opacity: 0.7
                text: root.topNote
              }
              Text {  // why Kodi can't be reached: at most 2 lines
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
                text: root.topStatus.why
              }
              Text {  // the fix, always whole
                width: parent.width
                visible: text !== ""
                textFormat: Text.PlainText
                wrapMode: Text.Wrap
                font.family: Style.font.family
                font.pixelSize: Style.font.bodySmall
                color: Commons.Color.popups.text
                opacity: 0.7
                text: root.topFix
              }
            }
            Button {
              id: powerButton
              anchors.right: closeButton.left
              anchors.top: parent.top
              enabled: root.connected
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

          // ---- the shortcut strip: five buttons (1-5; e then 1-5 changes one) --
          Row {
            id: stripRow
            width: parent.width
            spacing: Style.spacing.sm
            Repeater {
              model: root.stripButtons
              delegate: Item {
                id: stripKey
                required property var modelData
                required property int index
                width: (stripRow.width - stripRow.spacing * 4) / 5
                height: root.keySize
                opacity: root.reachable ? 1 : 0.4
                Rectangle {
                  anchors.fill: parent
                  radius: Style.cornerRadius
                  color: root.keyFill
                }
                Rectangle {  // hover and press
                  anchors.fill: parent
                  radius: Style.cornerRadius
                  color: Commons.Color.popups.text
                  opacity: stripMouse.pressed ? 0.16 : (stripMouse.containsMouse ? 0.08 : 0)
                }
                ButtonFace {
                  anchors.centerIn: parent
                  width: Style.space(26)
                  height: Style.space(26)
                  button: stripKey.modelData
                }
                MouseArea {
                  id: stripMouse
                  anchors.fill: parent
                  enabled: root.connected
                  hoverEnabled: true
                  cursorShape: Qt.PointingHandCursor
                  acceptedButtons: Qt.LeftButton | Qt.RightButton
                  pressAndHoldInterval: 500
                  property bool held: false
                  onPressed: held = false
                  onPressAndHold: { held = true; root.editStrip(stripKey.index) }
                  onClicked: function(mouse) {
                    if (held) return
                    if (mouse.button === Qt.RightButton) root.editStrip(stripKey.index)
                    else root.openStripButton(stripKey.index)
                  }
                }
                PanelToolTip {
                  visible: stripMouse.containsMouse && !stripMouse.pressed
                  text: strings.t("strip.key").arg(stripKey.modelData.label).arg(stripKey.index + 1)
                    + "\n" + strings.t("strip.changeHint")
                }
              }
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
              delegate: RemoteKey {
                required property var modelData
                width: (volumeRow.width - volumeRow.spacing * 2) / 3
                height: root.keySize
                action: modelData[0]
                iconText: String.fromCodePoint(modelData[1])
                tooltipText: strings.t("key." + modelData[0])
              }
            }
          }

          // The soundbar: Kodi's volume keys, over HDMI-CEC.
          Row {
            id: soundbarRow
            width: parent.width
            spacing: Style.spacing.sm
            visible: root.showSoundbar
            enabled: root.reachable
            opacity: enabled ? 1 : 0.4
            Text {
              id: soundbarLabel
              width: Style.space(90)
              height: Style.space(28)
              verticalAlignment: Text.AlignVCenter
              textFormat: Text.PlainText
              elide: Text.ElideRight
              font.family: Style.font.family
              font.pixelSize: Style.font.bodySmall
              color: Commons.Color.popups.text
              opacity: 0.7
              text: strings.t("remote.soundbar")
            }
            Repeater {
              model: [["soundbardown", 0xF075E], ["soundbarup", 0xF075D]]
              delegate: RemoteKey {
                required property var modelData
                width: (soundbarRow.width - soundbarLabel.width - soundbarRow.spacing * 2) / 2
                height: Style.space(28)
                action: modelData[0]
                iconText: String.fromCodePoint(modelData[1])
                tooltipText: strings.t("key." + modelData[0])
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
            // In the phone remote's order (RemoteKeys.ACTION_ROW).
            readonly property real keyWidth: (width - spacing * 4) / 5
            Button {
              width: actionRow.keyWidth
              height: root.keySize
              background: root.keyFill
              foreground: Commons.Color.popups.text
              opacity: NowPlaying.audioListOpens(root.audio) ? 1 : 0.4
              selected: root.audioOpen
              iconText: String.fromCodePoint(0xF057E)
              tooltipText: NowPlaying.audioKeyTip(root.audio, strings.t("key.audioList"), strings.t("remote.track"))
              onClicked: root.toggleAudioList()
            }
            Repeater {
              model: [["fullscreen", 0xF0293], ["info", 0xF02FD], ["keyboard", 0xF030C], ["playerinfo", 0xF0A07]]
              delegate: Button {
                required property var modelData
                width: actionRow.keyWidth
                height: root.keySize
                background: root.keyFill
                foreground: Commons.Color.popups.text
                selected: modelData[0] === "keyboard" && root.kodiInput !== null  // Kodi asks for text
                iconText: String.fromCodePoint(modelData[1])
                tooltipText: strings.t("key." + modelData[0])
                onClicked: {
                  if (modelData[0] === "keyboard") root.openKeyboard()
                  else root.send(modelData[0], false)
                }
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
              delegate: RemoteKey {
                required property var modelData
                readonly property bool arrow: ["up", "down", "left", "right"].indexOf(modelData[0]) >= 0
                width: root.padSize
                height: root.padSize
                opacity: modelData[0] === "" ? 0 : 1
                enabled: modelData[0] !== ""
                action: modelData[0]
                foreground: arrow ? Commons.Color.accent : Commons.Color.popups.text
                iconSize: arrow ? Style.font.icon * 1.5 : Style.font.icon
                fontSize: Style.font.title
                text: modelData[0] === "select" ? "OK" : ""
                iconText: modelData[1] === 0 ? "" : String.fromCodePoint(modelData[1])
                tooltipText: modelData[0] === "select" ? strings.t("key.selectOk")
                  : modelData[0] ? strings.t("key." + modelData[0]) : ""
              }
            }
          }

          // ---- now playing: a bar, as on a phone remote; a click or n opens the page
          Rectangle {
            id: nowBar
            width: parent.width
            // Kept under the page's last moment, so the card keeps its height.
            visible: root.playing !== null || root.nowOpen
            height: nowBarRow.height + nowBarLine.height
            radius: Style.cornerRadius
            color: root.keyFill
            MouseArea {
              anchors.fill: parent
              cursorShape: Qt.PointingHandCursor
              onClicked: root.openNowPlaying()
            }
            // How far it is: a thin line along the top.
            Rectangle {
              id: nowBarLine
              x: Style.cornerRadius
              width: parent.width - Style.cornerRadius * 2
              height: 2
              color: Qt.rgba(Commons.Color.popups.text.r, Commons.Color.popups.text.g,
                             Commons.Color.popups.text.b, 0.2)
              Rectangle {
                height: parent.height
                // Guarded on playing itself: canSeek can lag a step behind it when playback stops.
                width: root.playing && root.playing.durationSec > 0
                  ? parent.width * Math.min(1, root.livePosition / root.playing.durationSec) : 0
                color: Commons.Color.accent
              }
            }
            Item {
              id: nowBarRow
              anchors.top: nowBarLine.bottom
              width: parent.width
              height: Style.space(56)
              // The thumbnail, from the daemon's cache (never a URL), cropped
              // to a square. Fixed sizes only: an image sized from its own
              // picture was a binding loop that crashed the shell.
              Rectangle {
                id: nowThumb
                x: Style.spacing.sm
                anchors.verticalCenter: parent.verticalCenter
                width: Style.space(44)
                height: Style.space(44)
                radius: Style.cornerRadius
                color: root.keyFill
                Image {
                  anchors.fill: parent
                  visible: status === Image.Ready
                  source: root.artPath !== "" ? "file://" + root.artPath : ""
                  fillMode: Image.PreserveAspectCrop
                  asynchronous: true
                  cache: false
                  sourceSize.width: 128
                  sourceSize.height: 128
                }
              }
              Column {
                anchors.left: nowThumb.right
                anchors.leftMargin: Style.spacing.sm
                anchors.right: nowTransport.left
                anchors.rightMargin: Style.spacing.xs
                anchors.verticalCenter: parent.verticalCenter
                Text {
                  width: parent.width
                  textFormat: Text.PlainText
                  elide: Text.ElideRight
                  font.family: Style.font.family
                  font.pixelSize: Style.font.body
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
              }
              // Stop, play/pause, next: the phone remote's order.
              Row {
                id: nowTransport
                anchors.right: parent.right
                anchors.rightMargin: Style.spacing.xs
                anchors.verticalCenter: parent.verticalCenter
                enabled: root.reachable
                Button {
                  iconText: String.fromCodePoint(0xF04DB)
                  tooltipText: strings.t("key.stop")
                  onClicked: root.send("stop", false)
                }
                Button {
                  iconText: String.fromCodePoint(NowPlaying.showsPause(root.playing) ? 0xF03E4 : 0xF040A)
                  tooltipText: strings.t("key.playpause")
                  onClicked: root.send("playpause", false)
                }
                Button {
                  iconText: String.fromCodePoint(0xF04AD)
                  tooltipText: strings.t("key.next")
                  onClicked: root.send("next", false)
                }
              }
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
              height: Math.min(count, 5) * rowHeight
              clip: true
              boundsBehavior: Flickable.StopAtBounds
              model: root.audio ? NowPlaying.audioRows(root.audio, strings.t("remote.track")) : []
              delegate: Item {
                id: track
                required property var modelData
                required property int index
                readonly property bool isPlaying: track.modelData.current
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
                  color: track.isPlaying ? Commons.Color.accent : Commons.Color.popups.text
                  text: track.modelData.label
                }
              }
            }
          }
        }

        // ---- the power menu: under the power button, over the remote ---------
        MouseArea {  // a click beside the menu closes it, as on a phone remote
          z: 20
          anchors.fill: parent
          visible: root.powerOpen
          acceptedButtons: Qt.AllButtons
          onPressed: root.closePowerMenu()
          onWheel: function(wheel) { wheel.accepted = true }
        }
        Rectangle {
          id: powerPopup
          z: 21
          visible: root.powerOpen
          width: Style.space(250)
          x: card.width - card.padding - width
          y: card.padding + topBar.height + Style.spacing.xs
          height: powerColumn.implicitHeight + Style.spacing.xs * 2
          radius: Style.cornerRadius
          color: card.color
          border.width: 1
          border.color: Qt.rgba(Commons.Color.popups.text.r, Commons.Color.popups.text.g, Commons.Color.popups.text.b, 0.2)
          MouseArea {  // clicks between the rows stay in the menu
            anchors.fill: parent
            acceptedButtons: Qt.AllButtons
            onWheel: function(wheel) { wheel.accepted = true }
          }
          Column {
            id: powerColumn
            x: Style.spacing.xs
            y: Style.spacing.xs
            width: parent.width - Style.spacing.xs * 2
            Repeater {
              model: root.powerItems
              delegate: Column {
                id: powerRow
                required property string modelData
                required property int index
                width: powerColumn.width
                Item {  // the divider above Reboot and Shut down
                  width: parent.width
                  height: Style.spacing.sm * 2 + 1
                  visible: PowerMenu.dividerAbove(root.powerItems, powerRow.index)
                  Rectangle {
                    anchors.verticalCenter: parent.verticalCenter
                    width: parent.width
                    height: 1
                    color: Commons.Color.popups.text
                    opacity: 0.2
                  }
                }
                PageRow {
                  width: parent.width
                  selected: root.powerSelected === powerRow.index
                  label: strings.t("power." + powerRow.modelData)
                  onPicked: root.pickPower(powerRow.index)
                }
              }
            }
          }
        }

        // ---- the ☰ menu: a drawer from the left, over the remote ---------------
        Item {
          id: menuLayer
          z: 30
          anchors.fill: parent
          visible: root.menuOpen
          implicitHeight: menuColumn.implicitHeight + menuVersion.implicitHeight + card.padding * 2 + Style.spacing.lg
          Rectangle {  // the remote behind it, dimmed
            anchors.fill: parent
            radius: card.radius
            color: "black"
            opacity: 0.45
          }
          MouseArea {  // a click beside the drawer closes it
            anchors.fill: parent
            acceptedButtons: Qt.AllButtons
            onPressed: root.closeMenu()
            onWheel: function(wheel) { wheel.accepted = true }
          }
          Rectangle {
            id: drawer
            width: Math.round(parent.width * 0.8)
            height: parent.height
            radius: card.radius
            color: card.color
            border.width: 1
            border.color: Qt.rgba(Commons.Color.popups.text.r, Commons.Color.popups.text.g, Commons.Color.popups.text.b, 0.2)
            MouseArea {  // clicks and the wheel stay in the drawer
              anchors.fill: parent
              acceptedButtons: Qt.AllButtons
              onWheel: function(wheel) { wheel.accepted = true }
            }
            Column {
              id: menuColumn
              x: card.padding
              y: card.padding
              width: drawer.width - card.padding * 2
              spacing: Style.spacing.xs
              Text {
                width: parent.width
                textFormat: Text.PlainText
                elide: Text.ElideRight
                bottomPadding: Style.spacing.sm
                text: strings.t("menu.title")
                color: Commons.Color.popups.text
                font.family: Style.font.family
                font.pixelSize: Style.font.heading
              }
              SectionLabel {
                visible: root.boxList.length > 0
                topPadding: 0
                text: strings.t("menu.boxes")
              }
              Repeater {
                model: root.menuRows
                delegate: Column {
                  id: menuRow
                  required property var modelData
                  required property int index
                  width: menuColumn.width
                  Item {  // the divider under the boxes
                    width: parent.width
                    height: Style.spacing.sm * 2 + 1
                    visible: menuRow.modelData.kind === "manage" && root.boxList.length > 0
                    Rectangle {
                      anchors.verticalCenter: parent.verticalCenter
                      width: parent.width
                      height: 1
                      color: Commons.Color.popups.text
                      opacity: 0.2
                    }
                  }
                  PageRow {
                    width: parent.width
                    selected: root.menuSelected === menuRow.index
                    accent: menuRow.modelData.kind === "box" && menuRow.modelData.id === root.currentBox
                    glyph: String.fromCodePoint(menuRow.modelData.kind === "box" ? 0xF0502
                      : menuRow.modelData.kind === "manage" ? 0xF048B : 0xF0493)
                    label: menuRow.modelData.kind === "box" ? root.boxName(menuRow.modelData.id)
                      : strings.t("menu." + menuRow.modelData.kind)
                    onPicked: root.pickMenuRow(menuRow.index)
                  }
                }
              }
            }
            Text {
              id: menuVersion
              x: card.padding
              anchors.bottom: parent.bottom
              anchors.bottomMargin: card.padding
              width: drawer.width - card.padding * 2
              visible: root.version !== ""
              textFormat: Text.PlainText
              elide: Text.ElideRight
              text: strings.t("menu.version").arg(root.version)
              color: Commons.Color.popups.text
              opacity: 0.5
              font.family: Style.font.family
              font.pixelSize: Style.font.bodySmall
            }
          }
        }

        // ---- "Reboot <box>?": Cancel or Reboot (Shut down the same) ------------
        Item {
          z: 40
          anchors.fill: parent
          visible: root.powerDialog !== null
          Rectangle {
            anchors.fill: parent
            radius: card.radius
            color: "black"
            opacity: 0.45
          }
          MouseArea {  // a click beside the dialog cancels it
            anchors.fill: parent
            acceptedButtons: Qt.AllButtons
            onPressed: root.powerDialogKey("cancel")
            onWheel: function(wheel) { wheel.accepted = true }
          }
          Rectangle {
            width: parent.width - card.padding * 4
            height: dialogColumn.implicitHeight + card.padding * 2
            anchors.centerIn: parent
            radius: card.radius
            color: card.color
            border.width: 1
            border.color: Qt.rgba(Commons.Color.popups.text.r, Commons.Color.popups.text.g, Commons.Color.popups.text.b, 0.2)
            MouseArea {
              anchors.fill: parent
              acceptedButtons: Qt.AllButtons
            }
            Column {
              id: dialogColumn
              x: card.padding
              y: card.padding
              width: parent.width - card.padding * 2
              spacing: Style.spacing.lg
              Text {
                width: parent.width
                textFormat: Text.PlainText
                wrapMode: Text.Wrap
                maximumLineCount: 3
                elide: Text.ElideRight
                text: root.powerDialog
                  ? strings.t(root.powerDialog.action === "reboot" ? "power.askReboot" : "power.askShutdown")
                      .arg(root.topTitle !== "" ? root.topTitle : "Kodi")
                  : ""
                color: Commons.Color.popups.text
                font.family: Style.font.family
                font.pixelSize: Style.font.title
              }
              Item {
                width: parent.width
                height: dialogButtons.implicitHeight
                Row {
                  id: dialogButtons
                  anchors.right: parent.right
                  spacing: Style.spacing.sm
                  Button {
                    hasCursor: root.powerDialog !== null && root.powerDialog.at === 0
                    text: strings.t("power.cancel")
                    onClicked: root.powerDialogKey("cancel")
                  }
                  Button {
                    bordered: true
                    foreground: Commons.Color.urgent
                    hasCursor: root.powerDialog !== null && root.powerDialog.at === 1
                    text: root.powerDialog ? strings.t("power." + root.powerDialog.action) : ""
                    onClicked: root.powerDialogKey("confirm")
                  }
                }
              }
            }
          }
        }

        // ---- Kodi's keyboard: Send or Cancel -------------------------------------
        KodiTextDialog {
          id: kodiTextDialog
          z: 45
          anchors.fill: parent
          request: root.kodiInput
        }

        // ---- the short message, over the bottom of the remote ------------------
        // As a phone remote's: a few seconds, then it fades; an error stays
        // until the next action, or a click on it. Only shown or hidden
        // (opacity), never a layer or an effect.
        Rectangle {
          id: toast
          z: 50
          anchors.horizontalCenter: parent.horizontalCenter
          anchors.bottom: parent.bottom
          anchors.bottomMargin: card.padding + Style.spacing.md
          width: toastLabel.width + Style.spacing.lg * 2
          height: toastLabel.height + Style.spacing.md * 2
          radius: Math.min(height / 2, Style.cornerRadius + Style.spacing.md)
          readonly property color themed: Commons.Color.notifications.background
          color: Qt.rgba(themed.r, themed.g, themed.b, 1)
          border.width: root.toastError ? 2 : 1
          border.color: root.toastError ? Commons.Color.urgent : Commons.Color.notifications.border
          opacity: root.toastShown && root.opened ? 1 : 0
          visible: opacity > 0
          Behavior on opacity {
            NumberAnimation { duration: Style.duration(root.toastShown ? 150 : 250); easing.type: Easing.OutCubic }
          }
          TextMetrics {  // the one-line width, so the label's width never follows itself
            id: toastMetrics
            font: toastLabel.font
            text: root.toastText
          }
          Text {
            id: toastLabel
            anchors.centerIn: parent
            width: Math.min(Math.ceil(toastMetrics.advanceWidth) + 2, toast.parent.width - card.padding * 2 - Style.spacing.lg * 2)
            horizontalAlignment: Text.AlignHCenter
            textFormat: Text.PlainText
            wrapMode: Text.Wrap
            maximumLineCount: 4
            elide: Text.ElideRight
            font.family: Style.font.family
            font.pixelSize: Style.font.bodySmall
            color: root.toastError ? Commons.Color.urgent : Commons.Color.notifications.text
            text: root.toastText
          }
          MouseArea {
            anchors.fill: parent
            enabled: toast.visible
            acceptedButtons: Qt.AllButtons
            onPressed: root.hush()
          }
        }
      }
    }
  }

  // ---- Kodi's keyboard -------------------------------------------------------------

  // When Kodi asks for text, a dialog over the remote as on a phone remote:
  // Kodi's prompt, the field (dots for a password), Paste, Cancel and Send.
  // Nothing reaches Kodi while typing: Send (Enter) gives it the whole text
  // once and submits it (root.sendKodiText); Cancel (Esc, a click beside it)
  // only closes the dialog, and Kodi's keyboard stays on the TV. A new
  // request opens it with Kodi's text; its text is forgotten whenever it
  // closes, so a password typed into it doesn't stay in the field.
  component KodiTextDialog: Item {
    id: kodiText
    property var request: null        // the state's input, or null
    property bool open: false
    readonly property bool shown: open && request !== null
    readonly property bool fieldFocused: kodiTextField.activeFocus
    readonly property string requestKey: request
      ? request.type + "\n" + request.title + "\n" + request.value : ""
    visible: shown

    // A new request (another keyboard on the TV) opens it afresh; the end
    // of one closes it, and the keys go back to the remote.
    onRequestKeyChanged: {
      if (request) { show(true); return }
      var was = open
      hide()
      if (was) root.kodiTextClosed()
    }

    // Opens it; `fresh` starts the field again from Kodi's text even when
    // it is open already.
    function show(fresh) {
      if (!request) return
      if (!open || fresh) {
        kodiTextField.text = KodiInput.startText(request)
        kodiTextField.cursorPosition = kodiTextField.text.length
      }
      open = true
      take()
    }

    function hide() {
      open = false
      kodiTextField.text = ""
    }

    function take() {
      if (shown && root.opened) kodiTextField.forceActiveFocus()
    }

    // "send" or "cancel" (KodiInput.dialogKey).
    function act(key) {
      if (!shown) return
      var next = KodiInput.dialogKey(request, key, kodiTextField.text)
      if (next.send !== null && !root.sendKodiText(next.send)) return  // refused: it stays, the remote says why
      if (next.open) return
      hide()
      root.kodiTextClosed()
    }

    function pasteClipboard() {
      var r = KodiInput.paste(kodiTextField.text, kodiTextField.selectionStart, kodiTextField.selectionEnd,
                              root.clipboardText())
      kodiTextField.text = r.text
      kodiTextField.cursorPosition = r.cursor
      take()
    }

    Rectangle {
      anchors.fill: parent
      radius: card.radius
      color: "black"
      opacity: 0.45
    }
    MouseArea {  // a click beside the dialog cancels it
      objectName: "kodiTextBeside"
      anchors.fill: parent
      acceptedButtons: Qt.AllButtons
      onPressed: kodiText.act("cancel")
      onWheel: function(wheel) { wheel.accepted = true }
    }
    Rectangle {
      width: parent.width - card.padding * 4
      height: kodiTextColumn.implicitHeight + card.padding * 2
      anchors.centerIn: parent
      radius: card.radius
      color: card.color
      border.width: 1
      border.color: Qt.rgba(Commons.Color.popups.text.r, Commons.Color.popups.text.g, Commons.Color.popups.text.b, 0.2)
      MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.AllButtons
      }
      Column {
        id: kodiTextColumn
        x: card.padding
        y: card.padding
        width: parent.width - card.padding * 2
        spacing: Style.spacing.lg
        Text {
          objectName: "kodiTextTitle"
          width: parent.width
          textFormat: Text.PlainText
          wrapMode: Text.Wrap
          maximumLineCount: 3
          elide: Text.ElideRight
          text: KodiInput.title(kodiText.request, strings.t("kodiText.title"))
          color: Commons.Color.popups.text
          font.family: Style.font.family
          font.pixelSize: Style.font.title
        }
        Item {
          width: parent.width
          height: kodiTextField.height
          TextField {
            id: kodiTextField
            objectName: "kodiTextField"
            width: parent.width - kodiTextPaste.width - Style.spacing.sm
            foreground: Commons.Color.popups.text
            password: KodiInput.hidden(kodiText.request)
            maximumLength: KodiInput.MAX_TEXT
            Keys.onPressed: function(event) {
              if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                event.accepted = true
                if (!event.isAutoRepeat) kodiText.act("send")
              } else if (event.key === Qt.Key_Escape) {
                event.accepted = true
                kodiText.act("cancel")
              }
            }
          }
          Button {
            id: kodiTextPaste
            objectName: "kodiTextPaste"
            anchors.right: parent.right
            width: kodiTextField.height
            height: kodiTextField.height
            iconText: String.fromCodePoint(0xF0192)
            tooltipText: strings.t("kodiText.paste")
            onClicked: kodiText.pasteClipboard()
          }
        }
        Item {
          width: parent.width
          height: kodiTextButtons.implicitHeight
          Row {
            id: kodiTextButtons
            anchors.right: parent.right
            spacing: Style.spacing.sm
            Button {
              objectName: "kodiTextCancel"
              text: strings.t("kodiText.cancel")
              tooltipText: strings.t("kodiText.cancelHint")
              onClicked: kodiText.act("cancel")
            }
            Button {
              objectName: "kodiTextSend"
              bordered: true
              text: strings.t("kodiText.send")
              tooltipText: strings.t("kodiText.sendHint")
              onClicked: kodiText.act("send")
            }
          }
        }
      }
    }
  }

  // ---- a remote key for the mouse ---------------------------------------------

  // Keys that repeat (RemoteKeys.repeats: arrows, Kodi's volume) send on the press
  // and again while held, like a real remote's; OK sends on release and,
  // held, opens the context menu instead (a right click too); the others
  // send on a click. A PointHandler over the button sees the press without
  // taking it, so the button keeps its hover, press look and tooltip.
  component RemoteKey: Item {
    id: remoteKey
    property string action: ""
    property alias text: remoteKeyButton.text
    property alias iconText: remoteKeyButton.iconText
    property alias tooltipText: remoteKeyButton.tooltipText
    property alias foreground: remoteKeyButton.foreground
    property alias iconSize: remoteKeyButton.iconSize
    property alias fontSize: remoteKeyButton.fontSize
    readonly property bool repeating: RemoteKeys.repeats(action)
    property bool held: false  // OK held long enough: the context menu went instead
    Button {
      id: remoteKeyButton
      anchors.fill: parent
      background: root.keyFill
      foreground: Commons.Color.popups.text
      onClicked: {
        if (remoteKey.action === "" || remoteKey.repeating) return
        if (remoteKey.action === "select" && remoteKey.held) return
        root.send(remoteKey.action, false)
      }
      onRightClicked: if (remoteKey.action === "select") root.send("context", false)
    }
    Item {
      anchors.fill: parent
      PointHandler {
        id: remoteKeyPress
        acceptedButtons: Qt.LeftButton
        onActiveChanged: {
          remoteKeyTimer.stop()
          if (!active || remoteKey.action === "") return
          remoteKey.held = false
          if (remoteKey.repeating) {
            root.send(remoteKey.action, false)
            remoteKeyTimer.interval = RemoteKeys.REPEAT_DELAY
            remoteKeyTimer.start()
          } else if (remoteKey.action === "select") {
            remoteKeyTimer.interval = RemoteKeys.LONG_PRESS
            remoteKeyTimer.start()
          }
        }
      }
    }
    Timer {
      id: remoteKeyTimer
      onTriggered: {
        if (!remoteKeyPress.active || !root.opened) return
        if (remoteKey.action === "select") {
          remoteKey.held = true
          root.send("context", false)
          return
        }
        // Moved off the key: it stops, as on the phone.
        var p = remoteKeyPress.point.position
        if (p.x < 0 || p.y < 0 || p.x > remoteKey.width || p.y > remoteKey.height) return
        root.send(remoteKey.action, true)
        interval = RemoteKeys.REPEAT_INTERVAL
        start()
      }
    }
  }

  // ---- pieces of the strip's pages ------------------------------------------

  // A button's face: Kodi's art when it has some and no icon was chosen,
  // else the chosen or the matching built-in icon. Fixed sizes only: an
  // image sized from its own picture was a binding loop that crashed the shell.
  component ButtonFace: Item {
    id: face
    property var button: null
    Image {
      id: faceArt
      anchors.fill: parent
      source: face.button && face.button.icon === "" && face.button.art !== "" ? "file://" + face.button.art : ""
      fillMode: Image.PreserveAspectFit
      asynchronous: true
      cache: false
      sourceSize.width: 96
      sourceSize.height: 96
      visible: status === Image.Ready
    }
    Text {
      anchors.centerIn: parent
      visible: !faceArt.visible
      textFormat: Text.PlainText
      color: Commons.Color.popups.text
      font.family: Style.font.family
      font.pixelSize: Math.max(1, Math.round(face.height * 0.85))
      text: Shortcuts.buttonGlyph(face.button)
    }
  }

  // A page's title row: back arrow, title (and where it is), maybe a close button.
  component PageTitle: Item {
    id: pageTitle
    property string text: ""
    property string detail: ""
    property string backTooltip: ""
    property bool closable: false
    property string closeTooltip: ""
    signal back()
    signal closed()
    width: parent ? parent.width : 0
    height: Math.max(pageBack.implicitHeight, pageTitleText.implicitHeight)
    Button {
      id: pageBack
      anchors.left: parent.left
      anchors.verticalCenter: parent.verticalCenter
      iconText: String.fromCodePoint(0xF004D)
      tooltipText: pageTitle.backTooltip
      onClicked: pageTitle.back()
    }
    Column {
      id: pageTitleText
      anchors.left: pageBack.right
      anchors.leftMargin: Style.spacing.sm
      anchors.right: pageClose.visible ? pageClose.left : parent.right
      anchors.rightMargin: Style.spacing.sm
      anchors.verticalCenter: parent.verticalCenter
      Text {
        width: parent.width
        textFormat: Text.PlainText
        elide: Text.ElideRight
        text: pageTitle.text
        color: Commons.Color.popups.text
        font.family: Style.font.family
        font.pixelSize: Style.font.heading
      }
      Text {
        width: parent.width
        visible: text !== ""
        textFormat: Text.PlainText
        elide: Text.ElideLeft
        text: pageTitle.detail
        color: Commons.Color.popups.text
        opacity: 0.7
        font.family: Style.font.family
        font.pixelSize: Style.font.bodySmall
      }
    }
    Button {
      id: pageClose
      visible: pageTitle.closable
      anchors.right: parent.right
      anchors.verticalCenter: parent.verticalCenter
      iconText: String.fromCodePoint(0xF0156)
      tooltipText: pageTitle.closeTooltip
      onClicked: pageTitle.closed()
    }
  }

  component PageHint: Text {
    width: parent ? parent.width : 0
    textFormat: Text.PlainText
    wrapMode: Text.Wrap
    color: Commons.Color.popups.text
    opacity: 0.5
    font.family: Style.font.family
    font.pixelSize: Style.font.bodySmall
  }

  // A row to pick, with the mouse or the arrows and Enter.
  component PageRow: Item {
    id: pageRow
    property bool selected: false
    property bool accent: false
    property string label: ""
    property string detail: ""
    property string glyph: ""
    property bool chevron: false
    property int chevronGlyph: 0xF0142
    signal picked()
    implicitHeight: Math.max(Style.space(30), pageRowText.implicitHeight + Style.spacing.xs * 2)
    Rectangle {
      anchors.fill: parent
      radius: Style.cornerRadius
      color: Commons.Color.popups.text
      opacity: pageRow.selected ? 0.12 : (pageRowMouse.containsMouse ? 0.06 : 0)
    }
    MouseArea {
      id: pageRowMouse
      anchors.fill: parent
      hoverEnabled: true
      cursorShape: Qt.PointingHandCursor
      onClicked: pageRow.picked()
    }
    Text {
      id: pageRowGlyph
      x: Style.spacing.sm
      anchors.verticalCenter: parent.verticalCenter
      visible: pageRow.glyph !== ""
      textFormat: Text.PlainText
      text: pageRow.glyph
      color: pageRow.accent ? Commons.Color.accent : Commons.Color.popups.text
      font.family: Style.font.family
      font.pixelSize: Style.font.icon
    }
    Column {
      id: pageRowText
      anchors.left: pageRowGlyph.visible ? pageRowGlyph.right : parent.left
      anchors.leftMargin: Style.spacing.sm
      anchors.right: pageRowChevron.visible ? pageRowChevron.left : parent.right
      anchors.rightMargin: Style.spacing.sm
      anchors.verticalCenter: parent.verticalCenter
      Text {
        width: parent.width
        textFormat: Text.PlainText
        elide: Text.ElideRight
        text: pageRow.label
        color: pageRow.accent ? Commons.Color.accent : Commons.Color.popups.text
        font.family: Style.font.family
        font.pixelSize: Style.font.body
      }
      Text {
        width: parent.width
        visible: text !== ""
        textFormat: Text.PlainText
        elide: Text.ElideRight
        text: pageRow.detail
        color: Commons.Color.popups.text
        opacity: 0.6
        font.family: Style.font.family
        font.pixelSize: Style.font.bodySmall
      }
    }
    Text {
      id: pageRowChevron
      anchors.right: parent.right
      anchors.rightMargin: Style.spacing.sm
      anchors.verticalCenter: parent.verticalCenter
      visible: pageRow.chevron
      textFormat: Text.PlainText
      text: String.fromCodePoint(pageRow.chevronGlyph)
      color: Commons.Color.popups.text
      opacity: 0.6
      font.family: Style.font.family
      font.pixelSize: Style.font.icon
    }
  }

  // A box editor's field: its label over a text field. Up/Down move to the
  // next field, Enter saves, Esc goes back.
  component BoxField: Column {
    id: boxField
    property string label: ""
    property alias text: boxFieldInput.text
    property alias placeholder: boxFieldInput.placeholderText
    property alias password: boxFieldInput.password
    property alias maximumLength: boxFieldInput.maximumLength
    property bool current: false
    signal moved(int step)
    signal entered()
    signal escaped()
    signal focused()
    signal edited()
    function take() { boxFieldInput.forceActiveFocus() }
    spacing: 2
    Text {
      width: boxField.width
      textFormat: Text.PlainText
      elide: Text.ElideRight
      color: Commons.Color.popups.text
      opacity: 0.7
      font.family: Style.font.family
      font.pixelSize: Style.font.bodySmall
      text: boxField.label
    }
    TextField {
      id: boxFieldInput
      width: boxField.width
      foreground: Commons.Color.popups.text
      hasCursor: boxField.current
      onActiveFocusChanged: if (activeFocus) boxField.focused()
      onTextEdited: boxField.edited()
      Keys.onPressed: function(event) {
        var k = event.key
        if (k === Qt.Key_Up || k === Qt.Key_Down) {
          event.accepted = true
          boxField.moved(k === Qt.Key_Up ? -1 : 1)
        } else if ((k === Qt.Key_Return || k === Qt.Key_Enter) && !event.isAutoRepeat) {
          event.accepted = true
          boxField.entered()
        } else if (k === Qt.Key_Escape) {
          event.accepted = true
          boxField.escaped()
        }
      }
    }
  }

  // The plot in the Details dialog (SPEC "Details"): plain text but for its
  // web links (PlotLinks.js), underlined in the accent colour, and Kodi's
  // bold, italics and colours (styles: the state's plotStyles), as on a
  // phone remote. A click on a link, or Enter on the one Tab marked
  // (focusedLink), asks to open it (openLink). Read-only: it never takes
  // the keyboard.
  component DetailsPlot: TextEdit {
    id: plotText
    property string plot: ""
    property var styles: []
    property int focusedLink: -1
    property color linkColor: "blue"
    property color focusedColor: "white"
    readonly property var parts: PlotLinks.parts(plot)
    readonly property var links: PlotLinks.links(parts)
    signal openLink(string url)
    onPlotChanged: focusedLink = -1
    readOnly: true
    activeFocusOnPress: false
    activeFocusOnTab: false
    selectByMouse: false
    selectByKeyboard: false
    textFormat: TextEdit.RichText
    wrapMode: TextEdit.Wrap
    font.family: Style.font.family
    font.pixelSize: Style.font.body
    color: Commons.Color.popups.text
    text: PlotLinks.markup(parts, focusedLink, PlotLinks.css(linkColor), PlotLinks.css(focusedColor), styles)
    onLinkActivated: function(link) {
      var at = PlotLinks.linkIndex(link, links.length)
      if (at >= 0) openLink(links[at])
    }
    // Marks the next (1) or previous (-1) link, round the end; its box in
    // this item, or null without links.
    function moveFocus(dir) {
      focusedLink = PlotLinks.step(links.length, focusedLink, dir)
      if (focusedLink < 0) return null
      var start = PlotLinks.offset(parts, focusedLink)
      var a = positionToRectangle(start)
      var b = positionToRectangle(start + links[focusedLink].length)
      var top = Math.min(a.y, b.y)
      return Qt.rect(0, top, width, Math.max(a.y + a.height, b.y + b.height) - top)
    }
    // Opens the marked link; false when none is marked.
    function openFocused() {
      if (focusedLink < 0 || focusedLink >= links.length) return false
      openLink(links[focusedLink])
      return true
    }
    HoverHandler { cursorShape: plotText.hoveredLink !== "" ? Qt.PointingHandCursor : Qt.ArrowCursor }
  }

  // A heading in the Details dialog: Overview, Info, Cast.
  component DetailsHeading: Text {
    width: parent ? parent.width : 0
    topPadding: Style.spacing.lg
    bottomPadding: Style.spacing.xs
    textFormat: Text.PlainText
    elide: Text.ElideRight
    color: Commons.Color.popups.text
    font.family: Style.font.family
    font.pixelSize: Style.font.subtitle
    font.bold: true
  }

  // A badge in the Details dialog (4K, HEVC, DD+, 5.1 …): bold, outlined.
  component DetailsBadge: Rectangle {
    property string label: ""
    width: badgeLabel.implicitWidth + Style.spacing.sm * 2
    height: badgeLabel.implicitHeight + Style.spacing.xs * 2
    radius: Style.space(4)
    color: "transparent"
    border.width: 1
    border.color: Qt.rgba(Commons.Color.popups.text.r, Commons.Color.popups.text.g,
                          Commons.Color.popups.text.b, 0.5)
    Text {
      id: badgeLabel
      anchors.centerIn: parent
      textFormat: Text.PlainText
      font.family: Style.font.family
      font.pixelSize: Style.font.bodySmall
      font.bold: true
      color: Commons.Color.popups.text
      text: parent.label
    }
  }

  // A section's name in a page, in the accent colour.
  component SectionLabel: Text {
    width: parent ? parent.width : 0
    leftPadding: Style.spacing.sm
    topPadding: Style.spacing.sm
    textFormat: Text.PlainText
    elide: Text.ElideRight
    color: Commons.Color.accent
    font.family: Style.font.family
    font.pixelSize: Style.font.bodySmall
    font.bold: true
  }

  // A square in the icon page: the chosen one filled, the selected one ringed.
  component IconTile: Item {
    id: iconTile
    property bool selected: false
    property bool chosen: false
    property string tooltip: ""
    signal picked()
    Rectangle {
      anchors.fill: parent
      radius: Style.cornerRadius
      color: iconTile.chosen ? Qt.rgba(Commons.Color.accent.r, Commons.Color.accent.g, Commons.Color.accent.b, 0.3)
        : Qt.rgba(Commons.Color.popups.text.r, Commons.Color.popups.text.g, Commons.Color.popups.text.b,
                  iconTileMouse.containsMouse ? 0.16 : 0.08)
      border.width: iconTile.selected ? 2 : 0
      border.color: Commons.Color.accent
    }
    MouseArea {
      id: iconTileMouse
      anchors.fill: parent
      hoverEnabled: true
      cursorShape: Qt.PointingHandCursor
      onClicked: iconTile.picked()
    }
    PanelToolTip {
      visible: iconTileMouse.containsMouse && iconTile.tooltip !== ""
      text: iconTile.tooltip
    }
  }
}
