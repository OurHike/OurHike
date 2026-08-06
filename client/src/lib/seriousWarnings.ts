// Serious warnings (WIREFRAMES.md §8).
//
// `severity: serious` lives on the existing Report model and is set by a
// moderator, never self-declared - the client only ever reads it. A serious
// warning surfaces prominently in-app (a distinct pin, plus a banner when the
// map opens) and NEVER pushes. See lib/push.ts for where that rule is
// enforced rather than merely intended.

import { POI_PIN_SIZE } from '../map/poiIcons'

export type WarningSeverity = 'normal' | 'serious'

export interface WarningReport {
  id: string
  type: string
  severity: WarningSeverity
  mile: number
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
 * about which reports are warnings. The pin needs no mile - a report carries
 * lat/lon (#244) - so it cannot go through `warningsOnRoute` to inherit the
 * rule, and a second `=== 'serious'` written out at the call site is exactly
 * how a map full of pins ends up beside a banner that counts none of them.
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
