// Local search over what is already on the phone (WIREFRAMES.md Interactions).
//
// There is no network path here, by design rather than by omission. Search
// that needs signal is useless in exactly the place someone needs it, so this
// only ever matches against the exported POIs already downloaded - and the UI
// is required to say so when nothing matches (`7c`), because "not found" and
// "outside what you downloaded" are different answers.

export interface SearchablePoi {
  id: string
  name: string
  type: string
  /**
   * Which pipeline layer published this (`export_poi.py`'s DIRECT_SOURCES).
   * Optional because a phone that downloaded before the field existed has
   * POIs without one - see trailData.ts, where the same optionality is
   * explained at length.
   */
  source?: string
  /**
   * Distance along the trail, when it is known.
   *
   * Optional because it comes from the centerline index, which is built after
   * the trail lines download and can legitimately be absent - and search must
   * not depend on it. Requiring it once meant a null index emptied the search
   * results entirely: 800-odd shelters and water sources sitting in memory,
   * unfindable, because a number decorating each row could not be computed.
   */
  mile?: number
}

export interface SearchOptions {
  type?: string
}

/** Enough to scan without scrolling past the point of usefulness. */
export const SEARCH_RESULT_LIMIT = 25

export function searchPois(
  query: string,
  pois: SearchablePoi[],
  { type }: SearchOptions = {},
): SearchablePoi[] {
  const needle = query.trim().toLowerCase()
  // An empty query means "you haven't asked anything yet", not "show me all
  // 4,000 waypoints on the trail".
  if (needle === '') return []

  const scored = pois
    .filter((poi) => type === undefined || poi.type === type)
    .map((poi) => ({ poi, at: poi.name.toLowerCase().indexOf(needle) }))
    .filter(({ at }) => at !== -1)

  return scored
    .sort((a, b) => a.at - b.at || a.poi.name.localeCompare(b.poi.name))
    .slice(0, SEARCH_RESULT_LIMIT)
    .map(({ poi }) => poi)
}

/**
 * A TOWN, as opposed to an outfitter or a hostel (#802).
 *
 * `resupply` is the pipeline's catch-all: ATC's Communities layer folds
 * into it, and so do opentrail.org's stores and services. The layer is what
 * separates them, and `export_poi.py` records it - `atc_communities` is the
 * 59 designated "A.T. Community" towns and nothing else. So this is exact
 * rather than a heuristic, and it needs no pipeline change to be true.
 *
 * It is also INCOMPLETE, and the incompleteness is upstream: opentrail.org
 * publishes 103 more town points that the export deliberately drops. A town
 * that is not a designated Community does not read as a town here because
 * it is not on the phone at all.
 */
export const TOWN_SOURCE = 'atc_communities'

export function isTown(poi: { type: string; source?: string }): boolean {
  return poi.type === 'resupply' && poi.source === TOWN_SOURCE
}

/**
 * The mile a query asks about, or null when it asks about a name.
 *
 * Accepts "mi 500", "mile 500", "500.4" and a bare "500". A BARE NUMBER IS
 * A MILE because nothing on this trail is named one - and where a place
 * ever is, the name results are shown above the mile results rather than
 * instead of them, so nothing is lost by reading it both ways.
 *
 * The mile marker is the reference a shuttle driver, a guidebook and ATC's
 * own closures all quote, which is why it deserves to be a search term at
 * all (#753 gave every waypoint one).
 */
export function parseMileQuery(query: string): number | null {
  const match = query.trim().match(/^(?:mi|mile)?\s*(\d+(?:\.\d+)?)$/i)
  if (match === null) return null
  const mile = Number(match[1])
  return Number.isFinite(mile) ? mile : null
}

/** What sits near a mile, nearest first. Only POIs that carry a mile can be
 *  near one; the rest are not "far away", they are unplaceable. */
export function searchNearMile<T extends SearchablePoi>(
  mile: number,
  pois: readonly T[],
  limit: number = SEARCH_RESULT_LIMIT,
): T[] {
  return pois
    .filter((poi) => poi.mile !== undefined)
    .sort(
      (a, b) => Math.abs((a.mile as number) - mile) - Math.abs((b.mile as number) - mile),
    )
    .slice(0, limit)
}
