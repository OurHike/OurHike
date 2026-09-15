// A month of crews, with the published window's edge drawn on it (#1440,
// D21, frame 14j).
//
// WHY A CALENDAR NEEDED DESIGNING RATHER THAN DROPPING IN. A month grid shows
// days the published file was never asked about, and an empty cell out there
// reads as "no crew that day" when the truth is "nobody has said". Those are
// opposite statements about the trail's people, so the horizon is drawn:
// hatching past today + WORK_PROJECT_WINDOW_DAYS.
//
// And the past is a THIRD kind of nothing, greyed rather than hatched,
// because it is over rather than unknown. Two absences, two treatments, and a
// grid that can tell a reader which one they are looking at.
//
// A DOT IS NEVER A COUNT. Two dots means two crews and three means three, and
// past MAX_DAY_DOTS it stops adding them rather than turning a day into a
// score - the guardrail four docs share and the reason nothing in this app
// totals a hiker's anything.

import { MAX_DAY_DOTS, type WorkdayCalendarMonth } from '../lib/workProjects'
import './workdayCalendar.css'

/** Monday first, because a weekend reads as one block that way rather than
 *  being split across the two ends of the row - and the weekend is what a
 *  hiker scanning this grid is looking for. */
const COLUMNS = ['M', 'T', 'W', 'T', 'F', 'S', 'S']

export interface WorkdayCalendarProps {
  month: WorkdayCalendarMonth
  /** Which day is open below the grid, as "YYYY-MM-DD", or null. */
  selected: string | null
  onSelect: (date: string | null) => void
}

export function WorkdayCalendar({ month, selected, onSelect }: WorkdayCalendarProps) {
  const heading = month.first.toLocaleDateString('en-US', {
    month: 'long',
    year: 'numeric',
    timeZone: 'UTC',
  })

  return (
    <div className="workday-calendar">
      <p className="workday-calendar__month">{heading}</p>
      <div
        className="workday-calendar__grid"
        role="grid"
        aria-label={`Crews in ${heading}`}
      >
        {COLUMNS.map((letter, at) => (
          <span key={at} className="workday-calendar__column" aria-hidden="true">
            {letter}
          </span>
        ))}
        {Array.from({ length: month.blanks }, (_, at) => (
          <span key={`blank-${at}`} className="workday-calendar__blank" />
        ))}
        {month.cells.map((cell) => {
          const dots = Math.min(cell.crews.length, MAX_DAY_DOTS)
          const classes = [
            'workday-calendar__day',
            `workday-calendar__day--${cell.state}`,
            cell.weekend ? 'workday-calendar__day--weekend' : '',
            cell.date === selected ? 'workday-calendar__day--open' : '',
          ]
            .filter(Boolean)
            .join(' ')

          return (
            <button
              key={cell.date}
              type="button"
              className={classes}
              // The accessible name carries what the dots say, because a row
              // of decorative dots says nothing to a screen reader - and the
              // cap is stated rather than hidden, so "4 or more" is never
              // read back as exactly four.
              aria-label={
                cell.crews.length === 0
                  ? `${cell.dayOfMonth}, no crew posted`
                  : `${cell.dayOfMonth}, ${cell.crews.length} ${cell.crews.length === 1 ? 'crew' : 'crews'}`
              }
              aria-pressed={cell.date === selected}
              onClick={() => onSelect(cell.date === selected ? null : cell.date)}
            >
              <span className="workday-calendar__number" aria-hidden="true">
                {cell.dayOfMonth}
              </span>
              <span className="workday-calendar__dots" aria-hidden="true">
                {Array.from({ length: dots }, (_, at) => (
                  <span key={at} className="workday-calendar__dot" />
                ))}
              </span>
            </button>
          )
        })}
      </div>
      {/* The legend is not decoration here: hatching and grey are two
          different kinds of nothing, and a grid that does not say which is
          which has not solved the problem it was drawn for. */}
      <ul className="workday-calendar__legend">
        <li>
          <span className="workday-calendar__key workday-calendar__key--dot" /> a crew
          that day
        </li>
        <li>
          <span className="workday-calendar__key workday-calendar__key--beyond" /> beyond
          the published window
        </li>
        <li>
          <span className="workday-calendar__key workday-calendar__key--past" /> already
          gone
        </li>
      </ul>
    </div>
  )
}
