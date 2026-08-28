// Who the map's data belongs to, as the phone holds it (#927).
//
// pipeline/export_sources.py publishes `stewards.json`: one record per
// organization whose data actually reaches a hiker, carrying what that
// organization's own registry entry records - the licence, the attribution,
// the trust tier - and nothing this app composed for them.
//
// Shaped on lib/clubSections.ts, which solved the same problem for the
// corridor's attribution: a small keyed artifact, parsed defensively, with an
// EMPTY value that is a real state rather than a failure. A release exported
// before export_sources.py existed simply has no steward list, and the section
// renders nothing - the same treatment club_sections.json and spurs.json get.
//
// EVERY FIELD BUT THE NAME IS INDEPENDENTLY ABSENT, and that is the registry's
// real state rather than defensive coding. Measured 2026-08-23 against the
// checked-in registry:
//
//   - the ATC has a licence ("© ATC, used with permission") and NO attribution
//     and NO trust tier;
//   - OpenStreetMap and the U.S. Drought Monitor have attributions and NO
//     licence, because neither resolves to one of the registry's short
//     `<x>_licence` blocks.
//
// So each line is omitted on its own, never placeholdered and never filled in
// from a sibling. A card that printed "Licence: unknown" would be this app
// making a claim about somebody else's terms.

/** One organization whose data is on this phone. Mirrors the record
 *  pipeline/export_sources.py writes, field for field. */
export interface Steward {
  /** The registry's provider key - `ATC`, `NYS OPRHP`. Stable, and what a
   *  future org record would join on. */
  provider: string
  /** The organization in full, as a hiker should read it. */
  name: string
  /** `authoritative` | `community`, and null when the registry's shipping
   *  entries do not agree on one. Never inferred - see the exporter. */
  trust: string | null
  /** The steward's recorded terms, verbatim. Null when the registry holds no
   *  short form. */
  licence: string | null
  /** What the licence obliges this app to say, verbatim. */
  attribution: string | null
  /** The titles of the layers of theirs that ship. Their words, not ours. */
  layers: readonly string[]
  /** The registry keys behind those layers - what a graph edge's `source` is.
   *  NOT index-aligned with `layers`; both are sorted independently. */
  keys: readonly string[]
}

export type Stewards = readonly Steward[]

/** No steward list. A release built before the exporter existed, or a phone
 *  that has downloaded nothing - both are ordinary, and neither is an error. */
export const EMPTY_STEWARDS: Stewards = []

function optionalString(value: unknown): string | null {
  return typeof value === 'string' && value.trim() !== '' ? value : null
}

function stringList(value: unknown): readonly string[] {
  if (!Array.isArray(value)) return []
  return value.filter(
    (entry): entry is string => typeof entry === 'string' && entry !== '',
  )
}

/**
 * The published artifact, read defensively.
 *
 * A record with no `name` is DROPPED rather than rendered as a nameless card:
 * the whole point of this screen is saying whose data this is, and a card that
 * cannot answer that has nothing to say. Everything else about it may be
 * missing and it still earns its place - "the ATC's data is here, under these
 * terms" is useful with no tier and no layer list.
 */
export function parseStewards(value: unknown): Stewards {
  const raw = (value as { stewards?: unknown } | null | undefined)?.stewards
  if (!Array.isArray(raw)) return EMPTY_STEWARDS

  const stewards: Steward[] = []
  for (const entry of raw) {
    const record = entry as Record<string, unknown> | null
    const name = optionalString(record?.name)
    if (name === null) continue

    stewards.push({
      provider: optionalString(record?.provider) ?? name,
      name,
      trust: optionalString(record?.trust),
      licence: optionalString(record?.licence),
      attribution: optionalString(record?.attribution),
      layers: stringList(record?.layers),
      keys: stringList(record?.keys),
    })
  }
  return stewards
}

/** What came out of the store, which is whatever was put in it however many
 *  releases ago. Re-parsed rather than cast, for the reason
 *  storedClubSections is: the shape on disk is only as good as the build that
 *  wrote it. */
