// Legend contents: what's in the current viewport, with counts. See
// WIREFRAMES.md's Legend section - recomputed fresh per viewport (no
// caching/staleness here, that's the whole point of a legend that reflects
// "what's on screen right now"), and rows are tappable to hide except
// closure/serious-warning, which are always shown per Map Options/Hiker
// Safety (never a hideable safety layer, anywhere in the app).
//
// One row per category. The confidence split this used to carry, and why it
// went, is on LegendRow.

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
 */
export function computeLegendContents(
  bbox: BoundingBox,
  points: MapPoint[],
  verifiedOnly = false,
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
  }))
}
