/**
 * Ridge Runner At-Large: work the trail you were walking anyway.
 *
 * **THIS IS NOT A CREDENTIAL, AND THE SCREEN SAYS SO WHERE A BADGE WOULD
 * OTHERWISE GO.** ATC's Ridgerunners are staff. Somebody who picks a commitment
 * here is a volunteer trail monitor, and the difference matters on the
 * ground: a hiker must never take a closure, a fire rule or a camping
 * instruction from one as though it came from the agency. So nothing is
 * issued that works as a badge - no card, no public profile, no pin showing
 * where somebody is. The name is qualified everywhere it is visible to a
 * third party, which is what #763 asks for.
 *
 * **SEVEN DAYS IS A CEILING AND A REAL LIMIT, NOT A DEFAULT.** The commitment
 * closes on its own and cannot be extended, because a commitment that can be
 * extended becomes an obligation and this app does not do those. Starting
 * another window is a deliberate act on an empty page, never a renewal
 * prompt. `MAX_COMMITMENT_DAYS` on the server is the enforcement; this screen
 * is the explanation.
 *
 * **NOTHING NEW IS STORED ABOUT THE PERSON.** Everything filed in a window is
 * an ordinary report or condition note tagged to that window. There is no
 * runner record, no rank and no history beyond the notes themselves - so
 * ending a window leaves nothing behind that could be read as a standing.
 *
 * **AN EMPTY DAY COSTS NOTHING.** A day walked past without filing anything
 * stays empty and nothing is subtracted for it. A partial week is a week of
 * real work, and a screen that shaded the empty days would make it a streak.
 */

import { useState } from 'react'
import { PageHeader } from '../components'

/** The ceiling, mirrored from `MAX_COMMITMENT_DAYS` in the backend.
 *
 *  Stated here so the copy and the limit cannot drift apart in the direction
 *  that matters - a screen offering eight days against a server that refuses
 *  them is a promise broken at submit. The server is what enforces it.
 */
export const MAX_COMMITMENT_DAYS = 7

export const WINDOW_LENGTHS: readonly { days: number; label: string }[] = [
  { days: 1, label: 'Today only' },
  { days: 2, label: '2 days' },
  { days: 3, label: '3 days' },
  { days: 5, label: '5 days' },
  { days: 7, label: '7 days — the maximum' },
]

export interface RunnerTask {
  readonly key: string
  readonly name: string
  readonly blurb: string
}

/** The three things somebody can put at the front of their week.
 *
 *  Each files as something the app already has - a trash report, a condition
 *  note, a clearance report - rather than a new kind of record. "No new
 *  machinery" is the design constraint that keeps a window from becoming a
 *  parallel system with its own data.
 */
export const RUNNER_TASKS: readonly RunnerTask[] = [
  {
    key: 'cleanup',
    name: 'Clean-up and pack-out',
    blurb:
      'Trash you carry out, and where you found it. Files as a trash report — no new machinery.',
  },
  {
    key: 'invasives',
    name: 'Invasive species',
    blurb:
      'Barberry, stiltgrass, mile-a-minute. A photo helps the conservation lead more than a name does.',
  },
  {
    key: 'clearance',
    name: 'General trail clearance',
    blurb:
      'Brushing, small blowdowns, drainage. Anything needing a saw becomes a help request instead.',
  },
]

export interface RunnerDay {
  readonly iso: string
  readonly weekday: string
  readonly dayOfMonth: string
  readonly submissions: number
  readonly today: boolean
  readonly future: boolean
  readonly last: boolean
}

export interface RunnerFiling {
  readonly id: string
  readonly what: string
  readonly when: string
  readonly where: string
  readonly kind: string
}

export interface RidgeRunnerProps {
  /** The window in flight, or null when nobody is out. */
  readonly commitment: {
    readonly dayNumber: number
    readonly totalDays: number
    readonly rangeLabel: string
    readonly taskKeys: readonly string[]
    readonly days: readonly RunnerDay[]
  } | null
  readonly filings: readonly RunnerFiling[]
  readonly submissions: number
  readonly trashBags: number
  readonly invasivesLogged: number
  readonly milesWalked: number
  /** Which organization hears about it, worked out from the miles. */
  readonly hearingOrg: string | null
  readonly onStart: (days: number, taskKeys: readonly string[]) => void
  readonly onEnableTask: (key: string) => void
}

