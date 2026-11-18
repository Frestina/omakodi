---
id: 024
title: Artwork in the remote
milestone: M5
depends_on: [023]
---

## Goal

The remote shows the poster or thumbnail of what plays. Kodi's `/image/`
needs the login, so the daemon fetches it, not the QML.

## Scope

- SPEC first: where art is cached, sizes, what the state carries.
- Daemon: on a new item, fetch its `thumbnail` (or `art.poster`/`thumb`)
  through `/image/` with the login into `~/.cache/omakodi/` (dir 700, files
  600), image types only (checked by magic bytes, not the name), bounded
  size (a few MB), a bounded number of files kept. The state gains `art`: the
  local file path, or `""`.
- The remote shows it beside the title; nothing (no broken image) when
  there is none. The art URL itself never reaches the shell or the logs.

## Done when

- [x] Unit tests: fetch with the login, a non-image or oversized answer is
      dropped, old files are pruned, the URL isn't in the state.
- [x] Live, by the user: a YouTube video and a library item show their art.
      *2026-11-18: read-only check first (a YouTube `thumb`, 28 KB JPEG via
      `/image/`); then the user: "it worked".*
