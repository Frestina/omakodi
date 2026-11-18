---
id: 022
title: Marketplace listing
milestone: M4
depends_on: [015]
---

## Goal

omakodi listed in the Omarchy plugin marketplace. Split from ticket 015: the
user wants the remote complete before it is listed, so the repo and release
come first and the listing waits.

## Before it starts

The user decides when the remote is complete (likely some of the backlog's v2
remote: the now-playing panel, the queue list). Until then this ticket is
`blocked`; when they say go, the work they want first becomes tickets that
this one depends on.

## Done when

- [ ] The user says the remote is complete enough to list.
- [ ] The release being listed passes the release preflight (omarchy-plugin-release skill).
- [ ] Marketplace issue submitted with the user's approval (omarchy-plugin-publish skill).
