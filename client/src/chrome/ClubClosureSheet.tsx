// The sheet over a club closure tapped on the map (the maintainer's S6, poll
// of 2026-10-11: "same sheet as its list row").
//
// THE ROW IS THE PLANNED-HIKE LIST'S OWN. A row of "Notices for your planned
// hikes" opens nothing - it is a list item with its organization's link - so
// the sheet is that row, chrome/PlannedNoticeList.tsx's NoticeRow, for the
// tapped notice: its tag ("Closure", or "Starts Oct 20" until its own start),
// its title, the source's own category, where and when, the organization and
// its date, and its page. A hiker who meets the same closure in the list and
// on the map reads the same words, and the two cannot drift apart.
//
// IN THE CLOSING ORGANIZATION'S VOICE, as #1142 taught the tapped-line sheet
// to speak a temporary closure: the organization's name comes from the
// registry on the row (lib/notices.ts's noticeOrgLabel), and the note under
// it is chrome/OrgNoticeSheet.tsx's, which says the closure is theirs and not
// OurHike's, that OurHike has not checked the trail, and that it works out no
// detour. The route a hiker builds still goes through the closure (the
// maintainer's Q2 answer, 2026-10-11), so that last sentence is load-bearing.
//
// A CLOSURE THAT MAY NO LONGER APPLY SAYS SO HERE AND ONLY HERE. The map
// draws it with the same full mark (the maintainer chose "B: same mark" over
// fading it); its row greys and carries lib/noticeCurrency.ts's line, "Last
// reported March 5, 2026. It may no longer apply.", as it does in the list.

import { longDate } from '../lib/atcNoticeText'
import { noticeOrgLabel } from '../lib/notices'
import type { TrailClosure } from '../lib/publishedConditions'
import { possessive, type Stewards } from '../lib/stewards'
import { NoticeRow } from './PlannedNoticeList'

export interface ClubClosureSheetProps {
  notice: TrailClosure
  stewards: Stewards
  /** The phone's own calendar day (lib/passedToday.ts's `localDay`), which
   *  the notice's start and `current_until` are read against. */
  today: string
  /** When conditions/trail_closures.json was baked, for the age line. */
  generatedAt: Date | null
  onClose: () => void
}

export function ClubClosureSheet({
  notice,
  stewards,
  today,
  generatedAt,
  onClose,
}: ClubClosureSheetProps) {
  const org = noticeOrgLabel(stewards)(notice)
  const orgs = possessive(org)

  return (
    <div className="closure-sheet" role="dialog" aria-label="Closure notice">
      <div className="legend__head">
        <h2 className="legend__title">Closure notice</h2>
        <button type="button" className="legend__close" onClick={onClose}>
          <span className="visually-hidden">Close</span>
          <span aria-hidden="true">×</span>
        </button>
      </div>

      <ul className="atc-notices__list">
        <NoticeRow notice={notice} org={org} today={today} />
      </ul>

      <p className="closure-sheet__limit" role="note">
        This is {orgs} notice, not OurHike&rsquo;s. OurHike has not checked the trail
        itself, and does not work out detours &mdash; follow their notice, or the signage
        on the ground.
      </p>

      {generatedAt !== null && (
        <p className="closure-sheet__age">{`Gathered by OurHike on ${longDate(generatedAt)}.`}</p>
      )}
    </div>
  )
}
