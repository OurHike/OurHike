// Serious warnings (WIREFRAMES.md §8).
//
// `severity: serious` lives on the existing Report model and is set by a
// moderator, never self-declared - the client only ever reads it. A serious
// warning surfaces prominently in-app (a distinct pin, plus a banner when the
// map opens) and NEVER pushes. See lib/push.ts for where that rule is
// enforced rather than merely intended.

import { POI_PIN_SIZE } from '../map/poiIcons'
import { locateOnTrail, type TrailIndex } from './trailPosition'

export type WarningSeverity = 'normal' | 'serious'

export interface WarningReport {
  id: string
  type: string
  severity: WarningSeverity
  mile: number
}

/**
 * The report fields placing a warning needs — a structural subset of
 * `ReportSummary`, deliberately not an import of it.
 *
 * #244 asked that `WarningReport` end up derivable from what the backend
 * sends "by construction, not by hope". This is the construction: `placeAll`
 * below is the only way to build one, it takes this shape, and
 * `ReportSummary[]` is assignable to it — so the day the wire drops one of
 * these fields, the call site stops compiling instead of the banner quietly
 * counting nothing. Structural rather than imported so this module stays
 * testable without dragging in `import.meta.env` through `lib/api.ts`.
 */
export interface PlaceableReport {
  id: string
  type: string
  severity: WarningSeverity
  lat: number | null
  lon: number | null
  mile: number | null
}

/**
 * Every report that can be placed on the trail, as warnings with a mile.
 *
 * **Two sources for the mile, in this order, and the order is the point
 * (#244).**
 *
 * 1. This app's own snap of `lat`/`lon` onto the centerline, when it has
 *    both. Preferred because it is derived from the same index the hiker's
 *    own position is measured against, so "3 miles ahead" means the same
 *    thing on both sides of the comparison — and because it is current: a
 *    stored mile was measured against whatever centerline was published the
 *    day the report was filed, and relocations move those numbers.
 * 2. The mile the reporting phone recorded, when the snap cannot run. That
 *    is a report with a `poi_id` and no coordinates — which under the old
 *    lat/lon-only derivation could never appear on any hiker's banner at
 *    all, however serious a moderator had marked it.
 *
 * Reports that have neither are dropped rather than defaulted. Mile 0 is
 * Springer Mountain, and a warning filed at the wrong end of the trail is
 * worse than one that is missing: it is on somebody's banner, about a place
 * they are nowhere near.
 *
 * Severity is NOT filtered here — `warningsOnRoute` owns that, so the pins
 * and the banner cannot come to disagree about which reports are warnings.
 */
export function placeAll(
  reports: readonly PlaceableReport[],
  index: TrailIndex,
): WarningReport[] {
  return reports.flatMap((report) => {
    const snapped =
      report.lat === null || report.lon === null
        ? null
        : locateOnTrail(index, { lon: report.lon, lat: report.lat })

    const mile = snapped?.mile ?? report.mile
    if (mile === null) return []

    return [{ id: report.id, type: report.type, severity: report.severity, mile }]
  })
}

export interface RouteRange {
  fromMile: number
  toMile: number
}

/**
 * Whether a report is a serious warning at all.
 *
 * One line, and worth exporting anyway: the map draws these as pins and the
 * banner counts them along a route, and those two callers must never disagree
 * about which reports are warnings. The pin needs no mile - it goes at the
 * report's own lat/lon - so it cannot go through `warningsOnRoute` to inherit
 * the rule, and a second `=== 'serious'` written out at the call site is
 * exactly how a map full of pins ends up beside a banner that counts none of
 * them.
 */
export function isSeriousWarning(report: { severity: WarningSeverity }): boolean {
  return report.severity === 'serious'
}

export function warningsOnRoute(
  reports: WarningReport[],
  { fromMile, toMile }: RouteRange,
): WarningReport[] {
  // A southbound route runs backwards, so normalise rather than assuming
  // from < to.
  const low = Math.min(fromMile, toMile)
  const high = Math.max(fromMile, toMile)

  return reports.filter(
    (report) => isSeriousWarning(report) && report.mile >= low && report.mile <= high,
  )
}

/** Null for a clear route - there is no banner for good news. */
export function routeBannerText(count: number): string | null {
  if (count === 0) return null
  return `${count} serious warning${count === 1 ? '' : 's'} on your route`
}

// A variant inside the existing waypoint icon spec, not a new visual
// language: a warning that looks like nothing else on the map is a warning
// nobody has learned to read.
//
// `ordinaryPinPx` is IMPORTED rather than written down, and that is the whole
// reason this object is worth having. Held as its own literal it went stale
// silently - it said 17 while the pins on the map were drawn at 30, so the
// test below was comparing a warning pin against a number nothing rendered,
// and would have gone on passing when the pins grew past the warning itself.
// The rule this encodes ("the warning is the biggest thing on the map") is
// only a rule if it reads the real size.
export const WARNING_PIN = {
  /** One full touch target, and the ceiling every other pin stays under. */
  sizePx: 44,
  ordinaryPinPx: POI_PIN_SIZE,
  icon: 'triangle-alert',
  color: '#b2321f',
  halo: true,
} as const
