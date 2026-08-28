// Self-logged volunteer hours: the wire shapes, the display rules the
// 2026-08-20 decision sets, and the export that keeps the record the
// hiker's own (features/VOLUNTEERING.md §4-5, #761).
//
// The dashboard this feeds is a LOGBOOK, not a scoreboard, and the four
// rules from VOLUNTEERING.md §5 are enforced by what this module refuses to
// compute: nothing comparative (no averages, no percentiles, nothing about
// anyone else), no lack-state (no streaks, no "since June", no targets),
// and no composite score - hours are hours, days are days, and no formula
// folds them into a number to maximise.

import type { WorkProjectSummary } from './workProjects'

export const HOURS_ACTIVITIES = [
  'maintenance',
  'cleanup',
  'monitoring',
  'education',
  'admin',
  'other',
] as const

export type HoursActivity = (typeof HOURS_ACTIVITIES)[number]

export const ACTIVITY_LABELS: Record<HoursActivity, string> = {
  maintenance: 'Trail maintenance',
  cleanup: 'Clean-up / pack-out',
  monitoring: 'Monitoring',
  education: 'Education / outreach',
  admin: 'Club admin',
  other: 'Other',
}

/**
 * NYNJTC's own volunteer-hours form — a link out, never a data connection
 * (#1154). This logbook stays OurHike's own, exactly as designed above; a
 * hiker who also needs the day on NYNJTC's books follows this link and signs
 * into NYNJTC's own account on NYNJTC's own page. OurHike never sees that
 * password.
 *
 * No query-string prefill: fetched anonymously 2026-08-28, the form sits
 * behind NYNJTC's own login ("You must login or register to view this
 * form"), so whether their Drupal Webform even accepts prepopulation, and
 * under what field names, cannot be confirmed without an NYNJTC account.
 * Left unimplemented rather than guessed at.
 */
export const NYNJTC_HOURS_FORM_URL =
  'https://secure.nynjtc.org/webform/individual-trail-volunteer-report-form'

export type HoursState = 'claimed' | 'confirmed' | 'disputed'

/** What the outbox queues - field names match POST /volunteer-hours
 *  exactly, the FieldNoteDraft convention. */
export interface VolunteerHoursDraft {
  worked_on: string
  hours: number
  activity: HoursActivity
  note?: string
  club_id?: string
  work_project_id?: string
  mile?: number
  lat?: number
  lon?: number
}

/** One record as GET /volunteer-hours/mine serves it. */
export interface VolunteerHoursSummary {
  id: string
  club_id: string | null
  worked_on: string
  hours: number
  work_project_id: string | null
  activity: HoursActivity
  note: string | null
  mile: number | null
  lat: number | null
  lon: number | null
  state: HoursState
  /** ISO timestamp or null - when a club stood behind (or refused) it. */
  confirmed_at: string | null
  recorded_at: string
}

/**
 * The one total the dashboard prints, and which states are in it.
 *
 * Maintainer decision 2026-08-20 (recorded on #761): claimed hours count
 * everywhere immediately - the fee exemption included - until a club
 * disputes them. So the total is claimed + confirmed, disputed drops out,
 * and the LABEL travels with the number: a reader must always be able to
 * tell how much of a total is still somebody's own word. This supersedes
 * PRICING_MODEL.md's "grant, don't self-report" for the exemption; that
 * doc's record is updated in the same change.
 */
export interface HoursTotals {
  /** claimed + confirmed, the number the dashboard prints. */
  countedHours: number
  /** The slice of countedHours no club has confirmed yet - the label's
   *  substance, not a second score. */
  unconfirmedHours: number
  daysWorked: number
}

export function hoursTotals(records: readonly VolunteerHoursSummary[]): HoursTotals {
  const counted = records.filter((record) => record.state !== 'disputed')
  return {
    countedHours: counted.reduce((sum, record) => sum + record.hours, 0),
    unconfirmedHours: counted
      .filter((record) => record.state === 'claimed')
      .reduce((sum, record) => sum + record.hours, 0),
    // Distinct calendar days, because two records on one Saturday are one
    // day of showing up - and days are a real thing, never points.
    daysWorked: new Set(counted.map((record) => record.worked_on)).size,
  }
}

/** The state, in words a volunteer reads on their own logbook. */
export function stateLabel(state: HoursState): string {
  if (state === 'confirmed') return 'Confirmed by the club'
  if (state === 'disputed') return 'Disputed — worth a word with the club'
  return 'Claimed — not yet confirmed'
}

function csvField(value: string | number | null): string {
  if (value === null) return ''
  const text = String(value)
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text
}

/**
 * The record as a file the hiker can hand to anyone (value #6's
 * portability, and VOLUNTEERING.md rule 3: sharing is an EXPORT - a hiker
 * handing someone a file, never the app publishing a page). Every state
 * included and labeled, the export decision the issue asked to have made
 * deliberately rather than by accident: a club treasurer reading this can
 * see exactly which rows carry the club's word and which are still the
 * volunteer's own.
 */
export function hoursCsv(records: readonly VolunteerHoursSummary[]): string {
  const header = 'worked_on,hours,activity,state,club_confirmed_at,mile,note'
  const rows = records.map((record) =>
    [
      record.worked_on,
      record.hours,
      record.activity,
      record.state,
      record.confirmed_at ?? '',
      record.mile,
      record.note,
    ]
      .map(csvField)
      .join(','),
  )
  return [header, ...rows].join('\n') + '\n'
}

/** The workday a record was logged against, when it names one that is still
 *  in the fetched list - for the row's own line, never for a count. */
export function projectFor(
  record: VolunteerHoursSummary,
  projects: readonly WorkProjectSummary[] | null,
): WorkProjectSummary | null {
  if (record.work_project_id === null || projects === null) return null
  return projects.find((project) => project.id === record.work_project_id) ?? null
}
