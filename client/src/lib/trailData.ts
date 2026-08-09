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
//
// Every artifact here is held to the SHA-256 `latest.json` publishes for it
// (#197), the same check the raster archive gets. These are smaller and are
// fetched whole rather than resumed, so the splice that check was built for
// cannot happen to them - but "smaller" is not "less important": trails.geojson
// IS the trail line, and a corrupted POI file is a water source in the wrong
// place, which is the kind of wrong this app cannot be. A JSON file that is
// damaged rather than truncated parses perfectly well, so the parse is not the
// check people assume it is. Hashing whole bytes is cheap here because they are
// already whole in memory.

import { get, set, del } from 'idb-keyval'
import {
  DATA_BASE_URL,
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
import { publishedHash } from './dataManifest'
import { sha256Hex } from './sha256'

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
  /**
   * A photo of the place, with what the licence obliges us to say about it.
   *
   * The pipeline's fetch_poi_images.py matches openly-licensed Wikimedia
   * Commons photos (recent, by EXIF capture date) to POIs, downloads the
   * 640px rendering into our own bucket, and export_poi.py publishes the
   * bucket KEY as `photo_key` (#362). This field is that key resolved
   * through dataUrl() - the same build-time base every other artifact is
   * fetched from, so moving bucket or adding a CDN never invalidates
   * published data. All optional for the same backward-compat reason as
   * `source`, and this is the gate: the other four are facts about a photo,
   * so none is stored without one.
   */
  photoUrl?: string
  /** The Commons file page, where the full licence terms and history live. */
  photoPage?: string
  /** Who to credit. CC BY/BY-SA make the credit a condition of use, so the
   *  pipeline only ships an author-less photo when its licence needs no
   *  credit (public domain, CC0). */
  photoAuthor?: string
  /** The licence's short name, e.g. "CC BY-SA 4.0". */
  photoLicense?: string
  /** EXIF capture date, ISO "YYYY-MM-DD" - the card shows the month, because
   *  a two-year-old photo presented as current would be a quiet lie. */
  photoTaken?: string
  /**
   * Every photo of this place, card photo first.
   *
   * ATC's facility layers carry up to ten photographs per POI and 89% of them
   * use more than one, so the card shows `photos[0]` and lets a hiker step
   * through the rest. The five fields above describe that first photo and are
   * kept because a release published before galleries existed has only them -
   * `photos` is absent there, and one photo is still the honest reading.
   *
   * Each entry carries its own credit: the licence obliges attribution per
   * photograph, not per card, so moving to photo 3 moves its author, licence
   * and month with it.
   */
  photos?: PoiPhoto[]
}

/** One photo on a waypoint card, with what the licence obliges us to say
 *  about it. `url` is the bucket key already resolved through dataUrl(). */
export interface PoiPhoto {
  url: string
  page?: string
  author?: string
  license?: string
  taken?: string
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
  photo_key?: unknown
  photos?: unknown
  photo_page_url?: unknown
  photo_author?: unknown
  photo_license?: unknown
  photo_taken?: unknown
}

/** The property when it is a non-empty string, else nothing - the artifact
 *  writes null for absent values, and neither null nor "" is a fact worth
 *  storing. */
function stringProp(value: unknown): string | undefined {
  return typeof value === 'string' && value !== '' ? value : undefined
}

/**
 * The `photos` property as a usable list, or [] for anything unexpected.
 *
 * **It arrives as an array here and as a string in the .fgb, from the same
 * export.** The pipeline writes one JSON string, because FlatGeobuf property
 * values are scalars and a nested array cannot be a column at all - but GDAL
 * recognises a JSON-shaped string when writing GeoJSON and emits it as real
 * JSON, so the two artifacts genuinely disagree about this field's type
 * (measured 2026-08-09). Accepting both is not defensive padding: assuming
 * the string would return nothing for every POI in the format the client
 * actually reads.
 *
 * Every other failure mode - absent, malformed, not an array, an entry with
 * no key - degrades to "no gallery" rather than throwing: a published
 * artifact one version ahead of this build must never make a waypoint
 * unopenable.
 */
function readPhotoList(value: unknown): PoiPhoto[] {
  let parsed: unknown = value
  if (typeof value === 'string') {
    if (value === '') return []
    try {
      parsed = JSON.parse(value)
    } catch {
      return []
    }
  }
  if (!Array.isArray(parsed)) return []

  const photos: PoiPhoto[] = []
  for (const entry of parsed) {
    if (typeof entry !== 'object' || entry === null) continue
    const record = entry as Record<string, unknown>
    const key = stringProp(record.key)
    // No key, no photo. The other fields are a credit for something, and a
    // credit with nothing to credit is what the placeholder is for.
    if (key === undefined) continue
    const page = stringProp(record.page_url)
    const author = stringProp(record.author)
    const license = stringProp(record.license)
    const taken = stringProp(record.taken)
    photos.push({
      url: dataUrl(key),
      ...(page !== undefined ? { page } : {}),
      ...(author !== undefined ? { author } : {}),
      ...(license !== undefined ? { license } : {}),
      ...(taken !== undefined ? { taken } : {}),
    })
  }
  return photos
}

