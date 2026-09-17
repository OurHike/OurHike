/**
 * Which sections have nobody on them.
 *
 * **A GAP IS FLAGGED HERE AND NOWHERE A HIKER CAN SEE IT.** This screen is
 * for the organization deciding where to recruit, and a section with no
 * maintainer is not a section a hiker should avoid - the trail is the same
 * trail. Publishing coverage to the map would turn an organization's staffing
 * problem into a hiker's routing decision, which is nobody's idea of useful.
 *
 * **A VACANT SUPERVISOR IS NOT COVERED.** Somebody holds the miles, but the
 * role they report to is empty, so a report reaches a maintainer and stops
 * there. It gets its own state rather than counting as held, because an
 * organization reading a solid line as "handled" is exactly the error this
 * report exists to catch.
 *
 * **REQUIRED ROLES ARE COUNTED SEPARATELY FROM COVERAGE.** A role a managing
 * partner mandates and nobody holds puts an agreement at risk, not just a
 * stretch of trail, and the two numbers answer different questions. The
 * required list is derived from `OrgRole.required` and the holder counts the
 * caller passes - never from a hard-coded list of partner names.
 */

import { useState } from 'react'
import { AssistPanel } from '../AssistPanel'
import { PageHeader, SectionMap } from '../components'
import { formatDistance, type UnitSystem } from '../../lib/units'
import type { CoverageGap, OrgRole, OrgSection } from '../orgApi'

export interface CoverageProps {
  /** Every section the org publishes, for the map behind the gaps. */
  readonly sections: readonly OrgSection[]
  readonly gaps: readonly CoverageGap[]
  /** Sections held, but whose holder reports to a role nobody fills. */
  readonly supervisorVacant?: ReadonlySet<string>
  readonly sectionsTotal: number
  readonly regions: readonly string[]
  readonly region: string | null
  readonly roles: readonly OrgRole[]
  /** How many people hold each role, by role id. */
  readonly holders: Readonly<Record<string, number>>
  /** How many sections each role covers, by role id - for the required list. */
  readonly roleScope?: Readonly<Record<string, string>>
  readonly onRegion: (region: string | null) => void
  readonly onEditRegions?: () => void
  readonly onExport: (format: 'csv' | 'geojson') => void
  readonly slug: string
  readonly onBackToRoles: () => void
  /** The hiker's own choice, from Settings. Never assumed - #619. */
  readonly units: UnitSystem
}

