// Choosing what to report (WIREFRAMES.md §6).
//
// Five condition types in a grid, then a separate section for things about
// people holding one full-width card. WIREFRAMES.md calls that split out
// explicitly - "deliberately not icon buttons" - and it is right: reporting
// that someone followed you should not be one tap in a row of tiles next to
// litter. The heavier affordance sets the right expectation for the heavier
// form behind it.
//
// "Say thanks to a maintainer" sits in that same people section, decided
// 2026-07-29 (features/SAYING_THANKS.md, resolving WIREFRAMES.md's Known
// Deviations #2): a thanks is a comment about a specific place, so it is the
// seventh report type. It is deliberately not a sixth condition tile - it is
// not a trail condition, and it belongs beside the other card that is about
// people rather than about the trail.

import type { ReportDraft } from '../lib/outbox'
import './reporting.css'

export type ReportTypeId = ReportDraft['type']

const CONDITION_TYPES: Array<{
  id: ReportTypeId
  label: string
  glyph: string
  /** Only where a tile needs telling apart from its neighbour. */
  hint?: string
}> = [
  { id: 'blowdown', label: 'Blow down', glyph: '🪵' },
  { id: 'flooding', label: 'Flooding', glyph: '💧' },
  { id: 'trash', label: 'Trash', glyph: '🗑' },
  { id: 'shelter_repair', label: 'Shelter repair', glyph: '🔨' },
  // The two below genuinely overlap - a feral hog is both - so each carries a
  // hint. The distinction has to be legible where someone is choosing, not in
  // a data dictionary nobody reads.
  {
    id: 'animals',
    label: 'Animals',
    glyph: '🐾',
    hint: 'Sightings, food raids, anything aggressive',
  },
  {
    id: 'invasive_species',
    label: 'Invasive species',
    glyph: '🌿',
    hint: "Plants or pests that shouldn't be here",
  },
]

export interface ReportTypePickerProps {
  onPick: (type: ReportTypeId) => void
  /**
   * The closure path (#832), which is deliberately not a `ReportTypeId`.
   *
   * A closure is a stretch with two ends and its own table, not an eighth
   * report type - so it gets its own callback rather than being smuggled
   * through `onPick`'s type. It sits under the condition tiles rather than
   * among them for the reason the people section is separate: a tile in
   * that grid promises the form behind it is the one-tap form its
   * neighbours are, and this one asks for two miles.
   */
  onReportClosure: () => void
  /**
   * Backing out. Required, not optional: the reporting flow replaces the whole
   * shell including the tab bar (App.tsx), so a screen here with no way out is
   * one a hiker is stuck on - and someone who opened this to look at the
   * choices, or opened it by accident, has to be able to leave without filing
   * a report to escape.
   */
  onCancel: () => void
}

export function ReportTypePicker({
  onPick,
  onReportClosure,
  onCancel,
}: ReportTypePickerProps) {
  return (
    <main className="reporting">
      <h1 className="reporting__title">Report a problem</h1>

      <section className="reporting__grid" role="group" aria-label="Trail conditions">
        {CONDITION_TYPES.map((type) => (
          <button
            key={type.id}
            type="button"
            className="reporting__tile"
            onClick={() => onPick(type.id)}
          >
            <span aria-hidden="true" className="reporting__tile-glyph">
              {type.glyph}
            </span>
            <span>{type.label}</span>
            {type.hint !== undefined && (
              <span className="reporting__tile-hint">{type.hint}</span>
            )}
          </button>
        ))}
      </section>

      <section className="reporting__people" role="group" aria-label="The trail is shut">
        <button type="button" className="reporting__card" onClick={onReportClosure}>
          <span className="reporting__card-title">The trail is closed</span>
          <span className="reporting__card-body">
            A stretch nobody can walk — a washout, a slide, a club&rsquo;s own closure
            sign. Needs the miles it runs between, so it asks a little more than the tiles
            above.
          </span>
        </button>
      </section>

      <section
        className="reporting__people"
        role="group"
        aria-label="About people on the trail"
      >
        <h2 className="reporting__subtitle">About people on the trail</h2>

        <button
          type="button"
          className="reporting__card reporting__card--unsafe"
          onClick={() => onPick('bad_hikers')}
        >
          <span className="reporting__card-title">Something unsafe happened</span>
          <span className="reporting__card-body">
            Threats, robbery, being followed. Private to club moderators — never a public
            pin with anyone&rsquo;s name on it.
          </span>
        </button>

        {/* Stated before the tap, not after: someone in trouble right now needs
            to know this is the wrong tool before they spend time on a form. */}
        <p className="reporting__limit" role="note">
          Call 911 if you are in danger now. This reaches volunteers, sometimes days
          later.
        </p>

        <button
          type="button"
          className="reporting__card reporting__card--thanks"
          onClick={() => onPick('thanks')}
        >
          <span className="reporting__card-title">Say thanks to a maintainer</span>
          <span className="reporting__card-body">
            Someone looks after this stretch. If you don&rsquo;t know who, we&rsquo;ll
            work it out from where you are.
          </span>
        </button>
      </section>

      <p className="reporting__reassurance">
        Reading the map — water, shelters, closures, warnings — never needs an account.
      </p>

      {/* Bottom, and secondary, exactly as on the form behind it: the way out
          of the flow should be in the same place at both steps. */}
      <div className="reporting__actions">
        <button type="button" className="reporting__secondary" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </main>
  )
}
