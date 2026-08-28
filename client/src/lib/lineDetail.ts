// What the line-detail sheet says about the line a hiker tapped (#134).
//
// WIREFRAMES.md §3's blaze rules are the requirement: "tapping any line
// opens a sheet naming the blaze and its source, and says plainly when it's
// unknown." For a spur, features/SPUR_TRAILS.md §3 adds the facts the sheet
// exists for - where it goes, how far there and back, and where it joins
// the AT:
//
//   Blue blaze · spur
//   To Rocky Run Shelter — 0.2 mi each way
//   ≈20m there and back
//   Joins the AT at mi 1,043.2
//
// Built here rather than in the component for the same reason PoiCard's
// detail is resolved in the shell: the map knows what is drawn, and the app
// is what knows a line's spur record, its destination's name and the units
// the hiker chose. Everything the sheet renders is a string decided in this
// file, so the decisions are testable without a canvas.
//
// Three decisions carried over from #111 rather than relitigated (the
// issue's own list):
// - NO destination line at all when nothing resolved - not "Unknown
//   destination", which reads as a data error rather than the ordinary
//   situation it is for ~12% of spurs.
// - NO length threshold at either end. The median spur is 385 ft and the
//   longest 4.53 miles; suppressing either end's numbers buys nothing.
// - The round trip is ONE figure, not two legs - splitting it needs the
//   spur's own elevation profile, which does not exist.

import { blazeLabel } from './blaze'
import { describeSpur, type SpurRecord } from './spurDestination'
import { STANDARD_PACE, type PaceProfile } from './pace'
import type { StoredPoi } from './trailData'
import { formatDistance } from './units'
import type { UnitSystem } from './units'

/** The tapped feature's published properties, as map/lineTaps.ts reports
 *  them. Redeclared here rather than imported so this module stays free of
 *  the map layer - the same direction poiTaps keeps. */
export interface TappedLineFacts {
  id: string | null
  source: string | null
  name: string | null
  blazeColor: string | null
  /**
   * The facts a NEARBY trail's sheet needs and an A.T. line has never
   * carried (#783, features/NEARBY_TRAILS.md §2): how long it is, which park
   * it is in, and whether its steward marks it closed long-term.
   *
   * All optional, and every one of them independently absent: these arrive on
   * a network artifact that does not publish yet (#771's spike is what the
   * client reads until the licence answers land, #768/#769), so a build with
   * only the A.T. downloaded has none of them and must render exactly as it
   * did before. Each missing fact costs its own line, never the sheet.
   */
  lengthMiles?: number | null
  park?: string | null
  /** The steward's own status value, normalized by the pipeline. Only
   *  `Closed` renders - §3 is explicit that `Proposed` and blank/Unknown do
   *  not ship at all, so a value arriving here that is neither is a fact the
   *  sheet has nothing to say about rather than one it should paraphrase. */
  trailStatus?: string | null
  /**
   * Which kind of closed (#1142, NEARBY_TRAILS.md §3): `long_term` for a
   * steward's own trail status, `area` for a stretch derived from a
   * temporary closure polygon. `trail_status` alone cannot tell them apart -
   * both ship as `closed` - and the two owe a hiker different sentences.
   * Absent on an artifact published before #964 split the feeds, where the
   * long-term voice was the only voice there was.
   */
  closureKind?: string | null
  /** The closing organization's reason, verbatim, where they gave one -
   *  OPRHP's "Closed Until 2027" is prose in this field, not a date field
   *  the pipeline could parse, and it ships unparaphrased (§3). */
  closureReason?: string | null
  /** The registry key of the CLOSURE's own layer (`oprhp_trail_closures`) -
   *  not the trail line's source, which is whoever drew the line the
   *  closure landed on. The distinction is #1142's whole finding: a closure
   *  polygon crossing another org's trail must not be read in that org's
   *  name. */
  closureSource?: string | null
}

