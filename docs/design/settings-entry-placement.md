# Where the Settings entry should live

The sidebar bottom cluster has exactly two things today: the active
model/plugin indicator with the CPU/GPU switch, and the Settings leaf.
This document records the four placement options considered for the
Settings entry. It does not change any of them yet — the current placement
(the sidebar bottom leaf) stays until the owner picks one.

The structure is deliberately isolated: `Sidebar.tsx` renders the bottom
cluster from one small list, so replacing the leaf with any of the options
below does not touch navigation state, routing, search, or the model
indicator.

## Option 1 — Title bar, right next to the theme toggle

Put a Settings button in the title-bar control cluster beside the theme
switch.

- Visible in both sidebar states; no need to expand the rail.
- The title bar is already crowded on small windows.
- Breaks the single-home rule: the theme switch is the only control with
  that home today.

## Option 2 — Title bar, left next to the sidebar toggle

Put a Settings button beside the sidebar collapse control.

- Always visible, and groups "shell" controls together.
- Left edge is also the most likely place for accidental clicks while
  dragging the window.
- Still duplicates a control outside the nav composite, so keyboard order
  has to be wired separately.

## Option 3 — Icon-only button at the right of a future profile row

Add a profile row at the top of the sidebar and place an icon-only Settings
button at its far end.

- Natural home for account/provider identity later.
- Disappears when the sidebar is collapsed, so Settings becomes
  unreachable from the rail in that state.

## Option 4 — Settings inside a profile dropdown (favoured)

Add a profile/avatar button that stays in the collapsed rail and opens a
menu containing Settings.

- Reachable in BOTH sidebar states: the avatar remains as a 48px icon.
- Gives future account/provider actions one home instead of scattering
  them across the title bar and sidebar.
- Costs one extra click compared with the current leaf, but keeps the rail
  calmest.

**Favoured: option 4.** It is the only option that keeps Settings reachable
while collapsed and leaves room for profile-related actions without adding
a second control surface. No placement change is part of this work; this
document only records the decision for a follow-up.
