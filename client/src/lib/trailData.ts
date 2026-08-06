// The vector half of the offline map: trail lines and POIs.
//
// These are downloaded and kept in IndexedDB for the same reason the raster
// archive is (map/pmtilesSource.ts). Handing MapLibre an https:// URL for the
// trail lines would work perfectly on trailhead wifi and then render a topo
// background with no trail on it the first time the app is opened cold with no
// signal - which is precisely the situation it exists for.
//
// Trail lines are stored as the raw downloaded Blob rather than as parsed
// objects, so the object URL handed to MapLibre costs no re-serialisation of
// twelve megabytes of coordinates.

import { get, set, del } from 'idb-keyval'
import {
  dataUrl,
  ELEVATION_KEY,
  POI_TYPES,
  poiKey,
  SPURS_KEY,
  TRAILS_KEY,
  type PoiType,
} from './config'
import { parseProfile, type ElevationProfile } from './elevationProfile'
import type { SpurRecord } from './spurDestination'

export const TRAILS_BLOB_KEY = 'ourhike:trails'
export const POIS_KEY = 'ourhike:pois'
export const SPURS_STORE_KEY = 'ourhike:spurs'
export const ELEVATION_STORE_KEY = 'ourhike:elevation'

export interface StoredPoi {
  id: string
  type: string
  name: string
  lat: number
  lon: number
  confidence: 'high' | 'low'
  /**
   * Which published source listed this POI - "atc_shelters", "opentrail_at"
   * and the rest of pipeline/lib/poi_schema.py's ids, shown as words by
   * chrome/poiSources.ts.
   *
   * Optional because a phone that downloaded before the client read this field
   * has POIs in IndexedDB without one. Undefined then means "this copy predates
   * the field", not "the pipeline published no source", and the difference does
   * not matter to anything that reads it: both come out as a sheet with no
   * provenance line rather than a wrong one.
   */
  source?: string
}

export interface TrailData {
  trails: Blob
  pois: StoredPoi[]
  /** Spur detail keyed by trail id. Empty for a release built before
   *  export_spurs.py existed - the map still draws every spur, it just cannot
   *  say where one goes. */
  spurs: Record<string, SpurRecord>
  /** The along-the-trail elevation profile, or null for a release that does
   *  not publish one. Null costs the elevation ribbon and the waypoint lanes
   *  and nothing else - App.tsx omits both rather than drawing an empty one. */
  elevation: ElevationProfile | null
}

interface PoiProperties {
  id?: unknown
  poi_type?: unknown
  name?: unknown
  lat?: unknown
  lon?: unknown
  confidence?: unknown
  source?: unknown
}

function readPois(text: string, fallbackType: PoiType): StoredPoi[] {
  const parsed = JSON.parse(text) as { features?: Array<{ properties?: PoiProperties }> }
  const pois: StoredPoi[] = []

  for (const feature of parsed.features ?? []) {
    const props = feature.properties ?? {}
    // A POI with no coordinates cannot be drawn, found by search or reported
    // against, so it is dropped rather than carried as a broken row.
    if (typeof props.lat !== 'number' || typeof props.lon !== 'number') continue

    pois.push({
      id: String(props.id ?? `${fallbackType}:${props.lat},${props.lon}`),
      type: typeof props.poi_type === 'string' ? props.poi_type : fallbackType,
      name: typeof props.name === 'string' ? props.name : 'Unnamed',
      lat: props.lat,
      lon: props.lon,
      // Only an explicit 'high' counts as verified. Anything else - a missing
      // field, a value this build does not know - reads as low, which the
      // legend shows as "Unverified". Guessing the other way would vouch for
      // a water source nobody checked.
      confidence: props.confidence === 'high' ? 'high' : 'low',
      // Left off entirely when the artifact has none, rather than stored as a
      // placeholder string: the detail sheet decides whether to name a source
      // by whether there is one, and "unknown" is not a source.
      ...(typeof props.source === 'string' && props.source !== ''
        ? { source: props.source }
        : {}),
    })
  }

  return pois
}

export interface TrailDataProgress {
  /** What is being fetched right now, for a status line. */
  label: string
  completed: number
  total: number
}

export interface DownloadTrailDataOptions {
  onProgress?: (progress: TrailDataProgress) => void
  signal?: AbortSignal
}

async function fetchOrThrow(url: string, signal?: AbortSignal): Promise<Response> {
  const response = await fetch(url, { signal })
  if (!response.ok) {
    throw new Error(`Failed to fetch ${url}: ${response.status} ${response.statusText}`)
  }
  return response
}

/** Spur detail, or an empty map when this release does not publish it.
 *
 *  A 404 here is not a failed download. `spurs.json` did not exist before
 *  pipeline/export_spurs.py, and a phone pointed at an older release should
 *  still get its trails and POIs rather than an error - the map draws every
 *  spur either way, it just cannot say where one goes. Anything other than a
 *  missing file still throws, so a genuinely broken fetch is not swallowed
 *  along with it. */