export function Coverage({
  sections,
  gaps,
  supervisorVacant = new Set<string>(),
  sectionsTotal,
  regions,
  region,
  roles,
  holders,
  roleScope = {},
  onRegion,
  onEditRegions,
  onExport,
  slug,
  onBackToRoles,
  units,
}: CoverageProps) {
  const [selected, setSelected] = useState<string | null>(null)

  const gapIds = new Set(gaps.map((gap) => gap.section_id))
  const drawn = region
    ? sections.filter((section) => section.region === region)
    : sections

  const unfilled = roles.filter(
    (role) => role.required && role.retired_at === null && (holders[role.id] ?? 0) === 0,
  )

  return (
    <>
      <PageHeader
        eyebrow="Report · sections with no assigned role"
        title="Coverage gaps"
        sub={
          <>
            {gaps.length} of {sectionsTotal} sections{region ? ` in ${region}` : ''} have
            no role attached. Pick an area, or read the whole region at once.
          </>
        }
        glyph={
          <>
            <path d="M4 18 9 6l6 12 5-9" />
          </>
        }
      />

      <section className="org-panel">
        <div className="org-panel__head">
          <h2>Area</h2>
          {onEditRegions ? (
            <button type="button" className="org-link" onClick={onEditRegions}>
              Edit regions
            </button>
          ) : null}
        </div>
        <div className="org-chips">
          {regions.map((name) => (
            <button
              key={name}
              type="button"
              className="org-chip"
              aria-pressed={region === name}
              onClick={() => onRegion(name)}
            >
              {name}
            </button>
          ))}
          <button
            type="button"
            className="org-chip"
            aria-pressed={region === null}
            onClick={() => onRegion(null)}
          >
            Whole region
          </button>
        </div>
      </section>

      <div className="org-grid org-grid--two">
        <SectionMap
          sections={drawn}
          highlightId={selected}
          legend
          tone={(section) =>
            gapIds.has(section.id)
              ? 'gap'
              : supervisorVacant.has(section.id)
                ? 'vacant'
                : 'covered'
          }
          caption="Schematic until your GIS is published — the live report draws your own geometry."
        />

        <section className="org-panel">
          <div className="org-panel__head">
            <h2>Gaps here</h2>
            <span className="org-panel__count">{gaps.length}</span>
          </div>
          {gaps.length === 0 ? (
            <div className="org-callout" data-tone="good">
              <span>
                <strong>Every section here has somebody on it.</strong> True today — a
                hand-off next month makes it a question again, which is why this page is a
                report rather than a badge.
              </span>
            </div>
          ) : (
            <div className="org-stack">
              {gaps.map((gap) => {
                const vacant = supervisorVacant.has(gap.section_id)
                return (
                  <button
                    type="button"
                    className="org-card"
                    key={gap.section_id}
                    style={{ textAlign: 'left', cursor: 'pointer' }}
                    onClick={() =>
                      setSelected(selected === gap.section_id ? null : gap.section_id)
                    }
                  >
                    <div className="org-inline">
                      <span className="org-table__name">{gap.section_name}</span>
                      <span
                        className="org-pill"
                        data-tone={vacant ? 'waiting' : 'stopped'}
                        style={{ marginLeft: 'auto' }}
                      >
                        {vacant ? 'supervisor' : 'no role'}
                      </span>
                    </div>
                    <p className="org-mono">
                      {gap.trail_name ?? '(unnamed route)'}
                      {gap.miles === null ? '' : ` · ${formatDistance(gap.miles, units)}`}
                    </p>
                  </button>
                )
              })}
            </div>
          )}
          <p className="org-panel__note">
            Export as CSV or GeoJSON — the same shape your assignment loader already
            reads.
          </p>
          <div className="org-inline">
            <button
              type="button"
              className="org-btn org-btn--ghost org-btn--small"
              onClick={() => onExport('csv')}
            >
              CSV
            </button>
            <button
              type="button"
              className="org-btn org-btn--ghost org-btn--small"
              onClick={() => onExport('geojson')}
            >
              GeoJSON
            </button>
          </div>
        </section>
      </div>

      <section className="org-panel">
        <div className="org-panel__head">
          <h2>Required roles not filled</h2>
          <span className="org-panel__count">{unfilled.length}</span>
        </div>
        <p className="org-panel__note">
          Roles a managing partner mandates. These are the gaps that put your agreement at
          risk, not just your coverage.
        </p>
        {unfilled.length === 0 ? (
          <div className="org-callout" data-tone="good">
            <span>
              Every mandated role has somebody in it. Coverage above is a separate
              question — a section can have nobody on it while every required role is
              filled.
            </span>
          </div>
        ) : (
          <div className="org-card org-card--flush">
            <table className="org-table">
              <thead>
                <tr>
                  <th scope="col">Role</th>
                  <th scope="col">Required by</th>
                  <th scope="col">Where</th>
                </tr>
              </thead>
              <tbody>
                {unfilled.map((role) => (
                  <tr key={role.id}>
                    <td className="org-table__name">{role.name}</td>
                    <td>{role.required_by ?? 'your own rules'}</td>
                    <td>{roleScope[role.id] ?? 'whole trail'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <AssistPanel
        kind="coverage"
        slug={slug}
        title="Read the gaps with me"
        opening="It sees the same gap list you do, and nothing else about your organization. It can point at a pattern; it cannot attach a role, and would not be right to."
        placeholder="Which of these has been open longest?"
        context={[
          `${gaps.length} of ${sectionsTotal} sections have no role attached${region ? ` in ${region}` : ''}.`,
          ...gaps.map(
            (gap) =>
              `- ${gap.section_name}${gap.trail_name ? ` on ${gap.trail_name}` : ''}${gap.miles === null ? '' : `, ${gap.miles} miles`}`,
          ),
          unfilled.length === 0
            ? 'Every required role is filled.'
            : `Required roles nobody holds: ${unfilled.map((role) => role.name).join(', ')}.`,
        ].join('\n')}
      />

      <div className="org-inline">
        <button type="button" className="org-btn org-btn--ghost" onClick={onBackToRoles}>
          Back to roles
        </button>
      </div>
    </>
  )
}
