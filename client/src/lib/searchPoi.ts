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
