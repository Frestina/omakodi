---
id: 059
title: The plot's colours stay readable over the artwork
milestone: M7
depends_on: [056]
---

## Goal

056 checks Kodi's colours against the theme's popup colour, but with
art playing the Details card shows the art blurred through that colour
(35 %). Dark art on a light theme (or light art on a dark one) can make
a colour read worse. The user (2026-11-20): fix it if it can be.

## Scope

- SPEC first ("Details").
- While art shows behind the card, a colour must reach 4.5:1 against
  the worst background the card can show: the popup colour blended
  with black and with white at the art's strength (65 % popup, 35 %
  art), as well as the plain popup colour. No sampling of the image is
  needed, so the colours don't change as the art loads.
- If no colour of that hue can reach 4.5:1 against all three, use the
  one closest to it (the theme's text colour's side), and say so in a
  comment in the tests.
- Without art: as 056.
- The art's strength comes from the same value the card uses, so the
  two can't drift apart.

## Done when

- [ ] Unit tests: light and dark themes with and without art, a colour
      that only fails over art, the fallback.
- [ ] Live, by the user: a YouTube video with dark art on a light theme;
      the plot's colours read easily.
