// Legend contents: what's in the current viewport, with counts. See
// WIREFRAMES.md's Legend section - recomputed fresh per viewport (no
// caching/staleness here, that's the whole point of a legend that reflects
// "what's on screen right now"), and rows are tappable to hide except
// closure/serious-warning, which are always shown per Map Options/Hiker
// Safety (never a hideable safety layer, anywhere in the app).
//
// One row per category. The confidence split this used to carry, and why it
// went, is on LegendRow.
//
// AND WHAT IS DRAWN, WHERE THAT IS FEWER (#528).
//
// "What am I looking at right now" is the promise, and since collision culling
// arrived this had quietly been answering "what is inside this rectangle"
// instead. `icon-allow-overlap: false` means MapLibre draws no two colliding
// pins, so at hiking zooms a row can read `Privy 6` on a map with no privy pin
// on it - 3% of privies place at z14, measured. A count that is structurally
// unable to be wrong about presence and silently wrong about visibility is the
// more dangerous of the two.
//
// So a row carries the drawn count too, where it differs, and map/drawnPois.ts
// supplies it from what MapLibre actually placed. Per-row rather than as a
// single headline total, and deliberately: a "38 of 112 fit" line averages away
// the only rows that are alarming, which are the ones at or near zero.

export interface BoundingBox {
  west: number
  south: number
  east: number
  north: number
}

export interface MapPoint {
  id: string
  type: string
  lat: number
  lon: number
  confidence: 'high' | 'low'
}

/**
 * One row per category, and deliberately NOT one per category per confidence.
 *
 * It used to split: "Water 2" and "Water · Unverified 1" were two rows. That
 * doubled the length of a panel whose 2-column grid is about 116px wide beside
 * a desktop map, so half the labels wrapped onto a second line, and it spent
 * that room on a distinction a hiker cannot act on from here - the count is
 * "what is around me", and which particular spring is unconfirmed is a
 * question about one spring. The map still says it per pin (a broken rim), and
 * the waypoint card still says it in words, which is where somebody deciding
 * whether to walk to it is actually looking (chrome/PoiCard.tsx).
 */
export interface LegendRow {
  type: string
  count: number
  hideable: boolean
  /**
   * How many of `count` the map actually drew, or undefined where nobody
   * measured.
   *
   * Undefined and zero are different answers and must stay so: the pin layer is
   * absent on a cold start, and rendering "0 shown" then would claim a drop that
   * has not happened. Undefined renders as the plain count, exactly as this did
   * before #528.
   */
  drawnCount?: number
}

const NEVER_HIDEABLE = new Set(['closure', 'serious-warning'])

function isWithin(point: MapPoint, bbox: BoundingBox): boolean {
  return (
    point.lon >= bbox.west &&
    point.lon <= bbox.east &&
    point.lat >= bbox.south &&
    point.lat <= bbox.north
  )
}

/**
 * @param verifiedOnly The legend's "Verified?" toggle. Unverified points are
 *   left out of the COUNTS as well as off the map, because the whole promise
 *   of this panel is that it says what is on screen right now: a row reading
 *   "Water 3" over a map drawing two would be the panel telling the exact lie
 *   it exists to prevent.
 * @param drawn How many of each category MapLibre actually placed
 *   (map/drawnPois.ts), keyed by type alone so it joins these rows without a
 *   translation step. Omitted where nobody measured.
 */
export function computeLegendContents(
  bbox: BoundingBox,
  points: MapPoint[],
  verifiedOnly = false,
  drawn?: ReadonlyMap<string, number>,
): LegendRow[] {
  const counts = new Map<string, number>()

  for (const point of points) {
    if (!isWithin(point, bbox)) continue
    // Never a safety layer, whatever the toggle says. A closure nobody has
    // confirmed is still a closure, and "no off switch" has to mean every
    // switch - a filter that happens to take one off the panel is the same
    // failure as a button that does, and easier to ship by accident. The map
    // agrees structurally: closures and warnings are their own layers, so
    // poiFilter() cannot reach them either.
    if (verifiedOnly && point.confidence !== 'high' && !NEVER_HIDEABLE.has(point.type))
      continue
    // Keyed by type alone, so a verified and an unverified spring are two
    // springs rather than two rows - see LegendRow.
    counts.set(point.type, (counts.get(point.type) ?? 0) + 1)
  }

  return Array.from(counts.entries()).map(([type, count]) => ({
    type,
    count,
    hideable: !NEVER_HIDEABLE.has(type),
    // Absent from the measurement means none of this category was placed, which
    // is 0 rather than unmeasured - the whole map was measured, so a missing key
    // is an answer. `drawn` being absent entirely is the unmeasured case, and
    // then no row carries a figure at all.
    //
    // Clamped to the present count: a drawn figure larger than the rectangle
    // holds can only be a duplicate the probe failed to fold (see
    // map/drawnPois.ts), and `Water 14 · 17 shown` would discredit every other
    // row on the panel. The clamp also covers the `verifiedOnly` case, where the
    // counts above exclude unverified points and the map has filtered them out
    // too, so the two agree by construction rather than by coincidence.
    drawnCount: drawn === undefined ? undefined : Math.min(drawn.get(type) ?? 0, count),
  }))
}

/**
 * What to say at the head of the panel: how many waypoints are in view against
 * how many fit, or null when there is nothing to report.
 *
 * Null in three cases, and they are all "say nothing": nothing measured, nothing
 * present, or everything present is drawn. A line reading "112 of 112 fit" is
 * noise on a panel someone opens all day to answer a different question.
 *
 * The summary, not the point - see the header comment. It exists because "is
 * there anything here I am not being shown" should be answerable without reading
 * every row, and it is deliberately second-order: the rows are where a hiker
 * learns that the missing category is the privies.
 */
export function legendDropSummary(
  rows: readonly LegendRow[],
): { present: number; drawn: number } | null {
  const measured = rows.filter((row) => row.drawnCount !== undefined)
  if (measured.length === 0) return null

  const present = measured.reduce((total, row) => total + row.count, 0)
  const drawn = measured.reduce((total, row) => total + (row.drawnCount ?? 0), 0)
  return present > 0 && drawn < present ? { present, drawn } : null
}
