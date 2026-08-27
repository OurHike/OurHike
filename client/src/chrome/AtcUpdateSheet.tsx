// The sheet for an ATC trail update, and the reason it is not ClosureSheet.
//
// features/ATC_TRAIL_UPDATES.md §4 is the requirement, and #461 is the issue.
// The rule it enforces is one sentence: **OurHike did not verify this; the
// ATC published it, and those are different statements.** A sheet that said
// "Closed · mi 476.6 – 485.8" and nothing else would be OurHike asserting a
// closure it never checked - which misrepresents the ATC as much as it
// misleads the hiker, and is the failure OurHikeValues.md #4 exists to
// prevent.
//
// Three things here are therefore not optional detail:
//
// **The organization's name, on the claim.** Not in a map corner, not in a settings
// screen - on the thing being claimed, next to the date they last edited it.
//
// **Both dates, because there are two and they differ.** ATC's own
// `updated_at` is when the notice was last true as far as they know; our
// `reviewedAt` is when a person last checked our copy against their page. A
// notice ATC edited yesterday that nobody here has looked at since May is a
// real state, and the honest thing is to say so rather than to show whichever
// date flatters the app.
//
// **The link, which is load-bearing rather than a nicety.** The artifact
// carries facts and not ATC's prose - their paragraphs are their writing, and
// pipeline/sources.json's `licence` field records why we stop at the facts -
// so this link IS the detail. A hiker who needs to know what the detour
// actually is has nowhere else to go, which is exactly why the scheme is
// checked before it is rendered.

// The formatting lives in lib/atcNoticeText.ts, shared with NoticeList.tsx.
// Two surfaces rendering the same mile marker to different precision is a
// hiker reading two claims where there is one.
import { atcUpdatedAt, isSafeLink, longDate, mileRange } from '../lib/atcNoticeText'
import type { AtcUpdate } from '../lib/atcUpdates'
import { ATC_SOURCE_KEY } from '../lib/notices'
import { orgLabelFrom, type Stewards } from '../lib/stewards'

export interface AtcUpdateSheetProps {
  update: AtcUpdate
  /** When a person last checked the reviewed file against ATC's page, or null
   *  if the artifact does not say. */
  reviewedAt: Date | null
  /**
   * The published registry, which is where the organization's name comes from
   * (#1083, features/ORG_NOTICES.md §6).
   *
   * This sheet only ever shows an ATC row today - it is the only publisher
   * whose notices carry a mile, so the only one whose notices can be tapped on
   * the map - and the name is STILL read rather than written. The rule is
   * about where a claim about an organization comes from, not about how many
   * organizations there happen to be: a literal here is a literal somebody
   * copies into the second sheet.
   *
   * Empty is ordinary (lib/stewards.ts) and renders the raw registry key,
   * which is ugly and true.
   */
  stewards: Stewards
  onClose: () => void
}

export function AtcUpdateSheet({
  update,
  reviewedAt,
  stewards,
  onClose,
}: AtcUpdateSheetProps) {
  const updatedAt = atcUpdatedAt(update)
  const range = mileRange(update)
  const org = orgLabelFrom(stewards)(ATC_SOURCE_KEY)
  const orgs = org.endsWith('s') ? `${org}’` : `${org}’s`

  return (
    <div className="closure-sheet" role="dialog" aria-label={`${org} trail update`}>
      <div className="legend__head">
        {/* The organization's own category, verbatim. Not mapped onto
            ClosureReason: that enum would render a Detour as "Closed", which
            is a claim they did not make. */}
        <h2 className="legend__title">{update.category}</h2>
        <button type="button" className="legend__close" onClick={onClose}>
          <span className="visually-hidden">Close</span>
          <span aria-hidden="true">×</span>
        </button>
      </div>

      {/* Their headline, which is the most specific thing the artifact is
          allowed to carry. */}
      <p className="closure-sheet__status">{update.title}</p>

      <p className="closure-sheet__range">
        {update.states.length > 0 ? `${update.states.join(', ')} · ${range}` : range}
      </p>

      {/* The attribution, and the whole point of a separate component. */}
      <p className="closure-sheet__meta">
        {updatedAt === null ? org : `${org} — updated ${longDate(updatedAt)}`}
      </p>

      {isSafeLink(update.source_url) && (
        <a
          className="closure-sheet__link"
          href={update.source_url}
          target="_blank"
          rel="noreferrer"
        >
          Read {orgs} notice
        </a>
      )}

      <p className="closure-sheet__limit" role="note">
        This is {orgs} notice, not OurHike&rsquo;s. OurHike has not checked the trail
        itself, and does not work out detours &mdash; follow their notice, or the signage
        on the ground.
      </p>

      {/* The second age. Deliberately last and deliberately plain: it is the
          one a hiker only needs when something looks wrong. */}
      <p className="closure-sheet__age">
        {reviewedAt === null
          ? `OurHike can’t tell when it last checked ${orgs} updates.`
          : `OurHike last checked ${orgs} updates on ${longDate(reviewedAt)}.`}
      </p>
    </div>
  )
}
