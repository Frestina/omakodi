---
id: 046
title: Details like the phone remote
milestone: M7
depends_on: [026, 034, 045]
---

## Goal

The details of what plays laid out as on the user's phone remote.

## Scope

- SPEC first.
- Opened from the now-playing page's **Details** button (`d`): the title
  and subtitle; **Overview** with the whole plot (scrolling); the badges,
  including the video and audio codecs (4K, HEVC, DD+, 5.1 …); **Info**,
  one row per field with an icon: channel (YouTube), genre, show, date
  (premiered or aired, not only the year), studio, rating, age rating
  (MPAA), runtime, director, writer, country; **Cast** as cards with
  photo, name and role (photos through the art cache, so the login and
  any API key in an image URL stay out of the shell).
- Fields Kodi doesn't have are left out, as now.

## Done when

- [ ] Unit tests: the fields read from Kodi (library item, add-on item,
      YouTube), the badges, cast photos cached.
- [ ] Live, by the user: a library film and a YouTube video look like the
      phone's details.
