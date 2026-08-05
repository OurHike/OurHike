# Bundled glyphs

Font glyph PBFs served to MapLibre from the app's own origin, so every label
on the hiking sheet — place names, peak elevations, contour labels — renders
with no signal (issue #188). `src/map/liveTopo.ts` (`BUNDLED_GLYPHS`) is the
one place that points here, and `vite.config.ts`'s workbox `globPatterns` is
what puts all of this into the service worker's precache;
`scripts/check-build-output.mjs` fails the build if either drifts.

## Contents and provenance

`Noto Sans Regular/` — all 256 glyph ranges (`0-255.pbf` … `65280-65535.pbf`,
6,240,473 bytes total), fetched 2026-08-05 from
[protomaps/basemaps-assets](https://github.com/protomaps/basemaps-assets)
at commit `028c18f713baecad011301ff7a69acc39bcc2ae7`
(`fonts/Noto Sans Regular/`). The total matches the measurement recorded in
issue #188 byte for byte.

The directory name is load-bearing: MapLibre substitutes the style's
`text-font` stack into the `{fontstack}` URL token verbatim, so the folder
must be named exactly `Noto Sans Regular`, space included.

## Licence

Noto Sans is © The Noto Project Authors, licensed under the SIL Open Font
License 1.1 — the full text ships alongside the ranges in
`Noto Sans Regular/OFL.txt`, as the OFL requires of redistribution. See also
CONTRIBUTING.md's "A note on data and licences".
