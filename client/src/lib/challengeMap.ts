// The challenge map's geometry, as pipeline/export_challenge_map.py publishes
// it (#1965, features/CHALLENGES_BLAZE_CARD.md slice 5): the A.T. thinned for a
// phone with each vertex's mile, the states and Canada around it, and which
// state each stretch of trail is in. lib/challengeMapSvg.ts draws it.
//
// OPTIONAL, AND KEPT. config.ts declares CHALLENGE_MAP_KEY `@release
// optional`: a release without it has no map, and the Where view then shows
// the list alone. Once a copy has reached the phone it is kept (the conditions
// cache, as challenges.json is), so the map draws with no signal - the brief's
// "nothing on a challenge screen waits on the network".
//
// PARSED DEFENSIVELY. A run with a malformed part drops that part, never the
// map: a state with no polygons is not drawn, a trail run whose miles do not
// match its coordinates is not drawn, and a document with no trail at all is
// no map.

import { CHALLENGE_MAP_KEY, DATA_CONFIGURED, dataUrl } from './config'
import { recallPublished, rememberPublished } from './conditionsCache'
import { isTrailStateCode, type TrailStateCode } from './wherePlace'

export type LonLat = readonly [number, number]
/** GeoJSON MultiPolygon coordinates: polygons of rings of positions. */
export type Polygons = readonly (readonly (readonly LonLat[])[])[]

export interface TrailRun {
  coordinates: readonly LonLat[]
  /** The published mile of each coordinate, rising. */
  miles: readonly number[]
}

export interface MapState {
  id: string | null
  name: string | null
  /** The two-letter code for the fourteen trail states; null for the rest. */
  code: TrailStateCode | null
  trail: boolean
  label: LonLat
  polygons: Polygons
}

export interface StateRun {
  code: TrailStateCode
  fromMile: number
  toMile: number
}

export interface MapCredit {
  layer: string
  source: string
  credit: string
}

export interface ChallengeMap {
  frame: readonly [number, number, number, number]
  trail: readonly TrailRun[]
  states: readonly MapState[]
  borders: readonly (readonly LonLat[])[]
  canada: Polygons
  stateRuns: readonly StateRun[]
  credits: readonly MapCredit[]
  notices: readonly string[]
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function finite(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value)
}

function position(value: unknown): LonLat | null {
  return Array.isArray(value) && value.length >= 2 && finite(value[0]) && finite(value[1])
    ? [value[0], value[1]]
    : null
}

function line(value: unknown): LonLat[] | null {
  if (!Array.isArray(value)) return null
  const out: LonLat[] = []
  for (const entry of value) {
    const point = position(entry)
    if (point === null) return null
    out.push(point)
  }
  return out.length >= 2 ? out : null
}

function polygons(value: unknown): Polygons {
  if (!Array.isArray(value)) return []
  const out: LonLat[][][] = []
  for (const polygon of value) {
    if (!Array.isArray(polygon)) continue
    const rings = polygon.map(line).filter((ring): ring is LonLat[] => ring !== null)
    if (rings.length > 0) out.push(rings)
  }
  return out
}

function trailRun(value: unknown): TrailRun | null {
  if (!isRecord(value)) return null
  const coordinates = line(value.coordinates)
  const miles =
    Array.isArray(value.miles) && value.miles.every(finite)
      ? (value.miles as number[])
      : null
  if (coordinates === null || miles === null || miles.length !== coordinates.length)
    return null
  return { coordinates, miles }
}

function mapState(value: unknown): MapState | null {
  if (!isRecord(value)) return null
  const drawn = polygons(value.polygons)
  const label = position(value.label)
  if (drawn.length === 0 || label === null) return null
  const code = isTrailStateCode(value.code) ? value.code : null
  return {
    id: typeof value.id === 'string' ? value.id : null,
    name: typeof value.name === 'string' ? value.name : null,
    code,
    trail: value.trail === true && code !== null,
    label,
    polygons: drawn,
  }
}

function stateRun(value: unknown): StateRun | null {
  if (!Array.isArray(value) || value.length !== 3) return null
  const [code, from, to] = value
  return isTrailStateCode(code) && finite(from) && finite(to) && to >= from
    ? { code, fromMile: from, toMile: to }
    : null
}

/** The published document as the map draws it, or null when it holds no
 *  trail to draw. */
export function parseChallengeMap(document: unknown): ChallengeMap | null {
  if (!isRecord(document) || document.format !== 1) return null
  const trail = (Array.isArray(document.trail) ? document.trail : [])
    .map(trailRun)
    .filter((run): run is TrailRun => run !== null)
  if (trail.length === 0) return null
  const frame =
    Array.isArray(document.frame) &&
    document.frame.length === 4 &&
    document.frame.every(finite)
      ? (document.frame as [number, number, number, number])
      : null
  if (frame === null) return null
  const credits = (Array.isArray(document.credits) ? document.credits : []).flatMap(
    (entry) =>
      isRecord(entry) && typeof entry.credit === 'string' && entry.credit !== ''
        ? [
            {
              layer: String(entry.layer ?? ''),
              source: String(entry.source ?? ''),
              credit: entry.credit,
            },
          ]
        : [],
  )
  return {
    frame,
    trail,
    states: (Array.isArray(document.states) ? document.states : [])
      .map(mapState)
      .filter((state): state is MapState => state !== null),
    borders: (Array.isArray(document.borders) ? document.borders : [])
      .map(line)
      .filter((border): border is LonLat[] => border !== null),
    canada: polygons(document.canada),
    stateRuns: (Array.isArray(document.state_runs) ? document.state_runs : [])
      .map(stateRun)
      .filter((run): run is StateRun => run !== null),
    credits,
    notices: (Array.isArray(document.notices) ? document.notices : []).filter(
      (notice): notice is string => typeof notice === 'string',
    ),
  }
}

/**
 * The state a trail mile is in, by the published runs; null when the map has
 * none (an older release) or the mile is off both ends. Where the trail
 * follows a state line the runs alternate, and so does this answer - the
 * exporter's docstring says why that is honest rather than wrong.
 */
export function stateAtMile(
  runs: readonly StateRun[],
  mile: number,
): TrailStateCode | null {
  let low = 0
  let high = runs.length - 1
  while (low <= high) {
    const middle = (low + high) >> 1
    const run = runs[middle]
    if (mile < run.fromMile) high = middle - 1
    else if (mile > run.toMile) low = middle + 1
    else return run.code
  }
  return null
}

/** The kept copy, validated again, or null. */
export async function recallChallengeMap(): Promise<ChallengeMap | null> {
  const cached = await recallPublished(CHALLENGE_MAP_KEY)
  return cached === null ? null : parseChallengeMap(cached.document)
}

/** Ask the release, keep what parses, hand it back - or null, in which case
 *  the caller keeps what it had. A 404 is every release built before
 *  export_challenge_map.py, and never clears the kept copy. */
export async function fetchChallengeMap(
  signal?: AbortSignal,
): Promise<ChallengeMap | null> {
  if (!DATA_CONFIGURED) return null
  try {
    const response = await fetch(dataUrl(CHALLENGE_MAP_KEY), { signal })
    if (!response.ok) return null
    const document: unknown = await response.json()
    const parsed = parseChallengeMap(document)
    if (parsed === null || !isRecord(document)) return null
    await rememberPublished(CHALLENGE_MAP_KEY, document)
    return parsed
  } catch {
    return null
  }
}