export function RidgeRunner({
  commitment,
  filings,
  submissions,
  trashBags,
  invasivesLogged,
  milesWalked,
  hearingOrg,
  onStart,
  onEnableTask,
}: RidgeRunnerProps) {
  const [days, setDays] = useState(WINDOW_LENGTHS[2].days)
  const [picked, setPicked] = useState<readonly string[]>(['cleanup'])

  const active = new Set(commitment?.taskKeys ?? [])

  return (
    <>
      <PageHeader
        eyebrow={
          commitment
            ? `Ridge Runner At-Large · day ${commitment.dayNumber} of ${commitment.totalDays}`
            : 'Ridge Runner At-Large · nobody out'
        }
        title={
          window ? 'You are out this week' : 'Work the trail you were walking anyway'
        }
        sub={
          commitment ? (
            <>
              {commitment.rangeLabel}. Your window closes on its own.
              <br />
              Work the trail you were walking anyway.
            </>
          ) : (
            <>
              Pick a window and what you will watch for, and the app puts those tasks at
              the front for that week. Nothing starts until you say so, and nothing
              reminds you to.
            </>
          )
        }
        glyph={
          <>
            <path d="M3 18 8.5 8l3.5 5.5L15 9l6 9z" />
            <circle cx="18" cy="5.5" r="2" />
          </>
        }
      />

      {commitment ? (
        <>
          <section className="org-panel">
            <div className="org-panel__head">
              <h2>Your window</h2>
              <span className="org-panel__count">
                {commitment.totalDays} of {MAX_COMMITMENT_DAYS} days
              </span>
            </div>
            <p className="org-panel__note">
              {commitment.totalDays} days, because that is what you asked for.{' '}
              {MAX_COMMITMENT_DAYS} is the ceiling and it is a real limit, not a default —
              a commitment that can be extended becomes an obligation, and this app does
              not do those.
            </p>
            <div className="org-grid org-grid--three">
              {commitment.days.map((day) => (
                <div className="org-tile" key={day.iso}>
                  <span className="org-tile__label">{day.weekday}</span>
                  <span className="org-tile__value">{day.dayOfMonth}</span>
                  <span className="org-tile__meta">
                    {day.today
                      ? 'out now'
                      : day.last
                        ? 'window ends'
                        : day.future
                          ? ''
                          : day.submissions === 0
                            ? ''
                            : `${day.submissions} ${day.submissions === 1 ? 'submission' : 'submissions'}`}
                  </span>
                </div>
              ))}
            </div>
            <p className="org-mono">
              The days ahead are empty because they have not happened. A day you walk past
              without filing anything stays empty too, and nothing is subtracted for it —
              a partial week is a week of real work.
            </p>
          </section>

          <section className="org-panel">
            <div className="org-panel__head">
              <h2>What you have filed</h2>
              <span className="org-panel__count">this window</span>
            </div>
            <p className="org-panel__note">
              Everything here is an ordinary report or condition note, tagged to this
              window. Nothing new is stored about you.
            </p>
            {filings.length === 0 ? (
              <div className="org-empty">
                <h3>Nothing filed yet</h3>
                <p>
                  Which is a real state and not a failing one. The window is a window, not
                  a quota.
                </p>
              </div>
            ) : (
              <div className="org-stack">
                {filings.map((filing) => (
                  <div className="org-card" key={filing.id}>
                    <div className="org-inline">
                      <span className="org-table__name">{filing.what}</span>
                      <span
                        className="org-pill"
                        data-tone="quiet"
                        style={{ marginLeft: 'auto' }}
                      >
                        {filing.kind}
                      </span>
                    </div>
                    <p className="org-mono">
                      {filing.when} · {filing.where}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </section>

          <section className="org-panel">
            <div className="org-panel__head">
              <h2>What you are watching for</h2>
            </div>
            <p className="org-panel__note">
              The {active.size} you picked {active.size === 1 ? 'is' : 'are'} at the front
              of every screen this week. Turn another on and it joins them.
            </p>
            <div className="org-stack">
              {RUNNER_TASKS.map((task) => (
                <div className="org-card" key={task.key}>
                  <div className="org-inline">
                    <span className="org-table__name">{task.name}</span>
                    {active.has(task.key) ? (
                      <span
                        className="org-pill"
                        data-tone="done"
                        style={{ marginLeft: 'auto' }}
                      >
                        on
                      </span>
                    ) : (
                      <button
                        type="button"
                        className="org-link"
                        style={{ marginLeft: 'auto' }}
                        onClick={() => onEnableTask(task.key)}
                      >
                        turn it on
                      </button>
                    )}
                  </div>
                  <p className="org-panel__note">{task.blurb}</p>
                </div>
              ))}
            </div>
          </section>
        </>
      ) : (
        <div className="org-empty">
          <h3>Nobody is out</h3>
          <p>
            A window is something you start, walk, and let close. There is no standing to
            keep up and nothing accrues between windows.
          </p>
        </div>
      )}

      <div className="org-callout" data-tone="stop">
        <span>
          <strong>This is not a credential.</strong> ATC's Ridgerunners are staff. You are
          a volunteer trail monitor, and the difference matters on the ground: a hiker
          must never take a closure, a fire rule or a camping instruction from you as
          though it came from the agency. So nothing is issued that works as a badge — no
          card, no public profile, no pin showing where you are.
        </span>
      </div>

      <section className="org-panel">
        <div className="org-panel__head">
          <h2>This window</h2>
        </div>
        <div className="org-grid org-grid--three">
          <div className="org-tile">
            <span className="org-tile__label">Submissions</span>
            <span className="org-tile__value">{submissions}</span>
          </div>
          <div className="org-tile">
            <span className="org-tile__label">Trash packed out</span>
            <span className="org-tile__value">
              {trashBags} {trashBags === 1 ? 'bag' : 'bags'}
            </span>
          </div>
          <div className="org-tile">
            <span className="org-tile__label">Invasives logged</span>
            <span className="org-tile__value">{invasivesLogged}</span>
          </div>
          <div className="org-tile">
            <span className="org-tile__label">Miles walked</span>
            <span className="org-tile__value">{milesWalked.toFixed(1)}</span>
          </div>
        </div>
        <p className="org-mono">
          Counts of real things, no total across them, and nothing comparing you to
          another runner.
        </p>
      </section>

      <section className="org-card org-panel">
        <div className="org-panel__head">
          <h2>Which organization hears about it</h2>
        </div>
        <p className="org-panel__note">
          {hearingOrg === null ? (
            <>
              Nobody maintains the miles you are on, as far as our registry knows — so
              what you file reaches the map and no organization's queue. That is an honest
              gap rather than a silent drop.
            </>
          ) : (
            <>
              {hearingOrg} — worked out from who maintains the miles you are on, so you do
              not have to know.
            </>
          )}
        </p>
        <p className="org-mono">
          Offline all week? Everything queues and sends when you reach a signal, dated to
          when you wrote it.
        </p>
      </section>

      <section className="org-card org-panel">
        <div className="org-panel__head">
          <h2>Start another window</h2>
        </div>
        <div className="org-row">
          <label className="org-field" style={{ flex: '0 1 240px' }}>
            <span className="org-field__label">How long</span>
            <select
              className="org-select"
              value={days}
              onChange={(event) => setDays(Number(event.target.value))}
            >
              {WINDOW_LENGTHS.map((entry) => (
                <option key={entry.days} value={entry.days}>
                  {entry.label}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="org-chips">
          {RUNNER_TASKS.map((task) => (
            <button
              key={task.key}
              type="button"
              className="org-chip"
              aria-pressed={picked.includes(task.key)}
              onClick={() =>
                setPicked(
                  picked.includes(task.key)
                    ? picked.filter((key) => key !== task.key)
                    : [...picked, task.key],
                )
              }
            >
              {task.name}
            </button>
          ))}
        </div>
        <div className="org-inline">
          <button
            type="button"
            className="org-btn"
            disabled={picked.length === 0}
            onClick={() => onStart(days, picked)}
          >
            {commitment ? 'Start when this one ends' : 'Start this window'}
          </button>
        </div>
        <p className="org-mono">
          We will not remind you to. If you never come back to this page, nothing happens
          and nothing is lost.
        </p>
      </section>
    </>
  )
}
