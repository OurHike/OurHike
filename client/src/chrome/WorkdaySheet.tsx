// The sheet behind a workday pin (#760, features/VOLUNTEERING.md Phase B).
//
// This is the half the pin was waiting for. A pin with nothing behind it is
// decoration, and decoration a hiker might drive to a trailhead for is worse
// than no pin at all - which is why the map half of #760 was deliberately left
// out of the branch that shipped the list.
//
// Everything it renders comes from the same `WorkProjectSummary` the Volunteer
// tab lists, and the wording is deliberately the tab's wording. Two surfaces
// describing the same workday in different words is a hiker reading two
// claims where there is one.
//
// WHAT IT WILL NOT SAY
//
// **Nothing here signs anybody up, and nothing implies a place is held.**
// VOLUNTEERING.md is explicit that a signup is an introduction and never an
// enrolment - real workdays carry waivers, minimum ages, tool training and
// ATC registration, and "the app must never leave someone believing they are
// on a roster when they are not". Phase B has no write path at all, so the
// only action here is the club's own contact channel, labelled as asking
// rather than as joining.
//
// **No distance is invented.** A row the reviewed file could not place on the
// mile axis has no "trail mi away" line, rather than one measured from a
// coordinate that was never surveyed against the centerline.

import { workProjectDates, type WorkProjectSummary } from '../lib/workProjects'

export interface WorkdaySheetProps {
  project: WorkProjectSummary
  /** The hiker's own trail mile, or null - only used to say how far away
   *  this is, and only when the project has a mile of its own. */
  gpsMile: number | null
  onClose: () => void
}

export function WorkdaySheet({ project, gpsMile, onClose }: WorkdaySheetProps) {
  const away =
    project.mile !== null && gpsMile !== null
      ? `${Math.abs(project.mile - gpsMile).toLocaleString('en-US', {
          maximumFractionDigits: 1,
        })} trail mi away`
      : null

  return (
    <div className="closure-sheet" role="dialog" aria-label="Volunteer workday">
      <div className="legend__head">
        <h2 className="legend__title">{project.title}</h2>
        <button type="button" className="legend__close" onClick={onClose}>
          <span className="visually-hidden">Close</span>
          <span aria-hidden="true">×</span>
        </button>
      </div>

      <p className="closure-sheet__status">{workProjectDates(project)}</p>

      <p className="closure-sheet__range">
        {project.club_name}
        {away !== null && (
          <>
            <span aria-hidden="true"> · </span>
            {away}
          </>
        )}
        {project.capacity !== null && (
          <>
            <span aria-hidden="true"> · </span>
            {`room for ${project.capacity}`}
          </>
        )}
      </p>

      {project.description !== null && (
        <p className="closure-sheet__meta">{project.description}</p>
      )}

      {/* The club's own channel. An introduction, never an enrolment - and
          the app renders no confirmation of its own invention, because it
          has none to render: Phase B is read-only. */}
      {project.signup_contact !== null && (
        <a className="closure-sheet__link" href={project.signup_contact}>
          Ask the crew about joining
        </a>
      )}

      <p className="closure-sheet__meta">
        Posted by the club. Check with them before travelling — a workday can be called
        off after this was written.
      </p>
    </div>
  )
}
