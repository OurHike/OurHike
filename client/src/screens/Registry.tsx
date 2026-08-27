// The org console, read-only: every registered source as a table (#929).
//
// features/SOURCE_REGISTRY.md's admin half, frame `1m`, and the maintainer's
// scope call of 2026-08-27: the table first, so the features around it can be
// decided by somebody looking at the real registry rather than at a design.
//
// THE RULE THE WHOLE SCREEN IS BUILT AROUND, and it holds here structurally
// rather than by anybody's discipline: NOTHING HERE CHANGES A HIKER'S MAP.
// There is no control on this screen, no endpoint behind it and no state in
// it. Approving a source is a `pipeline/sources.json` diff in a pull request
// somebody merges, which is what makes an admin console safe to give an
// outside organization a seat in one day. This build gives nobody a seat; it
// shows the maintainer what is registered.
//
// WHAT IT DELIBERATELY DOES NOT DO, so the gap is a decision rather than an
// oversight:
//
//  - It composes nothing. Every cell is a field `pipeline/export_sources.py`
//    copied out of the registry. A "health" score or a "seems well licensed"
//    verdict would be this screen's opinion wearing the registry's authority,
//    which is the failure CLAUDE.md's evidence standard exists to prevent.
//  - It has no probe, no quarantine and no contact tiers. Those are frames
//    `1n`-`1p` and they need the backend #600 owns.
//  - It is desktop-shaped and says so rather than folding an eight-column
//    table into 390px. Frame `1p` is the phone answer and it is triage, which
//    is a different screen rather than this one made narrow.

import { useEffect, useState } from 'react'
import './settings.css'
import {
  byOrganization,
  fetchRegistry,
  type RegisteredSource,
  type SourceRegistry,
} from '../lib/registry'

export interface RegistryProps {
  onClose: () => void
  /** Injected by the tests. Production passes nothing and the screen fetches. */
  load?: () => Promise<SourceRegistry | null>
}

/** What each `licence_basis` word means on screen. The registry's own three,
 *  spelled out because "maintainer" is the one a reader would otherwise
 *  assume is a grant from the organization, and it is the opposite of one. */
const LICENCE_BASIS: Record<string, string> = {
  stated_by_org: 'Their terms',
  maintainer_authorisation: 'Your call',
  unresolved: 'Unanswered',
}

/** Which of three tints a `licence_basis` gets. THREE, not two: an
 *  `unresolved` registration is not the maintainer's call, it is nobody's yet,
 *  and painting it in the same colour as a decision somebody made would be
 *  this screen agreeing with itself rather than with the registry. */
function basisTone(basis: string | null): 'stated' | 'ours' | 'open' {
  if (basis === 'stated_by_org') return 'stated'
  if (basis === 'maintainer_authorisation') return 'ours'
  return 'open'
}

function Row({ source }: { source: RegisteredSource }) {
  return (
    <tr className="registry__row">
      <td className="registry__key">{source.key}</td>
      <td>{source.title ?? <span className="registry__gap">no title</span>}</td>
      {/* Null is the answer for twelve of the thirty-three, and it is a real
          one: `lib/source_registry.py` reads an absent kind as an ArcGIS
          feature layer, which is a fact about the fetcher rather than about
          the registration. Filling it in here would hide exactly the rows a
          probe could not describe. */}
      <td>{source.kind ?? <span className="registry__gap">not declared</span>}</td>
      <td>{source.trust ?? <span className="registry__gap">none</span>}</td>
      <td>
        <span
          className={`registry__pill registry__pill--${basisTone(source.licence_basis)}`}
        >
          {LICENCE_BASIS[source.licence_basis ?? ''] ?? 'Not recorded'}
        </span>
      </td>
      <td>
        {source.reaches_hikers ? (
          'Ships'
        ) : (
          <span className="registry__gap">Held back</span>
        )}
      </td>
      <td>{source.freshness_kind ?? <span className="registry__gap">no marker</span>}</td>
    </tr>
  )
}

