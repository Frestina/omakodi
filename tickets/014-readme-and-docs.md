---
id: 014
title: README, security and docs
milestone: M3
depends_on: [012, 017, 018, 019]
---

## Goal

Someone else can set it up, knows what it sends where, and knows its limits.

## Done when

- [ ] README: what it does, Kodi settings, add-ons, install, config, keybindings, key map, removal, Compatibility (exact versions tested).
- [ ] SECURITY.md: plain HTTP and the login-free port 9090 on the LAN, where the password lives, what is never logged.
- [ ] CHANGELOG.md with 0.1.0.
- [ ] `git leakguard` clean; no real hosts, addresses or account names anywhere.
