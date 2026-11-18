.pragma library

// The power menu and its "Reboot <box>?" dialog (SPEC "Remote panel"). Pure,
// so they can be checked without the shell.

// The rows, in the phone remote's order: Wake up, Turn on soundbar, Kodi's
// own power menu, then (after a divider) Reboot and Shut down when Kodi
// allows them. `power` is the state's {state, reboot, shutdown} or null
// (Kodi isn't answering); `wakeOnLan` false hides Wake up.
function items(power, wakeOnLan) {
  var out = []
  if (wakeOnLan !== false) out.push("wake")
  out.push("soundbaron", "powermenu")
  if (power && power.reboot === true) out.push("reboot")
  if (power && power.shutdown === true) out.push("shutdown")
  return out
}

function asks(action) {
  return action === "reboot" || action === "shutdown"
}

// Whether the divider goes above row `at`: above the first row that asks.
function dividerAbove(list, at) {
  return asks(list[at]) && (at === 0 || !asks(list[at - 1]))
}

// Picking row `action`: {send: the action to send at once, or "", ask: the
// action the dialog asks about, or ""}. Either way the menu closes.
function pick(action) {
  if (asks(action)) return { send: "", ask: action }
  if (action === "wake" || action === "soundbaron" || action === "powermenu") return { send: action, ask: "" }
  return { send: "", ask: "" }
}

// The dialog: {action, at}, `at` the button with the keyboard's cursor:
// 0 Cancel (where it starts), 1 the action.
function ask(action) {
  return asks(action) ? { action: action, at: 0 } : null
}

// A key (or click) in the dialog: "left", "right", "tab", "enter",
// "escape", "cancel" (its button clicked) or "confirm" (the action's
// button clicked). Returns {dialog: the dialog after it, or null once
// closed, send: the action to send, or ""}. Only Enter on the action's
// button, or a click on it, sends it.
function dialogKey(dialog, key) {
  if (!dialog || !asks(dialog.action)) return { dialog: null, send: "" }
  if (key === "left") return { dialog: { action: dialog.action, at: 0 }, send: "" }
  if (key === "right") return { dialog: { action: dialog.action, at: 1 }, send: "" }
  if (key === "tab") return { dialog: { action: dialog.action, at: dialog.at === 1 ? 0 : 1 }, send: "" }
  if (key === "confirm") return { dialog: null, send: dialog.action }
  if (key === "enter") return { dialog: null, send: dialog.at === 1 ? dialog.action : "" }
  if (key === "escape" || key === "cancel") return { dialog: null, send: "" }
  return { dialog: dialog, send: "" }
}
