/**
 * Stage 3: all three codeowners confirm the registry is accurate.
 *
 * **SIGNING OFF PUBLISHES NOTHING.** Three approvals produce a pull request
 * against the public repository; a person merging it is what reaches a phone,
 * and the next map build is what a hiker actually downloads. The screen says
 * that in as many words rather than leaving an organization to discover it -
 * "approved is not published" is the sentence the org home exists to keep
 * saying afterwards.
 *
 * **THE BLAZE MAPPING IS THEIRS TO CONFIRM.** `blaze_value_raw` is their own
 * string, exactly as their GIS spells it; `blaze_mapped` is what we can
 * render. Where we could not map one, the table shows a hatched swatch and
 * the string rather than a guessed colour: a blaze in a table is data, and a
 * wrong one puts somebody at the wrong junction.
 *
 * **TWO APPROVALS PUBLISH NOTHING.** The count is shown as a fraction rather
 * than a progress bar, because a bar at two-thirds reads like something that
 * is nearly done, and nearly-done is exactly what this is not.
 */

import { useState } from 'react'
import { PageHeader, RegistryTable, SectionMap } from '../components'
import { formatDistance, type UnitSystem } from '../../lib/units'
import type { Org, OrgPark, OrgSection } from '../orgApi'

export interface RegistrySignoffProps {
  readonly org: Org
  readonly registry: readonly OrgPark[]
  /** Who has confirmed, by person id. */
  readonly confirmed: ReadonlySet<string>
  /** Who is reading it now, by person id - shown as an honest in-between. */
  readonly reading?: ReadonlySet<string>
  readonly personId: string | null
  readonly approvalsRequired: number
  readonly onConfirm: () => void
  readonly onFlag: (note: string) => void
  readonly names?: Readonly<Record<string, string>>
  /** The hiker's own choice, from Settings. Never assumed - #619. */
  readonly units: UnitSystem
}

