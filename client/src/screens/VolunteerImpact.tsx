// "What you've put back" - the impact panel (wireframe 2e frame 2, #969).
//
// The reasoning that decides what may and may not appear here is in
// lib/volunteerImpact.ts, next to the code that enforces it. What this file
// owns is the two things a component can get wrong on its own:
//
// IT DOES NOT RENDER AT ALL WITH NOTHING TO SHOW. An empty panel headed "what
// you've put back" is the most pointed lack-state this screen could draw, and
// VOLUNTEERING.md §5's rule 2 is that it "shows what happened, it never shows
// what did not". Nothing logged means no panel - not a panel of dashes.
//
// AND THE OFF SWITCH IS PART OF THE FEATURE, not a setting somewhere else.
// #969: the guardrail "targets comparison and pressure, not memory", and the
// switch is what makes memory a claim the hiker can check rather than one the
// app makes about itself. It sits under the panel it turns off, because a
// control for this that lived in Settings would be one a hiker reading the
// panel could not find.

import {
  impactTiles,
  IMPACT_NOT_COUNTED,
  IMPACT_SUBTITLE,
  IMPACT_TITLE,
} from '../lib/volunteerImpact'
import type { VolunteerHoursSummary } from '../lib/volunteerHours'

export interface VolunteerImpactProps {
  /** The same logbook chrome/VolunteerHours.tsx renders - the backend's
   *  records plus this phone's unsent ones, merged by the shell. */
  records: readonly VolunteerHoursSummary[] | null
  /** The hiker's own switch (`impact_panel_shown`). Off hides the panel and
   *  keeps every record: this turns off a DISPLAY, never a logbook. */
  shown: boolean
  onToggleShown: (next: boolean) => void
}

export function VolunteerImpact({ records, shown, onToggleShown }: VolunteerImpactProps) {
  const tiles = impactTiles(records)
  if (tiles.length === 0) return null

  return (
    <section className="volunteer__section" aria-labelledby="volunteer-impact">
      <h2 id="volunteer-impact" className="volunteer__heading">
        {IMPACT_TITLE}
      </h2>
      <p className="volunteer__note volunteer__impact-promise">{IMPACT_SUBTITLE}</p>

      {shown ? (
        <>
          {/* A list rather than a grid of divs: these are items of a record,
              and a screen reader should be able to count them. No total across
              them and nowhere to put one - rule 4's "no single composite
              score", which is a fact about this markup and not only about the
              arithmetic above it. */}
          <ul className="volunteer__impact-tiles" data-testid="impact-tiles">
            {tiles.map((tile) => (
              <li key={tile.label} className="volunteer__impact-tile">
                <span className="volunteer__impact-value">{tile.value}</span>
                <span className="volunteer__impact-label">{tile.label}</span>
                {/* Inside the tile, because the qualifier belongs to the
                    number: #761's rule is that the state always travels where
                    the number does, and a "not yet confirmed" note that sat
                    below the grid would qualify all of them or none. */}
                {tile.caveat !== undefined && (
                  <span className="volunteer__impact-caveat">{tile.caveat}</span>
                )}
              </li>
            ))}
          </ul>

          <p className="volunteer__note">{IMPACT_NOT_COUNTED}</p>
        </>
      ) : (
        // What an off panel says, and what it must not say. Not "you have
        // hidden 11.5 hours" - putting the number in the sentence that hides
        // it would make the switch decorative. This states the promise instead:
        // the record is still yours, and this is a display.
        <p className="volunteer__note" data-testid="impact-off">
          Hidden. Your hours are still logged, still exportable, and still yours — this
          only turns off the summary.
        </p>
      )}

      <label className="volunteer__toggle">
        <input
          type="checkbox"
          name="impact_panel_shown"
          checked={shown}
          onChange={(event) => onToggleShown(event.target.checked)}
        />
        <span className="volunteer__toggle-label">Show what I’ve put back</span>
      </label>
    </section>
  )
}
