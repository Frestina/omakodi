---
id: 018
title: The remote keeps the keyboard; a click outside closes it
milestone: M2
depends_on: [010]
---

## Goal

While the remote is open the arrows work wherever the mouse is, and a click
outside it closes it, like Omarchy's own menus (SPEC "Remote panel").

Found in the ticket 012 live check: the arrows only worked while the mouse
was over the remote or the bar icon. The remote primes `Exclusive` focus for
250 ms, then settles on `OnDemand`; Hyprland's focus-follows-mouse then gives
the keyboard to the window under the pointer.

## Scope

- Follow Omarchy's `Ui/KeyboardPanel.qml`: the remote's layer surface covers
  the whole monitor (transparent), with the card placed inside it. The
  pointer is then always over the remote's own surface on that monitor, so
  focus stays with it. Keep the short `Exclusive` prime, then `OnDemand`
  (a long `Exclusive` routes every pointer event on every monitor to it).
- A click outside the card closes the remote. Clicks on the bar strip pass
  through (`mask`), so the bar icon still toggles it and other bar widgets
  work.
- The card's position doesn't change: centred below the bar on the focused
  monitor.
- Use the omarchy-panel-overlay skill.

## Not in this ticket

- Keeping the remote open while another window has the keyboard.

## Done when

- [ ] Live, laptop only: open with `SUPER SHIFT + K` with the mouse over a
      window; the arrows reach the remote (checked on the remote's status
      line or the fake, not the TV) without moving the mouse.
- [ ] Live: a click on a window closes the remote; the bar icon still
      toggles it; Esc and the close button still close it.
- [ ] Live: on a second monitor, if there is one, clicks there work.
