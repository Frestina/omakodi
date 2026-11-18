---
id: 022
title: Marketplace listing
milestone: M4
depends_on: [015, 023, 024, 025, 026, 027, 028, 029, 030, 031, 032]
---

## Goal

omakodi listed in the Omarchy plugin marketplace. Split from ticket 015: the
user wants the remote complete before it is listed, so the repo and release
come first and the listing waits.

## Before it starts

The user picked the v2 work that makes the remote complete (2026-11-18):
tickets 023–031. This ticket stays `blocked` until they are done and the
user says go. Before submitting, decide with the user whether `CLAUDE.md`
(agent instructions, flagged by the release preflight) stays in the repo.

## Done when

- [ ] The user says the remote is complete enough to list.
- [ ] The release being listed passes the release preflight (omarchy-plugin-release skill).
- [ ] Marketplace issue submitted with the user's approval (omarchy-plugin-publish skill).
