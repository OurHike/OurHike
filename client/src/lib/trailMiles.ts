// The published per-vertex miles, read into the shape the index builder takes
// (#1192, pipeline/export_trails.py's write_trail_miles).
//
// What the file is: `{ format, trails_sha256, miles: { <feature id>: [...] } }`,
// one number per vertex of the centerline feature that id names in
// trails.geojson, in that feature's own coordinate order. A MultiLineString
// feature carries one list per part instead; the client's index reads only
// LineStrings (lib/trailPosition.ts's collectTrailParts), and the chain merge
// upstream publishes the centerline as LineStrings, so those entries are
// skipped here rather than flattened into something that could mis-align.
//
// The pairing with the lines is checked at download time against the
// published hash (lib/trailData.ts's fetchTrailMiles), not here: by the time
// this runs the bytes are on the phone and were stored beside the lines they
// name. What this checks is shape, so a truncated or hand-edited store reads
// as "no miles" rather than as a thrown parse somewhere a launch reports as a
// failed download - the same posture collectTrailParts takes with the lines.

import type { TrailMilesById } from './trailPosition'

export interface TrailMiles {
  /** The trails.geojson these miles were measured on, by hash. */
  trailsSha256: string
  byId: TrailMilesById
}

function isNumberList(value: unknown): value is number[] {
  return Array.isArray(value) && value.every((entry) => typeof entry === 'number')
}

/**
 * Parses the published file, or returns null for anything that is not one.
 *
 * Takes the text rather than a parsed object because the parse is the cost:
 * about two megabytes of JSON, which is why the only production caller runs
 * on a worker (lib/trailIndexBuild.ts) and a launch never pays it on the
 * thread a tap is waiting for.
 */
export function parseTrailMiles(text: string): TrailMiles | null {
  let parsed: unknown
  try {
    parsed = JSON.parse(text)
  } catch {
    return null
  }
  if (typeof parsed !== 'object' || parsed === null) return null
  const { format, trails_sha256: trailsSha256, miles } = parsed as Record<string, unknown>
  if (format !== 1 || typeof trailsSha256 !== 'string') return null
  if (typeof miles !== 'object' || miles === null) return null

  const byId = new Map<string, readonly number[]>()
  for (const [id, list] of Object.entries(miles as Record<string, unknown>)) {
    if (isNumberList(list)) byId.set(id, list)
  }
  return { trailsSha256, byId }
}
