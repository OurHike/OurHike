/**
 * The whole roster, and three ways to add to it.
 *
 * **NOTHING HERE EVER OVERWRITES A PERSON.** Somebody who leaves the feed
 * goes inactive and keeps their history; somebody new is added. A sync that
 * could delete would mean a misconfigured endpoint erasing four years of
 * somebody's logged hours in one nightly run, and there is no undo a hiker
 * can reach for.
 *
 * **A DEACTIVATION RELEASES THE ROLES.** That is the point of deactivating
 * rather than ignoring: a section held by somebody who is no longer on the
 * roster reads as covered on the coverage report and is not, which is the one
 * way this table can mislead an organization about its own trails.
 *
 * **THE HOLD IS THE SAFETY VALVE, AND IT IS SERVER-SIDE.** A run proposing to
 * deactivate more than `DEACTIVATION_HOLD_FRACTION` of the roster stops and
 * asks rather than applying - a feed that returns an empty list because an
 * auth token expired should not empty a roster. This screen reports the hold;
 * it does not decide it, because a client-side guard is not a guard.
 *
 * **HOURS AND REPORTS ARE THE PERSON'S, NOT THE ORGANIZATION'S.** They stay
 * attached to the person through a deactivation, and through the organization
 * being deleted outright. The counts in this table are a view of somebody
 * else's record.
 */

import { useState } from 'react'
import { PageHeader } from '../components'
import type { RosterEntry, RosterSyncResult } from '../orgApi'

export type RosterTab = 'all' | 'add' | 'upload' | 'live'

export interface SyncRun {
  readonly id: string
  readonly ranAt: string
  readonly added: number
  readonly deactivated: number
  readonly active: number
  readonly firstRun: boolean
}

export interface RosterProps {
  readonly entries: readonly RosterEntry[]
  readonly activeCount: number
  readonly inactiveCount: number
  readonly canEdit: boolean
  /** Where the nightly read points, or null when nothing is connected. */
  readonly feedUrl: string | null
  readonly runs: readonly SyncRun[]
  /** The last run's outcome, when it held rather than applying. */
  readonly held: RosterSyncResult | null
  readonly hours?: Readonly<Record<string, number>>
  readonly onOpenPerson: (entry: RosterEntry) => void
  readonly onAddPerson: (person: { name: string; email: string }) => void
  readonly onUpload: (file: File) => void
  readonly onConnect: (endpoint: string) => void
}

const TABS: readonly { key: RosterTab; label: string }[] = [
  { key: 'all', label: 'All volunteers' },
  { key: 'add', label: 'Add a person' },
  { key: 'upload', label: 'Upload a list' },
  { key: 'live', label: 'Live connection' },
]

/** Whether a roster row matches what somebody typed into the search box.
 *
 *  Name, email, role and section all match, because an admin looking for
 *  "who has Pine Meadow" types the section, and a search that only read names
 *  would answer nothing and look broken rather than empty.
 */
export function matchesRoster(entry: RosterEntry, query: string): boolean {
  const needle = query.trim().toLowerCase()
  if (!needle) return true
  const haystack = [
    entry.full_name ?? '',
    entry.display_name ?? '',
    entry.email ?? '',
    ...entry.roles,
    ...entry.sections,
  ]
    .join(' ')
    .toLowerCase()
  return haystack.includes(needle)
}

