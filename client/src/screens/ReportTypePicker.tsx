// Choosing what to report (WIREFRAMES.md §6).
//
// Five condition types in a grid, then a separate section for things about
// people holding one full-width card. WIREFRAMES.md calls that split out
// explicitly - "deliberately not icon buttons" - and it is right: reporting
// that someone followed you should not be one tap in a row of tiles next to
// litter. The heavier affordance sets the right expectation for the heavier
// form behind it.
//
// "Say thanks to a maintainer" is NOT built. WIREFRAMES.md's own Known
// Deviations #2 leaves it an open product and data-model question: it is not
// a condition report, has no hazard location, and does not fit the Report
// type enum as written. Shipping a guess would bake in the wrong shape and be
// far harder to walk back than the gap is to live with.

import type { ReportDraft } from '../lib/outbox'
import './reporting.css'

export type ReportTypeId = ReportDraft['type']

const CONDITION_TYPES: Array<{ id: ReportTypeId; label: string; glyph: string }> = [
  { id: 'blowdown', label: 'Blow down', glyph: '🪵' },
  { id: 'flooding', label: 'Flooding', glyph: '💧' },
  { id: 'trash', label: 'Trash', glyph: '🗑' },
  { id: 'shelter_repair', label: 'Shelter repair', glyph: '🔨' },
  { id: 'animals', label: 'Animals', glyph: '🐾' },
]

export interface ReportTypePickerProps {
  onPick: (type: ReportTypeId) => void
}

export function ReportTypePicker({ onPick }: ReportTypePickerProps) {
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
          </button>
        ))}
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
      </section>

      <p className="reporting__reassurance">
        Reading the map — water, shelters, closures, warnings — never needs an account.
      </p>
    </main>
  )
}
