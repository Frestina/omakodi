import QtQuick
import Quickshell.Io
import "Protocol.js" as Protocol

// Owns `omakodi daemon` and the state the bar widget and the remote share
// (SPEC "Architecture", "IPC target"). One instance while the plugin is enabled;
// destroying it (disable, reload) stops the daemon.
Item {
  id: root
  property string omarchyPath: ""
  property var shell: null
  property var manifest: null

  readonly property string pluginId: "io.github.frestina.omakodi"
  // bin/omakodi from this plugin's directory, never from PATH, run by the
  // system Python in isolated mode (no user site, no PYTHON* variables).
  readonly property string command: decodeURIComponent(Qt.resolvedUrl("bin/omakodi").toString().replace(/^file:\/\//, ""))
  readonly property string python: "/usr/bin/python3"

  // ---- shared state --------------------------------------------------------
  property bool ready: false            // a state line has arrived
  property bool reachable: false
  property string error: ""             // Kodi's or the config's, as the daemon words it
  property var playing: null            // {title, subtitle, kind, paused, positionSec, durationSec}
  property int volume: -1               // -1: unknown
  property bool muted: false
  property var input: null              // Kodi's on-screen keyboard: {type, title, value, hidden}
  property var queue: null              // the video queue while it plays: {position, start, total, items}
  property var details: null            // what Kodi knows about the playing item: {title, plot, badges, info, cast, …}
  property var audio: null              // the audio tracks: {current, tracks: [{index, name, language, codec, channels}]}
  property var power: null              // {state: "on"|"off"|"restarting", reboot, shutdown}
  property bool canWake: false          // a MAC address is known: `wake` can turn the box on
  property bool wakeOnLan: true         // the config's wakeOnLan: false hides Wake up
  property string volumeKeys: "unknown" // where volup/voldown go: "kodi", "tv" (HDMI-CEC) or "unknown"
  property var youtube: null            // {mode, from, avoidUntil, box}: the YouTube mode (the remote's Settings)
  property var shortcuts: null          // {box, buttons: [5 × {label, sendLink, icon, art, auto, custom, typed}]}
  property var picker: null             // the "Choose from Kodi" page shown: {seq, title, crumb, folder, depth, status, error, items}
  property var boxes: ({ current: "", list: [] })  // the Kodi boxes: {current, list: [{name, host, httpPort, tcpPort, username, hasPassword, mac, knownMac}]}
  property bool connecting: false       // switched boxes; the new one hasn't answered yet
  property var found: null              // "Found on your network": {status, error, total, boxes: [{name, host, httpPort, tcpPort}]}
  property var boxTested: null          // what Test connection learnt: {id, name, mac}
  property string daemonStatus: "stopped"  // starting, running, restarting, stopped
  property string daemonError: ""       // set when the daemon keeps stopping
  property var lastResult: null         // {id, cmd, ok, text}
  property string progressText: ""      // the step a pending play is on

  signal resultArrived(var result)

  // ---- daemon lifecycle ----------------------------------------------------
  property bool _stopping: false
  property int _nextId: 1
  property var _pending: ({})           // id -> cmd
  property int _pendingCount: 0
  property int _pendingKeys: 0          // control commands not answered yet
  property int _backoffMs: 1000
  property int _quickExits: 0
  property double _startedAt: 0
  property string _lastStderr: ""

  readonly property int maxPending: 64
  readonly property int maxBackoffMs: 60000
  readonly property int stableMs: 30000

  function start() {
    if (_stopping || daemon.running) return
    daemonStatus = "starting"
    _lastStderr = ""
    daemon.stdinEnabled = true
    daemon.running = true
  }

  function _daemonGone() {
    if (_stopping || restartTimer.running) return
    var ranMs = _startedAt > 0 ? Date.now() - _startedAt : 0
    _startedAt = 0
    _failPending("omakodi daemon restarted")
    input = null
    picker = null  // the new daemon starts with no picker
    found = null
    if (ranMs >= stableMs) {
      _backoffMs = 1000
      _quickExits = 0
    } else {
      _quickExits += 1
    }
    if (_quickExits >= 3) {
      daemonError = ("omakodi daemon keeps stopping" + (_lastStderr ? ": " + _lastStderr : "")).slice(0, Protocol.MAX_TEXT)
      ready = true
      reachable = false
      playing = null
    }
    daemonStatus = "restarting"
    restartTimer.interval = _backoffMs
    restartTimer.start()
    _backoffMs = Math.min(_backoffMs * 2, maxBackoffMs)
  }

  function _failPending(text) {
    var old = _pending
    _pending = ({})
    _pendingCount = 0
    _pendingKeys = 0
    for (var k in old)
      _finish({ id: Number(k), ok: false, message: "", error: text }, old[k])
  }

  function _finish(msg, cmd) {
    var r = { id: msg.id, cmd: cmd, ok: msg.ok, text: msg.ok ? msg.message : msg.error }
    lastResult = r
    progressText = ""
    resultArrived(r)
  }

  function _consume(line) {
    var msg = Protocol.parse(line)
    if (!msg) return
    if (msg.type === "state") {
      ready = true
      reachable = msg.reachable
      error = msg.error
      playing = msg.playing
      volume = msg.volume
      muted = msg.muted
      // Only on a change: the remote resets its text field when this does.
      if (JSON.stringify(msg.input) !== JSON.stringify(input)) input = msg.input
      // Only on a change too: a new object would reset the remote's list.
      if (JSON.stringify(msg.queue) !== JSON.stringify(queue)) queue = msg.queue
      // And here: a new object would rebuild the Details dialog (its cast row).
      if (JSON.stringify(msg.details) !== JSON.stringify(details)) details = msg.details
      if (JSON.stringify(msg.audio) !== JSON.stringify(audio)) audio = msg.audio
      if (JSON.stringify(msg.power) !== JSON.stringify(power)) power = msg.power
      canWake = msg.wake
      wakeOnLan = msg.wakeOnLan
      volumeKeys = msg.volumeKeys
      if (JSON.stringify(msg.youtube) !== JSON.stringify(youtube)) youtube = msg.youtube
      if (JSON.stringify(msg.shortcuts) !== JSON.stringify(shortcuts)) shortcuts = msg.shortcuts
      if (JSON.stringify(msg.boxes) !== JSON.stringify(boxes)) boxes = msg.boxes
      connecting = msg.connecting
      daemonError = ""
      _quickExits = 0
    } else if (msg.type === "picker") {
      picker = msg
    } else if (msg.type === "found") {
      found = msg
    } else if (msg.type === "boxTest") {
      if (_pending[msg.id] !== undefined) boxTested = msg
    } else if (msg.type === "progress") {
      if (_pending[msg.id] !== undefined) progressText = msg.message
    } else if (_pending[msg.id] !== undefined) {
      var cmd = _pending[msg.id]
      var rest = ({})
      for (var k in _pending) if (Number(k) !== msg.id) rest[k] = _pending[k]
      _pending = rest
      _pendingCount = Math.max(0, _pendingCount - 1)
      if (cmd === "control") _pendingKeys = Math.max(0, _pendingKeys - 1)
      _finish(msg, cmd)
    }
  }

  // Sends one command; returns "" or why it wasn't sent. The outcome comes
  // later as lastResult / resultArrived.
  function send(cmd, fields) {
    if (!daemon.running || daemonStatus !== "running") return "omakodi daemon isn't running"
    if (_pendingCount >= maxPending) return "busy: too many commands waiting"
    var id = _nextId
    _nextId = _nextId >= 1000000000 ? 1 : _nextId + 1
    var next = ({})
    for (var k in _pending) next[k] = _pending[k]
    next[id] = cmd
    _pending = next
    _pendingCount += 1
    if (cmd === "control") _pendingKeys += 1
    daemon.write(Protocol.request(id, cmd, fields || ({})))
    return ""
  }

  function control(action, isRepeat) {
    var a = String(action || "")
    if (Protocol.ACTIONS.indexOf(a) < 0) return "unknown action; one of: " + Protocol.ACTIONS.join(", ")
    return send("control", isRepeat === true ? { action: a, repeat: true } : { action: a })
  }

  // A held key: send the repeat only when Kodi has answered the last key, so
  // holding an arrow never builds a backlog. The daemon drops arrow repeats
  // during fullscreen video. Returns "" or why it was dropped.
  function key(action, isRepeat) {
    if (isRepeat && _pendingKeys > 0) return "repeat dropped"
    return control(action, isRepeat === true)
  }

  // What is typed into Kodi's on-screen keyboard; `done` submits it.
  function sendText(text, done) {
    var t = String(text || "")
    if (t.length > Protocol.MAX_TEXT) return "text too long"
    return send("text", { text: t, done: done === true })
  }

  // The keyboard key ("Type text"): the daemon asks Kodi whether its
  // keyboard is open (the dialog then opens), or says Kodi isn't asking for
  // text.
  function openKeyboard() { return send("keyboard", ({})) }

  // Jumps the playing item to `seconds` from its start.
  function seek(seconds) {
    var s = Number(seconds)
    if (!(Math.floor(s) === s && s >= 0 && s <= Protocol.MAX_SEEK)) return "bad position"
    return send("seek", { seconds: s })
  }

  // Plays the queue entry at `position` (0 is the first), or takes it out.
  function _queueCommand(cmd, position) {
    var p = Number(position)
    if (!(Math.floor(p) === p && p >= 0 && p < Protocol.MAX_QUEUE)) return "bad position"
    return send(cmd, { position: p })
  }
  function playQueueEntry(position) { return _queueCommand("goto", position) }

  // Plays the audio track with Kodi's `index`.
  function setAudioTrack(index) {
    var i = Number(index)
    if (!(Math.floor(i) === i && i >= 0 && i <= Protocol.MAX_AUDIO_INDEX)) return "bad audio track"
    return send("audio", { index: i })
  }
  function removeQueueEntry(position) { return _queueCommand("remove", position) }

  function _link(cmd, text) {
    var t = String(text || "")
    if (t.length === 0) return "no link found"
    if (t.length > Protocol.MAX_LINK_TEXT) return "text too long"
    if (!Protocol.hasLink(t)) return "no link found"
    progressText = ""
    return send(cmd, { text: t })
  }

  function play(text) { return _link("play", text) }
  function queue(text) { return _link("queue", text) }
  function refresh() { return send("refresh", ({})) }
  // The YouTube mode for this box (the remote's Settings), and trying the
  // add-on again in smart mode after it failed.
  function setYoutubeMode(mode) {
    if (Protocol.YOUTUBE_MODES.indexOf(mode) < 0) return "unknown YouTube mode"
    return send("youtubeMode", { mode: mode })
  }
  function youtubeRetry() { return send("youtubeRetry", ({})) }
  // The shortcut strip (SPEC "Shortcut buttons"): open button `slot` (0-4)
  // on Kodi; change one; and the "Choose from Kodi" picker, a page at a
  // time (`seq` is the page shown, so an old list is refused).
  function _slot(slot) {
    var n = Number(slot)
    return Math.floor(n) === n && n >= 0 && n < Protocol.SLOTS ? n : -1
  }
  function openShortcut(slot) {
    var n = _slot(slot)
    if (n < 0) return "no such button"
    return send("shortcut", { slot: n })
  }
  function setShortcut(slot, change) {
    var n = _slot(slot)
    if (n < 0) return "no such button"
    var fields = { slot: n }
    for (var k in change) fields[k] = change[k]
    return send("shortcutSet", fields)
  }
  function browse(action, seq, index) {
    var fields = { action: String(action) }
    if (action !== "root") fields.seq = Number(seq)
    if (action === "open") fields.index = Number(index)
    return send("browse", fields)
  }
  // The Kodi boxes (SPEC "Kodi boxes"): switch to one, add or change one
  // (`key` "" for a new box, else its saved host), delete one, test a
  // box's settings, and search the network. The password, when typed,
  // goes to the daemon in `box` and nowhere else: never logged, never in
  // the state.
  function useBox(host) {
    var h = String(host || "")
    if (h === "" || h.length > 253) return "no such box"
    return send("box", { host: h })
  }
  function saveBox(key, box) { return send("boxSave", { key: String(key || ""), box: box }) }
  function deleteBox(host) {
    var h = String(host || "")
    if (h === "" || h.length > 253) return "no such box"
    return send("boxDelete", { host: h })
  }
  function testBox(key, box) {
    boxTested = null
    return send("boxTest", { key: String(key || ""), box: box })
  }
  function discover() { return send("discover", ({})) }

  // Wake-on-LAN: the magic packet for the box (SPEC "Wake-on-LAN").
  function wake() { return send("wake", ({})) }

  // ---- the remote panel ----------------------------------------------------
  function openRemote() { return !!(shell && shell.summon(pluginId, "{}")) }
  function closeRemote() { return !!(shell && shell.hide(pluginId)) }
  function toggleRemote() { return !!(shell && shell.toggle(pluginId, "{}")) }
  function remoteOpen() { return !!(shell && shell.isPluginOpen(pluginId)) }

  function statusJson() {
    return JSON.stringify({
      daemon: daemonStatus,
      ready: ready,
      reachable: reachable,
      error: daemonError || error,
      playing: playing,
      volume: volume >= 0 ? volume : null,
      muted: muted,
      input: input,
      queue: queue,
      details: details,
      audio: audio,
      power: power,
      wake: canWake,
      volumeKeys: volumeKeys,
      youtube: youtube,
      shortcuts: shortcuts,
      boxes: boxes,
      connecting: connecting,
      pending: _pendingCount,
      lastResult: lastResult
    })
  }

  Process {
    id: daemon
    command: [root.python, "-I", root.command, "daemon"]
    stdinEnabled: true
    stdout: SplitParser { onRead: function(line) { root._consume(line) } }
    stderr: SplitParser {
      onRead: function(line) {
        var s = String(line || "").trim()
        if (s) root._lastStderr = s.slice(0, 200)
      }
    }
    onRunningChanged: {
      if (running) {
        root._startedAt = Date.now()
        root.daemonStatus = "running"
      } else {
        root._daemonGone()
      }
    }
    onExited: root._daemonGone()
  }

  Timer {
    id: restartTimer
    repeat: false
    onTriggered: root.start()
  }

  Component.onCompleted: start()
  Component.onDestruction: {
    _stopping = true
    restartTimer.stop()
    daemon.running = false
  }

  IpcHandler {
    target: "io.github.frestina.omakodi"
    function toggleRemote(): string { return root.toggleRemote() ? "ok" : "unavailable" }
    function openRemote(): string { return root.openRemote() ? "ok" : "unavailable" }
    function closeRemote(): string { return root.closeRemote() ? "ok" : "unavailable" }
    function play(text: string): string { return root.play(text) || "ok" }
    function queue(text: string): string { return root.queue(text) || "ok" }
    function control(action: string): string { return root.control(action) || "ok" }
    function seek(seconds: int): string { return root.seek(seconds) || "ok" }
    function shortcut(button: int): string { return root.openShortcut(button - 1) || "ok" }
    function status(): string { return root.statusJson() }
  }
}
