// Serious warnings (WIREFRAMES.md §8).
//
// `severity: serious` lives on the existing Report model and is set by a
// moderator, never self-declared - the client only ever reads it. A serious
// warning surfaces prominently in-app (a distinct pin, plus a banner when the
// map opens) and NEVER pushes. See lib/push.ts for where that rule is
// enforced rather than merely intended.

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

export function warningsOnRoute(
  reports: WarningReport[],
  { fromMile, toMile }: RouteRange,
): WarningReport[] {
  // A southbound route runs backwards, so normalise rather than assuming
  // from < to.
  const low = Math.min(fromMile, toMile)
  const high = Math.max(fromMile, toMile)

  return reports.filter(
    (report) =>
      report.severity === 'serious' && report.mile >= low && report.mile <= high,
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
export const WARNING_PIN = {
  sizePx: 34,
  ordinaryPinPx: 17,
  icon: 'triangle-alert',
  color: '#b2321f',
  halo: true,
} as const
