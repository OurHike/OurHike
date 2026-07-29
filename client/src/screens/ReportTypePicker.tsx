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
    </main>
  )
}