export interface LineDetail {
  /** "Blue blaze · spur", "White blaze · Appalachian Trail", "Blaze not
   *  recorded · side trail" - the sheet's heading. */
  heading: string
  /** ATC's own name for the line, where they gave one. */
  name: string | null
  /** "To Rocky Run Shelter — 0.2 mi each way", or the distance alone when
   *  no destination was confidently resolved, or null with no length. */
  destinationLine: string | null
  /** "≈20m there and back", or null with no length. */
  roundTripLine: string | null
  /** "Joins the AT at mi 1,043.2", or null when the pipeline could not
   *  tell the spur's ends apart or the release predates the field (#136). */
  junctionLine: string | null
  /** "From the Appalachian Trail Conservancy’s …" - the provenance line,
   *  same shape as PoiCard's. */
  sourceLine: string | null
  /** "24.0 mi · Harriman State Park" - §2's length and park, on one line
   *  because they answer one question (what and where this trail is), and
   *  collapsing to whichever half is known when the other is not. */
  extentLine: string | null
  /** §3's closure sentence, kept in the SHEET rather than in the line, which
   *  is where the whole distinction lives: the taped band on the map says
   *  "do not walk this" for both kinds, and only the sheet says which kind
   *  it is. A long-term steward status reads "Closed by <steward> · layer
   *  edited <day>"; a stretch inside a temporary closure area reads
   *  "Temporarily closed by <closing org> · <their reason, verbatim>" with
   *  no date, because the closure layer publishes none per feature and the
   *  pipeline invents nothing (export_nearby_trails.apply_area_closures).
   *  Null for every trail not marked closed. (This comment used to claim
   *  temporary closures never reached this line at all - false since #964's
   *  area-derived records, which is #1142.) */
  closureLine: string | null
  /** "Not the trail you chose. Switching happens in the picker." - §2's
   *  refusal, said rather than implied. Null on the chosen trail's own lines,
   *  where there is nothing to refuse. */
  switchNote: string | null
}

/**
 * Sources drawn at the through-route width (map/style.ts's
 * PRIMARY_TRAIL_SOURCES). Restated rather than imported for the reason
 * TappedLineFacts is: this module must not pull the map style in. The two
 * lists are pinned to each other by lineDetail.test.ts.
 */
export const THROUGH_ROUTE_SOURCES: readonly string[] = ['centerline']

/**
 * The sources making up the trail system a hiker chose - map/nearbyTrails.ts's
 * CHOSEN_SYSTEM_SOURCES, restated for the reason THROUGH_ROUTE_SOURCES above
 * is: this module must not pull the map layer in. lineDetail.test.ts imports
 * both and fails if they drift.
 *
 * What it decides HERE is narrower than what it decides on the map: not how a
 * line is painted, only whether the sheet owes a hiker the sentence explaining
 * that tapping this trail will not switch to it.
 */
export const CHOSEN_SYSTEM_SOURCES: readonly string[] = ['centerline', 'side_trails']

/**
 * One registered source's own words about itself, as the pipeline publishes
 * them from `pipeline/sources.json`.
 *
 * NEARBY_TRAILS.md §6 is the requirement and it is a prohibition as much as a
 * shape: the provenance wording "ships from the pipeline's per-source
 * attribution fields (sources.json), NEVER hardcoded". The two A.T. feeds
 * below are hardcoded, which was fine while every line on the map was ATC's
 * and stops being fine the moment a second steward's trails draw - a table in
 * this file would be a copy of somebody else's licence text, going stale
 * silently, in a client that ships offline for months at a time.
 *
 * Shaped on lib/clubSections.ts's `sources`/`sourceEdited` pair, which solved
 * this once already for the corridor's attribution.
 */
export interface TrailSourceRecord {
  /** The steward's required attribution string, verbatim - `attribution` in
   *  sources.json. Verbatim matters: it is a licence condition, not a label
   *  this app gets to phrase. */
  attribution: string | null
  /** ISO day the layer itself was last edited (ArcGIS `dataLastEditDate`),
   *  which is the freshness §3 wants beside a long-term closure. */
  edited?: string | null
}

/** Per-source attribution, keyed by the pipeline's own source key. */
export type TrailSourceTable = Readonly<Record<string, TrailSourceRecord>>

/**
 * Where the line's data comes from, in the words the waypoint card already
 * uses for its sources.
 *
 * The two ATC feeds keep their written-out phrasing - they are this app's own
 * long-standing wording for the trail it was built around, they read better
 * than ATC's bare attribution string, and PoiCard says the same thing the same
 * way. Everything else reads its steward's own attribution out of the
 * published table, per §6.
 *
 * An unfamiliar source with no table entry shows its raw id rather than
 * nothing - the same call sourceLabel() makes, for the same reason: a raw id
 * is a poor label and still tells someone more than silence does.
 */
