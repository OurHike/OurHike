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
  /**
   * The steward's terms in FULL, verbatim, where their registry block quotes
   * them - against `licence` above, which is the one-line form.
   *
   * IT IS HERE BECAUSE ONE STEWARD'S TERMS REQUIRE IT. NJDEP's Data
   * Distribution Agreement says their data "may not be reproduced or
   * redistributed without all the metadata provided" (condition 2, quoted
   * whole in pipeline/sources.json's `njdep_licence`), and a name plus a
   * one-line summary is not that. So the agreement travels with the lines and
   * is read where the lines are accounted for.
   *
   * Null for most stewards, and that is not a gap: a block that quotes its
   * terms whole has decided they are worth a hiker reading, and one that
   * records only a short form has not. Absent renders as nothing.
   */
  terms: string | null
  /** Where `terms` was read from, so a hiker or a club can check this app's
   *  copy against the steward's own. Null wherever `terms` is. */
  termsSource: string | null
  /** The titles of the layers of theirs that ship. Their words, not ours. */
  layers: readonly string[]
  /** The registry keys behind those layers - what a graph edge's `source` is.
   *  NOT index-aligned with `layers`; both are sorted independently. */
  keys: readonly string[]
  /**
   * How to support the organization, in its own words, or null where it has
   * not asked (#932). Null renders as nothing: no button, no empty section.
   * Absent means the organization has not asked for support, which is not
   * the same as an organization that wants none, and neither is a thing to
   * guess at on a hiker's screen.
   */
  support: StewardSupport | null
  /**
   * Where to buy the organization's paper maps, and which map covers what,
   * or null where none is recorded (#1574). Null renders as nothing, exactly
   * as `support` does.
   */
  store: StewardStore | null
}

/** pipeline/export_sources.py's `support` record, field for field. */
export interface StewardSupport {
  /** The organization's own page. Opens in their site; OurHike holds nothing. */
  donateUrl: string
  /** Their own button, verbatim - "Become a Member", "Donate Today". Never
   *  a house string: a trail conservancy and a state parks department do
   *  not ask in the same voice. */
  donateCta: string
  /** Who actually receives the money, where that is not the steward the
   *  card names - NYS OPRHP's link resolves to the Natural Heritage Trust,
   *  a separate 501(c)(3). A surface rendering the button MUST render this
   *  too, or it tells a hiker their money reaches an agency it does not. */
  donateRecipient: string | null
  /** The screens the organization granted the line on. Closed vocabulary
   *  on the pipeline side; a surface checks itself against it. */
  donateSurfaces: readonly string[]
}

/** One paper map product, as the reviewed table publishes it. */
export interface PaperMap {
  /** The store's product handle - its URL path, and the stable key. */
  handle: string
  /** The product's title, the organization's own words, printed verbatim. */
  title: string
  /** The product page, referral query included, exactly as published.
   *  Copied, never composed. */
  url: string
  /** The sheet numbers the product holds - "118", "106A". */
  sheets: readonly string[]
  /** Place names the organization's own product description names, where it
   *  names any. */
  covers: readonly string[]
  /** Per sheet, the parks and trails the organization lists on it, in its
   *  own spelling - what lib/paperMaps.ts joins a hike's park against. */
  sheetCovers: Readonly<Record<string, readonly string[]>>
}

