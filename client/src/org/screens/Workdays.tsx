/**
 * Workdays, signups and hours - mirrored from their calendar, or made here.
 *
 * **WE MIRROR, AND WE NEVER WRITE BACK.** An organization already running
 * workdays on its own website is authoritative on them; a mirrored row is
 * read-only here and its edit button leaves for their site. The alternative -
 * a two-way sync - fails in the direction that matters, because the failure
 * mode is us overwriting a date somebody moved on their own calendar and
 * nobody finding out until a crew shows up on the wrong Saturday.
 *
 * **A ONE-TIME IMPORT IS THE THING THIS IS NOT.** It goes stale the first
 * time a date moves, and stale is worse than absent for a hiker driving to a
 * trailhead. Mirroring means their site stays the truth and this page follows
 * it, which is the same argument, from the other end, for refusing to write.
 *
 * **BOTH KINDS ARE SIGNED UP TO THE SAME WAY, FROM A HIKER'S SIDE.** The
 * mirrored one carries the organization's own signup link, the one made here
 * carries ours, and `WorkdaysWidget` is what draws either - so a hiker cannot
 * tell which is which and should not have to. The provenance chip is for the
 * admin reading this screen, who is the one person it matters to.
 */

import { useState } from 'react'
import { PageHeader, formatWorkdayRange } from '../components'
import type { Workday, WorkdaySignup } from '../orgApi'

export type WorkdayTab = 'workdays' | 'signups' | 'hours'

export interface WorkdayFeed {
  /** Where the mirror reads from, or null when nothing is connected. */
  readonly url: string | null
  readonly lastReadAt: string | null
  readonly cadence: string
}

export interface HoursRow {
  readonly id: string
  readonly personName: string
  readonly hours: number
  readonly section: string
  readonly loggedOn: string
}

export interface WorkdaysProps {
  readonly workdays: readonly Workday[]
  readonly feed: WorkdayFeed
  readonly signups: readonly WorkdaySignup[]
  readonly hoursToConfirm: readonly HoursRow[]
  readonly canEdit: boolean
  readonly names?: Readonly<Record<string, string>>
  readonly leaders?: Readonly<Record<string, string>>
  readonly onCreate: () => void
  readonly onEdit: (workday: Workday) => void
  readonly onSyncSettings: () => void
  readonly onConfirmHours: (row: HoursRow) => void
}

const TABS: readonly { key: WorkdayTab; label: string }[] = [
  { key: 'workdays', label: 'Workdays' },
  { key: 'signups', label: 'Signups' },
  { key: 'hours', label: 'Hours to confirm' },
]

/** How long ago the mirror last read, in the words a person would use.
 *
 *  Minutes up to an hour, then hours, then the date - because "1,412 minutes
 *  ago" is arithmetic the reader has to do, and the only question they are
 *  asking is whether this is current.
 */
