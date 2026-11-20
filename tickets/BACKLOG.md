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

- ~~**Two Kodis on one address**, **a box saved under a new address**~~:
  ticket 054 (2026-11-20, as the phone remote: boxes get an id).
- ~~**Test connection with a changed address**~~: keeps using the saved
  password, as the phone remote does (2026-11-20).
- ~~**The ☰ menu (043)** should list the boxes~~: done in 043.

## From ticket 043

- **The title of a box without a name** is its address (the phone shows
  the name typed when the box was added; omakodi's editor fills it from
  Kodi's name on Test connection). Kodi's `System.FriendlyName` could
  stand in until the box is named, read once each time Kodi comes on.
- ~~**The context key** (action row) has the same ☰ icon as the new menu
  button~~: done in 044 (the context key left the row: long press of OK).
- ~~**Kodi's volume level** ("Volume 80%") left the header with the
  phone's top bar and shows nowhere now~~: the user (2026-11-20): it
  stays hidden, as on the phone.

## From ticket 045

- **The audio track list** still opens under the now-playing bar; the
  phone remote shows it as a drop-down under its audio key. Move it if
  the user wants that too.
- **The demo scene** can now give what plays a made-up poster and a
  queue (`"art": true`, `"queue": […]` in the fake's scene); the next
  `preview.png` could show the now-playing page.
- ~~**Kodi's volume level** (from 043)~~: stays hidden (the user,
  2026-11-20).

## From ticket 046

- ~~**Colours in the plot**~~: ticket 052 (2026-11-20). The links went
  to ticket 049 (2026-11-19).
- ~~**The badges' and the audio tracks' words differ**~~: ticket 051,
  both as the phone remote words them (2026-11-20).

## From ticket 047

- **Kodi's text when the keyboard key finds the keyboard**: the phone
  remote then reads the text from Kodi's keyboard and starts the dialog
  with it. omakodi starts empty, because that text would be a password
  in clear and Kodi doesn't say which kind of field it is. Pre-fill only
  if a way turns up to tell a password field apart.
- **Without the event port**, a keyboard the keyboard key found is never
  seen closing (no `Input.OnInputFinished`): the key stays marked and opens
  the dialog again without asking Kodi. Ask Kodi again then, or leave it
  (the README says the event port is needed).
- ~~**Number, date, time and IP fields**~~: the phone remote has no
  number pad either, only a different phone keyboard; the same dialog for
  all of them is the same as the phone (2026-11-20).

## From ticket 048

- ~~**The phone's other messages**~~: ticket 053 (2026-11-20).
- ~~**The short message sits over the now-playing bar**~~: the phone's
  toasts cover its now-playing bar too, so it stays (2026-11-20).
- **The bar widget's tooltip** still shows Kodi's error in full; only the
  remote and the notifications say "Can't reach <box>".

## From ticket 051

- **The audio list with one track**: the phone remote opens its list
  for a single track too (one row, in the accent colour); the remote dims
  the audio key and says "This has only one audio track". Same as the
  phone, or keep?

## From ticket 052

- **Kodi's colours on a light theme**: the plot's colours are Kodi's (the
  YouTube add-on's light blue, green and cyan, white, the light basic
  names), made for a dark screen like the phone's. On a light Omarchy
  theme some are hard to read; the remote could darken them there.

## Ideas

- Moved to M6 on 2026-11-18: SendToKodi failures (038), a stop isn't a
  YouTube failure (039), `youtubeMode` as a widget setting (040).
- An Omarchy menu entry ("Play clipboard on Kodi").
- Open local files that Kodi can already reach through a shared folder.
