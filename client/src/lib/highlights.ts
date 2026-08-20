// Stretches of trail somebody says are worth going to (#858), read from the
// artifact pipeline/export_highlights.py publishes (#595).
//
// WHAT A HIGHLIGHT IS, AND WHAT IT DELIBERATELY IS NOT
//
// Two mileposts and a name, plus who says so. It carries NO length, NO ascent
// and NO time: the phone already holds ~141,000 elevation samples and derives
// all three (lib/elevationGain.ts into lib/naismith.ts), which keeps one number
// in one place and means a better profile improves every highlight without a
// republish. lib/highlightDetail.ts is where that derivation happens.
//
// THE WORD `stretch` IS NOT USED HERE
//
// It belongs to the ~50-mile offline download unit pipeline/cut_stretches.py
// cuts (#552, decided 2026-08-18). A highlight is a highlight, and where a
// sentence needs a general word for a piece of trail it says "section" - the
// same call chrome/ClubSheet.tsx already makes.
//
// LEGS, BECAUSE A MILE ONLY MEANS SOMETHING RELATIVE TO A TRAIL
//
// The maintainer's decision, 2026-08-19: a Highlight is its own entity and may
// cross trails, so its range is an ordered list of legs rather than one pair of
// mileposts. features/NEARBY_TRAILS.md settled on 2026-08-18 that the map's
// subject is one chosen trail at a time and that switching trails swaps the
// mile frame - which is exactly why a bare `start_mile` would be ambiguous the
// day the first loop leaves the A.T.
//
// Every entry published today has one leg. The shape is what lets the first
// cross-trail loop arrive without a migration, not a promise that one has.
//
// THE BASIS IS THE POINT
//
// "Popular" is three questions with completely different evidence behind them
// (features/CORRIDOR_VIEW.md), so a highlight names which one it is answering
// and the app never says "popular" flatly. Where a highlight carries more than
// one basis the app cites the STRONGEST and never two at once - see
// `strongestBasis` below, which is the whole of that rule.

/** What the app's own editorial list says, the weakest and first-shipping
 *  basis. Never blended with the others, and never sorted against them. */
export const NAMED = 'named'
/** ATC's own day-hike material. Attributable to them rather than to us, which
 *  is strictly better than `named` for the same stretch. */
export const PUBLISHED = 'published'
/** A count across hikers. Not published by anything today - #596's, and
 *  blocked on an explicit decision about features/EVENTING.md rule 2. Listed
 *  so a release that starts carrying it is understood rather than dropped. */
export const VISITED = 'visited'

/**
 * Strongest last is deliberate: `strongestBasis` reads right to left, so
 * adding a basis to this list is what decides its standing. `visited` is
 * NOT ranked above `published` - it answers a different question (where this
 * app's users sent something) and one it must never be read as answering
 * (where people hike).
 */
export const BASIS_STRENGTH: readonly string[] = [VISITED, NAMED, PUBLISHED]

export interface HighlightLeg {
  /** The trail this leg's miles are measured on - `AT` for the A.T. */
  trail: string
  startMile: number
  endMile: number
}

export interface HighlightCitation {
  /** "OurHike", or "Appalachian Trail Conservancy". */
  by: string
  /** One sentence on why it is on the list. May be empty. */
  note: string
  /** When a human last stood behind the row, `YYYY-MM-DD`. May be empty -
   *  and empty rather than today's date, which would be a claim nobody made. */
  reviewed: string
}

export interface Highlight {
  id: string
  name: string
  /** One or more, never blended. */
  bases: string[]
  citations: Record<string, HighlightCitation>
  legs: HighlightLeg[]
  /** The maintaining club the first leg starts in, or null where the club
   *  sections do not name one - the 38.5 unattributed miles. */
  club: string | null
  /**
   * A warning that the usual time estimate does not fit this ground (#851).
   *
   * Empty on every record published today - nothing sets it yet. It is here
   * because the problem is not hypothetical: Mahoosuc Arm is one of the ten
   * entries #856 published and is the climb out of Mahoosuc Notch, where
   * Naismith reads badly low. Carrying the field now means whichever way #851
   * is decided is a line on a sheet rather than a schema change.
   */
  caution: string
}