export function lastReadLabel(iso: string | null, now: Date = new Date()): string {
  if (!iso) return 'never read'
  const then = new Date(iso)
  if (Number.isNaN(then.getTime())) return 'never read'
  const minutes = Math.floor((now.getTime() - then.getTime()) / 60_000)
  if (minutes < 1) return 'read just now'
  if (minutes === 1) return 'last read 1 minute ago'
  if (minutes < 60) return `last read ${minutes} minutes ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `last read ${hours} ${hours === 1 ? 'hour' : 'hours'} ago`
  return `last read ${then.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}`
}

export function Workdays({
  workdays,
  feed,
  signups,
  hoursToConfirm,
  canEdit,
  names = {},
  leaders = {},
  onCreate,
  onEdit,
  onSyncSettings,
  onConfirmHours,
}: WorkdaysProps) {
  const [tab, setTab] = useState<WorkdayTab>('workdays')

  return (
    <>
      <PageHeader
        eyebrow="Manage volunteers · workdays"
        title="Workdays, signups and hours"
        sub={
          <>
            If you already run workdays on your own website, keep doing that — we mirror
            them and stay out of the way. If you would rather not run two systems, create
            them here instead. You can do both, and every workday says which one it came
            from.
          </>
        }
        glyph={
          <>
            <rect x="3.5" y="5" width="17" height="15" rx="2" />
            <path d="M3.5 9.5h17M8 3.5v3M16 3.5v3" />
          </>
        }
      />

      <section className="org-card org-panel">
        <div className="org-panel__head">
          <h2>
            {feed.url ? 'Your website is the system of record' : 'Nothing connected yet'}
          </h2>
          <span className="org-pill" data-tone={feed.url ? 'done' : 'quiet'}>
            {feed.url ? 'connected' : 'not connected'}
          </span>
        </div>
        {feed.url ? (
          <>
            <p className="org-mono">
              {feed.url} · {feed.cadence} · {lastReadLabel(feed.lastReadAt)}
            </p>
            <p className="org-panel__note">
              A mirrored workday is read-only here — we never write back to your site, and
              we never change what it told us. Your form keeps taking signups; we show
              hikers the link.
            </p>
          </>
        ) : (
          <p className="org-panel__note">
            Point us at a calendar feed and we will read it {feed.cadence}. Or skip it
            entirely and make workdays here — an organization that does not run its own
            calendar is not missing a step.
          </p>
        )}
        {canEdit ? (
          <div className="org-inline">
            <button
              type="button"
              className="org-btn org-btn--ghost org-btn--small"
              onClick={onSyncSettings}
            >
              Sync settings
            </button>
          </div>
        ) : null}
      </section>

      <div className="org-chips">
        {TABS.map((entry) => (
          <button
            key={entry.key}
            type="button"
            className="org-chip"
            aria-pressed={tab === entry.key}
            onClick={() => setTab(entry.key)}
          >
            {entry.label}
            {entry.key === 'hours' && hoursToConfirm.length > 0
              ? ` ${hoursToConfirm.length}`
              : ''}
          </button>
        ))}
      </div>

      {tab === 'workdays' ? (
        <>
          {workdays.length === 0 ? (
            <div className="org-empty">
              <h3>No workdays on the calendar</h3>
              <p>
                Nothing mirrored and nothing made here. That is the honest state rather
                than an empty filter — connect a feed above, or add the one you called on
                Thursday.
              </p>
            </div>
          ) : (
            <div className="org-stack">
              {workdays.map((workday) => {
                const mirrored = workday.source === 'mirrored'
                return (
                  <div className="org-card" key={workday.id}>
                    <div className="org-inline">
                      <span className="org-table__name">{workday.title}</span>
                      <span className="org-pill" data-tone={mirrored ? 'quiet' : 'done'}>
                        {mirrored ? 'mirrored' : 'yours, here'}
                      </span>
                    </div>
                    <p className="org-mono">
                      {formatWorkdayRange(workday.starts_on, workday.ends_on)}
                      {workday.meet_point ? ` · ${workday.meet_point}` : ''}
                      {leaders[workday.id] ? ` · led by ${leaders[workday.id]}` : ''}
                    </p>
                    <p className="org-panel__note">
                      {workday.interested_count} interested · {workday.confirmed_count}{' '}
                      confirmed
                      {workday.cap !== null && workday.confirmed_count >= workday.cap
                        ? ' · at capacity'
                        : ''}
                    </p>
                    {workday.description ? (
                      <p className="org-panel__note">{workday.description}</p>
                    ) : null}
                    <p className="org-mono">
                      {mirrored
                        ? 'Read-only here. Edit it on your own site and we pick the change up within the hour.'
                        : 'Made here because it did not exist on your site. Nothing there needed changing.'}
                    </p>
                    {canEdit ? (
                      <div className="org-inline">
                        {mirrored && workday.signup_url ? (
                          <a
                            className="org-btn org-btn--ghost org-btn--small"
                            href={workday.signup_url}
                          >
                            Edit on your site ↗
                          </a>
                        ) : (
                          <button
                            type="button"
                            className="org-btn org-btn--ghost org-btn--small"
                            onClick={() => onEdit(workday)}
                          >
                            Edit
                          </button>
                        )}
                      </div>
                    ) : null}
                  </div>
                )
              })}
            </div>
          )}

          {canEdit ? (
            <section className="org-card org-panel">
              <span className="org-eyebrow">Add one here instead</span>
              <p className="org-panel__note">
                For the workday you called on Thursday because a storm came through. It
                shows up beside your mirrored ones and is yours to edit.
              </p>
              <div className="org-inline">
                <button type="button" className="org-btn" onClick={onCreate}>
                  + New workday
                </button>
              </div>
            </section>
          ) : null}

          <div className="org-callout" data-tone="info">
            <span>
              <strong>Why not just import everything once.</strong> A one-time import goes
              stale the first time you move a date on your own site. Mirroring means your
              site stays the truth and this page follows it — which is also why we refuse
              to write back.
            </span>
          </div>

          <section className="org-card org-panel">
            <span className="org-eyebrow">What hikers see</span>
            <p className="org-panel__note">
              All {workdays.length} of them, on the map and in the next fourteen days —
              with your own signup link on the mirrored ones, and our form on the ones you
              made here. A hiker cannot tell which is which, and should not have to.
            </p>
          </section>
        </>
      ) : null}

      {tab === 'signups' ? (
        signups.length === 0 ? (
          <div className="org-empty">
            <h3>Nobody has put a hand up yet</h3>
            <p>
              Signups on mirrored workdays go to your own form and never reach us — so
              this list covers only the workdays you made here. It is not the whole
              picture and does not pretend to be.
            </p>
          </div>
        ) : (
          <div className="org-card org-card--flush">
            <table className="org-table">
              <thead>
                <tr>
                  <th scope="col">Who</th>
                  <th scope="col">Where they stand</th>
                  <th scope="col">What they said</th>
                  <th scope="col">Asked</th>
                </tr>
              </thead>
              <tbody>
                {signups.map((signup) => (
                  <tr key={signup.id}>
                    <td className="org-table__name">
                      {names[signup.person_id] ?? signup.person_id}
                    </td>
                    <td>
                      <span
                        className="org-pill"
                        data-tone={
                          signup.state === 'confirmed'
                            ? 'done'
                            : signup.state === 'interested'
                              ? 'waiting'
                              : signup.state === 'waitlisted'
                                ? 'waiting'
                                : 'quiet'
                        }
                      >
                        {signup.state === 'cancelled_by_volunteer'
                          ? 'they cancelled'
                          : signup.state}
                      </span>
                    </td>
                    <td>{signup.note ?? '—'}</td>
                    <td className="org-mono">
                      {new Date(signup.created_at).toLocaleDateString('en-US', {
                        month: 'short',
                        day: 'numeric',
                      })}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="org-table__foot">
              Interested is not confirmed. Somebody stays interested until you answer, and
              the volunteer's own screen says so in those words rather than showing them a
              place they do not have.
            </p>
          </div>
        )
      ) : null}

      {tab === 'hours' ? (
        hoursToConfirm.length === 0 ? (
          <div className="org-empty">
            <h3>Nothing waiting on you</h3>
            <p>
              Hours are the volunteer's record first. Confirming is for your own reporting
              — it does not create the entry and unconfirming does not delete it.
            </p>
          </div>
        ) : (
          <>
            <div className="org-card org-card--flush">
              <table className="org-table">
                <thead>
                  <tr>
                    <th scope="col">Who</th>
                    <th scope="col">Hours</th>
                    <th scope="col">Section</th>
                    <th scope="col">Logged</th>
                    <th scope="col" />
                  </tr>
                </thead>
                <tbody>
                  {hoursToConfirm.map((row) => (
                    <tr key={row.id}>
                      <td className="org-table__name">{row.personName}</td>
                      <td className="org-table__num">{row.hours}</td>
                      <td>{row.section}</td>
                      <td className="org-mono">{row.loggedOn}</td>
                      <td>
                        {canEdit ? (
                          <button
                            type="button"
                            className="org-link"
                            onClick={() => onConfirmHours(row)}
                          >
                            confirm
                          </button>
                        ) : null}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="org-callout" data-tone="info">
              <span>
                <strong>Hours belong to the person who walked them.</strong> Confirming
                adds your organization's countersignature for its own reporting. It does
                not create the entry, and declining to confirm does not remove it from
                their record.
              </span>
            </div>
          </>
        )
      ) : null}
    </>
  )
}
