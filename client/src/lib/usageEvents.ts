// The phone's half of usage measurement (#1902, features/EVENTING.md §0).
//
// Six things are counted and nothing else: the app installed, a sign-in, a
// hike plan made, a hike plan completed, the map coming into view, and a
// session with the screens it showed. `USAGE_EVENTS` is the registry, and it
// is the same list the backend's `UsageEvent` holds - `POST /usage-events`
// refuses any other name, which is what stops "no free text" from being a
// rule everyone remembers until the afternoon somebody puts a trail name in
// an event key (EVENTING.md §3).
//
// Everything here is pure: what a row looks like, the heartbeat flags that
// let a phone count itself without an identifier, the session-length
// buckets, and how a plan is split across clubs. Storage and sending are
// lib/usageQueue.ts; the moments that record are lib/useUsageMeasurement.ts.
//
// WHAT A ROW NEVER CARRIES, AND WHY THAT IS ENFORCED HERE RATHER THAN HOPED
//
// No account id - the server takes the account from the token, and only when
// the hiker said yes (`linked`). No time of day - a date is all the monthly
// figures use, and a time beside a position is most of a movement trace. No
// text - a club is a closed-alphabet id (`clubId`), and `UsageRow` has no
// string field a sentence could ride in on except `app_version`, which the
// server checks against a pattern too.

export const USAGE_EVENTS = [
  'app_installed',
  'user_login',
  'hike_plan_made',
  'hike_plan_completed',
  'map_screen_viewed',
  'session',
] as const

export type UsageEventName = (typeof USAGE_EVENTS)[number]
export type UsagePlatform = 'ios' | 'android' | 'web'
export type SessionLength = 'under_1m' | 'm1_to_5' | 'm5_to_20' | 'over_20m'

/**
 * A stretch of A.T. whose club ATC's own centreline does not name - 38.5
 * miles, 1.90% of the corridor, measured by pipeline/export_club_sections.py
 * (#594). A club-shaped answer that says "not recorded" rather than guessing,
 * and not the same as no club at all, which is an event about no trail.
 */
export const CLUB_NOT_RECORDED = '_unrecorded'

/** The phone's GPS fix, as the map already held it. Sealed by the server. */
export interface UsageFix {
  lat: number
  lon: number
  accuracy_m?: number
}

/** One event, exactly as `POST /usage-events` takes it (app/schemas/analytics.py). */
export interface UsageRow {
  id: string
  event: UsageEventName
  local_date: string
  platform: UsagePlatform
  app_version?: string
  week_first: boolean
  month_first: boolean
  ever_first: boolean
  club_firsts: string[]
  clubs?: Record<string, number>
  miles?: number
  pageviews?: number
  session_length?: SessionLength
  fix?: UsageFix
}

/**
 * A row waiting to send, and whether it may be linked to the account.
 *
 * Decided when the row is RECORDED, not when it is sent: a hiker who said yes,
 * walked a week offline and said no on the way home has a week of rows that
 * were recorded under the yes - and the no applies from the moment it was
 * said. lib/usageQueue.ts drops linked rows that are still waiting when the
 * answer changes to no, so the yes does not outlive itself either.
 */
export interface QueuedUsageRow {
  row: UsageRow
  linked: boolean
}

/**
 * What the phone remembers so it can answer "first time this week / this
 * month / ever" without anybody else ever telling two phones apart
 * (EVENTING.md §2, MeasurementState in §10).
 */
export interface Heartbeat {
  /** ISO year and week of the last recorded event, `2026-W44`. */
  week: string | null
  /** Calendar month of the last recorded event, `2026-10`. */
  month: string | null
  /** Whether this install has recorded anything, ever. */
  ever: boolean
  /** The clubs already touched in `month`. */
  clubs: string[]
}

export const FRESH_HEARTBEAT: Heartbeat = {
  week: null,
  month: null,
  ever: false,
  clubs: [],
}

/**
 * A stretch of the A.T. and who maintains it - lib/clubSections.ts `ClubRun`,
 * narrowed to the two fields measurement reads, so this module stays a leaf.
 */
export interface ClubRunLike {
  startMile: number
  endMile: number
  club: { acronym: string } | null
}

// --- dates ----------------------------------------------------------------------

