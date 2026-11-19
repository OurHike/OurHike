# Blaze card — design frames

One `.dc.html` per phone frame, rendered at 390 px wide (the sizes are in `canvas.json`).
Each file is plain HTML in the Design Component format: the markup under `<x-dc>` is the
screen; the `<script type="text/x-dc">` block holds its data and logic. They are the spec
for `features/CHALLENGES_BLAZE_CARD.md`, not shippable code.

- `Main.dc.html` — 1 · New to the challenge (welcome; the four-beat explainer)
- `Card.dc.html` — 2 · Your card
- `Tile.dc.html` — 3 · A tile, opened (photo-led; the slot is a labelled stand-in)
- `Where.dc.html` — 4 · Where did it happen?
- `Line.dc.html` — 5 · Where your blazes are (map + trail-order list)
- `Home.dc.html` — 6 · Today, once joined (walk prompt at the top, season strip at the bottom)
- `Poster.dc.html` — 7 · Share poster, 1080×1350
- `BlazeCard.dc.html` — the card component: the 26-icon set and the icon per item for all 100
- `StateStrip.dc.html` — the fourteen-stop line; its mile bands are approximate (@unvalidated)
- `item-icons.json` — icon per item id (26 names, defined in `BlazeCard.dc.html`)
- `self-report-on-trail.json` — per at-home item id: whether "Where did it happen?" is asked
- `map-phone.svg`, `map-where.svg`, `map-welcome.svg`, `map-poster.svg` — the maps, in the app's Field
  palette with the challenge diamond pin; real A.T. line (OSM) and real outlines; `mapbuild/` rebuilds them

The live canvas: https://claude.ai/artifact/JbZbp377XmGrS92o4AvmpE
