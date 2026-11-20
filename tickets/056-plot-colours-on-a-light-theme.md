---
id: 056
title: The plot's colours stay readable on a light theme
milestone: M7
depends_on: [052]
---

## Goal

Kodi's colours in the Details overview (052) are made for a dark
screen; on a light Omarchy theme some (white, light blue, cyan, light
green) are hard to read. The user (2026-11-20): make them not hard to
read.

## Scope

- SPEC first ("Details").
- When a colour has too little contrast against the dialog's background
  (the theme's colour, as the remote draws it), the remote darkens (on a
  light theme) or lightens (on a dark one) that colour until it reads,
  keeping its hue. A rule like WCAG's contrast ratio, 4.5:1 for body
  text, decides "reads".
- Colours that already read are left as Kodi gave them, so a dark theme
  looks as now (the same as the phone).
- The theme can change while the remote is open: the colours follow.

## Done when

- [x] Unit tests: the contrast rule, light and dark backgrounds, white
      on white, a colour that already reads left alone, hue kept.
- [x] Live, by the user: a YouTube video's Details on a light theme and
      on the usual dark one. *2026-11-20: the user's check passes.*
