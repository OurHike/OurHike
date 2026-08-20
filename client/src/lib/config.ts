// Where published data is fetched from.
//
// The base URL is a build-time variable rather than a constant because the
// bucket it points at is not knowable from the source tree - it is whatever
// R2 (or a local static server, during a field test) is serving
// pipeline/publish.py's output. Set VITE_DATA_BASE_URL at build time; see
// client/README.md.
//
// Keys are flat at the bucket root and must match publish.py's artifact
// names exactly - a mismatch here is a 404 on a mountain, which is why the
// background tier names are spelled the same way in both places.

import type { DetailLevel } from './downloadDetail'

const RAW_BASE: string = import.meta.env.VITE_DATA_BASE_URL ?? ''

export const DATA_BASE_URL = RAW_BASE.replace(/\/+$/, '')

/** False when no bucket was configured at build time, so the UI can say so
 *  instead of firing downloads at a relative path that will never resolve. */
export const DATA_CONFIGURED = DATA_BASE_URL !== ''

export function dataUrl(key: string): string {
  return `${DATA_BASE_URL}/${key}`
}

/** Mirrors publish.py's BACKGROUND_ARCHIVES. */
const BACKGROUND_ARCHIVES: Record<DetailLevel, string> = {
  light: 'background_z11.pmtiles',
  standard: 'background.pmtiles',
  fine: 'background_z13.pmtiles',
}

export function archiveUrl(level: DetailLevel): string {
  return dataUrl(BACKGROUND_ARCHIVES[level])
}

/** The same tier as `latest.json` names it - the flat key publish.py uploaded,
 *  which is what a published hash is looked up by (lib/dataManifest.ts). */
export function archiveKey(level: DetailLevel): string {
  return BACKGROUND_ARCHIVES[level]
}

export const TRAILS_KEY = 'trails.geojson'

/**
 * The corridor-view centerline: the same trail, simplified to 100 m and
 * merged into one feature (pipeline/export_trails.py's write_overview, #869).
 *
 * 51,068 gzipped bytes against `trails.geojson`'s 4,143,296, measured against
 * the live bucket 2026-08-20 - 81x smaller, which at 12 Mbps is about 34 ms
 * of transfer against 2.8 s. That difference is the whole point: a first run
 * spends its three entry steps looking at the map behind them, and the real
 * centerline cannot arrive inside them.
 *
 * NOT NAVIGATION DATA, and the client has to keep that true. No point on it
 * is more than 100 m from the surveyed line, which is 0.013 px at the
 * corridor view and 0.43 px at the pin seam - and 14 px at z14, which is a
 * line in the wrong place. So it is drawn only below the seam
 * (map/style.ts's TRAIL_OVERVIEW_LAYER_ID), dropped the moment the real
 * centerline is on the map, and never stored: a phone with no signal has no
 * trail line, exactly as before, because what it is missing is the real one.
 *
 * Absent from a release exported before it existed, which reads as "no
 * overview" rather than as a failure - the same rule spurs.json and
 * elevation_profile.json already follow.
 */
export const TRAILS_OVERVIEW_KEY = 'trails_overview.geojson'

// Where each blue-blazed spur leads, keyed by the trail id in trails.geojson.
//
// A separate artifact rather than properties on trails.geojson because the
// client stores that file as an opaque Blob and hands it straight to MapLibre
// (lib/trailData.ts) - it never reads a property off it, so enriching it would
// put the answer somewhere the app structurally cannot look.
//
// Published by pipeline/export_spurs.py. Absent from data releases built
// before that existed, which lib/trailData.ts treats as "no spur detail" - not
// as a failed download.
export const SPURS_KEY = 'spurs.json'

// Who maintains which stretch of trail, published by
// pipeline/export_club_sections.py (#594): 30 clubs tiling 2,197.5 miles, plus
// the 38.5 miles in 27 runs ATC's own centerline cannot attribute.
//
// A separate artifact for the same reason spurs.json is one - the client hands
// trails.geojson to MapLibre as an opaque Blob and never reads a property off
// it. It carries mile ranges and no geometry, which is enough:
// lib/trailPosition.ts's trailSlice and trailPointAtMile turn a mile range into
// the coordinates the corridor view draws (features/CORRIDOR_VIEW.md, #598),
// so nothing about this needs the published centerline schema to change.
//
// Absent from releases built before export_club_sections.py, which
// lib/trailData.ts treats as "no attribution" rather than a failed download -
// the same way spurs.json is treated.
export const CLUB_SECTIONS_KEY = 'club_sections.json'

// Stretches of trail somebody says are worth going to, published by
// pipeline/export_highlights.py (#595): a name, ordered legs, and which basis
// the claim rests on.
//
// Small, keyed, and separate for the same reason club_sections.json is - and
// it carries no length, ascent or time, because the phone derives all three
// from the elevation profile it already holds (features/CORRIDOR_VIEW.md).
//
// Absent from releases built before that exporter, which lib/trailData.ts
// treats as "nothing to explore yet" rather than a failed download.
export const HIGHLIGHTS_KEY = 'highlights.json'

// The along-the-trail elevation profile, published by
// pipeline/export_elevation.py: ~141,000 {distance_mi, elevation_ft} samples at
// 25 m spacing along the real centerline. 7.0 MB of JSON that gzips to 0.89 MB,
// measured against the live bucket 2026-08-15 - under 7% of what trails.geojson
// already costs, which is why it is fetched whole rather than windowed.
// Windowing it would also defeat the point: the ribbon has to work in a dead
// zone fifty miles from where it downloaded.
//
// That gzipped figure is only what a hiker actually pays since #717. This
// comment quoted it for a long time while pipeline/publish.py uploaded with no
// Content-Encoding at all, so R2 served every one of the 7.0 MB - a claim about
// a compression nothing was performing.
//
// Absent from data releases built before export_elevation.py existed, which
// lib/trailData.ts treats as "no profile" rather than a failed download - the
// same way spurs.json is treated.
export const ELEVATION_KEY = 'elevation_profile.json'

// 'crossing' is published but is currently an empty FeatureCollection; it is
// listed anyway so it starts working the day the pipeline fills it, rather
// than needing a client release to notice.
//
// This list is the download list, so it is also the size of a hiker's first
// fetch. 'viewpoint', 'parking' and 'privy' roughly double the POI count
// (2,021 more features from ATC's own facility layers) - real weight, and
// still small beside trails.geojson, which at 12.3 MB raw and 4.1 MB gzipped
// (measured 2026-08-15) is the artifact that decides whether a download over a
// hostel's wifi is comfortable. The whole launch fetch is 21.5 MB of text that
// gzips to 5.3 MB, which is what #717 made it cost.
//
// Keep it in step with pipeline/lib/poi_schema.POI_TYPES: verify_release.py
// parses THIS array to know which artifacts a release must serve, so a type
// published but missing here is a layer that silently never reaches a phone.
export const POI_TYPES = [
  'shelter',
  'water',
  'campsite',
  'resupply',
  'crossing',
  'viewpoint',
  'parking',
  'privy',
] as const

export type PoiType = (typeof POI_TYPES)[number]

export function poiKey(type: PoiType): string {
  return `poi_${type}.geojson`
}