function lineSourceLabel(
  source: string | null,
  sources: TrailSourceTable,
): string | null {
  if (source === null) return null
  if (source === 'centerline')
    return 'the Appalachian Trail Conservancy’s trail centerline'
  if (source === 'side_trails')
    return 'the Appalachian Trail Conservancy’s side trails data'
  const attribution = sources[source]?.attribution ?? null
  return attribution !== null && attribution.trim() !== '' ? attribution : source
}

/**
 * An ISO day as "4 Aug 2026", or null for anything unparseable.
 *
 * Deliberately not relative ("edited 3 weeks ago"): this phone may have been
 * offline for a month, so a relative age computed against its own clock would
 * drift away from the truth exactly when a hiker is furthest from checking it.
 * WIREFRAMES.md §11's staleness wording has the same reasoning.
 */
function formatEditedDay(iso: string | null | undefined): string | null {
  if (iso === null || iso === undefined || iso.trim() === '') return null
  const parsed = new Date(iso)
  if (Number.isNaN(parsed.getTime())) return null
  return parsed.toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    timeZone: 'UTC',
  })
}

/**
 * The steward's status value, and whether it means "closed long-term".
 *
 * Compared case-insensitively against the one value §3 admits. Everything else
 * - `Proposed`, blank, `Unknown`, anything new the layer starts publishing -
 * returns false and gets no line, which is the omit-rather-than-guess rule:
 * the pipeline is what decides a segment ships at all, and a status this
 * client does not recognise is not a claim it should paraphrase.
 */
function isLongTermClosed(status: string | null | undefined): boolean {
  return typeof status === 'string' && status.trim().toLowerCase() === 'closed'
}

/** A mile marker, grouped with one decimal - the same rendering PoiCard and
 *  the position line give a mile, so three surfaces show one number. Mile
 *  markers do not convert (lib/units.ts's opening rule): `mi 1,043.2` is a
 *  shared coordinate, not a distance. */
function formatMileMarker(mile: number): string {
  return mile.toLocaleString('en-US', {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })
}

/**
 * Everything the sheet can say about one tapped line.
 *
 * Every field is independently nullable because the underlying facts are
 * independently missing, and each absent fact costs its own line rather
 * than the sheet - the same shape describeSpur() keeps.
 */
