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

- [x] Unit tests: light and dark themes with and without art, a colour
      that only fails over art, the fallback. (Built as the result below
      allows: a test that the plot's background is the opaque dialog in
      the card's colour; 056's tests cover the colours on it.)
- [x] Live, by the user: a YouTube video with dark art on a light theme;
      the plot's colours read easily. *2026-11-20: the user's check passes.*

## Result (2026-11-20)

The art never shows behind the plot. The Details dialog is a dialog on
the now-playing page: the page covers the card (its blurred art
included) with an opaque rectangle in the card's colour, and the dialog
itself is an opaque rectangle in that colour (`Panel.qml`, the
Rectangle holding `detailsPane`). So the plot is always drawn on the
popup colour 056 checks against, art or not, and no blend rule is
needed. `tests/test_plot_links.py` `PlotBackgroundTest` holds that: the
plot's `backgroundColor` is `card.color`, the rectangle under it is
`card.color` with nothing between made translucent (no `opacity`, no
layer), and the card's colour is the theme's popup colour made opaque.
If the dialog ever lets the art through, the test fails and the rule in
the scope above has to be built. SPEC "Details" says so.
