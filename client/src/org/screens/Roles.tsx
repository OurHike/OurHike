/**
 * Who looks after which section, and who answers to whom.
 *
 * **A SECTION CARRIES AS MANY ROLES AND AS MANY PEOPLE AS IT NEEDS.**
 * Co-maintainers, a sawyer crew and a corridor monitor on the same miles is
 * normal, and a model that allowed one person per stretch would be a model
 * every organization worked around. `MaintainerAssignment`'s own docstring
 * says the same thing from the other end: resolution returns zero or more,
 * never exactly one.
 *
 * **ASSIGNMENTS ARE DATED, SO JUNE'S MAINTAINER STAYS JUNE'S MAINTAINER.**
 * Nothing here overwrites: a hand-off closes one row and opens another. The
 * question that matters is historical - who should hear about a report
 * written three weeks ago - and an editable "current maintainer" field
 * destroys that answer every time a section changes hands.
 *
 * **A ROLE NOBODY HOLDS CAN BE REMOVED; ONE IN USE IS RETIRED.** Retiring
 * stops it being assignable and keeps everybody's history. A mandated role
 * cannot be removed at all while the requirement stands - an organization
 * that inherited a role from the ATC cannot delete its way out of it, and the
 * button says `mandated` rather than being greyed out with no reason.
 */

import { useState } from 'react'
import { PageHeader } from '../components'
import type { OrgRole, RoleCategory } from '../orgApi'

export interface RoleHolders {
  readonly [roleId: string]: number
}

/** One job, on one stretch, with the person who supervises it. */
export interface RoleOnSection {
  readonly id: string
  readonly roleName: string
  readonly sectionName: string
  /** The anchors, as the row prints them. Absent for a whole-trail role. */
  readonly where: string | null
  /** Who holds it. Empty is a gap, and the point of the screen. */
  readonly who: readonly string[]
  /** Who they answer to, or null - which is its own kind of gap. */
  readonly supervisor: string | null
  readonly required: boolean
}

export type RoleFilter = 'all' | 'gaps' | 'no supervisor' | 'required'

/** Which rows a filter keeps.
 *
 *  Split out because the four are easy to get subtly wrong in a way no
 *  screenshot shows: "gaps only" means nobody holds it, and "no supervisor"
 *  means somebody does and answers to nobody. Those are different problems
 *  and an organization acts on them differently - the first is recruiting,
 *  the second is a reporting line that never got drawn.
 */
export function keepsRow(row: RoleOnSection, filter: RoleFilter): boolean {
  if (filter === 'gaps') return row.who.length === 0
  if (filter === 'no supervisor') return row.supervisor === null
  if (filter === 'required') return row.required
  return true
}

export interface RolesProps {
  readonly roles: readonly OrgRole[]
  readonly holders: RoleHolders
  readonly canEdit: boolean
  readonly onCreate: (role: {
    name: string
    category: RoleCategory
    reportsTo: string | null
  }) => void
  readonly onRetire: (role: OrgRole) => void
  /** Every role attached to a section, for the second half of the screen. */
  readonly attached?: readonly RoleOnSection[]
}

const CATEGORY_LABEL: Record<RoleCategory, string> = {
  trail_maintenance: 'Trail maintenance',
  stewards: 'Stewards',
  environmental: 'Environmental',
}

