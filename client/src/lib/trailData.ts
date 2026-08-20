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
// check people assume it is. Being already whole in memory is what lets these
// go through `crypto.subtle.digest` rather than the vendored streaming fold the
// archive needs - see sha256Of below, and #717 for the 10x that was costing.

import { get, set, del } from 'idb-keyval'
import {
  DATA_BASE_URL,
  dataUrl,
  ELEVATION_KEY,
  POI_TYPES,
  CLUB_SECTIONS_KEY,
  HIGHLIGHTS_KEY,
  poiKey,
  SPURS_KEY,
  TRAILS_KEY,
  type PoiType,
} from './config'
import {
  EMPTY_CLUB_SECTIONS,
  parseClubSections,
  storedClubSections,
  type ClubSections,
} from './clubSections'
import { parseHighlights, storedHighlights, type Highlight } from './highlights'
import { parseProfile, type ElevationProfile } from './elevationProfile'
import type { NearbyPart } from './nearbyClause'
import type { SpurRecord } from './spurDestination'
import { publishedHashes, type PublishedHashLookup } from './dataManifest'
import { sha256Hex } from './sha256'
import { clearTrailsMerged, sniffMergedChains, writeTrailsMerged } from './trailShape'

export const TRAILS_BLOB_KEY = 'ourhike:trails'
export const POIS_KEY = 'ourhike:pois'
export const SPURS_STORE_KEY = 'ourhike:spurs'
export const ELEVATION_STORE_KEY = 'ourhike:elevation'
export const CLUB_SECTIONS_STORE_KEY = 'ourhike:club-sections'
export const HIGHLIGHTS_STORE_KEY = 'ourhike:highlights'

export interface StoredPoi {
  id: string
  type: string
  name: string
  lat: number
  lon: number
  confidence: 'high' | 'low'
  /**
   * NOBO miles from Springer, projected by the pipeline onto the same
   * ordered metric centerline the elevation profile is sampled along
   * (export_poi.attach_miles, #753) - so this and the ribbon's distance_mi
   * are one measurement by construction. A POSITION, never a heading: a
   * southbound hiker walks toward smaller numbers, and direction stays the
   * derived view lib/hikeDirection.ts already provides.
   *
   * Optional because a copy downloaded before the field was published has
   * none - absent means "this data release predates the mile", and a
   * consumer that needs it (the planner, a mile-range photo scope) says it
   * needs a newer download rather than deriving a second scale locally.
   */
  mile?: number
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
   * How many people the shelter sleeps.
   *
   * Shelters only, and not all of them: ATC's own layer has no capacity
   * field, so the pipeline joins a hiker-maintained list onto it by name
   * (pipeline/build_shelter_capacity.py) and publishes nothing for the
   * shelters that list covers in pairs or writes as "xxx". Absent therefore
   * means "nobody has published a number", never "small" and never zero -
   * the card omits the line rather than guessing at one.
   */
  capacity?: number
  /**
   * How far the nearest water source is, in feet, by ATC's own measurement
   * (pipeline/build_water_distance.py - their Campsite Sustainability Index
   * states a distance per site, never a location).
   *
   * Carried by shelters and campsites, and by the water POIs the pipeline
   * synthesizes onto their sites from the same number (#694) - those inherit
   * the site's coordinates because no real ones exist, which is exactly why
   * a card must prefer THIS figure over a coordinate-derived distance
   * (chrome/PoiCard.tsx's partDistance). Absent means nobody has published a
   * distance, never "no water" - the same rule as `capacity`.
   */
  waterDistanceFt?: number
  /**
   * One sentence about the place, for every POI type ATC's own facility
   * layers feed - shelters, campsites, viewpoints, parking areas, privies.
   *
   * Composed by the pipeline from ATC's own inventory columns rather than
   * copied from a text field - ATC has no prose description (see
   * pipeline/lib/poi_description.py). Optional for the same backward-compat
   * reason as `source`: a phone that downloaded before this existed has POIs
   * without one, and water and resupply never have one at all - they come
   * from opentrail.org's tags and ATC's Communities layer, which carry no
   * inventory to compose from.
   */
  description?: string
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
  /**
   * Which SITE this POI belongs to, and whether it is the anchor or a member
   * (#523, pipeline/lib/poi_sites.py).
   *
   * A shelter, its privy and its campsites are one place with parts. The map
   * draws one pin for the site rather than letting the members lose a collision
   * they cannot win - map/poiSites.ts has the numbers.
   *
   * Optional for the same backward-compat reason as `source`: a phone that
   * downloaded before #523 published the grouping has POIs without them, and
   * undefined means "this copy predates the grouping" rather than "this POI is
   * not in a site". Both draw a plain pin, which is what that phone drew before.
   */
  siteId?: string
  /**
   * The parts around this site's anchor, ready for lib/nearbyClause.ts to make
   * a sentence of: a noun phrase each and how far each one is, in feet.
   *
   * Anchors only, and only those with parts - which is 291 of the corridor's
   * points. The pipeline composed this as finished prose inside `description`
   * until #625, where the distances were metres for everybody; the phrases are
   * still ATC's inventory read aloud and still composed there, and the distance
   * arrives as a number so the card can write it in the hiker's own units.
   *
   * Optional for the same backward-compat reason as `source`: a phone that
   * downloaded before this existed has POIs without it, and its cards read
   * exactly as they did - the old prose still sits in `description`, metres and
   * all, until the next download replaces it.
   */
  nearby?: NearbyPart[]
  /** `"anchor"` or `"member"`. Not a union type on purpose: a later release
   *  could publish a third role, and a phone must not fail to parse a POI over
   *  a word it does not know. map/poiSites.ts treats an unfamiliar role as "not
   *  in a site", so the pin stays. */
  siteRole?: string
  /** The site's own name, e.g. "Mt. Algo Shelter" - what the pipeline's
   *  normalisation matched on. Carried for the waypoint card (#526) rather than
   *  for the pin, which shows the anchor's own name. */
  siteName?: string
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
  /** Who maintains which stretch of trail. Empty for a release built before
   *  export_club_sections.py existed, which costs the corridor view its
   *  subject and nothing else - the trail still draws, in its blaze. */
  clubSections: ClubSections
  /** Stretches worth going to. Empty for a release built before
   *  export_highlights.py existed, which costs the corridor view its second
   *  subject and nothing else. */
  highlights: Highlight[]
}

