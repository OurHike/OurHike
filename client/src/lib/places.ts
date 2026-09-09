// The places a hiker can name (#1371, #1373): parks, towns, trailheads,
// parking areas and the long trails, as `places.json` publishes them.
//
// The record the exporter writes and the shape every place search on the
// phone resolves against - first run's "where do you hike?", step 2's stop
// picker, the finder's location facet, the volunteer map's place search. One
// resolver rather than four, for the reason lib/suggestedHikes.ts's
// `searchPlaces` gives: nothing here needs signal, and nothing here geocodes.
//
// EVERY LINE A ROW PRINTS IS THE EXPORTER'S OWN, and the two that are
// measurements say so in the document: `trailMiles` is miles of published
// trail line inside a park's boundary or within `trailRadiusMiles` of a point,
// and when the exporter had no line to measure against it omits the field on
// every row and sets `trailMilesMeasured: false`. A row with no `trailMiles`
// therefore means UNKNOWN, never zero, and the sentence a screen prints has
// to keep that apart from a measured `0` - "no trail data held" is a fact
// about the download; "nothing measured" is a fact about this release.
//
// JUNK COSTS THE ROW, NEVER THE LIST (lib/suggestedHikesData.ts's rule for a
// document somebody else wrote): a row missing what a search cannot do
// without - an id, a name, a kind and a point - is dropped; everything else
// degrades to its honest absence.

export const PLACE_KINDS = ['park', 'town', 'trailhead', 'parking', 'trail'] as const
export type PlaceKind = (typeof PLACE_KINDS)[number]

export interface Place {
  id: string
  name: string
  kind: PlaceKind
  lon: number
  lat: number
  /** The published waypoint this place is, when it is one - so a pick here
   *  can also open the waypoint the app holds. */
  poiId?: string
  /** Two-letter state, only where the source said it. */
  state?: string
  /** The publisher's own category word ("State Park", "Historic Site"). */
  category?: string
  /** The park polygon a point sits inside, by name. */
  within?: string
  /** [west, south, east, north], for parks and trails, so a map can fit the
   *  place rather than centre on a point inside it. */
  bbox?: readonly [number, number, number, number]
  /** Miles of published trail - see the module docstring for what it
   *  measures, and why absent is not zero. */
  trailMiles?: number
  source?: string
}

export interface PlacesDocument {
  generatedAt: string | null
  /** The radius `trailMiles` was measured within, for a point. */
  trailRadiusMiles: number | null
  /** False when the exporter had no published line to measure against. */
  trailMilesMeasured: boolean
  places: Place[]
}

export const NO_PLACES: PlacesDocument = {
  generatedAt: null,
  trailRadiusMiles: null,
  trailMilesMeasured: false,
  places: [],
}

function nonEmptyString(value: unknown): string | null {
  return typeof value === 'string' && value.trim() !== '' ? value : null
}

function finite(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function validBbox(
  value: unknown,
): readonly [number, number, number, number] | undefined {
  if (!Array.isArray(value) || value.length !== 4) return undefined
  const parts = value.map(finite)
  if (parts.some((part) => part === null)) return undefined
  const [west, south, east, north] = parts as number[]
  if (west > east || south > north) return undefined
  return [west, south, east, north]
}

/** One row, or null when it lacks what a search cannot do without. */
export function validatePlace(candidate: unknown): Place | null {
  if (typeof candidate !== 'object' || candidate === null) return null
  const row = candidate as Record<string, unknown>
  const id = nonEmptyString(row.id)
  const name = nonEmptyString(row.name)
  const kind = (PLACE_KINDS as readonly unknown[]).includes(row.kind)
    ? (row.kind as PlaceKind)
    : null
  const lon = finite(row.lon)
  const lat = finite(row.lat)
  if (id === null || name === null || kind === null || lon === null || lat === null) {
    return null
  }
  if (lon < -180 || lon > 180 || lat < -90 || lat > 90) return null

  const place: Place = { id, name, kind, lon, lat }
  const poiId = nonEmptyString(row.poiId)
  if (poiId !== null) place.poiId = poiId
  const state = nonEmptyString(row.state)
  if (state !== null) place.state = state
  const category = nonEmptyString(row.category)
  if (category !== null) place.category = category
  const within = nonEmptyString(row.within)
  if (within !== null) place.within = within
  const bbox = validBbox(row.bbox)
  if (bbox !== undefined) place.bbox = bbox
  const trailMiles = finite(row.trailMiles)
  if (trailMiles !== null && trailMiles >= 0) place.trailMiles = trailMiles
  const source = nonEmptyString(row.source)
  if (source !== null) place.source = source
  return place
}

/** The whole document, with every unreadable row dropped. */
export function validatePlaces(document: unknown): PlacesDocument {
  if (typeof document !== 'object' || document === null) return NO_PLACES
  const doc = document as Record<string, unknown>
  const rows = Array.isArray(doc.places) ? doc.places : []
  const places = rows.map(validatePlace).filter((place): place is Place => place !== null)
  const radius = finite(doc.trailRadiusMiles)
  return {
    generatedAt: nonEmptyString(doc.generated_at) ?? nonEmptyString(doc.generatedAt),
    trailRadiusMiles: radius !== null && radius > 0 ? radius : null,
    trailMilesMeasured: doc.trailMilesMeasured === true,
    places,
  }
}

/**
 * How many matches a field offers under itself - lib/suggestedHikes.ts's
 * PLACE_MATCH_LIMIT, and @unvalidated for the same reason: six fits under a
 * field on a 390px phone; nobody has typed into this field yet.
 */
export const PLACE_MATCH_LIMIT = 6

/**
 * Places whose name contains the query, earliest match first, then the
 * kinds a hiker most often means (a park or a town before a lot), then by
 * name. lib/searchPoi.ts's own ordering, over this set.
 */
export function searchPlaces(
  places: readonly Place[],
  query: string,
  limit: number = PLACE_MATCH_LIMIT,
): Place[] {
  const needle = query.trim().toLowerCase()
  if (needle === '') return []
  const rank: Record<PlaceKind, number> = {
    park: 0,
    town: 1,
    trail: 2,
    trailhead: 3,
    parking: 4,
  }
  return places
    .map((place) => ({ place, at: place.name.toLowerCase().indexOf(needle) }))
    .filter(({ at }) => at !== -1)
    .sort(
      (a, b) =>
        a.at - b.at ||
        rank[a.place.kind] - rank[b.place.kind] ||
        a.place.name.localeCompare(b.place.name),
    )
    .slice(0, limit)
    .map(({ place }) => place)
}

/** The kind, as a screen prints it under a name: the publisher's own
 *  category where one was published, else the kind word. */
export function placeKindLabel(place: Place): string {
  return place.category ?? place.kind
}
