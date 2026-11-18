# Backlog

Not in v1. Turn an item into a ticket when it is picked up.

## v2

Moved to tickets 023–031 (milestone M5) on 2026-11-18.

## v3

Moved to tickets 041 (shortcut buttons) and 042 (several Kodi boxes),
milestone M6, on 2026-11-18.

## From the ticket 012 live check

- **`kind` for add-on items** is `"unknown"` (Kodi's `type` for a plugin
  item); nothing shows it yet. If v2 needs it, derive it from the player
  (`video`/`audio`).

## From ticket 041

- **The marketplace screenshot** (`preview.png`, made by the demo) still
  shows the Play link / Queue link buttons; make it again before the next
  release, with the fake Kodi answering the picker if it should show one.

## From ticket 042

- **Two Kodis on one address** (different ports, say in containers) can't
  both be saved: a box is known by its `host`, which its per-box state is
  kept under. Give boxes an id if that ever matters.
- **A box saved under a new address** starts without its shortcut
  buttons, YouTube mode, MAC address and soundbar finding (kept under the
  old `host`). Move them along on save if users change addresses often.
- **Test connection with a changed address** uses the box's saved
  password when the field is untouched (as a phone remote's filled field
  would). Ask the user whether a changed address should need the password
  typed again.
- ~~**The ☰ menu (043)** should list the boxes~~: done in 043.

## From ticket 043

- **The title of a box without a name** is its address (the phone shows
  the name typed when the box was added; omakodi's editor fills it from
  Kodi's name on Test connection). Kodi's `System.FriendlyName` could
  stand in until the box is named, read once each time Kodi comes on.
- **The context key** (action row) has the same ☰ icon as the new menu
  button; 044 (the keys like the phone remote) should give it another.
- **Kodi's volume level** ("Volume 80%") left the header with the phone's
  top bar and shows nowhere now; ask the user whether 044 or 045 should
  show it (the phone shows none).

## Ideas

- Moved to M6 on 2026-11-18: SendToKodi failures (038), a stop isn't a
  YouTube failure (039), `youtubeMode` as a widget setting (040).
- An Omarchy menu entry ("Play clipboard on Kodi").
- Open local files that Kodi can already reach through a shared folder.
