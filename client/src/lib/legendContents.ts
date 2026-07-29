// Legend contents: what's in the current viewport, with counts. See
// WIREFRAMES.md's Legend section - recomputed fresh per viewport (no
// caching/staleness here, that's the whole point of a legend that reflects
// "what's on screen right now"), and rows are tappable to hide except
// closure/serious-warning, which are always shown per Map Options/Hiker
// Safety (never a hideable safety layer, anywhere in the app).

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
): LegendRow[] {
  const counts = new Map<string, number>()

  for (const point of points) {
    if (!isWithin(point, bbox)) continue
    const key = `${point.type}::${point.confidence}`
    counts.set(key, (counts.get(key) ?? 0) + 1)
  }

  return Array.from(counts.entries()).map(([key, count]) => {
    const [type, confidence] = key.split('::') as [string, 'high' | 'low']
    return { type, confidence, count, hideable: !NEVER_HIDEABLE.has(type) }
  })
}
