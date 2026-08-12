// Legend contents: what's in the current viewport, with counts. See
// WIREFRAMES.md's Legend section - recomputed fresh per viewport (no
// caching/staleness here, that's the whole point of a legend that reflects
// "what's on screen right now"), and rows are tappable to hide except
// closure/serious-warning, which are always shown per Map Options/Hiker
// Safety (never a hideable safety layer, anywhere in the app).
//
// AND WHAT IS DRAWN, WHERE THAT IS FEWER (#528).
//
// "What am I looking at right now" is the promise, and since collision culling
// arrived this had quietly been answering "what is inside this rectangle"
// instead. `icon-allow-overlap: false` means MapLibre draws no two colliding
// pins, so at hiking zooms a row can read `Privy · 6` on a map with no privy
// pin on it - 3% of privies place at z14, measured. A count that is
// structurally unable to be wrong about presence and silently wrong about
// visibility is the more dangerous of the two.
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

export interface LegendRow {
  type: string
  confidence: 'high' | 'low'
  count: number
  hideable: boolean
  /**
   * How many of `count` the map actually drew, or undefined where nobody
   * measured.
   *
   * Undefined and zero are different answers and must stay so: the layer is
   * absent on a cold start, and rendering "0 shown" then would claim a drop
   * that has not happened. Undefined renders as the plain count, exactly as
   * this did before #528.
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

export function computeLegendContents(
  bbox: BoundingBox,
  points: MapPoint[],
  drawn?: ReadonlyMap<string, number>,
): LegendRow[] {
  const counts = new Map<string, number>()

  for (const point of points) {
    if (!isWithin(point, bbox)) continue
    const key = `${point.type}::${point.confidence}`
    counts.set(key, (counts.get(key) ?? 0) + 1)
  }

  return Array.from(counts.entries()).map(([key, count]) => {
    const [type, confidence] = key.split('::') as [string, 'high' | 'low']
    return {
      type,
      confidence,
      count,
      hideable: !NEVER_HIDEABLE.has(type),
      // Absent from the measurement means none of this category was placed,
      // which is 0 rather than unmeasured - the whole map was measured, so a
      // missing key is an answer. `drawn` being absent entirely is the
      // unmeasured case, and then no row carries a figure at all.
      //
      // Clamped to the present count: a drawn figure larger than the rectangle
      // holds can only be a duplicate the probe failed to fold (see
      // map/drawnPois.ts), and `Water · 14 · 17 shown` would discredit every
      // other row on the panel.
      drawnCount: drawn === undefined ? undefined : Math.min(drawn.get(key) ?? 0, count),
    }
  })
}

/**
 * What to say at the head of the panel: how many waypoints are in view against
 * how many fit, or null when there is nothing to report.
 *
 * Null in three cases, and they are all "say nothing": nothing measured,
 * nothing present, or everything present is drawn. A line reading "112 of 112
 * fit" is noise on a panel someone opens all day to answer a different
 * question.
 *
 * The summary, not the point - see the header comment. It exists because the
 * question "is there anything here I am not being shown" should be answerable
 * without reading every row, and it is deliberately a second-order thing: the
 * rows are where a hiker learns that the missing category is the privies.
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