export function buildLineDetail(
  line: TappedLineFacts,
  spurs: Record<string, SpurRecord>,
  pois: readonly StoredPoi[],
  units: UnitSystem = 'imperial',
  trailName = 'Appalachian Trail',
  /** The hiker's own pace (#880), so a spur's round trip is measured the same
   *  way as every other estimate rather than quoting a generic walker's. */
  pace: PaceProfile = STANDARD_PACE,
  /** Per-source attribution as published (§6). Defaults to empty, which is
   *  what an A.T.-only release has and what every existing caller passes by
   *  omission - the two ATC feeds are named without it. */
  sources: TrailSourceTable = {},
): LineDetail {
  const throughRoute = line.source !== null && THROUGH_ROUTE_SOURCES.includes(line.source)
  // Whether this line belongs to somebody else's network - the same question
  // map/nearbyTrails.ts asks to decide the ghosting, restated here rather than
  // imported so this module stays free of the map layer (the direction
  // TappedLineFacts and THROUGH_ROUTE_SOURCES already keep). lineDetail.test.ts
  // pins the two lists to each other.
  const nearbyTrail = line.source !== null && !CHOSEN_SYSTEM_SOURCES.includes(line.source)
  const spur = line.id !== null ? spurs[line.id] : undefined

  // The kind, for the heading: the through-route is named as the trail it
  // is; a side trail with a spur record is what SPUR_TRAILS.md calls a
  // spur; the rest are side trails - Access approaches, alternate routes -
  // that ATC classifies as something else.
  const kind = throughRoute ? trailName : spur !== undefined ? 'spur' : 'side trail'

  const detail = describeSpur(spur, units, undefined, pace)
  const destination =
    detail.destinationPoiId === null
      ? undefined
      : pois.find((poi) => poi.id === detail.destinationPoiId)

  // "To X — 0.2 mi each way" only when a destination was confidently
  // resolved AND this phone's POI store can actually name it - a release
  // downloaded before the destination's layer shipped has the id and not
  // the name, and "To atc_shelters:abc-123" is worse than the distance
  // alone.
  const destinationLine =
    detail.distanceLabel === null
      ? null
      : destination === undefined
        ? detail.distanceLabel
        : `To ${destination.name} — ${detail.distanceLabel}`

  const junctionMile = spur?.junction_mile
  const junctionLine =
    typeof junctionMile === 'number' && Number.isFinite(junctionMile)
      ? `Joins the AT at mi ${formatMileMarker(junctionMile)}`
      : null

  const source = lineSourceLabel(line.source, sources)

  // §2's length and park, on one line. Either half stands alone: OPRHP
  // publishes a `Miles` value on every segment and a `Unit` on most, so a
  // trail with a length and no park is the ordinary case rather than an
  // error, and "24.0 mi · " with nothing after it would read as one.
  const lengthLabel =
    typeof line.lengthMiles === 'number' &&
    Number.isFinite(line.lengthMiles) &&
    line.lengthMiles > 0
      ? formatDistance(line.lengthMiles, units)
      : null
  const park =
    line.park !== null && line.park !== undefined && line.park.trim() !== ''
      ? line.park.trim()
      : null
  const extentLine =
    lengthLabel === null && park === null
      ? null
      : [lengthLabel, park].filter((part) => part !== null).join(' · ')

  // §3: the closure, in the voice of whoever actually closed it (#1142).
  //
  // Two kinds ship under one `trail_status` and they part ways here. A
  // LONG-TERM closure is the trail steward's own status on their own line, so
  // its sentence is theirs: their attribution, their layer's edit date. An
  // AREA closure is a temporary polygon laid over ground - possibly over
  // another organization's line - so its sentence belongs to the CLOSING org
  // (`closure_source`), carries their reason verbatim, and shows no date at
  // all: the closure layer publishes none per feature, the pipeline invents
  // nothing, and the trail LINE's edit date - what this sentence used to show
  // - is a fact about the wrong layer wearing a freshness it never had.
  //
  // Attribution comes from the same published table the provenance line
  // uses, so the two cannot disagree about who said what. With no table
  // entry the by-clause drops rather than inventing an authority - and
  // unlike lineSourceLabel's raw-key fallback, a bare registry key is never
  // printed in the authority slot of a safety sentence: "From
  // oprhp_trails." names a dataset poorly; "Closed by oprhp_trail_closures"
  // reads as a malfunction on the one line a hiker is meant to obey.
  const closureLine = (() => {
    if (!isLongTermClosed(line.trailStatus)) return null
    const attributionOf = (key: string | null | undefined): string | null => {
      const attribution =
        key === null || key === undefined ? null : (sources[key]?.attribution ?? null)
      return attribution !== null && attribution.trim() !== '' ? attribution : null
    }

    if (line.closureKind === 'area') {
      const steward = attributionOf(line.closureSource)
      const who =
        steward === null ? 'Temporarily closed' : `Temporarily closed by ${steward}`
      const reason =
        typeof line.closureReason === 'string' && line.closureReason.trim() !== ''
          ? line.closureReason.trim()
          : null
      return reason === null ? who : `${who} · ${reason}`
    }

    // `long_term`, and - the same sentence - a record with no kind at all:
    // an artifact from before #964 split the feeds carried only this voice,
    // and reading its closures in it is what that build meant.
    const record = line.source === null ? undefined : sources[line.source]
    const steward = attributionOf(line.source)
    const day = formatEditedDay(record?.edited)
    const who = steward === null ? 'Closed' : `Closed by ${steward}`
    return day === null ? who : `${who} · layer edited ${day}`
  })()

  return {
    heading: `${blazeLabel(line.blazeColor)} · ${kind}`,
    // The through-route's name is already the heading; repeating ATC's
    // formal name under it ("Appalachian National Scenic Trail") would be
    // the same fact twice in adjacent lines.
    name: throughRoute ? null : (spur?.name ?? line.name),
    destinationLine,
    roundTripLine: detail.roundTripLabel,
    junctionLine,
    sourceLine: source === null ? null : `From ${source}.`,
    extentLine,
    closureLine,
    // §2's refusal, and the sheet is where it is SAID rather than merely
    // enacted. The argument, from the doc: making a nearby trail the chosen
    // one swaps the mile frame, the elevation ribbon, the Naismith numbers and
    // the amenity POI set at once - at 263 junctions per park, a one-tap
    // switch is an accidental context loss waiting to happen, in exactly the
    // moment a wrong screen costs the most. A hiker who taps a trail wanting
    // to walk it is owed the reason they cannot do it here, not a sheet that
    // silently lacks the button. Where switching DOES live is named, because
    // "not here" without "there" is the half of the sentence that helps.
    switchNote: nearbyTrail
      ? 'Not the trail you chose. Switching happens in the picker.'
      : null,
  }
}
