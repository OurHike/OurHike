// Report a bug, at the foot of Settings (#626).
//
// Its own file rather than more rows in Settings.tsx, for the reason
// AboutBuild.tsx gives above it and BRANCHING.md gives about App.tsx: a screen
// everything is appended to becomes the file every branch collides in.
//
// DIRECTLY BELOW "ABOUT THIS BUILD", WHICH IS THE POINT. That section ends by
// saying the build is worth quoting if you report a problem with the app - and
// until this existed, it was directions for a journey the app never described.
// The three rows above are now also the thing these links carry for you
// (lib/bugReport.ts), so the pairing is mechanical and not only editorial.
//
// THE FIRST JOB IS NOT CATCHING TRAIL REPORTS. "Report a bug" sits one word
// away from "Report a problem", which is the in-app flow a blowdown goes
// through and the one a moderator actually reads. CONTRIBUTING.md, the README
// and the header of every issue form all say nobody watches GitHub for a
// washed-out crossing; a bug link in Settings is precisely where somebody
// would test that. So the steer comes before the options rather than under
// them, and it names the flow that IS right rather than only refusing this one.
//
// WHY THE INVITATION IS HERE AND NOT IN A DOC NOBODY OPENS. This project is
// built to be handed to the clubs that maintain the trails rather than owned
// by whoever wrote it (README.md, CONTRIBUTING.md). Somebody who has read
// enough of the app to file a good bug report is the closest thing to a next
// maintainer this screen will ever meet, and the moment they have gone looking
// for where to report it is the one moment they are already pointed at the
// repository.

import {
  BUG_REPORT_OPTIONS,
  bugReportUrl,
  CONTRIBUTING_URL,
  GOOD_FIRST_ISSUE_URL,
} from '../lib/bugReport'
import { BUILD_INFO, type BuildInfo } from '../lib/buildInfo'

export interface ReportBugProps {
  /**
   * Which build the report will name. Defaults to the real one, and is
   * injectable for the reason AboutBuild.tsx gives - the real value is a live
   * commit, so a test asserting on it would be asserting on when it ran.
   */
  build?: BuildInfo
}

export function ReportBug({ build = BUILD_INFO }: ReportBugProps) {
  return (
    <section className="settings__group">
      <h2 className="settings__heading">Report a bug</h2>

      {/* Before the options, not after them. Somebody who has already tapped
          has already gone to the wrong place. */}
      <p className="settings__note">
        Something you found out on the trail — a blowdown, a dry spring, a shelter that
        has been damaged — is not a bug. That goes through <b>Report a problem</b>, where
        a moderator sees it and can act on it. Nobody is watching the issue tracker for
        those.
      </p>

      <div className="settings__links">
        {BUG_REPORT_OPTIONS.map((option) => (
          <a
            key={option.id}
            className="settings__link"
            href={bugReportUrl(option, build)}
            target="_blank"
            rel="noreferrer"
          >
            {option.label}
            <span className="settings__link-hint">{option.hint}</span>
          </a>
        ))}
      </div>

      {/* Said plainly, because this app is used where there is no signal and
          these four links are the one part of Settings that cannot work there.
          A dead tab on a ridge costs somebody the thought they walked up with,
          so the note says what to do instead - and what to do is read the
          three rows immediately above, which is where the copy button is. */}
      <p className="settings__note">
        Each of these opens GitHub in your browser, so they need signal. Out of range,
        write down what happened while you can still see it — the build details above are
        the part worth copying.
      </p>

      <p className="settings__note">
        OurHike is open source, and built to be handed to the clubs that maintain the
        trail rather than owned by whoever wrote it. If you write code, you are welcome to
        fix what you found —{' '}
        <a href={CONTRIBUTING_URL} target="_blank" rel="noreferrer">
          how the project works
        </a>
        , and{' '}
        <a href={GOOD_FIRST_ISSUE_URL} target="_blank" rel="noreferrer">
          somewhere to start
        </a>
        .
      </p>
    </section>
  )
}
