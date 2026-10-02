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
// A v2 release's `v2/trail_miles.json` is the same file with `format` 2 and
// each list delta-coded in thousandths (unpackTrailMiles below); both read to
// the same numbers.
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
  const {
    format,
    trails_sha256: trailsSha256,
    miles,
    milli_mile_deltas: deltas,
  } = parsed as Record<string, unknown>
  if (typeof trailsSha256 !== 'string') return null
  if (format === 2) return unpackTrailMiles(trailsSha256, deltas)
  if (format !== 1) return null
  if (typeof miles !== 'object' || miles === null) return null

  const byId = new Map<string, readonly number[]>()
  for (const [id, list] of Object.entries(miles as Record<string, unknown>)) {
    if (isNumberList(list)) byId.set(id, list)
  }
  return { trailsSha256, byId }
}

/**
 * `v2/trail_miles.json` (decision 44, stage 6 of #1793): v1's file with each
 * chain's miles as whole thousandths of a mile, the first vertex's as itself
 * and every later one as its step from the vertex before
 * (pipeline/dbt/models/publish/pub_trail_miles_v2.sql writes it). A step can
 * be negative, where the chain runs backwards (lib/trailPosition.ts splits a
 * piece there), and is kept.
 *
 * A thousandth-count over 1,000 is the double nearest the decimal, which is
 * what JSON.parse makes of v1's text, so a chain reads the same numbers from
 * either file (Reasoned from IEEE 754's correctly rounded division;
 * pipeline/parity.py's trail_miles_v2 family holds the published files to
 * it). A chain whose list is not whole numbers is skipped, as v1's reading
 * skips a list that is not numbers: one step that is not whole would put
 * every later vertex of that chain at the wrong mile.
 */
function unpackTrailMiles(trailsSha256: string, deltas: unknown): TrailMiles | null {
  if (typeof deltas !== 'object' || deltas === null || Array.isArray(deltas)) return null
  const byId = new Map<string, readonly number[]>()
  for (const [id, list] of Object.entries(deltas as Record<string, unknown>)) {
    if (!Array.isArray(list) || !list.every((step) => Number.isInteger(step))) continue
    let milli = 0
    byId.set(
      id,
      (list as number[]).map((step) => {
        milli += step
        return milli / 1000
      }),
    )
  }
  return { trailsSha256, byId }
}
