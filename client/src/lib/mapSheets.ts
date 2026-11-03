// The footprint of every NYNJTC paper map sheet, as the bucket's own archive
// holds it (#1574 - A hiker on NYNJTC ground has nowhere to buy the paper map
// for where they are).
//
// WHAT THIS READS. `archive/nynjtc_map_sheets.json`, written ONCE by
// pipeline/archive_nynjtc_sheet_extents.py from the Avenza Map Store's product
// pages - the publisher's own georeference of each sheet's PDF, four lon/lat
// corners per sheet. NYNJTC publishes no index of which sheet covers what
// ground (their ArcGIS org was probed whole on 2026-09-17: no sheet field on
// any of 27 services, no tiles, no index item), so this archive is the only
// footprint there is, and Avenza is a third party that may stop selling the
// sheets. The maintainer's rule for the data follows from that: not a
// pipeline that runs regularly, "just an archive that sits in its own folder
// in r2". So the key is at the bucket ROOT, beside `conditions/`, outside
// any release folder (lib/dataRelease.ts), and nothing rewrites it on a
// schedule.
//
// WHAT THE PHONE DOES WITH IT. lib/paperMaps.ts asks which sheets hold a
// tapped point and names the product those sheets belong to, from the
// `paper_maps` the stewards artifact carries (lib/stewards.ts). A sheet with
// no footprint (Catskill 145 and 146 on 2026-09-17, which Avenza does not
// sell) holds no point, so ground on those two sheets alone is matched to
// nothing - a miss, never a wrong answer.
//
// THE FOOTPRINT IS AN UPRIGHT BOX, AS AVENZA PRINTS IT, and one set is
// printed diagonal: the four Delaware Water Gap & Kittatinny sheets run
// along the ridge, so their boxes claim ground at the corners that the paper
// does not show. The box is what the publisher published; nothing here
// shrinks it, and the sheet's own reference row records the over-claim.
//
// NEVER FATAL, like lib/publishedConditions.ts: an unreachable bucket, a
// document this build cannot read, or an environment the archive was never
// written to all yield null, and every surface that reads this renders
// exactly as it did before the archive existed.

import { DATA_CONFIGURED, dataUrl } from './config'
import { recallPublished, rememberPublished } from './conditionsCache'

/** The key pipeline/archive_nynjtc_sheet_extents.py writes. Must match
 *  exactly: pipeline/tests/test_published_key_contract.py holds the two
 *  spellings together, as it does for every other key the app fetches. */
export const NYNJTC_MAP_SHEETS_KEY = 'archive/nynjtc_map_sheets.json'

export type LonLat = readonly [number, number]

export interface MapSheet {
  /** The sheet's corners, lon/lat, in ring order. At least three. */
  readonly bounds: readonly LonLat[]
  /** The store product handle the archive says this sheet belongs to, or
   *  null where the archive named none. lib/paperMaps.ts joins on the
   *  stewards artifact's own sheet lists first and reads this only as a
   *  cross-check, so an archive written against a newer table cannot name
   *  a product this phone's stewards do not carry. */
  readonly product: string | null
}

/** Sheet number -> footprint, for every sheet the archive holds a footprint
 *  for. A sheet the archive lists with `bounds: null` is absent here. */
export type MapSheets = Readonly<Record<string, MapSheet>>

function lonLat(value: unknown): LonLat | null {
  if (!Array.isArray(value) || value.length < 2) return null
  const lon = value[0]
  const lat = value[1]
  if (typeof lon !== 'number' || typeof lat !== 'number') return null
  if (!Number.isFinite(lon) || !Number.isFinite(lat)) return null
  if (lon < -180 || lon > 180 || lat < -90 || lat > 90) return null
  return [lon, lat]
}

/**
 * The archive document, read defensively.
 *
 * Null for a document with no `sheets` object at all - a shape this build
 * cannot read, kept out of the cache so the next offline session does not
 * inherit it. A sheet whose footprint does not parse is dropped on its own:
 * one unreadable row costs that sheet, never the archive.
 */
export function parseMapSheets(document: unknown): MapSheets | null {
  const sheets = (document as { sheets?: unknown } | null | undefined)?.sheets
  if (sheets === null || typeof sheets !== 'object' || Array.isArray(sheets)) return null

  const parsed: Record<string, MapSheet> = {}
  for (const [sheet, raw] of Object.entries(sheets as Record<string, unknown>)) {
    const record = raw as Record<string, unknown> | null
    const bounds = record?.bounds
    if (!Array.isArray(bounds)) continue
    const ring = bounds.map(lonLat)
    if (ring.length < 3 || ring.some((corner) => corner === null)) continue
    const product = record?.product
    parsed[sheet] = {
      bounds: ring as LonLat[],
      product: typeof product === 'string' && product !== '' ? product : null,
    }
  }
  return parsed
}

/**
 * Whether a point lies inside a ring - the even-odd rule, cast eastward.
 *
 * Plain lon/lat arithmetic, no projection: a sheet is at most a third of a
 * degree across and the test is inside-or-not, so the flattening that would
 * matter for a distance does not matter here. A point exactly on an edge
 * lands on whichever side the arithmetic puts it, which for a paper map's
 * edge is a coin toss either way.
 */
export function pointInRing(ring: readonly LonLat[], lon: number, lat: number): boolean {
  let inside = false
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i]
    const [xj, yj] = ring[j]
    const crosses = yi > lat !== yj > lat
    if (crosses && lon < ((xj - xi) * (lat - yi)) / (yj - yi) + xi) inside = !inside
  }
  return inside
}

/** Every sheet whose footprint holds the point, in sheet order. Empty is the
 *  ordinary answer for most of the map: NYNJTC's sheets cover a region a
 *  day's drive across, and the A.T. runs from Georgia to Maine. */
export function sheetsContaining(
  sheets: MapSheets,
  lon: number,
  lat: number,
): readonly string[] {
  return Object.keys(sheets)
    .filter((sheet) => pointInRing(sheets[sheet].bounds, lon, lat))
    .sort()
}

/**
 * The archive, from the bucket when there is signal and from the copy this
 * phone kept when there is not - lib/publishedConditions.ts's posture,
 * through the same cache, because the failure modes are the same: a dead
 * spot mid-fetch is exactly the state a kept copy exists for.
 */
export async function fetchMapSheets(
  online: boolean,
  signal?: AbortSignal,
): Promise<MapSheets | null> {
  if (!DATA_CONFIGURED) return null
  if (!online) return recalled()

  try {
    const response = await fetch(dataUrl(NYNJTC_MAP_SHEETS_KEY), { signal })
    if (!response.ok) return recalled()
    const document = (await response.json()) as Record<string, unknown>
    const parsed = parseMapSheets(document)
    // Kept only when it parsed, so a shape this build refuses never
    // overwrites the last one it could read.
    if (parsed !== null) void rememberPublished(NYNJTC_MAP_SHEETS_KEY, document)
    return parsed ?? (await recalled())
  } catch {
    return recalled()
  }
}

async function recalled(): Promise<MapSheets | null> {
  const cached = await recallPublished(NYNJTC_MAP_SHEETS_KEY)
  if (cached === null) return null
  return parseMapSheets(cached.document)
}