/** `2026-10-27` on the phone's own calendar - the hiker's day, not UTC's. */
export function usageDate(now: Date): string {
  const year = String(now.getFullYear()).padStart(4, '0')
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

/**
 * The ISO 8601 week a local date falls in, as `2026-W44`.
 *
 * ISO weeks start on Monday, so a Saturday-Sunday weekend hike lands inside
 * one week rather than straddling two (EVENTING.md §2).
 */
export function isoWeek(now: Date): string {
  const day = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const weekday = (day.getDay() + 6) % 7 // Monday 0 .. Sunday 6
  day.setDate(day.getDate() - weekday + 3) // the Thursday of this week decides its year
  const firstThursday = new Date(day.getFullYear(), 0, 4)
  const week =
    1 +
    Math.round(
      ((day.getTime() - firstThursday.getTime()) / 86_400_000 -
        3 +
        ((firstThursday.getDay() + 6) % 7)) /
        7,
    )
  return `${day.getFullYear()}-W${String(week).padStart(2, '0')}`
}

// --- the heartbeat ---------------------------------------------------------------

export interface HeartbeatStamp {
  week_first: boolean
  month_first: boolean
  ever_first: boolean
  club_firsts: string[]
}

/**
 * The flags one event carries, and the heartbeat after it.
 *
 * A phone active four days in a week records events on all four, and exactly
 * one of them says `week_first` - so the server's count of `week_first` rows
 * is a count of phones, with no phone ever told apart from another.
 */
export function stampHeartbeat(
  heartbeat: Heartbeat,
  now: Date,
  clubs: readonly string[],
): { stamp: HeartbeatStamp; next: Heartbeat } {
  const week = isoWeek(now)
  const month = usageDate(now).slice(0, 7)
  const sameMonth = heartbeat.month === month
  const seen = new Set(sameMonth ? heartbeat.clubs : [])
  const clubFirsts = clubs.filter((club) => !seen.has(club))
  for (const club of clubFirsts) seen.add(club)
  return {
    stamp: {
      week_first: heartbeat.week !== week,
      month_first: !sameMonth,
      ever_first: !heartbeat.ever,
      club_firsts: clubFirsts,
    },
    next: { week, month, ever: true, clubs: [...seen] },
  }
}

// --- sessions --------------------------------------------------------------------

/** A visit ends after this long out of sight, the common analytics convention. */
export const SESSION_IDLE_MS = 30 * 60 * 1000

/** A session's length in the four buckets the server stores (EVENTING.md §3's bucketing). */
export function sessionLength(ms: number): SessionLength {
  const minutes = ms / 60_000
  if (minutes < 1) return 'under_1m'
  if (minutes < 5) return 'm1_to_5'
  if (minutes < 20) return 'm5_to_20'
  return 'over_20m'
}

// --- the fix -----------------------------------------------------------------------

/**
 * Reasoned, not measured: a fix older than this describes where the phone
 * WAS, and a count stamped with it would say the hiker was somewhere they
 * have since left. Ten minutes is about half a mile of walking.
 */
export const FIX_MAX_AGE_MS = 10 * 60 * 1000

/**
 * @unvalidated - picked: a fix vaguer than this cannot say which trail the
 * phone was on, which is all the club attribution needs it for. What would
 * settle it is the accuracy distribution the GPS trace tool (#1180) records.
 */
export const FIX_MAX_ACCURACY_M = 100

export interface HeldFix {
  lat: number
  lon: number
  accuracy: number | null
  at: Date
}

/**
 * The fix to send with an event that happened at `now`, or none.
 *
 * Only a fix the map ALREADY HOLDS: measurement never switches location on,
 * and nothing here asks for a position. A hiker with location off sends no
 * fix at all.
 */
export function usableFix(held: HeldFix | null, now: Date): UsageFix | undefined {
  if (held === null) return undefined
  if (!Number.isFinite(held.lat) || !Number.isFinite(held.lon)) return undefined
  // A fix taken AFTER the moment being described does not describe it. A few
  // seconds the other way are allowed for a phone clock and a GPS clock that
  // disagree.
  const age = now.getTime() - held.at.getTime()
  if (age < -5_000 || age > FIX_MAX_AGE_MS) return undefined
  if (held.accuracy !== null && !(held.accuracy <= FIX_MAX_ACCURACY_M)) return undefined
  return held.accuracy === null
    ? { lat: held.lat, lon: held.lon }
    : { lat: held.lat, lon: held.lon, accuracy_m: Math.round(held.accuracy * 10) / 10 }
}

// --- clubs -------------------------------------------------------------------------

/**
 * A club's id as the server accepts it, or null.
 *
 * ATC's acronyms already fit (`NYNJTC`, `AMC-WMA`); this is the guarantee
 * that one which does not is dropped rather than refused - a refused batch
 * costs every row in it.
 */
export function clubId(acronym: string | null | undefined): string | null {
  if (acronym === null || acronym === undefined) return null
  const cleaned = acronym.replace(/[^A-Za-z0-9._-]/g, '').slice(0, 64)
  return /^[A-Za-z0-9]/.test(cleaned) ? cleaned : null
}

/** The club at one A.T. mile: its id, `CLUB_NOT_RECORDED`, or null off the corridor. */
export function clubAtTrailMile(
  timeline: readonly ClubRunLike[],
  mile: number,
): string | null {
  if (!Number.isFinite(mile)) return null
  for (let i = 0; i < timeline.length; i += 1) {
    const run = timeline[i]
    if (mile < run.startMile) return null
    const last = i === timeline.length - 1
    if (mile < run.endMile || (last && mile === run.endMile)) {
      return run.club === null ? CLUB_NOT_RECORDED : clubId(run.club.acronym)
    }
  }
  return null
}

/**
 * How a stretch of A.T. splits across clubs, in miles.
 *
 * "Assigned by # miles specific for each club" (the maintainer, poll
 * 2026-10-27, confirmed against a drawn example): each club gets the miles of
 * the plan that are on its trail. Direction does not matter - a southbound
 * plan covers the same miles.
 */
export function milesByClub(
  timeline: readonly ClubRunLike[],
  fromMile: number,
  toMile: number,
): Record<string, number> {
  const low = Math.min(fromMile, toMile)
  const high = Math.max(fromMile, toMile)
  const miles: Record<string, number> = {}
  if (!Number.isFinite(low) || !Number.isFinite(high) || high <= low) return miles
  for (const run of timeline) {
    const overlap = Math.min(high, run.endMile) - Math.max(low, run.startMile)
    if (overlap <= 0) continue
    const id = run.club === null ? CLUB_NOT_RECORDED : clubId(run.club.acronym)
    if (id === null) continue
    miles[id] = (miles[id] ?? 0) + overlap
  }
  return miles
}

/**
 * Club shares from miles: each club's miles over the total, summing to one.
 *
 * Rounded to four places and the last club given the remainder, so the shares
 * sum to exactly one however the miles divide - the server allows a little
 * slack (app/schemas/analytics.py `SHARE_TOLERANCE`) and this does not lean on it.
 */
export function sharesFromMiles(
  miles: Record<string, number>,
): Record<string, number> | undefined {
  const entries = Object.entries(miles).filter(([, value]) => value > 0)
  const total = entries.reduce((sum, [, value]) => sum + value, 0)
  if (entries.length === 0 || !(total > 0)) return undefined
  entries.sort(([, a], [, b]) => b - a)
  const kept = entries.slice(0, 12)
  const keptTotal = kept.reduce((sum, [, value]) => sum + value, 0)
  const shares: Record<string, number> = {}
  let assigned = 0
  kept.forEach(([club, value], index) => {
    if (index === kept.length - 1) {
      shares[club] = Math.round((1 - assigned) * 10_000) / 10_000
    } else {
      const share = Math.round((value / keptTotal) * 10_000) / 10_000
      shares[club] = share
      assigned += share
    }
  })
  return shares
}

// --- the row ---------------------------------------------------------------------------

/** The version string the server accepts, or none. */
export function usageVersion(version: string): string | undefined {
  return /^[0-9A-Za-z][0-9A-Za-z.+_-]{0,39}$/.test(version) ? version : undefined
}

export interface UsageDetails {
  clubs?: Record<string, number>
  miles?: number
  pageviews?: number
  session_length?: SessionLength
  fix?: UsageFix
}

/** One row, stamped with the heartbeat flags `stampHeartbeat` worked out for it. */
export function usageRow(options: {
  id: string
  event: UsageEventName
  now: Date
  platform: UsagePlatform
  version: string
  stamp: HeartbeatStamp
  details: UsageDetails
}): UsageRow {
  const { details } = options
  const row: UsageRow = {
    id: options.id,
    event: options.event,
    local_date: usageDate(options.now),
    platform: options.platform,
    week_first: options.stamp.week_first,
    month_first: options.stamp.month_first,
    ever_first: options.stamp.ever_first,
    club_firsts: options.stamp.club_firsts,
  }
  const version = usageVersion(options.version)
  if (version !== undefined) row.app_version = version
  if (details.clubs !== undefined) row.clubs = details.clubs
  if (
    details.miles !== undefined &&
    Number.isFinite(details.miles) &&
    details.miles >= 0
  ) {
    row.miles = Math.round(Math.min(details.miles, 5000) * 10) / 10
  }
  if (details.pageviews !== undefined)
    row.pageviews = Math.max(0, Math.min(10_000, Math.round(details.pageviews)))
  if (details.session_length !== undefined) row.session_length = details.session_length
  if (details.fix !== undefined) row.fix = details.fix
  return row
}
