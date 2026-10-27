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
  /** The first event of this kind on this phone this month. */
  kind_month_first: boolean
  /** On a `month_first` row: this phone was counted last month too. */
  month_returning: boolean
  /** An account was signed in on this phone - never which one. */
  signed_in: boolean
  clubs?: Record<string, number>
  miles?: number
  pageviews?: number
  session_length?: SessionLength
  fix?: UsageFix
}

/**
 * A row waiting to send, and which account it may be linked to.
 *
 * `linkedTo` is lib/accountTag.ts's tag of the account that was signed in, with the
 * hiker's yes, when the row was RECORDED - or null. lib/usageQueue.ts sends a
 * row linked only while that same account is signed in with its yes still
 * standing; every other row goes without an account. So a phone shared by
 * two hikers cannot send one's rows with the other's token, a sign-out sends
 * what was waiting unlinked rather than losing it, and a no said on the way
 * home applies to the week of rows still waiting (`unlinkWaitingRows`).
 */
export interface QueuedUsageRow {
  row: UsageRow
  linkedTo: string | null
}

/**
 * What the phone remembers so it can answer "first time this week / this
 * month / ever" without anybody else ever telling two phones apart
 * (EVENTING.md §2, MeasurementState in §10).
 *
 * SETS OF PERIODS, NOT THE LAST ONE. A session row is dated when the visit
 * began and recorded when it ended, so rows do not arrive in date order: a
 * visit from Sunday night is recorded after Monday's first row. Remembering
 * only the last week made that Sunday row "first this week" a second time,
 * and the next Monday row a second time too - two phones where there was one,
 * in ordinary use and not only when a clock was wrong. 400 seeded synthetic
 * histories with clock steps switched off counted 1,458 of 2,243 phone-months
 * more than once before this (usageHeartbeat.test.ts, 2026-10-27; the
 * generator is harsher than real use, and the real rate was never measured).
 */
export interface Heartbeat {
  /** ISO weeks this phone has been counted in, `2026-W44`, oldest first. */
  weeks: string[]
  /** Calendar months this phone has been counted in, `2026-10`, oldest first. */
  months: string[]
  /** Whether this install has recorded anything, ever. */
  ever: boolean
  /** The clubs already counted, for each remembered month. */
  clubs: Record<string, string[]>
  /** The event kinds already counted, for each remembered month. */
  kinds: Record<string, string[]>
}

/**
 * How many weeks and months are remembered. Reasoned: a row is dated at
 * most a visit's length before the row recorded ahead of it, plus whatever a
 * phone's clock does, so ten weeks and four months leave room for a clock
 * that jumps a fortnight. A row older than everything remembered cannot be
 * told apart from one already counted, and is treated as counted - an
 * undercount by one phone, never a double count.
 */
export const WEEKS_REMEMBERED = 10
export const MONTHS_REMEMBERED = 4

export const FRESH_HEARTBEAT: Heartbeat = {
  weeks: [],
  months: [],
  ever: false,
  clubs: {},
  kinds: {},
}

function strings(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === 'string')
    : []
}

function stringLists(value: unknown): Record<string, string[]> {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) return {}
  return Object.fromEntries(
    Object.entries(value as Record<string, unknown>).map(([key, list]) => [
      key,
      strings(list),
    ]),
  )
}

/**
 * A heartbeat read back from storage, whatever wrote it. An earlier build of
 * this branch stored only the last week and month; those become one-entry
 * sets, which is exactly what they knew.
 */
export function normaliseHeartbeat(raw: unknown): Heartbeat {
  if (typeof raw !== 'object' || raw === null) return FRESH_HEARTBEAT
  const stored = raw as Record<string, unknown>
  const legacyMonth = typeof stored.month === 'string' ? stored.month : null
  return {
    weeks: Array.isArray(stored.weeks)
      ? strings(stored.weeks).sort()
      : typeof stored.week === 'string'
        ? [stored.week]
        : [],
    months: Array.isArray(stored.months)
      ? strings(stored.months).sort()
      : legacyMonth === null
        ? []
        : [legacyMonth],
    ever: stored.ever === true,
    clubs:
      Array.isArray(stored.clubs) && legacyMonth !== null
        ? { [legacyMonth]: strings(stored.clubs) }
        : stringLists(stored.clubs),
    kinds: stringLists(stored.kinds),
  }
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
  kind_month_first: boolean
  month_returning: boolean
}

