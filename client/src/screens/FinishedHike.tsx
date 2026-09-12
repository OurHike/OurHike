// A finished hike, as it lives in Plan afterwards (#1317).
//
// A FINISHED HIKE IS STILL A HIKE. It keeps its sections, its miles and its
// dates, and it never leaves the list unless the hiker forgets it - which
// this screen says out loud, because "finished" in most apps means archived,
// greyed, or gone from the place it used to be. Here it means the walking is
// done and the record is not.
//
// EXPORT IS A COMMITMENT, AND NOT A DOOR ON THIS SCREEN. FEATURES.md's own
// line stands - the trail belongs to the trails, not to this app, and a hiker
// who wants their years of walking out of here in GPX or GeoJSON will get
// them, a section as a LineString along the centerline between its ends. But
// no writer exists yet (#1373, inventory P20: four frames draw export as
// shipped, and nothing in `client/src` writes a track), and until #1373 this
// screen offered an "Export it" door wired to a handler that did nothing. A
// refusal is a sentence, never a control that does nothing (#1373, D10) - so
// the door is absent until the writer lands, rather than present and dead.
// The commitment lives in FEATURES.md, where a promise belongs; a button is a
// claim that it is kept.

import type { UnitSystem } from '../lib/units'
import './plan.css'

export interface FinishedSection {
  id: string
  name: string
  /** `156.2 mi · 24,800 ft ↑`, or distance alone where this download cannot
   *  measure the whole stretch - the reason is said once on the screen rather
   *  than per row. No ≈time, deliberately, though the handoff's frame draws
   *  one: the hiker walked it, and the app's estimate of how long their own
   *  finished walk took is the app arguing with them about their afternoon
   *  (#982's rule, screens/WalkedHike.tsx). */
  figures: string
  /** `walked · 2024 · northbound`, or `walked · 2024 · recorded from memory`. */
  provenance: string
}

export interface FinishedHikeProps {
  hikeName: string
  /** `14 Mar 2024 – 12 Aug 2026 · 2,198.4 mi · 0 mi to go`. Zero, never
   *  "unknown": a finished hike has nothing left and says so. */
  header: string
  photo: string | null
  sections: readonly FinishedSection[]
  /** How many there are in total, when the list is showing fewer. */
  totalSections: number
  /** True when any section's figures are distance-only, so the reason is
   *  said once rather than on every row. Derived by the shell from the
   *  sections it built (#1373, inventory P31) - it was hard-coded false
   *  while every row printed distance alone. */
  someUnpriced: boolean
  units: UnitSystem
  onOpenSection: (id: string) => void
  onAllSections: () => void
  onShare: () => void
  onStartAnother: () => void
  onBack: () => void
}

export function FinishedHike({
  hikeName,
  header,
  photo,
  sections,
  totalSections,
  someUnpriced,
  onOpenSection,
  onAllSections,
  onShare,
  onStartAnother,
  onBack,
}: FinishedHikeProps) {
  return (
    <div className="finished-hike">
      <header className="plan-band plan-band--trips">
        <div className="plan-band__words">
          <span className="plan-band__eyebrow">finished hike</span>
          <h1 className="plan-band__word">{hikeName}</h1>
        </div>
        <button type="button" className="plan-band__switch" onClick={onBack}>
          Done
        </button>
      </header>

      <div className="finished-hike__body">
        <p className="finished-hike__header">{header}</p>

        {photo !== null && <img className="finished-hike__photo" src={photo} alt="" />}

        <section className="finished-hike__sections" aria-label="Sections in this hike">
          <div className="plan-home__section-head">
            <span className="plan-home__title">Sections</span>
            {totalSections > sections.length && (
              <button type="button" className="plan-home__all" onClick={onAllSections}>
                All {totalSections} ›
              </button>
            )}
          </div>
          {sections.map((section) => (
            <button
              type="button"
              className="plan-home__row"
              key={section.id}
              onClick={() => onOpenSection(section.id)}
            >
              <span className="plan-home__row-name">{section.name}</span>
              <span className="plan-home__meta">{section.figures}</span>
              <span className="plan-home__meta">{section.provenance}</span>
            </button>
          ))}
          {/* Said once rather than on every row: repeating it per section
              would make a download's limitation look like a property of each
              walk. */}
          {someUnpriced && (
            <p className="plan-home__refused">
              Some sections show distance alone — this download has no elevation profile
              for them, or a gap in it there.
            </p>
          )}
        </section>

        <button type="button" className="plan-kind__door" onClick={onShare}>
          <span className="plan-kind__door-name">Share it with someone</span>
          <span className="plan-kind__door-note">
            A hiker you&rsquo;re connected to, or a plain-text card for anyone.
          </span>
        </button>
        <button type="button" className="plan-kind__door" onClick={onStartAnother}>
          <span className="plan-kind__door-name">Start another long hike</span>
          <span className="plan-kind__door-note">This one stays exactly as it is.</span>
        </button>

        <p className="finished-hike__closing">
          A finished hike is still a hike: it keeps its sections, its miles and its dates,
          and it never leaves the list unless you forget it.
        </p>
      </div>
    </div>
  )
}
