.pragma library

// The box editor's checks (SPEC "Kodi boxes"), the same as editor_box() in
// lib/omakodi/boxes.py (a test runs both over the same texts), so Save is
// only offered for settings the daemon takes. No password is ever checked
// or kept here: it goes to the daemon as typed.

var HOST_RE = /^[A-Za-z0-9._:-]{1,253}$/  // lib/omakodi/config.py HOST_RE
var MAC_RE = /^[0-9a-f]{2}([:-])[0-9a-f]{2}(\1[0-9a-f]{2}){4}$/i

// Python's str.strip() and str.split(): Unicode white space (JS's \s
// lacks \x1c-\x1f and \x85 and has ﻿).
var SPACE = "\t\n\v\f\r\x1c\x1d\x1e\x1f \x85\xa0                　"
function strip(s) {
  s = String(s)
  var a = 0, b = s.length
  while (a < b && SPACE.indexOf(s[a]) >= 0) a++
  while (b > a && SPACE.indexOf(s[b - 1]) >= 0) b--
  return s.slice(a, b)
}

// The address as the daemon keeps it, or "" when it takes none.
function host(value) {
  var h = strip(value || "")
  return HOST_RE.test(h) ? h : ""
}

// A port from its field: empty is the default; -1 when it isn't one.
function port(value, fallback) {
  var p = strip(value === undefined || value === null ? "" : value)
  if (p === "") return fallback
  if (!/^[0-9]{1,5}$/.test(p)) return -1
  var n = Number(p)
  return n >= 1 && n <= 65535 ? n : -1
}

// A MAC address field: "" (read from Kodi), the address in lower case
// with ":", or null when it isn't a box's.
function mac(value) {
  var m = strip(value || "")
  if (m === "") return ""
  if (!MAC_RE.test(m)) return null
  m = m.toLowerCase().replace(/-/g, ":")
  if (m === "00:00:00:00:00:00" || (parseInt(m.slice(0, 2), 16) & 1)) return null
  return m
}

// What is wrong with the editor's fields ("address", "webPort",
// "livePort", "mac"), or "" when Save may send them.
function problem(form) {
  if (host(form.host) === "") return "address"
  if (port(form.httpPort, 8080) < 0) return "webPort"
  if (port(form.tcpPort, 9090) < 0) return "livePort"
  if (mac(form.mac) === null) return "mac"
  return ""
}

// The `box` the daemon's boxSave and boxTest take. The password only when
// it was typed in (`passwordEdited`): otherwise the saved one stays.
function fields(form) {
  var box = {
    name: String(form.name || "").slice(0, 300),
    host: String(form.host || "").slice(0, 300),
    httpPort: port(form.httpPort, 8080),
    tcpPort: port(form.tcpPort, 9090),
    username: String(form.username || "").slice(0, 1024),
    mac: String(form.mac || "").slice(0, 64)
  }
  if (form.passwordEdited === true) box.password = String(form.password || "").slice(0, 1024)
  return box
}