/** pipeline/export_sources.py's `store` record, field for field. */
export interface StewardStore {
  /** The organization's own store page for its maps. */
  storeUrl: string
  /** Their own words for the link - "Trail Maps", read off their site. */
  storeCta: string
  /** The screens the organization granted the link on. A separate grant
   *  from `donateSurfaces`: buying a thing is not giving. */
  storeSurfaces: readonly string[]
  paperMaps: readonly PaperMap[]
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

/** A link the app may open: https, and nothing else. A support or store
 *  record carrying anything else is dropped whole rather than rendered with
 *  a dead button - the same refusal lib/atcNoticeText.ts's isSafeLink makes
 *  for a notice's link. */
function httpsUrl(value: unknown): string | null {
  const url = optionalString(value)
  return url !== null && url.startsWith('https://') ? url : null
}

/**
 * The support record, or null - whole or not at all. A record with a
 * destination and no button text, or no list of screens, is not a record
 * with fewer permissions; it is one whose permissions nobody wrote down, and
 * the pipeline refuses to publish that shape (export_sources.py). Refusing
 * it here too is what keeps an older artifact from rendering a button its
 * organization never granted a screen for.
 */
function parseSupport(value: unknown): StewardSupport | null {
  const record = value as Record<string, unknown> | null | undefined
  if (record === null || record === undefined || typeof record !== 'object') return null
  const donateUrl = httpsUrl(record.donate_url ?? record.donateUrl)
  const donateCta = optionalString(record.donate_cta ?? record.donateCta)
  const donateSurfaces = stringList(record.donate_surfaces ?? record.donateSurfaces)
  if (donateUrl === null || donateCta === null || donateSurfaces.length === 0) return null
  return {
    donateUrl,
    donateCta,
    donateRecipient: optionalString(record.donate_recipient ?? record.donateRecipient),
    donateSurfaces,
  }
}

function parsePaperMap(value: unknown): PaperMap | null {
  const record = value as Record<string, unknown> | null | undefined
  if (record === null || record === undefined || typeof record !== 'object') return null
  const handle = optionalString(record.handle)
  const title = optionalString(record.title)
  const url = httpsUrl(record.url)
  const sheets = stringList(record.sheets)
  if (handle === null || title === null || url === null || sheets.length === 0)
    return null
  const rawCovers = (record.sheet_covers ?? record.sheetCovers) as
    Record<string, unknown> | null | undefined
  const sheetCovers: Record<string, readonly string[]> = {}
  for (const sheet of sheets) {
    sheetCovers[sheet] = stringList(rawCovers?.[sheet])
  }
  return { handle, title, url, sheets, covers: stringList(record.covers), sheetCovers }
}

/** The store record, or null - the same whole-or-nothing rule as the
 *  support record. A product that does not parse costs that product and
 *  nothing else: the store link stands without it. */
function parseStore(value: unknown): StewardStore | null {
  const record = value as Record<string, unknown> | null | undefined
  if (record === null || record === undefined || typeof record !== 'object') return null
  const storeUrl = httpsUrl(record.store_url ?? record.storeUrl)
  const storeCta = optionalString(record.store_cta ?? record.storeCta)
  const storeSurfaces = stringList(record.store_surfaces ?? record.storeSurfaces)
  if (storeUrl === null || storeCta === null || storeSurfaces.length === 0) return null
  const rawMapsValue = record.paper_maps ?? record.paperMaps
  const rawMaps = Array.isArray(rawMapsValue) ? rawMapsValue : []
  const paperMaps = rawMaps
    .map(parsePaperMap)
    .filter((map): map is PaperMap => map !== null)
  return { storeUrl, storeCta, storeSurfaces, paperMaps }
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
      terms: optionalString(record?.terms),
      // Snake case on the wire, camel here - the exporter writes
      // `terms_source` beside `terms`. Both spellings are read, here and in
      // parseSupport, parsePaperMap and parseStore, because this parser also
      // reads back what trailData.ts stored, which is the parsed (camel) shape.
      // Reading snake case alone dropped termsSource (since v1.3.0) and
      // support and store (v1.3.2) on every relaunch that loaded from the
      // phone - found writing the v1.3.2 stored-shapes ledger (#1639).
      termsSource: optionalString(record?.terms_source ?? record?.termsSource),
      layers: stringList(record?.layers),
      keys: stringList(record?.keys),
      support: parseSupport(record?.support),
      store: parseStore(record?.store),
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

/**
 * An organization's name, made possessive: `the ATC` -> `the ATC’s`.
 *
 * Here rather than in the component that first needed it, because there are
 * two callers and were two implementations - NoticeList.tsx declared this
 * with a comment saying it was "one rule with one caller", while
 * OrgNoticeSheet.tsx inlined the same expression a few lines into its body.
 * Two copies of one rule is the state where they can disagree, and this one
 * is a rule about ENGLISH rather than about notices or sheets, so neither
 * component was ever its home.
 *
 * An organization whose name already ends in s takes the bare apostrophe.
 * None of the registered organizations does today; the branch is there so the
 * first one that registers does not read wrong.
 */
export function possessive(name: string): string {
  return name.endsWith('s') ? `${name}’` : `${name}’s`
}
