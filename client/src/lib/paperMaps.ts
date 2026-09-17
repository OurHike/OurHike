// Which of an organization's paper maps covers a place (#1574 - A hiker on
// NYNJTC ground has nowhere to buy the paper map for where they are).
//
// Two joins, both answered here so the hike detail and the tapped-line sheet
// cannot disagree about what a sheet is called or which product it belongs
// to:
//
//   BY NAME  (paperMapsForPlace) - a published hike names its park, and the
//            stewards artifact carries, per sheet, the parks and trails the
//            organization lists on that sheet in its own spelling
//            (pipeline/reference/nynjtc_paper_maps.json, `sheet_covers`).
//            "Harriman State Park" is on sheets 118 and 119 because NYNJTC
//            says "Southern Harriman State Park" and "Northern Harriman
//            State Park" are.
//
//   BY GROUND (paperMapsAt) - the tapped point either lies inside a sheet's
//            footprint (lib/mapSheets.ts, the one-time archive) or it does
//            not, and the sheet number names the product through the same
//            per-product sheet list.
//
// THE NAME JOIN IS WORD-CONTAINMENT, NOT EQUALITY, and the reason is the
// example above: the organization's index qualifies a park by which half of
// it a sheet shows, and a hike names the whole park. So two names match when
// one's words appear, in order, inside the other's - `harriman state park`
// inside `southern harriman state park` - and the shorter side has at least
// MIN_CONTAINED_CHARS characters, so `pond` does not join every pond. This
// is REASONED rather than measured: the hike finder's 385 park names are not
// in the checkout this was written in, so the join rate on the real list is
// unmeasured. @unvalidated - what would settle it is running
// paperMapsForPlace over every `park` in suggested_hikes.json and reading the
// misses; a park that matches nothing costs a hike its line, never a wrong
// line.
//
// NOTHING HERE PRINTS A PRICE, and nothing here builds a URL: every link is
// the one the pipeline published, referral query and all, and the phone
// copies it.

import { sheetsContaining, type MapSheets } from './mapSheets'
import type { PaperMap, Steward, Stewards } from './stewards'

/** The screens a store block may grant (pipeline/export_sources.py's
 *  STORE_SURFACES). Closed on both ends, and the map is on neither. */
export type StoreSurface = 'sources_screen' | 'hike_detail' | 'trail_sheet'

export interface PaperMapMatch {
  steward: Steward
  map: PaperMap
  /** The sheets that made the match - those whose footprint holds the
   *  point, or whose park list names the place - in sheet order. Empty when
   *  the product's own `covers` named the place and no sheet did, which is
   *  the honest reading: the organization says the park is on this map, and
   *  does not say which sheet. */
  sheets: readonly string[]
}

/** Below this many characters the shorter name is too short to be contained
 *  meaningfully. `Teatown` is 7 and is a real sheet-index entry; `pond`,
 *  `park` and `trail` are what the floor exists to stop. */
export const MIN_CONTAINED_CHARS = 6

/** The steward whose registry keys include `source` - a graph edge's
 *  `source`, or the key prefix of a published hike's id
 *  (`nynjtc_hike_finder:7909`). Null for a key no steward claims. */
export function stewardForSource(
  stewards: Stewards,
  source: string | null,
): Steward | null {
  if (source === null || source === '') return null
  return stewards.find((steward) => steward.keys.includes(source)) ?? null
}

/** A place name as words: lower-cased, apostrophes closed up, other
 *  punctuation dropped, one space between. "Sam's Point Preserve" and
 *  "Sams Point Preserve" are one name, and so are the straight and curly
 *  apostrophe spellings of it. */