interface PoiProperties {
  id?: unknown
  poi_type?: unknown
  name?: unknown
  lat?: unknown
  lon?: unknown
  mile?: unknown
  confidence?: unknown
  source?: unknown
  capacity?: unknown
  water_distance_ft?: unknown
  description?: unknown
  photo_key?: unknown
  photos?: unknown
  photo_page_url?: unknown
  photo_author?: unknown
  photo_license?: unknown
  photo_taken?: unknown
  site_id?: unknown
  site_role?: unknown
  site_name?: unknown
  nearby?: unknown
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

/**
 * The `nearby` property as a usable list, or [] for anything unexpected.
 *
 * Both shapes, for the reason readPhotoList takes both: the pipeline writes one
 * JSON string because FlatGeobuf property values are scalars, and GDAL
 * re-expands a JSON-shaped string into real JSON when it writes the .geojson -
 * so one export genuinely produces two types for this field.
 *
 * Every failure mode degrades to "no nearby sentence" rather than throwing: a
 * published artifact one version ahead of this build must never make a waypoint
 * unopenable. An entry needs both halves to be worth keeping - a phrase with no
 * distance is a part the card cannot place, and a distance with no phrase is a
 * number with nothing to attach it to.
 */
function readNearbyList(value: unknown): NearbyPart[] {
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

  const parts: NearbyPart[] = []
  for (const entry of parsed) {
    if (typeof entry !== 'object' || entry === null) continue
    const record = entry as Record<string, unknown>
    const phrase = stringProp(record.phrase)
    const distance = record.distance_ft
    if (
      phrase === undefined ||
      typeof distance !== 'number' ||
      !Number.isFinite(distance)
    ) {
      continue
    }
    parts.push({ phrase, distance_ft: distance })
  }
  return parts
}

/** A whole count of people, or nothing. Anything else the artifact could
 *  hold - null for a shelter with no published number, a non-finite value, a
 *  zero or a fraction from a source that meant something other than people -
 *  is not a capacity, and rendering "Sleeps 0" would be worse than silence. */
function capacityProp(value: unknown): number | undefined {
  return typeof value === 'number' && Number.isInteger(value) && value > 0
    ? value
    : undefined
}

/** A whole distance in feet, or nothing - the same guard as capacityProp for
 *  the same reason: the pipeline publishes null where it refused to state a
 *  number (pipeline/build_water_distance.py's zeros and holdbacks), and a
 *  card rendering "Water · 0 m" from a null would be the guess it refused. */
function waterDistanceProp(value: unknown): number | undefined {
  return typeof value === 'number' && Number.isInteger(value) && value > 0
    ? value
    : undefined
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
    const capacity = capacityProp(props.capacity)
    const waterDistanceFt = waterDistanceProp(props.water_distance_ft)
    const description = stringProp(props.description)
    // #523's grouping (pipeline/lib/poi_sites.py). Read here rather than
    // dropped, because these three are what let the map draw one pin for a
    // shelter and its privy instead of drawing the shelter and DELETING the
    // privy - see map/poiSites.ts for the 3%-of-privies measurement behind
    // that. Additive on the artifact, so a phone that downloaded before #523
    // simply has none of them.
    const siteId = stringProp(props.site_id)
    const siteRole = stringProp(props.site_role)
    const siteName = stringProp(props.site_name)
    // The anchor's parts (#614, #625). Structure rather than the prose this
    // used to arrive as, which is what lets the card write the distances in
    // the units the hiker chose - see lib/nearbyClause.ts.
    const nearby = readNearbyList(props.nearby)

    pois.push({
      id: String(props.id ?? `${fallbackType}:${props.lat},${props.lon}`),
      type: typeof props.poi_type === 'string' ? props.poi_type : fallbackType,
      name: typeof props.name === 'string' ? props.name : 'Unnamed',
      lat: props.lat,
      lon: props.lon,
      // Only an explicit 'high' counts as verified. Anything else - a missing
      // field, a value this build does not know - reads as low, which the map
      // draws with a broken rim, the waypoint card says in words, and the
      // legend's "Verified?" filter takes off the screen. Guessing the other
      // way would vouch for a water source nobody checked.
      confidence: props.confidence === 'high' ? 'high' : 'low',
      // Absent rather than guessed when the release predates the field or
      // published null - the same omit-don't-invent rule as capacity.
      ...(typeof props.mile === 'number' && Number.isFinite(props.mile)
        ? { mile: props.mile }
        : {}),
      // Left off entirely when the artifact has none, rather than stored as a
      // placeholder string: the detail sheet decides whether to name a source
      // by whether there is one, and "unknown" is not a source.
      ...(typeof props.source === 'string' && props.source !== ''
        ? { source: props.source }
        : {}),
      // Same rule as the source line: left off entirely rather than stored
      // as a zero, so the card can tell "sleeps nobody knows how many" from
      // a number.
      ...(capacity !== undefined ? { capacity } : {}),
      ...(waterDistanceFt !== undefined ? { waterDistanceFt } : {}),
      ...(description !== undefined ? { description } : {}),
      // All three ride together or not at all: a role with no site to belong
      // to cannot be acted on, and map/poiSites.ts would treat it as a POI in
      // no site anyway. Keeping them coupled here means that reading is stated
      // in one place rather than inferred in two.
      ...(siteId !== undefined && siteRole !== undefined
        ? { siteId, siteRole, ...(siteName !== undefined ? { siteName } : {}) }
        : {}),
      // Left off entirely when there is nothing in it, like every optional
      // above: an empty list and an absent field would render identically, and
      // storing the empty one would put an array on 40,000 POIs to say nothing.
      ...(nearby.length > 0 ? { nearby } : {}),
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
  /**
   * The trail lines are on the phone and can be drawn (#863).
   *
   * Fired exactly once per download, at the moment `loadTrailLines()` would
   * start answering with these bytes - which is before the waypoints are
   * fetched on a first download, and at the final commit on every other one
   * (see below for why those differ). The centerline itself does not travel
   * through here: it is in IndexedDB by then, and one path for minting the
   * object URL is worth more than saving the caller a Blob-handle read.
   */
  onCenterline?: () => void
}

/**
 * A release that is only half here, so the next launch finishes it rather
 * than reading the phone as done.
 *
 * ABSENT MEANS COMPLETE, which is what makes this safe to add to a store that
 * already has releases in it: every phone that downloaded before this existed
 * has a whole one and no marker, and reads correctly.
 *
 * The marker is the answer to the objection that kept the commit
 * all-or-nothing until now - that a store holding trail lines and no
 * waypoints is *invisible*, so the map draws its trail while search and the
 * legend are silently empty. It is not invisible any more: {@link
 * haveTrailData} answers false while it is set, so the launch fetch downloads
 * the release again instead of stopping.
 */
export const TRAIL_DATA_PARTIAL_KEY = 'ourhike:trail-data-partial'

/**
 * An artifact could not be what the bucket says it should be.
 *
 * Its own type rather than a bare Error because of what the phone holds
 * afterwards: whatever trail data it ALREADY had, untouched, which is a
 * materially different situation from a fetch that failed halfway.
 *
 * "Untouched" is exact, and since #863 it is also the whole of the claim. A
 * phone that held nothing may keep the trail lines this download had already
 * fetched and verified - they are drawn, they are marked as a release that is
 * not finished, and the next attempt fetches the release again from the start.
 * Nothing that was there before is replaced or removed either way, which is
 * what the sentence below says and all it says.
 */
export class TrailDataHashMismatchError extends Error {
  readonly artifactKey: string

  constructor(artifactKey: string) {
    super(
      `The trail data that arrived is not what was published (${artifactKey}), ` +
        `so this release was not kept. Any map already on this phone is untouched.`,
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

/**
 * SHA-256 of bytes that are already whole in memory.
 *
 * `crypto.subtle.digest` where it exists, which is every browser this app
 * targets over https, and lib/sha256.ts where it does not.
 *
 * The vendored fold is not the wrong code - it is the right code for the job
 * it was written for, which is the 1.18 GB archive that cannot be handed to
 * `crypto.subtle.digest` as one buffer at all (see its header, and #448 for
 * the archive path's own main-thread problem). None of that reasoning reaches
 * here. These artifacts are already one buffer, which is precisely the case
 * the platform's own digest exists for: native, and off the main thread.
 *
 * Measured 2026-08-15, x86, over the eleven artifacts of one launch fetch
 * (21.5 MB): vendored JS 624 ms against native 60 ms, a 10.4x difference, all
 * of the former synchronous on the thread that is also drawing the map. A
 * phone is materially slower than the machine those numbers came from.
 */
async function sha256Of(bytes: Uint8Array): Promise<string> {
  const subtle = globalThis.crypto?.subtle
  // Absent on http:// origins and in some test environments. The fallback is
  // the same algorithm over the same bytes, so this is a speed decision and
  // never a correctness one.
  if (subtle === undefined) return sha256Hex(bytes)

  const digest = await subtle.digest('SHA-256', bytes as unknown as BufferSource)
  return [...new Uint8Array(digest)]
    .map((byte) => byte.toString(16).padStart(2, '0'))
    .join('')
}

async function readChecked(
  artifactKey: string,
  response: Response,
  expectedHash: string | null,
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
  // The DECODED bytes, which is what makes serving these artifacts gzipped
  // safe: `fetch` applies Content-Encoding before anything here sees them, so
  // the hash is still over exactly the bytes publish.py hashed on disk.
  if (expectedHash !== null && (await sha256Of(bytes)) !== expectedHash) {
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
  expected: PublishedHashLookup,
  signal?: AbortSignal,
): Promise<FetchedArtifact> {
  return readChecked(
    artifactKey,
    await fetchArtifactResponse(artifactKey, signal),
    expected(artifactKey),
  )
}

/** An artifact a release may predate - spurs.json and elevation_profile.json -
 *  where a 404 means "this release has no such file" rather than a failure. */
async function fetchOptionalArtifact(
  artifactKey: string,
  expected: PublishedHashLookup,
  signal?: AbortSignal,
): Promise<FetchedArtifact | null> {
  const response = await fetchArtifactResponse(artifactKey, signal)
  if (response.status === 404) return null
  return readChecked(artifactKey, response, expected(artifactKey))
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
async function fetchSpurs(
  expected: PublishedHashLookup,
  signal?: AbortSignal,
): Promise<Record<string, SpurRecord>> {
  const fetched = await fetchOptionalArtifact(SPURS_KEY, expected, signal)
  if (fetched === null) return {}
  const parsed: unknown = JSON.parse(decode(fetched.bytes))
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return {}
  return parsed as Record<string, SpurRecord>
}

/** Who maintains which stretch, or nothing when this release does not publish it.
 *
 *  A 404 is treated the way fetchSpurs() treats one, and for the same reason:
 *  `club_sections.json` did not exist before pipeline/export_club_sections.py,
 *  and a phone pointed at an older release should still get its trails and
 *  POIs. The corridor view then has no subject below the seam, which is
 *  exactly the screen this app shipped with. */
async function fetchClubSections(
  expected: PublishedHashLookup,
  signal?: AbortSignal,
): Promise<ClubSections> {
  const fetched = await fetchOptionalArtifact(CLUB_SECTIONS_KEY, expected, signal)
  if (fetched === null) return EMPTY_CLUB_SECTIONS
  return parseClubSections(JSON.parse(decode(fetched.bytes)) as unknown)
}

/** The curated highlights, or nothing when this release does not publish them.
 *
 *  A 404 is treated the way fetchSpurs() treats one, for the reason every
 *  optional artifact here is: a phone pointed at an older release should still
 *  get its trails, its POIs and its club sections. */
async function fetchHighlights(
  expected: PublishedHashLookup,
  signal?: AbortSignal,
): Promise<Highlight[]> {
  const fetched = await fetchOptionalArtifact(HIGHLIGHTS_KEY, expected, signal)
  if (fetched === null) return []
  return parseHighlights(JSON.parse(decode(fetched.bytes)) as unknown)
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
 *  7.0 MB on the wire today and 0.89 MB gzipped, measured against the live
 *  bucket 2026-08-15. Which of those two numbers a hiker pays depends on
 *  pipeline/publish.py setting Content-Encoding, which it did not until #717 -
 *  this file's own comments quoted the gzipped figure for a compression that
 *  was never applied. It is fetched last either way, so a hiker on a failing
 *  connection has the trail and the POIs in hand before the decoration is
 *  attempted. */
async function fetchElevation(
  expected: PublishedHashLookup,
  signal?: AbortSignal,
): Promise<ElevationProfile | null> {
  const fetched = await fetchOptionalArtifact(ELEVATION_KEY, expected, signal)
  if (fetched === null) return null
  return parseProfile(decode(fetched.bytes))
}

export async function downloadTrailData({
  onProgress,
  signal,
  onCenterline,
}: DownloadTrailDataOptions = {}): Promise<void> {
  const total = POI_TYPES.length + 3
  let completed = 0

  const report = (label: string) => onProgress?.({ label, completed, total })
  /** One artifact landed. Called as each finishes rather than in list order,
   *  because the middle group below is no longer sequential. */
  const finished = (label: string) => {
    completed += 1
    report(label)
  }

  // ONE read of latest.json, shared by every artifact in this attempt (#717).
  // It used to be fetched inside readChecked, so eleven artifacts meant eleven
  // round trips for the same 3.5 KB, each one sitting between two downloads.
  // A snapshot is also the more correct thing to verify a single attempt
  // against: every artifact here is checked against one published version,
  // rather than against whatever the bucket happened to be serving at the
  // moment that particular file finished.
  report('Trail lines')
  const expected = await publishedHashes({ signal })

  // The trail lines first, alone, and awaited before anything else starts.
  // They are the canary (see useTrailData.ts's `ensure`): whatever would stop
  // these twelve megabytes stops the rest, and finding that out should not
  // cost a hiker nine more requests to learn.
  const fetchedTrails = await fetchArtifact(TRAILS_KEY, expected, signal)
  // Rebuilt from the verified bytes, keeping the served content type: what
  // MapLibre is handed has to be the bytes that were checked, not a second
  // read of the response.
  const trails = new Blob([fetchedTrails.buffer], { type: fetchedTrails.contentType })
  finished('Trail lines')

  // THE CENTERLINE GOES ON THE PHONE NOW, ON A PHONE THAT HAS NOTHING (#863).
  //
  // A first run's entry steps are a card over the map, and on an empty phone
  // there was no map behind them: the commit below waits for the whole
  // release, which on a 4x-throttled phone profile at 12 Mbps was ~12 s, and
  // three steps take about eight seconds to click through. So the hiker read
  // three sentences about a map over an empty background, and the download
  // window opened before the trail line appeared. Measured 2026-08-20: the
  // lines themselves were fetched and hash-checked at 4.8 s, then sat in
  // memory for seven seconds waiting for eight POI files and a profile.
  //
  // ONLY WHEN THE PHONE HOLDS NOTHING, which is the state this is fixing.
  // Where a release is already stored, nothing is written until the whole new
  // one has arrived, exactly as before - that map already has a line to draw,
  // and new lines beside the previous release's waypoints would be a
  // downgrade rather than a fix (the test below holds it).
  //
  // The marker is what stops this being the invisible half-release the commit
  // below exists to prevent - see TRAIL_DATA_PARTIAL_KEY. Set BEFORE the
  // bytes, so a phone killed between the two reads as partial rather than as
  // done.
  const committingCenterlineFirst = (await loadTrailLines()) === null
  if (committingCenterlineFirst) {
    await set(TRAIL_DATA_PARTIAL_KEY, true)
    await set(TRAILS_BLOB_KEY, trails)
    writeTrailsMerged(sniffMergedChains(decode(fetchedTrails.bytes)))
    onCenterline?.()
  }

  // The eight POI files and the spurs together, rather than one after another.
  // Nothing orders them against each other - they are eight independent
  // artifacts, none of which is read before all of them have arrived - and
  // serially they spent a round trip of dead time per file. Measured on a
  // first run, the eight POI files and spurs.json occupied 23.6s to 29.4s of a
  // chain that was mostly waiting.
  //
  // Still all-or-nothing: `Promise.all` rejects on the first failure and
  // nothing below commits, which is the property the `set()` calls at the end
  // depend on.
  const [poiGroups, spurs, clubSections, highlights] = await Promise.all([
    Promise.all(
      POI_TYPES.map(async (type) => {
        const fetched = await fetchArtifact(poiKey(type), expected, signal)
        finished(type)
        return readPois(decode(fetched.bytes), type)
      }),
    ),
    fetchSpurs(expected, signal).then((value) => {
      finished('Spur destinations')
      return value
    }),
    // Beside the spurs rather than after them: another small keyed artifact
    // that nothing else is waiting on, and a serial fetch here would buy a
    // round trip of dead time for 30 clubs' worth of JSON.
    fetchClubSections(expected, signal).then((value) => {
      finished('Maintaining clubs')
      return value
    }),
    fetchHighlights(expected, signal).then((value) => {
      finished('Highlights')
      return value
    }),
  ])
  // Flattened in POI_TYPES order rather than in completion order, so what is
  // stored does not depend on which request happened to finish first.
  const pois: StoredPoi[] = poiGroups.flat()

  // Last, and on its own, which is the one piece of ordering worth keeping -
  // see fetchElevation. A hiker whose connection dies here has the trail and
  // every waypoint on the phone and loses only the ribbon.
  report('Elevation profile')
  const elevation = await fetchElevation(expected, signal)
  finished('Elevation profile')

  // Nothing is committed until everything has arrived. Writing the trail lines
  // as soon as they landed meant a POI fetch failing - signal dropping partway
  // is the ordinary case here, not the edge one - left a store holding new
  // trail lines and no POIs at all. That state is invisible: the map draws its
  // trail, and search and the legend are simply empty, with the error long
  // gone from a React state variable by the next launch. Holding both until
  // the end costs the few megabytes already in hand and makes a failed
  // download leave the phone exactly as it found it.
  //
  // Still true of every download onto a phone that already holds a release.
  // The one exception is the block above, where there is no previous release
  // to keep whole and the invisibility is answered by a marker instead.
  if (!committingCenterlineFirst) {
    await set(TRAILS_BLOB_KEY, trails)
  }
  await set(POIS_KEY, pois)
  await set(SPURS_STORE_KEY, spurs)
  await set(CLUB_SECTIONS_STORE_KEY, clubSections)
  await set(HIGHLIGHTS_STORE_KEY, highlights)
  await set(ELEVATION_STORE_KEY, elevation)
  // Recorded beside the bytes it describes, and only here: whether the
  // trails just stored have the merged-chain shape decides the map's
  // `tolerance` for them on every later launch (lib/trailShape.ts, #161).
  // Written on every commit, not just when true - a re-download from an
  // older release has to take the flag back down with it.
  if (!committingCenterlineFirst) {
    writeTrailsMerged(sniffMergedChains(decode(fetchedTrails.bytes)))
  }
  // The release is whole. Last of all, so every earlier line above can fail
  // and leave a phone that knows it has to come back.
  await del(TRAIL_DATA_PARTIAL_KEY)
  // On the atomic path this is the moment the lines became readable, so it is
  // the moment to say so; on the other path it has already been said, once,
  // eight artifacts ago.
  if (!committingCenterlineFirst) onCenterline?.()
  report('Done')
}

/**
 * The trail line alone.
 *
 * A Blob HANDLE, so this costs an IndexedDB round trip and reads none of the
 * twelve megabytes behind it - which is what makes it worth having separately
 * from {@link loadTrailData}. Everything else that read is holding is
 * deserialised structured-clone data: 2,837 POI objects and a 141,000-sample
 * elevation profile, paid whether or not the caller wanted them. First run
 * wants exactly this and nothing else (lib/useTrailData.ts).
 */
export async function loadTrailLines(): Promise<Blob | null> {
  const trails = (await get(TRAILS_BLOB_KEY)) as Blob | undefined
  return trails instanceof Blob ? trails : null
}

/**
 * Whether a WHOLE release has committed to this phone.
 *
 * Two questions since #863, because the commit is no longer always
 * all-or-nothing: are the trail lines here, and is the release they belong to
 * finished. The second is a small boolean rather than a read of the waypoints
 * themselves - the caller that asks this most is the launch fetch, deciding
 * whether to fetch at all, and it would then throw 2,837 deserialised POIs
 * away.
 *
 * False for a half-downloaded release, which is what sends the launch fetch
 * back for the WHOLE thing rather than resuming into it. Resuming would mean
 * a newer manifest's waypoints against the centerline of whatever release was
 * interrupted - a mixed measurement rather than a saving, and the trail lines
 * are the cheapest artifact in the set to fetch again.
 */
export async function haveTrailData(): Promise<boolean> {
  if ((await loadTrailLines()) === null) return false
  return (await get(TRAIL_DATA_PARTIAL_KEY)) !== true
}

export async function loadTrailData(): Promise<TrailData | null> {
  const trails = await loadTrailLines()
  if (trails === null) return null

  const pois = ((await get(POIS_KEY)) as StoredPoi[] | undefined) ?? []
  const spurs =
    ((await get(SPURS_STORE_KEY)) as Record<string, SpurRecord> | undefined) ?? {}
  // Undefined and null both mean "no ribbon". They arrive from different
  // places - nothing stored at all, versus a release that published no profile
  // - and neither is a state the map screen has to tell apart.
  const elevation =
    ((await get(ELEVATION_STORE_KEY)) as ElevationProfile | undefined) ?? null
  // Through storedClubSections rather than a bare cast: what is in the store
  // was written by whatever version of this app was installed then, and the
  // corridor view reads it on every camera move.
  const clubSections = storedClubSections(await get(CLUB_SECTIONS_STORE_KEY))
  const highlights = storedHighlights(await get(HIGHLIGHTS_STORE_KEY))
  return { trails, pois, spurs, elevation, clubSections, highlights }
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
  await del(CLUB_SECTIONS_STORE_KEY)
  await del(HIGHLIGHTS_STORE_KEY)
  await del(ELEVATION_STORE_KEY)
  // No data, no claim about how much of it is here (#863) - the same
  // reasoning as clearTrailsMerged() below.
  await del(TRAIL_DATA_PARTIAL_KEY)
  clearTrailsMerged()
}