export function RegistrySignoff({
  org,
  registry,
  confirmed,
  reading = new Set<string>(),
  personId,
  approvalsRequired,
  onConfirm,
  onFlag,
  names = {},
  units,
}: RegistrySignoffProps) {
  const [flagging, setFlagging] = useState(false)
  const [note, setNote] = useState('')
  const [selected, setSelected] = useState<OrgSection | null>(null)

  const sections = registry.flatMap((park) =>
    park.trails.flatMap((trail) => trail.sections),
  )
  const blazes = new Map<string, string | null>()
  for (const park of registry) {
    for (const trail of park.trails) {
      if (trail.blaze_value_raw) blazes.set(trail.blaze_value_raw, trail.blaze_mapped)
    }
  }
  const unmapped = [...blazes.entries()].filter(([, mapped]) => mapped === null)
  const alreadyConfirmed = personId !== null && confirmed.has(personId)

  return (
    <>
      <PageHeader
        eyebrow={`Stage 3 of 3 · sign-off · ${confirmed.size} of ${approvalsRequired}`}
        title="All three admins confirm it is accurate"
        sub={
          <>
            This is exactly what hikers will see. Park or trail system, then trail, then
            section — a route with no name or blaze is fine, it just needs to be
            somewhere. Approve it, or flag a line and your note goes back with it.
          </>
        }
        glyph={
          <>
            <circle cx="12" cy="12" r="8.5" />
            <path d="m8.5 12 2.5 2.5 4.5-5" />
          </>
        }
      />

      <div className="org-grid org-grid--two">
        <RegistryTable
          parks={registry}
          selectedSectionId={selected?.id ?? null}
          onSelect={setSelected}
          footnote={`${sections.length} sections · click a row to isolate one`}
        />
        <div className="org-stack">
          <SectionMap
            sections={sections}
            highlightId={selected?.id ?? null}
            caption={
              selected
                ? `${selected.name} · ${selected.miles === null ? 'length unknown' : formatDistance(selected.miles, units)}`
                : `All ${sections.length} sections`
            }
          />

          <div className="org-card org-panel">
            <div className="org-panel__head">
              <h2>Blaze mapping</h2>
              <span className="org-panel__count">{blazes.size} of your own values</span>
            </div>
            <p className="org-panel__note">
              Your own strings on the left, what we can render on the right. This is yours
              to confirm rather than ours to assume — a blaze in a table is the colour of
              the paint on the tree.
            </p>
            <table className="org-table">
              <thead>
                <tr>
                  <th scope="col">Your value</th>
                  <th scope="col">What we draw</th>
                </tr>
              </thead>
              <tbody>
                {[...blazes.entries()].map(([raw, mapped]) => (
                  <tr key={raw}>
                    <td className="org-mono">{raw}</td>
                    <td>
                      {mapped ? (
                        <span className="org-pill" data-tone="done">
                          {mapped}
                        </span>
                      ) : (
                        <span className="org-pill" data-tone="waiting">
                          nothing yet — shown as the word
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {unmapped.length > 0 ? (
              <div className="org-callout" data-tone="warn">
                <span>
                  <strong>
                    {unmapped.length} of your blaze values have nothing we can draw.
                  </strong>{' '}
                  Those trails render with the word rather than a colour. We would rather
                  show nothing than guess — a wrong swatch is a hiker at the wrong
                  junction.
                </span>
              </div>
            ) : null}
          </div>
        </div>
      </div>

      <section className="org-card org-panel">
        <div className="org-panel__head">
          <h2>Sign-off</h2>
          <span className="org-panel__count">
            {confirmed.size} of {approvalsRequired}
          </span>
        </div>
        <div className="org-stack">
          {org.admins.map((seat) => {
            const isConfirmed = confirmed.has(seat.person_id)
            const isReading = !isConfirmed && reading.has(seat.person_id)
            return (
              <div className="org-inline" key={seat.id}>
                <span className="org-table__name">
                  {names[seat.person_id] ?? seat.person_id}
                </span>
                <span
                  className="org-pill"
                  data-tone={isConfirmed ? 'done' : isReading ? 'waiting' : 'quiet'}
                  style={{ marginLeft: 'auto' }}
                >
                  {isConfirmed ? 'confirmed' : isReading ? 'reading' : 'not started'}
                </span>
              </div>
            )
          })}
        </div>

        {flagging ? (
          <div className="org-stack">
            <label className="org-field">
              <span className="org-field__label">
                Which line, and what is wrong with it. Your note travels back with the
                proposal.
              </span>
              <textarea
                className="org-textarea"
                value={note}
                onChange={(event) => setNote(event.target.value)}
              />
            </label>
            <div className="org-inline">
              <button
                type="button"
                className="org-btn org-btn--small"
                onClick={() => {
                  onFlag(note)
                  setFlagging(false)
                  setNote('')
                }}
              >
                Send the note back
              </button>
              <button
                type="button"
                className="org-btn org-btn--ghost org-btn--small"
                onClick={() => setFlagging(false)}
              >
                Never mind
              </button>
            </div>
            <p className="org-mono">
              Flagging a line does not start the registry over. It comes back with your
              note attached and everything else stays where it is.
            </p>
          </div>
        ) : (
          <div className="org-inline">
            <button
              type="button"
              className="org-btn"
              disabled={alreadyConfirmed}
              onClick={onConfirm}
            >
              {alreadyConfirmed ? 'You have confirmed' : 'Confirm accurate'}
            </button>
            <button
              type="button"
              className="org-btn org-btn--ghost"
              onClick={() => setFlagging(true)}
            >
              Flag a line
            </button>
          </div>
        )}

        <div className="org-callout" data-tone="info">
          <span>
            <strong>Nothing publishes on two approvals.</strong> When all{' '}
            {approvalsRequired} agree we open a pull request against the public repository
            — a person merges it, and the next map build is what puts your sections on a
            phone. Sections stay editable afterwards: every change is dated rather than
            overwritten.
          </span>
        </div>
      </section>
    </>
  )
}