export function Roster({
  entries,
  activeCount,
  inactiveCount,
  canEdit,
  feedUrl,
  runs,
  held,
  hours = {},
  onOpenPerson,
  onAddPerson,
  onUpload,
  onConnect,
}: RosterProps) {
  const [tab, setTab] = useState<RosterTab>('all')
  const [query, setQuery] = useState('')
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [endpoint, setEndpoint] = useState(feedUrl ?? '')

  const shown = entries.filter((entry) => matchesRoster(entry, query))

  return (
    <>
      <PageHeader
        eyebrow={`Volunteers · ${activeCount.toLocaleString()} active · ${inactiveCount.toLocaleString()} inactive`}
        title="Your roster"
        sub={
          <>
            The whole roster in one table, and three ways to add to it — none of which
            ever overwrite a person. Somebody who leaves your feed goes inactive and keeps
            their history; somebody new gets added.
          </>
        }
        glyph={
          <>
            <circle cx="9" cy="8" r="3.2" />
            <path d="M3.5 19a5.5 5.5 0 0 1 11 0" />
            <path d="M16 6.2a3 3 0 0 1 0 5.6M17.5 19a5.5 5.5 0 0 0-2.2-4.4" />
          </>
        }
      />

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
          </button>
        ))}
      </div>

      {tab === 'all' ? (
        <section className="org-panel">
          <label className="org-field">
            <span className="org-field__label">Search</span>
            <input
              className="org-input"
              value={query}
              placeholder="Search a name, email, role or section…"
              onChange={(event) => setQuery(event.target.value)}
            />
          </label>
          <p className="org-mono">
            {shown.length.toLocaleString()} {shown.length === 1 ? 'person' : 'people'} ·{' '}
            {activeCount.toLocaleString()} active
          </p>

          {shown.length === 0 ? (
            <div className="org-empty">
              <h3>Nobody matches that</h3>
              <p>
                {entries.length === 0
                  ? 'The roster is empty. Add somebody by hand, upload a list, or connect a feed — all three are above, and none of them is the required one.'
                  : 'The search reads names, emails, roles and sections. Nothing here carries that word.'}
              </p>
            </div>
          ) : (
            <div className="org-card org-card--flush">
              <div className="org-table__scroll">
                <table className="org-table">
                  <thead>
                    <tr>
                      <th scope="col">Name</th>
                      <th scope="col">Email</th>
                      <th scope="col">Roles</th>
                      <th scope="col">Where</th>
                      <th scope="col">Hrs</th>
                      <th scope="col">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {shown.map((entry) => {
                      const key =
                        entry.person_id ?? entry.email ?? entry.full_name ?? 'unknown'
                      const inactive =
                        entry.roles.length === 0 && entry.person_id !== null
                      return (
                        <tr key={key}>
                          <td>
                            <button
                              type="button"
                              className="org-link"
                              onClick={() => onOpenPerson(entry)}
                            >
                              {entry.display_name ?? entry.full_name ?? '(no name yet)'}
                            </button>
                          </td>
                          <td className="org-mono">{entry.email ?? '—'}</td>
                          <td>
                            {entry.roles.length === 0 ? (
                              <span className="org-mono">no roles — released</span>
                            ) : (
                              entry.roles.join(' · ')
                            )}
                          </td>
                          <td>
                            {entry.sections.length === 0
                              ? '—'
                              : entry.sections.join(' · ')}
                          </td>
                          <td className="org-table__num">
                            {entry.person_id ? (hours[entry.person_id] ?? '—') : '—'}
                          </td>
                          <td>
                            <span
                              className="org-pill"
                              data-tone={
                                entry.pending_invite
                                  ? 'waiting'
                                  : inactive
                                    ? 'quiet'
                                    : 'done'
                              }
                            >
                              {entry.pending_invite
                                ? 'new'
                                : inactive
                                  ? 'inactive'
                                  : 'active'}
                            </span>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
              <p className="org-table__foot">
                Click anyone to open their page. They see the same page — their details
                are theirs to edit, their roles are yours.
              </p>
            </div>
          )}
        </section>
      ) : null}

      {tab === 'add' ? (
        <section className="org-card org-panel">
          <div className="org-panel__head">
            <h2>Add a person</h2>
          </div>
          <p className="org-panel__note">
            For the volunteer who turned up on Saturday. An email is enough — they get a
            seat the moment they sign in, and nothing is sent until you welcome them.
          </p>
          <div className="org-row">
            <label className="org-field">
              <span className="org-field__label">Their name</span>
              <input
                className="org-input"
                value={name}
                placeholder="Ana Reyes"
                onChange={(event) => setName(event.target.value)}
              />
            </label>
            <label className="org-field">
              <span className="org-field__label">Their email</span>
              <input
                className="org-input"
                value={email}
                placeholder="ana@example.org"
                onChange={(event) => setEmail(event.target.value)}
              />
            </label>
          </div>
          <div className="org-inline">
            <button
              type="button"
              className="org-btn org-btn--small"
              disabled={!canEdit || !email.trim()}
              onClick={() => {
                onAddPerson({ name: name.trim(), email: email.trim() })
                setName('')
                setEmail('')
              }}
            >
              Add them
            </button>
          </div>
          <p className="org-mono">
            Adding somebody who already has an OurHike account attaches them rather than
            making a second person. The email is what matches, and a mismatch adds a new
            row rather than merging two.
          </p>
        </section>
      ) : null}

      {tab === 'upload' ? (
        <section className="org-card org-panel">
          <div className="org-panel__head">
            <h2>Upload a list</h2>
          </div>
          <p className="org-panel__note">
            Any CSV with a name and an email per person. Extra columns are kept and
            ignored — we map whatever you send rather than asking you to reshape your
            export.
          </p>
          <label className="org-field">
            <span className="org-field__label">Your file</span>
            <input
              className="org-input"
              type="file"
              accept=".csv,text/csv,application/json"
              disabled={!canEdit}
              onChange={(event) => {
                const file = event.target.files?.[0]
                if (file) onUpload(file)
              }}
            />
          </label>
          <div className="org-callout" data-tone="info">
            <span>
              <strong>Uploading the same list twice is safe.</strong> Matching people are
              left alone, new ones are added, and nobody is welcomed a second time. An
              upload never deactivates — only a live connection can do that, and only
              within the hold below.
            </span>
          </div>
        </section>
      ) : null}

      {tab === 'live' ? (
        <>
          <section className="org-card org-panel">
            <div className="org-panel__head">
              <h2>Live connection</h2>
              <span className="org-pill" data-tone={feedUrl ? 'done' : 'quiet'}>
                {feedUrl ? 'connected' : 'not connected'}
              </span>
            </div>
            <p className="org-panel__note">
              For whoever runs your IT. Point us at an endpoint that returns your active
              volunteers and we read it nightly — so the roster maintains itself.
            </p>
            <label className="org-field">
              <span className="org-field__label">Endpoint URL</span>
              <input
                className="org-input"
                value={endpoint}
                placeholder="https://members.example.org/api/active-volunteers"
                onChange={(event) => setEndpoint(event.target.value)}
              />
            </label>
            <div className="org-inline">
              <button
                type="button"
                className="org-btn org-btn--small"
                disabled={!canEdit || !endpoint.trim()}
                onClick={() => onConnect(endpoint.trim())}
              >
                Test and connect
              </button>
              <span className="org-mono">
                We show you the diff from the first run before it applies.
              </span>
            </div>
          </section>

          {held ? (
            <div className="org-callout" data-tone="stop">
              <span>
                <strong>
                  The last run wanted to deactivate {held.deactivations_held} people and
                  stopped.
                </strong>{' '}
                {held.held_reason ??
                  'That is more of your roster than one night should move, so nothing was applied.'}{' '}
                A feed that returns an empty list because a token expired looks exactly
                like an organization that disbanded, and we would rather ask than guess
                which.
              </span>
            </div>
          ) : null}

          <section className="org-panel">
            <div className="org-panel__head">
              <h2>Recent runs</h2>
            </div>
            {runs.length === 0 ? (
              <div className="org-empty">
                <h3>Nothing has run yet</h3>
                <p>
                  The first read shows you its diff before applying anything, so
                  connecting is not the same as changing your roster.
                </p>
              </div>
            ) : (
              <div className="org-stack">
                {runs.map((run) => (
                  <div className="org-card" key={run.id}>
                    <span className="org-table__name">{run.ranAt}</span>
                    <p className="org-mono">
                      {run.firstRun
                        ? `First run · imported ${run.added.toLocaleString()} people`
                        : `Added ${run.added} · marked ${run.deactivated} inactive · ${run.active.toLocaleString()} active`}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </section>

          <div className="org-callout" data-tone="info">
            <span>
              <strong>The sync only ever adds or deactivates.</strong> People who
              disappear from your feed are marked inactive and their roles are released,
              so a section never looks covered when it isn't. Nothing is deleted, no
              record is overwritten, and their hours and reports stay attached to them.
            </span>
          </div>

          <section className="org-card org-panel">
            <span className="org-eyebrow">What we need back</span>
            <p className="org-panel__note">
              Any JSON or CSV with a name and an email per person. Extra columns are kept
              and ignored; we'll map whatever you send.
            </p>
            <pre className="org-code">
              {'[{ "name": "Ana Reyes", "email": "ana@…", "active": true }]'}
            </pre>
          </section>
        </>
      ) : null}
    </>
  )
}
