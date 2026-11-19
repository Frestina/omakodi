.pragma library

// The dialog for Kodi's keyboard (SPEC "Remote panel"), as on a phone
// remote: Kodi's prompt, a text field, Paste, Cancel and Send. Pure, so it
// can be checked without the shell. Nothing is sent while typing: Send
// gives Kodi the whole text once and submits it.

var MAX_TEXT = 300  // Protocol.MAX_TEXT, what the daemon takes

// The dialog's title: Kodi's prompt, or `fallback` ("Send text to Kodi").
function title(input, fallback) {
  return input && typeof input.title === "string" && input.title !== "" ? input.title : fallback
}

// Dots for a password.
function hidden(input) {
  return !!input && input.hidden === true
}

// What the field starts with: Kodi's text, never a password's (the daemon
// leaves it out anyway).
function startText(input) {
  if (!input || hidden(input) || typeof input.value !== "string") return ""
  return input.value.slice(0, MAX_TEXT)
}

// Paste: `clip` in place of the selection [from, to) of `text`, line breaks
// as spaces (the field is one line), at most MAX_TEXT characters in all.
// Returns {text, cursor}: the cursor after what was pasted.
function paste(text, from, to, clip) {
  text = String(text || "")
  var a = Math.max(0, Math.min(text.length, Math.min(from, to)))
  var b = Math.max(a, Math.min(text.length, Math.max(from, to)))
  var room = Math.max(0, MAX_TEXT - (text.length - (b - a)))
  var c = String(clip || "").replace(/[\r\n]+/g, " ").slice(0, room)
  return { text: text.slice(0, a) + c + text.slice(b), cursor: a + c.length }
}

// The keyboard key (Type text, k): "open" (the dialog again, while Kodi asks
// for text) or "ask" (the daemon asks Kodi whether its keyboard is open).
function keyboardKey(input) {
  return input ? "open" : "ask"
}

// A key or click in the dialog: "send" (Send, Enter), "cancel" (Cancel,
// Esc, a click beside it), anything else stays. Returns {open: whether the
// dialog stays open, send: the text to send with `done: true`, or null}.
// Cancel sends nothing: Kodi's keyboard stays on the TV.
function dialogKey(input, key, text) {
  if (!input) return { open: false, send: null }
  if (key === "send") return { open: false, send: String(text || "").slice(0, MAX_TEXT) }
  if (key === "cancel") return { open: false, send: null }
  return { open: true, send: null }
}
