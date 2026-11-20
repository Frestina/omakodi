.pragma library

// The remote's top bar and its ☰ menu (SPEC "Remote panel"). Pure, so they
// can be checked without the shell.

// The status line under the box's name. `s`: {ready (the daemon has said
// something), daemonError, connecting (switched boxes, no answer yet),
// reachable, error, power}. Returns {word: "connected", "offline",
// "connecting" or "", note: "off", "restarting" or "", why: the error to
// show under it, detail: the error's own fix (its lines after the first,
// SPEC "Messages"), fix: whether the "is Kodi on" fix goes under that}.
function status(s) {
  var none = { word: "", note: "", why: "", detail: "", fix: false }
  if (!s) return none
  if (!s.ready) return { word: "connecting", note: "", why: "", detail: "", fix: false }
  if (s.daemonError) return { word: "offline", note: "", why: String(s.daemonError), detail: "", fix: false }
  if (s.connecting) return { word: "connecting", note: "", why: "", detail: "", fix: false }
  var error = s.error ? String(s.error) : ""
  var cut = error.indexOf("\n")
  var why = cut < 0 ? error : error.slice(0, cut)
  var detail = cut < 0 ? "" : error.slice(cut + 1).trim()
  if (s.reachable) {
    // Kodi answers but refuses (a wrong password): its error says the fix.
    if (error) return { word: "offline", note: "", why: why, detail: detail, fix: false }
    return { word: "connected", note: "", why: "", detail: "", fix: false }
  }
  var state = s.power ? s.power.state : ""
  if (state === "off" || state === "restarting") return { word: "offline", note: state, why: "", detail: "", fix: false }
  return { word: "offline", note: "", why: why, detail: detail, fix: true }
}

// The title: the box in use's name (the address when it has none), "" with
// no box yet. `boxes` is the state's {current (the box's id), list}.
function title(boxes) {
  if (!boxes || !boxes.list) return ""
  for (var i = 0; i < boxes.list.length; i++)
    if (boxes.list[i].id === boxes.current) return boxes.list[i].name || boxes.list[i].host
  return ""
}

// The menu's rows, in the phone remote's order: each saved box (a click
// switches to it, by its id), then Manage Kodi boxes and Settings. The
// version under them isn't a row.
function menuRows(boxes) {
  var rows = []
  var list = boxes && boxes.list ? boxes.list : []
  for (var i = 0; i < list.length; i++) rows.push({ kind: "box", id: list[i].id })
  rows.push({ kind: "manage", id: "" })
  rows.push({ kind: "settings", id: "" })
  return rows
}

// Where the menu's cursor starts: on the box in use (its id), else the first row.
function menuStart(rows, current) {
  for (var i = 0; i < rows.length; i++) if (rows[i].kind === "box" && rows[i].id === current) return i
  return 0
}

// Up/Down in the menu: stays within the rows.
function menuMove(at, step, count) {
  if (count <= 0) return 0
  return Math.max(0, Math.min(count - 1, at + step))
}
