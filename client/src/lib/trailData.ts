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
import { dataUrl, POI_TYPES, poiKey, TRAILS_KEY, type PoiType } from './config'

export const TRAILS_BLOB_KEY = 'ourhike:trails'
export const POIS_KEY = 'ourhike:pois'

export interface StoredPoi {
  id: string
  type: string
  name: string
  lat: number
  lon: number
  confidence: 'high' | 'low'
}

export interface TrailData {
  trails: Blob
  pois: StoredPoi[]
}

interface PoiProperties {
  id?: unknown
  poi_type?: unknown
  name?: unknown
  lat?: unknown
  lon?: unknown
  confidence?: unknown
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

export async function downloadTrailData({
  onProgress,
  signal,
}: DownloadTrailDataOptions = {}): Promise<void> {
  const total = POI_TYPES.length + 1
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
  report('Done')
}

export async function loadTrailData(): Promise<TrailData | null> {
  const trails = (await get(TRAILS_BLOB_KEY)) as Blob | undefined
  if (!(trails instanceof Blob)) return null

  const pois = ((await get(POIS_KEY)) as StoredPoi[] | undefined) ?? []
  return { trails, pois }
}

export async function deleteTrailData(): Promise<void> {
  await del(TRAILS_BLOB_KEY)
  await del(POIS_KEY)
}