export const NO_HIGHLIGHTS: readonly Highlight[] = []

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function finite(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function text(value: unknown): string {
  return typeof value === 'string' ? value : ''
}

function parseLeg(value: unknown): HighlightLeg | null {
  if (!isRecord(value)) return null
  const trail = text(value.trail)
  const startMile = finite(value.start_mile)
  const endMile = finite(value.end_mile)
  if (trail === '' || startMile === null || endMile === null) return null
  // Normalised rather than trusted. The exporter already orders them, and a
  // backwards leg here would produce a negative length that quietly subtracts
  // from a multi-leg total.
  return {
    trail,
    startMile: Math.min(startMile, endMile),
    endMile: Math.max(startMile, endMile),
  }
}

function parseCitations(value: unknown): Record<string, HighlightCitation> {
  if (!isRecord(value)) return {}
  const out: Record<string, HighlightCitation> = {}
  for (const [basis, raw] of Object.entries(value)) {
    if (!isRecord(raw)) continue
    out[basis] = {
      by: text(raw.by),
      note: text(raw.note),
      reviewed: text(raw.reviewed),
    }
  }
  return out
}

function parseHighlight(value: unknown): Highlight | null {
  if (!isRecord(value)) return null
  const id = text(value.id)
  const name = text(value.name)
  if (id === '' || name === '') return null

  const legs = Array.isArray(value.legs)
    ? value.legs.map(parseLeg).filter((leg): leg is HighlightLeg => leg !== null)
    : []
  // A highlight with no placeable leg is nowhere. The exporter refuses to
  // publish one; this refuses to read one, so a hand-edited or half-written
  // artifact cannot put a nameless marker on the map.
  if (legs.length === 0) return null

  const bases = Array.isArray(value.bases)
    ? value.bases.filter(
        (basis): basis is string => typeof basis === 'string' && basis !== '',
      )
    : []
  if (bases.length === 0) return null

  return {
    id,
    name,
    bases,
    citations: parseCitations(value.citations),
    legs,
    club: typeof value.club === 'string' && value.club !== '' ? value.club : null,
    caution: text(value.caution),
  }
}

/**
 * Parses `highlights.json`.
 *
 * Never throws, and never loses the whole list over one bad row - the same
 * restraint lib/clubSections.ts applies, for the same reason: a corridor with
 * nine of ten highlights on it is worth more than an empty one.
 */
export function parseHighlights(raw: unknown): Highlight[] {
  const list = isRecord(raw) ? raw.highlights : raw
  if (!Array.isArray(list)) return []
  return list
    .map(parseHighlight)
    .filter((highlight): highlight is Highlight => highlight !== null)
}

/**
 * What came back from IndexedDB, or nothing when it is not the shape this
 * version stores.
 *
 * A named function rather than a cast, for the reason lib/clubSections.ts's
 * `storedClubSections` is one: the stored shape is the DOMAIN shape
 * (`startMile`) and the artifact's is not (`start_mile`), so running the
 * artifact parser over a stored value would silently yield an empty list that
 * looks exactly like a release publishing no highlights.
 */
export function storedHighlights(value: unknown): Highlight[] {
  if (!Array.isArray(value)) return []
  return value.filter(
    (entry): entry is Highlight =>
      isRecord(entry) && typeof entry.id === 'string' && Array.isArray(entry.legs),
  )
}

/**
 * The basis the app should cite, or null for a highlight carrying none it
 * knows.
 *
 * The whole of features/CORRIDOR_VIEW.md's "no blended score" rule as it
 * reaches a screen: one basis is shown, the strongest, and the others are not
 * shown beside it. Two citations on one card would read as corroboration -
 * two independent sources agreeing - when they are two different questions
 * with one answer between them.
 *
 * An unrecognised basis loses to every known one rather than winning by
 * accident: a release that adds a fourth should not silently outrank ATC.
 */
export function strongestBasis(highlight: Highlight): string | null {
  let best: string | null = null
  let bestRank = -1
  for (const basis of highlight.bases) {
    const rank = BASIS_STRENGTH.indexOf(basis)
    if (rank > bestRank) {
      bestRank = rank
      best = basis
    }
  }
  // -1 means nothing on the list was recognised. Naming one anyway would put
  // a citation on screen the app cannot word.
  return bestRank < 0 ? null : best
}

/** Total trail miles, summed across every leg. */
export function highlightMiles(highlight: Highlight): number {
  return highlight.legs.reduce((sum, leg) => sum + (leg.endMile - leg.startMile), 0)
}

/** The highlights whose first leg lies within a mile window, in mile order.
 *
 *  First leg, not any leg: a loop that leaves the A.T. and comes back is one
 *  place on the corridor, and a hiker panning past it should meet it once. */
export function highlightsWithin(
  highlights: readonly Highlight[],
  fromMile: number,
  toMile: number,
): Highlight[] {
  const low = Math.min(fromMile, toMile)
  const high = Math.max(fromMile, toMile)
  return highlights
    .filter((highlight) => {
      const leg = highlight.legs[0]
      return leg.startMile <= high && leg.endMile >= low
    })
    .sort((a, b) => a.legs[0].startMile - b.legs[0].startMile)
}