async function fetchSpurs(signal?: AbortSignal): Promise<Record<string, SpurRecord>> {
  const response = await fetch(dataUrl(SPURS_KEY), { signal })
  if (response.status === 404) return {}
  if (!response.ok) {
    throw new Error(
      `Failed to fetch ${SPURS_KEY}: ${response.status} ${response.statusText}`,
    )
  }
  const parsed: unknown = JSON.parse(await response.text())
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return {}
  return parsed as Record<string, SpurRecord>
}

/** The elevation profile, or null when this release does not publish one.
 *
 *  A 404 is treated the way fetchSpurs() treats one, for the same reason:
 *  `elevation_profile.json` did not exist before pipeline/export_elevation.py,
 *  and a phone pointed at an older release should still get its map rather than
 *  an error. A body that is not the array of samples this expects is also null
 *  rather than a throw - parseProfile() has the reasoning - so a ribbon that
 *  cannot be drawn never costs the trail lines that arrived beside it.
 *
 *  This is the largest of the vector downloads at 0.87 MB gzipped, and it is
 *  fetched last so a hiker on a failing connection has the trail and the POIs
 *  in hand before the decoration is attempted. */
async function fetchElevation(signal?: AbortSignal): Promise<ElevationProfile | null> {
  const response = await fetch(dataUrl(ELEVATION_KEY), { signal })
  if (response.status === 404) return null
  if (!response.ok) {
    throw new Error(
      `Failed to fetch ${ELEVATION_KEY}: ${response.status} ${response.statusText}`,
    )
  }
  return parseProfile(await response.text())
}

export async function downloadTrailData({
  onProgress,
  signal,
}: DownloadTrailDataOptions = {}): Promise<void> {
  const total = POI_TYPES.length + 3
  let completed = 0

  const report = (label: string) => onProgress?.({ label, completed, total })

  report('Trail lines')
  const trails = await (await fetchOrThrow(dataUrl(TRAILS_KEY), signal)).blob()
  completed += 1

  const pois: StoredPoi[] = []
  for (const type of POI_TYPES) {
    report(type)
    const text = await (await fetchOrThrow(dataUrl(poiKey(type)), signal)).text()
    pois.push(...readPois(text, type))
    completed += 1
  }

  report('Spur destinations')
  const spurs = await fetchSpurs(signal)
  completed += 1

  report('Elevation profile')
  const elevation = await fetchElevation(signal)
  completed += 1

  // Nothing is committed until everything has arrived. Writing the trail lines
  // as soon as they landed meant a POI fetch failing - signal dropping partway
  // is the ordinary case here, not the edge one - left a store holding new
  // trail lines and no POIs at all. That state is invisible: the map draws its
  // trail, and search and the legend are simply empty, with the error long
  // gone from a React state variable by the next launch. Holding both until
  // the end costs the few megabytes already in hand and makes a failed
  // download leave the phone exactly as it found it.
  await set(TRAILS_BLOB_KEY, trails)
  await set(POIS_KEY, pois)
  await set(SPURS_STORE_KEY, spurs)
  await set(ELEVATION_STORE_KEY, elevation)
  report('Done')
}

export async function loadTrailData(): Promise<TrailData | null> {
  const trails = (await get(TRAILS_BLOB_KEY)) as Blob | undefined
  if (!(trails instanceof Blob)) return null

  const pois = ((await get(POIS_KEY)) as StoredPoi[] | undefined) ?? []
  const spurs =
    ((await get(SPURS_STORE_KEY)) as Record<string, SpurRecord> | undefined) ?? {}
  // Undefined and null both mean "no ribbon". They arrive from different
  // places - nothing stored at all, versus a release that published no profile
  // - and neither is a state the map screen has to tell apart.
  const elevation =
    ((await get(ELEVATION_STORE_KEY)) as ElevationProfile | undefined) ?? null
  return { trails, pois, spurs, elevation }
}

/**
 * Removes the trail's own data.
 *
 * Deliberately NOT part of "delete the map" since #192: the background is
 * what a hiker chooses, downloads and reclaims, and this is what the trail
 * is. Taking these few megabytes along with several hundred would strip the
 * trail line off the screen until the next launch with signal fetched it
 * straight back - the app downloads it by default wherever it is missing.
 *
 * Kept because the store owns the operation and switching trails will want
 * it. Nothing in the app calls it today.
 */
export async function deleteTrailData(): Promise<void> {
  await del(TRAILS_BLOB_KEY)
  await del(POIS_KEY)
  await del(SPURS_STORE_KEY)
  await del(ELEVATION_STORE_KEY)
}
