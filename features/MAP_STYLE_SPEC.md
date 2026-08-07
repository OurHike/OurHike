# Map appearance — user-selectable style, mode, and detail

> **Status, 2026-08-07:** received from the design project (`Map Styles.html`
> lives there, with the live mockups and the copy-ready palette blocks this
> spec refers to) and built the same day at the spec's own v1 scope: `field` +
> `night_hike` + the detail control, red light included.
> [MAP_OPTIONS.md](MAP_OPTIONS.md) §6 records what shipped and the choices
> made where this spec left room; the remaining three palettes land as
> values-only changes to `client/src/map/liveTopo.ts`'s tables. The spec
> itself is kept verbatim below - it is what code comments citing
> MAP_STYLE_SPEC.md mean.

PR-shaped spec, written against `main` (2026-08-06). Companion to the live
mockups in this project's `Map Styles.html`, which render every palette below
on the real stack (OpenFreeMap tiles, 3DEP contours, `liveTopoLayers()` verbatim).

## What the hiker gets

Three independent preferences, all display-only (never a map rebuild — the
same rule `attachContourUnits` already enforces):

| Preference | Values | Default |
|---|---|---|
| `mapStyle` | `quiet_pine` · `field` · `night_hike` · `parchment` · `ridgeline` | `field` (day) |
| `mapMode` | `day` · `night` · `auto` (follows `prefers-color-scheme`) | `auto` |
| `mapDetail` | `full` · `standard` · `minimal` | `standard` |

- `night_hike` also carries a `red_light` sub-mode (settings toggle, never default).
- v1 could ship only `field` + `night_hike` + the detail control and still be
  most of the value; the other palettes are additive.

## 1. Palette becomes a parameter (`liveTopo.ts`)

`TOPO_PALETTE` stops being one constant and becomes a lookup keyed by
`(mapStyle, mapMode)`. Layer stack unchanged — every entry has the same 20 keys.

Field / day (the reviewed favorite — 1b in the mockups):

```ts
export const TOPO_PALETTE = {
  wood: '#dcebd2', scrub: '#e8f0dd', wetland: '#cfe3d8', rock: '#eae6da',
  park: '#d3e6c6', parkEdge: '#5f8f57',
  water: '#8fc0dc', waterEdge: '#2e79a6', waterway: '#2e79a6',
  contour: '#8a6c42', contourIndex: '#5f4527', contourLabel: '#4a3620',
  // Roads/tracks NEUTRAL GRAY on purpose: nothing on the ground may share
  // a hue with a blaze color (review finding, 2026-08-06).
  roadMajor: '#dad6ca', roadMajorEdge: '#8e897a', roadMinor: '#ddd9cd',
  track: '#7b776b', path: '#55503f',
  boundary: '#6f6753', label: '#14130f', labelHalo: '#ffffff',
} as const
// style.ts: MAP_BACKGROUND_COLOR = '#ffffff'
// hillshade: shadow #4a4234 · highlight #ffffff · accent #6f6753
// water_name text-color #1c5c86 · trail casing #14130f
// HILLSHADE_EXAGGERATION (hiking-zoom end) = 0.30
// Field extras: peak text-size 12→14, contour label 10→11, halos 1.4→1.8
```

All other palettes (field/night, quiet_pine day+night, night_hike dark+red,
parchment day+lantern, ridgeline day+night) are in `Map Styles.html` — each
card's "Drop-in TOPO_PALETTE" block, copy-ready. Red-light additionally
overrides `line-color` on `trail-blaze` to `#e8804a` (blaze identity moves to
the tapped trail card).

## 2. Detail level (the "too much detail" fix)

Pure layer visibility — `setLayoutProperty(id, 'visibility', …)` on a live
map, via a `whenStyleReady` attach helper exactly like `attachContourUnits`:

| Layer | full | standard | minimal |
|---|---|---|---|
| `topo-boundary` (admin borders) | ✓ | — | — |
| `topo-track`, `topo-road-minor` | ✓ | ✓ | — |
| `topo-contour` (minor lines) + `topo-contour-label` | ✓ | ✓ | — |
| `topo-water-label`, `topo-scrub` | ✓ | ✓ | — |
| index contours, paths, peaks, places, major roads, water, trails | ✓ | ✓ | ✓ |

Borders default OFF (standard): wanted sometimes, distracting mostly.
Minimal keeps index contours so terrain still reads, and keeps paths because
side trails are hiker signal, not clutter.

## 3. Wiring

- `lib/userPreferences.ts`: add the three keys (+ `red_light`), persisted like
  `units`.
- `MapView.tsx`: `mapStyle`/`mapMode` stay OUT of the map-building effect's
  deps; an `attachMapAppearance(map, prefs)` helper re-paints via
  `setPaintProperty` per layer (palettes share layer IDs, so one loop covers
  all 20+ paint targets). `mapDetail` is the visibility loop above. Neither
  tears down WebGL under a hiker.
- `auto` mode: listen to `matchMedia('(prefers-color-scheme: dark)')`, apply
  the style's night palette; night_hike is the auto-dark for `field`.
- App chrome should follow `mapMode` (pine-900 chrome in night modes).
- Tests: palette tables are data — snapshot per (style, mode) that every key
  is a valid hex and layer IDs resolve; detail matrix asserted per level.

## Open questions

- Does `mapStyle` belong in onboarding or only Settings? (Suggest: Settings
  only; default field/day + auto night_hike is right for most.)
- Parchment as the forced style for print/export views?
- Should `minimal` also thin place labels to towns+ at hiking zooms?