/**
 * Whether a period is new to a remembered set. A full set has forgotten
 * whatever came before its oldest entry, so a period older than that is
 * unknown - and unknown counts as already counted.
 */
function isNew(seen: readonly string[], period: string, cap: number): boolean {
  if (seen.includes(period)) return false
  return seen.length < cap || period > seen[0]
}

/** `seen` with `period` added, sorted, keeping the newest `cap`. */
function remember(seen: readonly string[], period: string, cap: number): string[] {
  if (seen.includes(period)) return [...seen]
  const next = [...seen, period].sort()
  return next.length > cap ? next.slice(next.length - cap) : next
}

/** `2026-01` -> `2025-12`. */
export function previousMonth(month: string): string {
  const [year, number] = month.split('-').map(Number)
  return number === 1
    ? `${String(year - 1).padStart(4, '0')}-12`
    : `${String(year).padStart(4, '0')}-${String(number - 1).padStart(2, '0')}`
}

/**
 * The flags one event carries, and the heartbeat after it.
 *
 * A phone active four days in a week records events on all four, and exactly
 * one of them says `week_first` - so the server's count of `week_first` rows
 * is a count of phones, with no phone ever told apart from another. The same
 * holds per month, per club per month, and per kind of event per month
 * (`kind_month_first`: phones that made a plan this month, every phone and
 * not only hikers who linked an account). `month_returning` rides on the
 * `month_first` row and says the phone was counted last month too, which is
 * the whole of what new / returning / back-again needs.
 */
export function stampHeartbeat(
  heartbeat: Heartbeat,
  now: Date,
  clubs: readonly string[],
  kind: UsageEventName,
): { stamp: HeartbeatStamp; next: Heartbeat } {
  const week = isoWeek(now)
  const month = usageDate(now).slice(0, 7)
  const monthFirst = isNew(heartbeat.months, month, MONTHS_REMEMBERED)
  // A month older than everything remembered: its clubs and kinds are as
  // unknown as the month itself, so nothing about it is first either.
  const forgotten = !monthFirst && !heartbeat.months.includes(month)

  const seenClubs = heartbeat.clubs[month] ?? []
  const clubFirsts = forgotten
    ? []
    : [...new Set(clubs)].filter((club) => !seenClubs.includes(club))
  const seenKinds = heartbeat.kinds[month] ?? []
  const kindFirst = !forgotten && !seenKinds.includes(kind)

  const months = forgotten
    ? heartbeat.months
    : remember(heartbeat.months, month, MONTHS_REMEMBERED)
  const kept = (lists: Record<string, string[]>, current: string[]) => {
    const all = forgotten ? lists : { ...lists, [month]: current }
    return Object.fromEntries(months.filter((m) => m in all).map((m) => [m, all[m]]))
  }

  return {
    stamp: {
      week_first: isNew(heartbeat.weeks, week, WEEKS_REMEMBERED),
      month_first: monthFirst,
      ever_first: !heartbeat.ever,
      club_firsts: clubFirsts,
      kind_month_first: kindFirst,
      month_returning: monthFirst && heartbeat.months.includes(previousMonth(month)),
    },
    next: {
      weeks: remember(heartbeat.weeks, week, WEEKS_REMEMBERED),
      months,
      ever: true,
      clubs: kept(heartbeat.clubs, [...seenClubs, ...clubFirsts]),
      kinds: kept(heartbeat.kinds, kindFirst ? [...seenKinds, kind] : [...seenKinds]),
    },
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
  signedIn: boolean
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
    kind_month_first: options.stamp.kind_month_first,
    month_returning: options.stamp.month_returning,
    signed_in: options.signedIn,
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
