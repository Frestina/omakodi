.pragma library

// The remote's short message (SPEC "Remote panel"), as a phone remote's:
// it shows a few seconds and goes; an error stays until the next action.
// Pure, so it can be checked without the shell.

var SHOW_MS = 3000

// Answers shown in a place of their own: Test connection's beside its
// button, the picker's on its page, the network search on the Kodi boxes
// page.
var ELSEWHERE = ["boxTest", "browse", "discover"]

// How long a message stays: SHOW_MS, or 0 (until the next action) for an
// error.
function lasts(error) {
  return error === true ? 0 : SHOW_MS
}

// A command the service refused before sending it, in the phone remote's
// words where it has them (SPEC "Messages"): "no link found" (the IPC's
// answer) is "No link found"; the others as they are.
function refusal(text) {
  var t = String(text || "")
  return t === "no link found" ? "No link found" : t
}

// What a command's result `r` ({cmd, ok, text}) shows: {text, error}, or
// null for nothing (no words, or answered elsewhere). `editing`: the box
// editor waits for its Save or Delete and shows that answer itself.
function fromResult(r, editing) {
  if (!r || !r.text) return null
  if (ELSEWHERE.indexOf(r.cmd) >= 0) return null
  if ((r.cmd === "boxSave" || r.cmd === "boxDelete") && editing === true) return null
  return { text: String(r.text), error: r.ok === false }
}