export function Registry({ onClose, load = fetchRegistry }: RegistryProps) {
  // Three states, not two. `undefined` is "still asking", `null` is "could not
  // ask", and a registry is an answer. A screen that rendered the second as an
  // empty table would say nothing is registered on the evidence that the phone
  // is offline.
  const [registry, setRegistry] = useState<SourceRegistry | null | undefined>(undefined)

  useEffect(() => {
    let cancelled = false
    void load().then((value) => {
      if (!cancelled) setRegistry(value)
    })
    return () => {
      cancelled = true
    }
  }, [load])

  const groups = registry ? byOrganization(registry) : []
  const shipping = registry?.sources.filter((source) => source.reaches_hikers).length ?? 0
  // COUNTED ON THE VALUE, NOT ON THE ABSENCE OF THE OTHER ONE. There are three
  // bases, and `!stated_by_org` quietly folds `unresolved` in with
  // `maintainer_authorisation` - which printed "27 ship on your own
  // authorisation" over a set including GATC, whose terms nobody has answered
  // and whose data ships nowhere. A sentence claiming a decision the
  // maintainer never made is the display-outrunning-its-source failure, on the
  // one screen whose whole job is saying what rests on what.
  const ourCall =
    registry?.sources.filter((s) => s.licence_basis === 'maintainer_authorisation')
      .length ?? 0
  const unanswered =
    registry?.sources.filter((s) => s.licence_basis === 'unresolved').length ?? 0

  return (
    <div className="registry" role="dialog" aria-label="The source registry">
      <div className="legend__head">
        <h2 className="legend__title">Sources</h2>
        <button type="button" className="legend__close" onClick={onClose}>
          <span className="visually-hidden">Close</span>
          <span aria-hidden="true">×</span>
        </button>
      </div>

      <p className="registry__note" role="note">
        Read only. Nothing on this screen changes what is on a hiker&rsquo;s phone &mdash;
        a source reaches one by a change to <code>pipeline/sources.json</code> that
        somebody merges.
      </p>

      {registry === undefined && <p className="registry__state">Reading the registry…</p>}

      {registry === null && (
        // "We could not ask" and "nothing is registered" are different claims,
        // and this screen can only honestly make the first one here.
        <p className="registry__state">
          OurHike couldn&rsquo;t read the registry. It is fetched rather than carried
          offline, so this needs a connection.
        </p>
      )}

      {registry !== null && registry !== undefined && (
        <>
          <p className="registry__counts">
            <strong>{registry.sources.length}</strong> registered sources across{' '}
            <strong>{groups.length}</strong> organizations · <strong>{shipping}</strong>{' '}
            reach a hiker · <strong>{ourCall}</strong> ship on your own authorisation
            rather than the organization&rsquo;s stated terms
            {unanswered > 0 && (
              <>
                {' '}
                · <strong>{unanswered}</strong> waiting on an answer
              </>
            )}
          </p>

          {groups.map(({ provider, org, sources }) => (
            <section className="registry__org" key={provider}>
              <h3 className="registry__org-name">
                {org?.name ?? provider}
                {/* The empty mark slot, on every organization, because none of
                    them has licensed one. #933: an organization's identity is
                    the one thing in this app that must not be approximated,
                    and a visibly empty slot is also the thing most likely to
                    prompt somebody to go and ask. */}
                <span className="registry__mark" aria-label="No licensed mark">
                  no mark
                </span>
              </h3>
              <p className="registry__org-meta">
                <code>{org?.steward_id ?? provider}</code> ·{' '}
                {sources.length === 1 ? '1 source' : `${sources.length} sources`}
              </p>
              {org?.note !== null && org?.note !== undefined && (
                <p className="registry__org-note">{org.note}</p>
              )}

              <div className="registry__scroll">
                <table className="registry__table">
                  <thead>
                    <tr>
                      <th scope="col">Key</th>
                      <th scope="col">Layer</th>
                      <th scope="col">Kind</th>
                      <th scope="col">Trust</th>
                      <th scope="col">Licence rests on</th>
                      <th scope="col">Reaches a hiker</th>
                      <th scope="col">Freshness</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sources.map((source) => (
                      <Row key={source.key} source={source} />
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          ))}

          {registry.sources.length === 0 && (
            <p className="registry__state">This release carries no registry.</p>
          )}
        </>
      )}
    </div>
  )
}
