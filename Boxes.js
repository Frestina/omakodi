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

// lib/omakodi/rpc.py is_address(): an IP address, or a name of
// dot-separated labels (letters, digits, "_", inner "-"; at most 63 each,
// 253 in all). Not "kodi..lan", nor one with a port in it. Every IPv4
// address is such a name too; an IPv6 one is checked as Python's
// ipaddress does.
var LABEL_RE = /^[A-Za-z0-9_]([A-Za-z0-9_-]{0,61}[A-Za-z0-9_])?$/
var HEXTET_RE = /^[0-9A-Fa-f]{1,4}$/
var OCTET_RE = /^(0|[1-9][0-9]{0,2})$/

function ipv4(text) {
  var octets = text.split(".")
  if (octets.length !== 4) return false
  for (var i = 0; i < 4; i++)
    if (!OCTET_RE.test(octets[i]) || Number(octets[i]) > 255) return false
  return true
}

function ipv6(text) {
  if (text === "" || text.length > 45) return false
  var parts = text.split(":")
  if (parts.length < 3 || parts.length > 9) return false
  if (parts[parts.length - 1].indexOf(".") >= 0) {  // an IPv4 address at the end: two parts
    if (!ipv4(parts.pop())) return false
    parts.push("0", "0")
  }
  if (parts.length > 9) return false
  var skip = -1
  for (var i = 1; i < parts.length - 1; i++) {
    if (parts[i] !== "") continue
    if (skip >= 0) return false  // one "::" at most
    skip = i
  }
  var hi = parts.length, lo = 0
  if (skip >= 0) {
    hi = skip
    lo = parts.length - skip - 1
    if (parts[0] === "") {
      hi -= 1
      if (hi !== 0) return false
    }
    if (parts[parts.length - 1] === "") {
      lo -= 1
      if (lo !== 0) return false
    }
    if (8 - (hi + lo) < 1) return false
  } else if (parts.length !== 8 || parts[0] === "" || parts[7] === "") {
    return false
  }
  for (var j = 0; j < hi; j++) if (!HEXTET_RE.test(parts[j])) return false
  for (var k = parts.length - lo; k < parts.length; k++) if (!HEXTET_RE.test(parts[k])) return false
  return true
}

function isAddress(text) {
  if (typeof text !== "string" || text === "") return false
  if (text.indexOf(":") >= 0) return ipv6(text)
  var name = text.charAt(text.length - 1) === "." ? text.slice(0, -1) : text
  if (name.length === 0 || name.length > 253) return false
  var labels = name.split(".")
  for (var i = 0; i < labels.length; i++) if (!LABEL_RE.test(labels[i])) return false
  return true
}

// The address as the daemon keeps it, or "" when it takes none (boxes.py
// editor_host()).
function host(value) {
  var h = strip(value || "")
  return HOST_RE.test(h) && isAddress(h) ? h : ""
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