export function storedStewards(value: unknown): Stewards {
  if (value === undefined || value === null) return EMPTY_STEWARDS
  // Already the parsed array (what this module put there), or the raw
  // artifact shape. Both are accepted so a store written by either path reads
  // back the same.
  if (Array.isArray(value)) return parseStewards({ stewards: value })
  return parseStewards(value)
}

/**
 * How many layers a steward ships, as a sentence, or null for none.
 *
 * A count and not a summary. The v2 wireframe's frame `1h` shows
 * "Centerline, shelters, closures · 12 layers", and the first half of that is
 * a human picking three layers out of eleven to stand for the rest. This app
 * has the titles and no basis for choosing among them, and a machine-picked
 * three would read exactly like an editorial summary somebody wrote.
 *
 * Saying so rather than leaving it: a per-steward one-line description is a
 * field features/SOURCE_REGISTRY.md's org record should carry and the registry
 * does not have yet (#929 builds the console that would collect it). Until
 * then the count is the true half.
 */
export function layerCountLine(steward: Steward): string | null {
  const count = steward.layers.length
  if (count === 0) return null
  return count === 1 ? '1 layer' : `${count} layers`
}

/**
 * A graph edge's `source` key, as the organization a hiker should read
 * (#978, frame `1j`'s live tally).
 *
 * Three answers, in honesty order:
 * - a steward claims the key: their `name`, their words;
 * - no steward claims it: the KEY itself, which is ugly and true - a raw
 *   `oprhp_trails` says "this app has a key it cannot name" where a prettied
 *   guess would say something nobody stands behind;
 * - null (an edge with no source at all): "Unattributed", which is not a
 *   claim about who maintains it but a statement that nothing does the
 *   claiming.
 */
/**
 * The published attributions, keyed the way lib/lineDetail.ts's
 * TrailSourceTable wants them: one entry per registry key, carrying the
 * steward's verbatim attribution (#1142).
 *
 * Derived from the same stewards artifact every credit surface reads, so the
 * tapped-line sheet and the sources screen cannot disagree about whose words
 * a layer ships under. No `edited` date rides along - stewards.json does not
 * carry per-layer edit dates, and the sheet's date clause simply stays silent
 * rather than this table inventing one.
 */
export function trailSourceTableFrom(
  stewards: Stewards,
): Readonly<Record<string, { attribution: string | null }>> {
  const table: Record<string, { attribution: string | null }> = {}
  for (const steward of stewards) {
    for (const key of steward.keys) {
      table[key] = { attribution: steward.attribution }
    }
  }
  return table
}

export function orgLabelFrom(stewards: Stewards): (source: string | null) => string {
  const byKey = new Map<string, string>()
  for (const steward of stewards) {
    for (const key of steward.keys) byKey.set(key, steward.name)
  }
  return (source) => {
    if (source === null) return 'Unattributed'
    return byKey.get(source) ?? source
  }
}

/**
 * A graph edge's or a notice's `source` key, as the organization's SHORT name.
 *
 * `orgLabelFrom`'s sibling, and the difference is the surface. That one
 * answers a card, where "New York-New Jersey Trail Conference" is what a hiker
 * should read. This one answers the header's single line, which a hiker reads
 * while walking - `pipeline/sources.json`'s `provider` is the registry's own
 * short form for exactly that ("ATC", "NYNJTC", "NYS OPRHP"), so the
 * abbreviation is the organization's rather than one this app shortened.
 *
 * Same three honesty tiers as `orgLabelFrom`, for the same reasons: the
 * provider where a steward claims the key, the raw key where none does, and
 * "Unattributed" for no key at all.
 */
export function orgProviderFrom(stewards: Stewards): (source: string | null) => string {
  const byKey = new Map<string, string>()
  for (const steward of stewards) {
    for (const key of steward.keys) byKey.set(key, steward.provider)
  }
  return (source) => {
    if (source === null) return 'Unattributed'
    return byKey.get(source) ?? source
  }
}
