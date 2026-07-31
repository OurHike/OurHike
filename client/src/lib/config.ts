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

export const TRAILS_KEY = 'trails.geojson'

// 'crossing' is published but is currently an empty FeatureCollection; it is
// listed anyway so it starts working the day the pipeline fills it, rather
// than needing a client release to notice.
export const POI_TYPES = ['shelter', 'water', 'campsite', 'resupply', 'crossing'] as const

export type PoiType = (typeof POI_TYPES)[number]

export function poiKey(type: PoiType): string {
  return `poi_${type}.geojson`
}