function readPois(text: string, fallbackType: PoiType): StoredPoi[] {
  const parsed = JSON.parse(text) as { features?: Array<{ properties?: PoiProperties }> }
  const pois: StoredPoi[] = []

  for (const feature of parsed.features ?? []) {
    const props = feature.properties ?? {}
    // A POI with no coordinates cannot be drawn, found by search or reported
    // against, so it is dropped rather than carried as a broken row.
    if (typeof props.lat !== 'number' || typeof props.lon !== 'number') continue

    // A key, resolved here rather than stored resolved: what is kept in
    // IndexedDB should survive the app being rebuilt against a different
    // data base URL.
    const photoKey = stringProp(props.photo_key)
    const photoUrl = photoKey === undefined ? undefined : dataUrl(photoKey)
    const photoPage = stringProp(props.photo_page_url)
    const photoAuthor = stringProp(props.photo_author)
    const photoLicense = stringProp(props.photo_license)
    const photoTaken = stringProp(props.photo_taken)
    const photoList = readPhotoList(props.photos)

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
      // Photo fields ride only behind a photo URL: an author or licence with
      // no photo is a credit for nothing, and would render as one.
      ...(photoUrl !== undefined
        ? {
            photoUrl,
            ...(photoPage !== undefined ? { photoPage } : {}),
            ...(photoAuthor !== undefined ? { photoAuthor } : {}),
            ...(photoLicense !== undefined ? { photoLicense } : {}),
            ...(photoTaken !== undefined ? { photoTaken } : {}),
            // Only when there is more than one: a single-photo gallery is
            // the card as it already is, and storing a one-entry list would
            // put next/previous controls on every photo that has no next.
            ...(photoList.length > 1 ? { photos: photoList } : {}),
          }
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

/**
 * An artifact could not be what the bucket says it should be.
 *
 * Its own type rather than a bare Error because nothing partial is committed
 * when this is thrown: the phone keeps whatever trail data it already had,
 * which is a materially different situation from a fetch that failed halfway.
 */
export class TrailDataHashMismatchError extends Error {
  readonly artifactKey: string

  constructor(artifactKey: string) {
    super(
      `The trail data that arrived is not what was published (${artifactKey}), ` +
        `so none of it was saved. Any map already on this phone is untouched.`,
    )
    this.name = 'TrailDataHashMismatchError'
    this.artifactKey = artifactKey
  }
}

/**
 * One artifact's bytes, held to its published hash.
 *
 * Where the manifest names no hash for the key (an older release, a field-test
 * server, no bucket configured), there is no expectation and the bytes are
 * returned unchecked - the same downgrade lib/archiveDownload.ts makes, for
 * the same reason: absence of a check must never become a failure.
 */
interface FetchedArtifact {
  /** The verified bytes themselves - what a Blob is rebuilt from, so what is
   *  stored is what was checked rather than a second read of the response. */
  buffer: ArrayBuffer
  bytes: Uint8Array
  contentType: string
}

async function readChecked(
  artifactKey: string,
  response: Response,
  signal?: AbortSignal,
): Promise<FetchedArtifact> {
  if (!response.ok) {
    // Shown to the hiker in the download window, so the sentence leads and is
    // theirs: what failed is the trail details, and anything already here is
    // safe. The artifact key and status ride along in parentheses - the same
    // compromise TrailDataHashMismatchError makes above - because "which
    // file" is what a field report needs and what these errors used to lead
    // with ("Failed to fetch pois.json: 403 Forbidden").
    throw new Error(
      `The trail details could not be fetched (${artifactKey}: the server ` +
        `answered ${response.status}). Anything already on this phone is untouched.`,
    )
  }

  const buffer = await response.arrayBuffer()
  const bytes = new Uint8Array(buffer)
  const expected = await publishedHash(artifactKey, { signal })
  if (expected !== null && sha256Hex(bytes) !== expected) {
    throw new TrailDataHashMismatchError(artifactKey)
  }

  return { buffer, bytes, contentType: response.headers.get('content-type') ?? '' }
}

/**
 * The host an artifact was asked of, for the message below.
 *
 * A build with no bucket configured is described rather than named, and that
 * is not just defensiveness about the relative URL: resolving it would print
 * the app's OWN origin, which is the one host that is certainly not the
 * problem. (That build has its own notice - see App.tsx's DATA_CONFIGURED
 * block - and this sentence should not quietly contradict it.)
 *
 * Anything unparseable is described too. A sentence about a failure must not
 * fail.
 */
function hostOf(url: string): string {
  if (DATA_BASE_URL === '') return 'the data source'
  try {
    return new URL(url, globalThis.location?.href ?? 'http://localhost/').host
  } catch {
    return 'the data source'
  }
}

/**
 * `fetch`, with the artifact named when the request never completes at all.
 *
 * A non-OK response already says which file and what the server answered
 * (readChecked above). A fetch that REJECTS says neither. The browser throws a
 * bare TypeError whose entire message is "NetworkError when attempting to
 * fetch resource." on Firefox, or "Failed to fetch" on Chrome - no URL, no
 * artifact, and no way to tell apart the several very different things that
 * produce it: no signal, DNS, a bucket whose public access is off, or a CORS
 * policy that does not name the origin the app is served from.
 *
 * That bare sentence is what reached the hiker in the download window, and it
 * is what reached us in a field report. It is the same eight words whether the
 * phone is in a dead zone or the bucket is refusing this origin, which are the
 * two ends of "your problem" and "our problem".
 *
 * So the key and the host it was asked of go back in. The browser's own
 * sentence is KEPT rather than replaced - it is the only part that separates a
 * refusal from a dead zone - and the original rides along as `cause` for a
 * console that wants the stack.
 *
 * An abort is deliberately not wrapped: that is the hiker cancelling, it is
 * why publishedHash() re-throws it by name, and a cancellation dressed up as a
 * failed download would be a lie about what happened.
 */
async function fetchArtifactResponse(
  artifactKey: string,
  signal?: AbortSignal,
): Promise<Response> {
  const url = dataUrl(artifactKey)
  try {
    return await fetch(url, { signal })
  } catch (error) {
    if ((error as { name?: string } | null)?.name === 'AbortError') throw error
    const reason = error instanceof Error ? error.message : String(error)
    throw new Error(
      `The trail details could not be fetched (${artifactKey}: the request to ` +
        `${hostOf(url)} did not complete - ${reason}). Anything already on this ` +
        `phone is untouched.`,
      { cause: error },
    )
  }
}

/** An artifact this release must have. */
async function fetchArtifact(
  artifactKey: string,
  signal?: AbortSignal,
): Promise<FetchedArtifact> {
  return readChecked(
    artifactKey,
    await fetchArtifactResponse(artifactKey, signal),
    signal,
  )
}

/** An artifact a release may predate - spurs.json and elevation_profile.json -
 *  where a 404 means "this release has no such file" rather than a failure. */
async function fetchOptionalArtifact(
  artifactKey: string,
  signal?: AbortSignal,
): Promise<FetchedArtifact | null> {
  const response = await fetchArtifactResponse(artifactKey, signal)
  if (response.status === 404) return null
  return readChecked(artifactKey, response, signal)
}

const decode = (bytes: Uint8Array) => new TextDecoder().decode(bytes)

/** Spur detail, or an empty map when this release does not publish it.
 *
 *  A 404 here is not a failed download. `spurs.json` did not exist before
 *  pipeline/export_spurs.py, and a phone pointed at an older release should
 *  still get its trails and POIs rather than an error - the map draws every
 *  spur either way, it just cannot say where one goes. Anything other than a
 *  missing file still throws, so a genuinely broken fetch is not swallowed
 *  along with it. */
async function fetchSpurs(signal?: AbortSignal): Promise<Record<string, SpurRecord>> {
  const fetched = await fetchOptionalArtifact(SPURS_KEY, signal)
  if (fetched === null) return {}
  const parsed: unknown = JSON.parse(decode(fetched.bytes))
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
  const fetched = await fetchOptionalArtifact(ELEVATION_KEY, signal)
  if (fetched === null) return null
  return parseProfile(decode(fetched.bytes))
}

export async function downloadTrailData({
  onProgress,
  signal,
}: DownloadTrailDataOptions = {}): Promise<void> {
  const total = POI_TYPES.length + 3
  let completed = 0

  const report = (label: string) => onProgress?.({ label, completed, total })

  report('Trail lines')
  const fetchedTrails = await fetchArtifact(TRAILS_KEY, signal)
  // Rebuilt from the verified bytes, keeping the served content type: what
  // MapLibre is handed has to be the bytes that were checked, not a second
  // read of the response.
  const trails = new Blob([fetchedTrails.buffer], { type: fetchedTrails.contentType })
  completed += 1

  const pois: StoredPoi[] = []
  for (const type of POI_TYPES) {
    report(type)
    const fetched = await fetchArtifact(poiKey(type), signal)
    pois.push(...readPois(decode(fetched.bytes), type))
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
