---
id: 004
title: "Send a link: play and queue"
milestone: M1
depends_on: [002]
---

## Goal

`omakodi play` and `omakodi queue` send a link to the right add-on, as in
SPEC "Sending a link" steps 1–4 and 6. The YouTube verdict is ticket 005;
here YouTube links are opened without watching.

## Scope

- `lib/omakodi/links.py`: URL extraction, YouTube video ID, plugin paths.
- `lib/omakodi/route.py`: mode × installed add-ons × failed-recently → route
  and note (pure function).
- `--clipboard` (wl-paste), `--notify` (notify-send, plain text, app name
  omakodi).
- Check SendToKodi 0.10.x on a real box or its source: `?url=` or a bare
  encoded URL. Record the answer in SPEC.

## Done when

- [x] Link tests: every YouTube URL form in SPEC, playlists/channels not treated as videos, trailing punctuation, text around the link, no link.
- [x] Route tests: every mode with every combination of installed add-ons.
- [x] Queue with nothing playing plays instead; with something playing adds to playlist 1 and reports the size.
- [x] Missing add-on errors match SPEC wording.
