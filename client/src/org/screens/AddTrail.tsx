/**
 * One new trail, not a new registry.
 *
 * **THE DIFF SHOWS ADDITIONS ONLY, AND THAT IS THE POINT OF THE SCREEN.** An
 * organization with 312 live sections adding a fourteenth trail is asking one
 * question - what changes? - and the answer they need is "nothing you already
 * publish". A screen that re-ran the whole registry would make an
 * organization read three hundred rows to find fourteen, and they would stop
 * doing it.
 *
 * **A TRAIL WITH NO MAINTAINER YET IS FINE.** It publishes, and the coverage
 * report shows its sections as gaps until roles are attached. Blocking the
 * publish on having somebody to hold it would mean a trail that exists on the
 * ground staying off the map because a volunteer has not been found - which
 * is backwards: hikers walk it either way.
 *
 * **ADDING SECTIONS NEEDS ALL THREE CODEOWNERS.** It changes the registry
 * files, so it is the three-approval path rather than the one-admin one. A
 * corrected privy note is a smaller edit and takes one. The screen says which
 * this is before the button rather than after.
 */

import { useState } from 'react'
import { AssistPanel } from '../AssistPanel'
import { formatDistance, type UnitSystem } from '../../lib/units'
import { PageHeader, RegistryTable, SectionMap } from '../components'
import type { OrgPark } from '../orgApi'

export interface AddTrailProps {
  readonly orgName: string
  /** What the org already publishes - untouched by anything here. */
  readonly liveSections: number
  /** The proposed trail, as a registry fragment, or null before one is read. */
  readonly proposed: readonly OrgPark[] | null
  readonly onRead: (pointer: string) => void
  readonly onPropose: () => void
  readonly onBack: () => void
  /** Junctions reused rather than duplicated, where the read found any. */
  readonly junctionsReused?: number
  readonly slug: string
  /** The hiker's own choice, from Settings. Never assumed - #619. */
  readonly units: UnitSystem
}

export function AddTrail({
  orgName,
  liveSections,
  proposed,
  onRead,
  onPropose,
  onBack,
  junctionsReused = 0,
  slug,
  units,
}: AddTrailProps) {
  const [pointer, setPointer] = useState('')

  const added = proposed
    ? proposed.flatMap((park) => park.trails.flatMap((trail) => trail.sections))
    : []
  const miles = added.reduce((total, section) => total + (section.miles ?? 0), 0)

  return (
    <>
      <PageHeader
        eyebrow="Manage the registry · add a trail"
        title="One new trail, not a new registry"
        sub={
          <>
            Your {liveSections} live sections stay exactly as they are. We read only what
            you point us at, and you get a diff of what would be <strong>added</strong> —
            nothing already published is touched.
          </>
        }
        glyph={
          <>
            <path d="M12 5v14M5 12h14" />
          </>
        }
      />

      <section className="org-card org-panel">
        <span className="org-eyebrow">Adding to an existing registry</span>
        <p className="org-panel__note">
          Which trail are we adding? Paste its layer URL, drop its files, or just tell us
          the name if it is already on your GIS server.
        </p>
        <div className="org-row">
          <label className="org-field">
            <span className="org-field__label">The layer, or the name</span>
            <input
              className="org-input"
              value={pointer}
              placeholder="Sterling Ridge — it's layer 4 on our server now"
              onChange={(event) => setPointer(event.target.value)}
            />
          </label>
          <button
            type="button"
            className="org-btn org-btn--small"
            disabled={!pointer.trim()}
            onClick={() => onRead(pointer.trim())}
          >
            Read it
          </button>
        </div>
        <p className="org-mono">
          Ends anchor to whatever you already publish. Where a new section shares an
          endpoint with an existing one, we anchor the junction to the point you already
          have rather than making a second one.
        </p>
      </section>

      {proposed === null ? (
        <div className="org-empty">
          <h3>Nothing read yet</h3>
          <p>
            Point us at a layer and we will come back with what is in it — how many
            sections, how many miles, and which of your existing junctions it touches.
          </p>
        </div>
      ) : (
        <>
          <section className="org-panel">
            <div className="org-panel__head">
              <h2>The diff</h2>
              <span className="org-panel__count">additions only</span>
            </div>
            <div className="org-grid org-grid--three">
              <div className="org-tile">
                <span className="org-tile__label">Sections added</span>
                <span className="org-tile__value">+{added.length}</span>
              </div>
              <div className="org-tile">
                <span className="org-tile__label">Miles added</span>
                <span className="org-tile__value">{formatDistance(miles, units)}</span>
              </div>
              <div className="org-tile">
                <span className="org-tile__label">Existing sections changed</span>
                <span className="org-tile__value">0</span>
                <span className="org-tile__meta">
                  and this screen has no way to make that number anything else
                </span>
              </div>
              <div className="org-tile">
                <span className="org-tile__label">Junctions reused</span>
                <span className="org-tile__value">{junctionsReused}</span>
                <span className="org-tile__meta">
                  anchored to points you already publish rather than duplicated
                </span>
              </div>
            </div>
          </section>

          <div className="org-grid org-grid--two">
            <RegistryTable
              parks={proposed}
              footnote={`${added.length} sections proposed`}
            />
            <SectionMap
              sections={added}
              caption={`${added.length} proposed sections · nothing live is drawn here`}
            />
          </div>

          <div className="org-callout" data-tone="info">
            <span>
              <strong>A trail with no maintainer yet is fine.</strong> It publishes, and
              the coverage report will show all {added.length} sections as gaps until you
              attach roles. Hikers walk it either way.
            </span>
          </div>

          <div className="org-callout" data-tone="warn">
            <span>
              <strong>Who has to approve this.</strong> Adding sections changes the
              registry files, so all three codeowners approve — the same as the first
              time. A smaller edit, like a corrected privy note, needs one admin.
            </span>
          </div>

          <div className="org-inline">
            <button type="button" className="org-btn" onClick={onPropose}>
              Propose these {added.length} sections
            </button>
            <button type="button" className="org-btn org-btn--ghost" onClick={onBack}>
              Back to org home
            </button>
          </div>
        </>
      )}

      <AssistPanel
        kind="addtrail"
        slug={slug}
        title="Adding to an existing registry"
        opening="It sees what you pointed us at and the count of what you already publish — never the 312 rows themselves. Nothing it says changes a section; the Propose button below is still the only thing that does."
        placeholder="It's layer 4 on our server now"
        context={
          proposed === null
            ? `${liveSections} sections already published. Nothing has been read yet.`
            : // THROUGH `formatDistance` EVEN THOUGH NOBODY READS THIS
              // DIRECTLY. It is the model's context, and the model's answer
              // is rendered on the screen beside it - so a context in miles
              // produces a suggestion in miles next to a table in
              // kilometres. The unit a hiker chose has to reach the whole
              // screen, not the visible half of it.
              `${liveSections} sections already published, untouched. Proposed: ${added.length} sections, ${formatDistance(miles, units)}, ${junctionsReused} junctions reused.`
        }
      />

      <p className="org-mono">Registry for {orgName}.</p>
    </>
  )
}
