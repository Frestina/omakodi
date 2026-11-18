.pragma library

// The remote's top bar and its ☰ menu (SPEC "Remote panel"). Pure, so they
// can be checked without the shell.

// The status line under the box's name. `s`: {ready (the daemon has said
// something), daemonError, connecting (switched boxes, no answer yet),
// reachable, error, power}. Returns {word: "connected", "offline",
// "connecting" or "", note: "off", "restarting" or "", why: the error to
// show under it, fix: whether the "is Kodi on" fix goes under that}.
function status(s) {
  var none = { word: "", note: "", why: "", fix: false }
  if (!s) return none
  if (!s.ready) return { word: "connecting", note: "", why: "", fix: false }
  if (s.daemonError) return { word: "offline", note: "", why: String(s.daemonError), fix: false }
  if (s.connecting) return { word: "connecting", note: "", why: "", fix: false }
  var error = s.error ? String(s.error) : ""
  if (s.reachable) {
    // Kodi answers but refuses (a wrong password): its error says the fix.
    if (error) return { word: "offline", note: "", why: error, fix: false }
    return { word: "connected", note: "", why: "", fix: false }
  }
  var state = s.power ? s.power.state : ""
  if (state === "off" || state === "restarting") return { word: "offline", note: state, why: "", fix: false }
  return { word: "offline", note: "", why: error, fix: true }
}

// The title: the box in use's name (the address when it has none), "" with
// no box yet. `boxes` is the state's {current, list}.
function title(boxes) {
  if (!boxes || !boxes.list) return ""
  for (var i = 0; i < boxes.list.length; i++)
    if (boxes.list[i].host === boxes.current) return boxes.list[i].name || boxes.list[i].host
  return ""
}

// The menu's rows, in the phone remote's order: each saved box (a click
// switches to it), then Manage Kodi boxes and Settings. The version under
// them isn't a row.
function menuRows(boxes) {
  var rows = []
  var list = boxes && boxes.list ? boxes.list : []
  for (var i = 0; i < list.length; i++) rows.push({ kind: "box", host: list[i].host })
  rows.push({ kind: "manage", host: "" })
  rows.push({ kind: "settings", host: "" })
  return rows
}

// Where the menu's cursor starts: on the box in use, else the first row.
function menuStart(rows, current) {
  for (var i = 0; i < rows.length; i++) if (rows[i].kind === "box" && rows[i].host === current) return i
  return 0
}

// Up/Down in the menu: stays within the rows.
function menuMove(at, step, count) {
  if (count <= 0) return 0
  return Math.max(0, Math.min(count - 1, at + step))
}
