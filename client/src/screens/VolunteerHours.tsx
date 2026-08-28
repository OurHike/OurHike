// The hours section of the Volunteer tab: a day's work logged in four
// fields, and the private record above it (features/VOLUNTEERING.md §4-5,
// #761).
//
// A LOGBOOK, NOT A SCOREBOARD - the four rules from the doc, enforced in
// what this screen declines to render: nothing comparative, no lack-state
// (nothing about days NOT worked, no streaks, no targets), private by
// default with sharing as an EXPORT the hiker hands to someone, and counts
// of real things only - hours and days, never a composite score.
//
// Hours are claimed, not computed: the app could infer them from GPS and
// would be wrong constantly (a lunch break, a drive to the trailhead, a
// phone in a pack all day). Ask the person. They know.

import { useState } from 'react'
import {
  ACTIVITY_LABELS,
  HOURS_ACTIVITIES,
  hoursCsv,
  hoursTotals,
  NYNJTC_HOURS_FORM_URL,
  stateLabel,
  type HoursActivity,
  type VolunteerHoursDraft,
  type VolunteerHoursSummary,
} from '../lib/volunteerHours'
import { localDay } from '../lib/passedToday'

export interface VolunteerHoursProps {
  /**
   * The logbook: what the backend holds plus this phone's own unsent
   * records, merged by the shell - or null when neither exists to show,
   * which renders as the form alone rather than as an empty history
   * (an empty history is a lack-state this screen does not draw).
   */
  records: readonly VolunteerHoursSummary[] | null
  onLog: (draft: VolunteerHoursDraft) => void
  now: Date
}

export function VolunteerHours({ records, onLog, now }: VolunteerHoursProps) {
  const [workedOn, setWorkedOn] = useState(() => localDay(now))
  const [hours, setHours] = useState('')
  const [activity, setActivity] = useState<HoursActivity>('maintenance')
  const [note, setNote] = useState('')
  const [logged, setLogged] = useState(false)

  const parsedHours = Number(hours)
  const canLog =
    hours.trim() !== '' &&
    Number.isFinite(parsedHours) &&
    parsedHours > 0 &&
    parsedHours <= 24

  const totals = records === null ? null : hoursTotals(records)

  const log = () => {
    const trimmed = note.trim()
    onLog({
      worked_on: workedOn,
      hours: parsedHours,
      activity,
      ...(trimmed === '' ? {} : { note: trimmed }),
    })
    setHours('')
    setNote('')
    setLogged(true)
  }

  return (
    <section className="volunteer__section" aria-labelledby="volunteer-hours">
      <h2 id="volunteer-hours" className="volunteer__heading">
        Your hours
      </h2>
      <p className="volunteer__note">
        Clubs report volunteer hours to ATC and the land agencies, where they carry real
        weight in funding. A day you log here is claimed in your name until a club
        confirms it — and it stays yours either way.
      </p>
      <p className="volunteer__note">
        {/* A link out, never a data connection (#1154) - this logbook stays
            OurHike's own. NYNJTC's own form is where a hiker signs into their
            NYNJTC account, on NYNJTC's own page; OurHike never sees it. */}
        Volunteering with NYNJTC? This logbook is OurHike’s own — report the same day on{' '}
        <a
          className="volunteer__workday-contact"
          data-testid="hours-nynjtc-link"
          href={NYNJTC_HOURS_FORM_URL}
          target="_blank"
          rel="noopener noreferrer"
        >
          NYNJTC’s own volunteer hours form
        </a>{' '}
        too, where you’ll sign into your NYNJTC account.
      </p>

      {logged && (
        <p className="volunteer__note" role="status">
          Logged. It sends when there’s signal, and shows below right away.
        </p>
      )}

      <div className="volunteer__hours-form">
        <label className="volunteer__field">
          <span className="volunteer__field-label">Day</span>
          <input
            type="date"
            data-testid="hours-worked-on"
            value={workedOn}
            max={localDay(now)}
            onChange={(event) => setWorkedOn(event.target.value)}
          />
        </label>
        <label className="volunteer__field">
          <span className="volunteer__field-label">Hours</span>
          <input
            type="number"
            data-testid="hours-count"
            min={0.5}
            max={24}
            step={0.5}
            value={hours}
            onChange={(event) => setHours(event.target.value)}
          />
        </label>
        <label className="volunteer__field">
          <span className="volunteer__field-label">What kind of work</span>
          <select
            data-testid="hours-activity"
            value={activity}
            onChange={(event) => setActivity(event.target.value as HoursActivity)}
          >
            {HOURS_ACTIVITIES.map((value) => (
              <option key={value} value={value}>
                {ACTIVITY_LABELS[value]}
              </option>
            ))}
          </select>
        </label>
        <label className="volunteer__field">
          <span className="volunteer__field-label">What you did (optional)</span>
          <textarea
            data-testid="hours-note"
            rows={2}
            value={note}
            placeholder="Cleared four blowdowns south of the gap…"
            onChange={(event) => setNote(event.target.value)}
          />
        </label>
        <button
          type="button"
          className="volunteer__log-button"
          data-testid="hours-log"
          disabled={!canLog}
          onClick={log}
        >
          Log the day
        </button>
      </div>

      {records !== null && records.length > 0 && totals !== null && (
        <>
          {/* One total, labeled - never a composite score, never a target.
              The unconfirmed slice rides WITH the number (the 2026-08-20
              decision: claimed counts until disputed, and the state always
              travels where the number does). */}
          <p className="volunteer__totals" data-testid="hours-totals">
            {`${totals.countedHours.toLocaleString('en-US', {
              maximumFractionDigits: 1,
            })} hours over ${totals.daysWorked} ${totals.daysWorked === 1 ? 'day' : 'days'}`}
            {totals.unconfirmedHours > 0 && (
              <span className="volunteer__totals-caveat">
                {` — ${totals.unconfirmedHours.toLocaleString('en-US', {
                  maximumFractionDigits: 1,
                })} of them not yet confirmed by a club`}
              </span>
            )}
          </p>

          <ul className="volunteer__hours-list">
            {records.map((record) => (
              <li key={record.id} className="volunteer__hours-record">
                <p className="volunteer__hours-line">
                  {`${record.worked_on} · ${record.hours.toLocaleString('en-US', {
                    maximumFractionDigits: 1,
                  })}h · ${ACTIVITY_LABELS[record.activity] ?? record.activity}`}
                </p>
                <p className="volunteer__hours-state">{stateLabel(record.state)}</p>
                {record.note !== null && (
                  <p className="volunteer__hours-note">“{record.note}”</p>
                )}
              </li>
            ))}
          </ul>

          {/* Sharing is an export - a hiker handing someone a file, never
              the app publishing a page (rule 3, and value #6's GPX/CSV
              portability). Every state included and labeled, which is the
              export decision #761 asked to have made deliberately. */}
          <a
            className="volunteer__export"
            data-testid="hours-export"
            download="ourhike-volunteer-hours.csv"
            href={`data:text/csv;charset=utf-8,${encodeURIComponent(hoursCsv(records))}`}
          >
            Export as CSV
          </a>
        </>
      )}
    </section>
  )
}
