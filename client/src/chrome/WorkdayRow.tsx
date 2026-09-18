// One crew, wherever crews are listed (#1440, frames 14g, 14h, 14j, 14k).
//
// ONE ROW, FOUR SURFACES, and that is the whole reason this is a component
// rather than markup in `Today.tsx`: the crews out today, the filtered list,
// a calendar day's crews, and the two headings a walking hiker sees are four
// readings of one list, and the handoff's own rule for them is that they
// "cannot drift". A row drawn four times is four places for a club's name to
// stop being printed.
//
// WHAT THE ROW WILL NOT DO. It does not compute a distance, a date or a
// position - every one of those arrives as a finished string from
// `lib/workProjects.ts` (`workProjectDates`, `workdayAwayLine`,
// `crewOffWalkLine`, `crewWalkPositionLine`), so no surface can re-round a
// figure another surface printed. And it never invents a line: a crew with no
// capacity prints no capacity, a crew with no contact gets no link, and a
// crew the file never placed prints no distance rather than one measured from
// a coordinate nobody surveyed.
//
// THE LINK IS AN INTRODUCTION, NOT AN ENROLMENT (VOLUNTEERING.md): it is the
// club's own channel, and nothing here renders a roster claim of its own
// invention.

import { CrewContactLink } from './CrewContactLink'
import './volunteerRow.css'

export interface WorkdayRowProps {
  title: string
  /** Everything after the title, already formatted, in the order it reads:
   *  the club, then the dates, then whichever distance this surface measures.
   *  Joined with the middle dots here so the separator has one home. */
  meta: readonly string[]
  /**
   * What this app says about meeting them, when the surface has something to
   * say - the two hiking-mode headings do, the volunteer list does not.
   *
   * Kept separate from `description` below, and that separation is the point:
   * one is this app's sentence and the other is the club's own words, and
   * blending them would put phrasing in a club's mouth that it did not write.
   */
  lead?: string
  /** The club's own description of the work, or absent. */
  description?: string | null
  /** The club's own channel, or absent. */
  contact?: string | null
}

export function WorkdayRow({
  title,
  meta,
  lead,
  description = null,
  contact = null,
}: WorkdayRowProps) {
  return (
    <li className="workday-row">
      <p className="workday-row__title">{title}</p>
      <p className="workday-row__meta">
        {/* Keyed by position, not by the text: two parts CAN read the same
            ("today" beside a club called Today is silly but legal), and a
            duplicate key is a React warning about a list that never
            reorders. */}
        {meta.map((part, at) => (
          <span key={at}>
            {at > 0 && <span aria-hidden="true"> · </span>}
            {part}
          </span>
        ))}
      </p>
      {lead !== undefined && <p className="workday-row__lead">{lead}</p>}
      {description !== null && <p className="workday-row__description">{description}</p>}
      <CrewContactLink contact={contact} className="workday-row__contact" />
    </li>
  )
}
