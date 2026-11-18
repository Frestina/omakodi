.pragma library

// The power menu's ask-again rule (SPEC "Remote panel"). Pure, so it can be
// checked without the shell.

// The rows: Kodi's own power menu, turn on the TV, then reboot and shut
// down when Kodi allows them. `power` is the state's {state, reboot,
// shutdown} or null.
function items(power) {
  var out = ["powermenu", "tvon"]
  if (power && power.reboot === true) out.push("reboot")
  if (power && power.shutdown === true) out.push("shutdown")
  return out
}

// Picking row `action` with `armed` the row picked once before (or ""):
// returns {send: action to send or "", armed: the row now waiting for a
// second press or ""}. Kodi's power menu and turning on the TV go at
// once; reboot and shut down only on a second pick of the same row.
function pick(action, armed) {
  if (action === "powermenu" || action === "tvon") return { send: action, armed: "" }
  if (action !== "reboot" && action !== "shutdown") return { send: "", armed: "" }
  if (armed === action) return { send: action, armed: "" }
  return { send: "", armed: action }
}