export function placeWords(name: string): string[] {
  return name
    .toLowerCase()
    .replace(/[\u2019']/g, '')
    .replace(/[^\p{L}\p{N}]+/gu, ' ')
    .trim()
    .split(' ')
    .filter((word) => word !== '')
}

function containsWords(longer: string[], shorter: string[]): boolean {
  if (shorter.length === 0 || shorter.length > longer.length) return false
  for (let start = 0; start + shorter.length <= longer.length; start++) {
    let all = true
    for (let i = 0; i < shorter.length; i++) {
      if (longer[start + i] !== shorter[i]) {
        all = false
        break
      }
    }
    if (all) return true
  }
  return false
}

/** Whether two place names name one place, by the rule the module comment
 *  sets out. Symmetric. */
export function placeNamesMatch(a: string, b: string): boolean {
  const wordsA = placeWords(a)
  const wordsB = placeWords(b)
  if (wordsA.length === 0 || wordsB.length === 0) return false
  const [longer, shorter] =
    wordsA.length >= wordsB.length ? [wordsA, wordsB] : [wordsB, wordsA]
  if (
    shorter.join(' ').length < MIN_CONTAINED_CHARS &&
    shorter.join(' ') !== longer.join(' ')
  ) {
    return false
  }
  return containsWords(longer, shorter)
}

function granted(steward: Steward, surface: StoreSurface): boolean {
  return steward.store !== null && steward.store.storeSurfaces.includes(surface)
}

/**
 * The maps of `steward` that name `place`, on a surface the organization has
 * granted. Empty for a steward with no store, a surface not granted, no place,
 * or a place none of their sheets names.
 */
export function paperMapsForPlace(
  steward: Steward | null,
  surface: StoreSurface,
  place: string | null | undefined,
): PaperMapMatch[] {
  if (steward === null || !granted(steward, surface)) return []
  if (place === null || place === undefined || place.trim() === '') return []
  const matches: PaperMapMatch[] = []
  for (const map of steward.store!.paperMaps) {
    const sheets = map.sheets.filter((sheet) =>
      (map.sheetCovers[sheet] ?? []).some((name) => placeNamesMatch(name, place)),
    )
    const byProduct = map.covers.some((name) => placeNamesMatch(name, place))
    if (sheets.length > 0 || byProduct) matches.push({ steward, map, sheets })
  }
  return matches
}

/**
 * The maps whose sheets hold the point, on a surface their organization has
 * granted. One match per product, carrying every sheet of it that holds the
 * point - two sheets overlap at their shared edge, and a point on the overlap
 * is on both.
 *
 * Joined through the STEWARDS' sheet lists, never the archive's own product
 * field: the archive is written once and the table it was written from may
 * be older or newer than what this phone holds, and the phone's own copy is
 * the one it can stand behind.
 */
export function paperMapsAt(
  stewards: Stewards,
  sheets: MapSheets | null,
  surface: StoreSurface,
  lon: number,
  lat: number,
): PaperMapMatch[] {
  if (sheets === null) return []
  const held = sheetsContaining(sheets, lon, lat)
  if (held.length === 0) return []
  const matches: PaperMapMatch[] = []
  for (const steward of stewards) {
    if (!granted(steward, surface)) continue
    for (const map of steward.store!.paperMaps) {
      const onThisMap = held.filter((sheet) => map.sheets.includes(sheet))
      if (onThisMap.length > 0) matches.push({ steward, map, sheets: onThisMap })
    }
  }
  return matches
}

function consecutive(sheets: readonly string[]): boolean {
  const numbers = sheets.map((sheet) => (/^\d+$/.test(sheet) ? Number(sheet) : NaN))
  if (numbers.some((n) => Number.isNaN(n))) return false
  for (let i = 1; i < numbers.length; i++) {
    if (numbers[i] !== numbers[i - 1] + 1) return false
  }
  return true
}

/**
 * "sheet 118", "sheets 118 and 119", "sheets 120–123", "sheets 104, 105 and
 * 106A" - or null for no sheets, which a caller renders as no clause rather
 * than as "sheets ".
 */
export function sheetLabel(sheets: readonly string[]): string | null {
  if (sheets.length === 0) return null
  if (sheets.length === 1) return `sheet ${sheets[0]}`
  if (sheets.length > 2 && consecutive(sheets)) {
    return `sheets ${sheets[0]}–${sheets[sheets.length - 1]}`
  }
  const head = sheets.slice(0, -1).join(', ')
  return `sheets ${head} and ${sheets[sheets.length - 1]}`
}

/**
 * The words before the linked title: "This spot is on sheet 119 of the New
 * York-New Jersey Trail Conference’s" - the caller follows it with the
 * product title as the link, so the title is the organization's own words
 * and the only thing a hiker taps. With no sheet to name: "This spot is on
 * the New York-New Jersey Trail Conference’s".
 */
export function paperMapLead(match: PaperMapMatch, subject: string): string {
  const label = sheetLabel(match.sheets)
  const owner = `the ${match.steward.name}’s`
  return label === null
    ? `${subject} is on ${owner}`
    : `${subject} is on ${label} of ${owner}`
}
