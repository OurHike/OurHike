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

// The along-the-trail elevation profile, published by
// pipeline/export_elevation.py: ~141,000 {distance_mi, elevation_ft} samples at
// 25 m spacing along the real centerline. 6.5 MB of JSON that gzips to 0.87 MB
// - under 7% of what trails.geojson alone already costs, which is why it is
// fetched whole rather than windowed. Windowing it would also defeat the point:
// the ribbon has to work in a dead zone fifty miles from where it downloaded.
//
// Absent from data releases built before export_elevation.py existed, which
// lib/trailData.ts treats as "no profile" rather than a failed download - the
// same way spurs.json is treated.
export const ELEVATION_KEY = 'elevation_profile.json'

// 'crossing' is published but is currently an empty FeatureCollection; it is
// listed anyway so it starts working the day the pipeline fills it, rather
// than needing a client release to notice.
export const POI_TYPES = ['shelter', 'water', 'campsite', 'resupply', 'crossing'] as const

export type PoiType = (typeof POI_TYPES)[number]

export function poiKey(type: PoiType): string {
  return `poi_${type}.geojson`
}