export function Roles({
  roles,
  holders,
  canEdit,
  onCreate,
  onRetire,
  attached = [],
}: RolesProps) {
  const [adding, setAdding] = useState(false)
  const [filter, setFilter] = useState<RoleFilter>('all')
  const [supervisor, setSupervisor] = useState('')
  const [name, setName] = useState('')
  const [category, setCategory] = useState<RoleCategory>('trail_maintenance')
  const [reportsTo, setReportsTo] = useState('')

  const live = roles.filter((role) => role.retired_at === null)
  const required = live.filter((role) => role.required).length
  const byId = new Map(roles.map((role) => [role.id, role]))

  /** The reporting tree, as the indentation a reader can follow.
   *
   *  Drawn from `reports_to_role_id` rather than stored, so a tree and a set
   *  of rows cannot disagree - which is the same argument
   *  `core/org_access.py` makes for deriving "supervisor" rather than storing
   *  it.
   */
  const depth = (role: OrgRole, seen = new Set<string>()): number => {
    if (!role.reports_to_role_id || seen.has(role.id)) return 0
    const parent = byId.get(role.reports_to_role_id)
    if (!parent) return 0
    seen.add(role.id)
    return 1 + depth(parent, seen)
  }

  const grouped = (
    ['trail_maintenance', 'stewards', 'environmental'] as RoleCategory[]
  ).map((key) => ({ key, roles: live.filter((role) => role.category === key) }))

  return (
    <>
      <PageHeader
        eyebrow="Manage volunteers · roles"
        title="Who looks after which section"
        sub={
          <>
            First define the roles your organization actually has, then attach each one to
            a section. A section can carry as many roles and as many people as it needs —
            co-maintainers, a sawyer crew and a corridor monitor on the same miles is
            normal. Assignments are dated, so June's maintainer stays June's maintainer.
          </>
        }
        glyph={
          <>
            <circle cx="12" cy="7.5" r="3.5" />
            <path d="M5 20a7 7 0 0 1 14 0" />
          </>
        }
        actions={
          canEdit ? (
            <button
              type="button"
              className="org-btn org-btn--small"
              onClick={() => setAdding(true)}
            >
              + New role
            </button>
          ) : null
        }
      />

      <section className="org-panel">
        <div className="org-panel__head">
          <h2>Defined roles</h2>
          <span className="org-panel__count">
            {live.length} defined · {required} required
          </span>
        </div>
        <p className="org-panel__note">
          A role nobody holds can be removed outright. One in use is{' '}
          <strong>retired</strong> instead — it stops being assignable and everybody who
          held it keeps their history. A mandated role cannot be removed while the
          requirement stands.
        </p>

        {adding ? (
          <div className="org-card org-stack">
            <div className="org-row">
              <label className="org-field">
                <span className="org-field__label">
                  What it is called, in your own words
                </span>
                <input
                  className="org-input"
                  value={name}
                  placeholder="Corridor monitor"
                  onChange={(event) => setName(event.target.value)}
                />
              </label>
              <label className="org-field" style={{ flex: '0 1 200px' }}>
                <span className="org-field__label">Kind of work</span>
                <select
                  className="org-select"
                  value={category}
                  onChange={(event) => setCategory(event.target.value as RoleCategory)}
                >
                  {Object.entries(CATEGORY_LABEL).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="org-field" style={{ flex: '0 1 220px' }}>
                <span className="org-field__label">Answers to</span>
                <select
                  className="org-select"
                  value={reportsTo}
                  onChange={(event) => setReportsTo(event.target.value)}
                >
                  <option value="">nobody inside the org</option>
                  {live.map((role) => (
                    <option key={role.id} value={role.id}>
                      {role.name}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <div className="org-inline">
              <button
                type="button"
                className="org-btn org-btn--small"
                disabled={!name.trim()}
                onClick={() => {
                  onCreate({ name: name.trim(), category, reportsTo: reportsTo || null })
                  setName('')
                  setReportsTo('')
                  setAdding(false)
                }}
              >
                Define it
              </button>
              <button
                type="button"
                className="org-btn org-btn--ghost org-btn--small"
                onClick={() => setAdding(false)}
              >
                Cancel
              </button>
            </div>
            <p className="org-mono">
              Who a role answers to is what makes somebody a supervisor. There is no
              separate supervisor flag to set, and no way for a title and the reporting
              line to disagree.
            </p>
          </div>
        ) : null}

        {live.length === 0 ? (
          <div className="org-empty">
            <h3>No roles yet</h3>
            <p>
              Start with the two or three your organization actually uses. The reporting
              line is what decides who confirms whose work, so a flat list of one role is
              a real answer for a small organization rather than a half-finished one.
            </p>
          </div>
        ) : (
          grouped
            .filter((group) => group.roles.length > 0)
            .map((group) => (
              <div className="org-card org-card--flush" key={group.key}>
                <table className="org-table">
                  <thead>
                    <tr>
                      <th scope="col">{CATEGORY_LABEL[group.key]}</th>
                      <th scope="col">Held by</th>
                      <th scope="col">Answers to</th>
                      <th scope="col" />
                    </tr>
                  </thead>
                  <tbody>
                    {group.roles.map((role) => {
                      const held = holders[role.id] ?? 0
                      const parent = role.reports_to_role_id
                        ? (byId.get(role.reports_to_role_id)?.name ?? '—')
                        : '—'
                      return (
                        <tr key={role.id}>
                          <td>
                            <span style={{ paddingLeft: depth(role) * 14 }}>
                              <span className="org-table__name">{role.name}</span>{' '}
                              <span
                                className="org-pill"
                                data-tone={role.required ? 'waiting' : 'quiet'}
                              >
                                {role.required ? 'required' : 'optional'}
                              </span>
                            </span>
                            {role.required_by ? (
                              <div className="org-mono">
                                required by {role.required_by}
                              </div>
                            ) : null}
                          </td>
                          <td className="org-table__num">
                            {held === 0
                              ? 'nobody yet'
                              : held === 1
                                ? '1 person holds this'
                                : `${held} hold this`}
                          </td>
                          <td>{parent}</td>
                          <td>
                            {canEdit ? (
                              role.required ? (
                                <span className="org-mono">mandated</span>
                              ) : (
                                <button
                                  type="button"
                                  className="org-link"
                                  onClick={() => onRetire(role)}
                                >
                                  {held === 0 ? 'remove' : 'retire'}
                                </button>
                              )
                            ) : null}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            ))
        )}
      </section>

      <section className="org-panel">
        <div className="org-panel__head">
          <h2>By kind of work</h2>
          <span className="org-panel__count">{live.length} live</span>
        </div>
        <div className="org-grid org-grid--three">
          {grouped.map((group) => (
            <div className="org-tile" key={`summary-${group.key}`}>
              <span className="org-tile__label">{CATEGORY_LABEL[group.key]}</span>
              <span className="org-tile__value">{group.roles.length}</span>
              <span className="org-tile__meta">
                {group.roles.length === 0
                  ? 'none defined'
                  : group.roles.map((role) => role.name).join(' · ')}
              </span>
            </div>
          ))}
        </div>
      </section>

      <section className="org-panel">
        <div className="org-panel__head">
          <h2>Attach roles to sections</h2>
          <span className="org-panel__count">{attached.length} attached</span>
        </div>
        <p className="org-panel__note">
          Each row is one job on one stretch of trail, with the person who supervises it.
          A row with nobody on it is the coverage report's raw material; a row with
          somebody and no supervisor is a different problem — their reports reach a
          maintainer and stop there.
        </p>

        <div className="org-chips">
          {(
            [
              ['all', 'All roles'],
              ['gaps', 'Gaps only'],
              ['no supervisor', 'No supervisor'],
              ['required', 'Required roles'],
            ] as [RoleFilter, string][]
          ).map(([key, label]) => (
            <button
              key={key}
              type="button"
              className="org-chip"
              aria-pressed={filter === key}
              onClick={() => setFilter(key)}
            >
              {label} {attached.filter((row) => keepsRow(row, key)).length}
            </button>
          ))}
        </div>

        <label className="org-field" style={{ maxWidth: 280 }}>
          <span className="org-field__label">Supervisor</span>
          <select
            className="org-select"
            value={supervisor}
            onChange={(event) => setSupervisor(event.target.value)}
          >
            <option value="">Any supervisor</option>
            {[...new Set(attached.map((row) => row.supervisor).filter(Boolean))].map(
              (name) => (
                <option key={name as string} value={name as string}>
                  {name}
                </option>
              ),
            )}
          </select>
        </label>

        {(() => {
          const rows = attached.filter(
            (row) =>
              keepsRow(row, filter) &&
              (supervisor === '' || row.supervisor === supervisor),
          )
          if (rows.length === 0) {
            return (
              <div className="org-empty">
                <h3>
                  {attached.length === 0
                    ? 'Nothing attached yet'
                    : 'Nothing matches those filters'}
                </h3>
                <p>
                  {attached.length === 0
                    ? 'Define the roles above first, then attach each one to the stretch it covers. A section can carry as many as it needs.'
                    : 'Which is an answer rather than an empty table — there is no row in this organization that is both of those things.'}
                </p>
              </div>
            )
          }
          return (
            <div className="org-card org-card--flush">
              <div className="org-table__scroll">
                <table className="org-table">
                  <thead>
                    <tr>
                      <th scope="col">Role</th>
                      <th scope="col">Section</th>
                      <th scope="col">Who</th>
                      <th scope="col">Supervisor</th>
                      <th scope="col">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((row) => (
                      <tr key={row.id}>
                        <td>
                          <span className="org-table__name">{row.roleName}</span>
                          {row.required ? <div className="org-mono">required</div> : null}
                        </td>
                        <td>
                          <span className="org-table__name">{row.sectionName}</span>
                          {row.where ? <div className="org-mono">{row.where}</div> : null}
                        </td>
                        <td>
                          {row.who.length === 0 ? (
                            <span className="org-mono">nobody yet</span>
                          ) : (
                            <>
                              {row.who.join(', ')}
                              <div className="org-mono">
                                {row.who.length === 1
                                  ? '1 person'
                                  : `${row.who.length} people`}
                              </div>
                            </>
                          )}
                        </td>
                        <td>
                          {row.supervisor ?? (
                            <span className="org-mono">nobody above them</span>
                          )}
                        </td>
                        <td>
                          <span
                            className="org-pill"
                            data-tone={
                              row.who.length === 0
                                ? 'stopped'
                                : row.supervisor === null
                                  ? 'waiting'
                                  : 'done'
                            }
                          >
                            {row.who.length === 0
                              ? 'gap'
                              : row.supervisor === null
                                ? 'no supervisor'
                                : 'assigned'}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )
        })()}
      </section>

      <div className="org-callout" data-tone="info">
        <span>
          <strong>Supervisors propose, admins confirm.</strong> A supervisor can put
          somebody on a stretch and an admin makes it live. RLS says who may write, never
          whether a write was right — and a wrong section assignment sends a hiker's
          report to the wrong person for as long as nobody notices.
        </span>
      </div>
    </>
  )
}
