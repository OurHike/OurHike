// Every ATC notice the app is holding, in one list.
//
// features/ATC_TRAIL_UPDATES.md ended its open questions with "**Where the
// suppressed ones go.** 'List entry' still has no surface". This is that
// surface, and the reason it stopped being optional is that "suppressed" was
// never the whole of it. THERE IS NO SCREEN IN THIS APP THAT SHOWS ALL OF WHAT
// THE ATC SAID. What existed before this file:
//
//  - **The banner**, which shows at most two updates - the nearest actionable
//    one and the nearest region-wide one - and only ever AHEAD of the hiker
//    (lib/atcUpdates.ts is explicit that warning about something behind you is
//    how a warning surface teaches people to ignore it).
//  - **A tap on the map**, which requires the notice to be drawn, and requires
//    the hiker to already suspect there is something there to tap.
//
// So an update that obstructs nothing, spans a range rather than a point, and
// sits behind the hiker reached them through NOTHING. That is not an edge
// case: `atcBandCandidates` drops every non-obstructing range, `closureBands`
// drops everything over `MAX_BAND_MILES`, and `atcPointNotices` picks up only
// the ones ATC filed at a single mile. Each of those three filters is right on
// its own terms and each was written about the MAP. None of them was ever a
// decision that a hiker should not be able to read the notice.
//
// WHAT THIS IS NOT. It is not ATC's notice. The artifact carries facts and a
// link and deliberately not their prose - pipeline/sources.json's `licence`
// field on `atc_trail_updates` is the reasoning, and #458 is where the
// maintainer settled the conservative reading on their own judgement as an ATC
// trail volunteer. So every row here ends at their page, and the header says
// so rather than leaving a reader to infer that a list this complete-looking
// is complete. Showing everything OurHike holds and being honest that OurHike
// does not hold everything are the same requirement, not competing ones.

import { atcUpdatedAt, isSafeLink, longDate, mileRange } from '../lib/atcNoticeText'
import { atcBandId, isReviewedByAPerson, type AtcUpdate } from '../lib/atcUpdates'

export interface AtcNoticeListProps {
  /** Every update the app holds, in whatever order it read them. */
  updates: readonly AtcUpdate[]
  /**
   * The band ids the map is drawing right now.
   *
   * Passed in rather than re-derived from the update. The three filters above
   * would give the answer this build INTENDS, and `trailSlice` can still
   * refuse a mile that falls outside this build's centerline - so a list that
   * worked it out itself would tell a hiker to look for a dot that is not
   * there. The shell already holds both drawn collections (App.tsx), so the
   * true answer is free.
   */
  drawnIds: ReadonlySet<string>
  /** When a person last checked the reviewed file against ATC's page, or null
   *  if the artifact does not say. */
  reviewedAt: Date | null
  onClose: () => void
}

/**
 * NOBO order, which is the order a hiker holds the trail in.
 *
 * Not by date, and not by severity. Date would put a notice edited yesterday
 * above one two miles ahead, and this app has no severity to sort by - it
 * refuses to rank ATC's categories against each other, which is the whole
 * argument of lib/atcUpdateStyle.ts. Mile is the one ordering that is a fact
 * about the trail rather than a judgement about the notices.
 */
function byMile(updates: readonly AtcUpdate[]): AtcUpdate[] {
  return [...updates].sort((a, b) => a.start_mile_marker - b.start_mile_marker)
}

export function AtcNoticeList({
  updates,
  drawnIds,
  reviewedAt,
  onClose,
}: AtcNoticeListProps) {
  const ordered = byMile(updates)

  return (
    <div
      className="atc-notices"
      role="dialog"
      aria-label="Every Appalachian Trail Conservancy trail update"
    >
      <div className="legend__head">
        <h2 className="legend__title">
          {ordered.length === 1
            ? '1 ATC trail update'
            : `${ordered.length} ATC trail updates`}
        </h2>
        <button type="button" className="legend__close" onClick={onClose}>
          <span className="visually-hidden">Close</span>
          <span aria-hidden="true">×</span>
        </button>
      </div>

      {/* First, not last. A reader who takes this list for the notices
          themselves has been misled by the time they reach a footnote. */}
      <p className="closure-sheet__limit" role="note">
        Everything the Appalachian Trail Conservancy has posted that OurHike holds a copy
        of &mdash; including the ones the map does not draw. OurHike carries their facts
        and a link, never their notice in full, so what each one actually says is on their
        page.
      </p>

      {ordered.length === 0 ? (
        // "Nothing here" and "we could not ask" are different statements, and
        // this component can only honestly make the first. App.tsx does not
        // mount it at all when the fetch failed - see the comment there.
        <p className="atc-notices__empty">OurHike is holding no ATC trail updates.</p>
      ) : (
        <ul className="atc-notices__list">
          {ordered.map((update) => {
            const updatedAt = atcUpdatedAt(update)
            const onMap = drawnIds.has(atcBandId(update))

            return (
              <li className="atc-notices__item" key={update.atc_id}>
                {/* ATC's own category, verbatim, for the reason
                    AtcUpdateSheet.tsx gives: mapping it onto ClosureReason
                    would render a Detour as "Closed", which is a claim they
                    did not make. */}
                <p className="atc-notices__category">{update.category}</p>

                <p className="atc-notices__title">{update.title}</p>

                <p className="closure-sheet__range">
                  {update.states.length > 0
                    ? `${update.states.join(', ')} · ${mileRange(update)}`
                    : mileRange(update)}
                </p>

                {/* The reviewer's answer to the one question ATC's category
                    cannot be read for (lib/atcUpdates.ts, `obstructs_trail`).
                    Both branches are stated: "the trail is passable" is a
                    thing a hiker wants to have been told, not the absence of
                    a warning. */}
                <p className="atc-notices__passability">
                  {!isReviewedByAPerson(update)
                    ? 'OurHike has not checked this one yet — read the ATC’s page.'
                    : update.obstructs_trail
                      ? 'The ATC says this stops a hiker walking through.'
                      : 'The ATC did not report the trail itself blocked here.'}
                </p>

                <p className="closure-sheet__meta">
                  {updatedAt === null
                    ? 'Appalachian Trail Conservancy'
                    : `Appalachian Trail Conservancy — updated ${longDate(updatedAt)}`}
                </p>

                {/* Where a notice with no mark on the map says so. A hiker who
                    read this list, walked the miles and saw nothing red would
                    otherwise be entitled to conclude the notice had been
                    lifted. */}
                {!onMap && (
                  <p className="atc-notices__offmap">
                    Not drawn on the map &mdash; read it here.
                  </p>
                )}

                {isSafeLink(update.source_url) && (
                  <a
                    className="closure-sheet__link"
                    href={update.source_url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Read the ATC&rsquo;s notice
                  </a>
                )}
              </li>
            )
          })}
        </ul>
      )}

      {/* The second age, last and plain - the same placement and the same
          reasoning as the single-notice sheet. It is the one a hiker only
          needs when something looks wrong. */}
      <p className="closure-sheet__age">
        {reviewedAt === null
          ? 'OurHike cannot tell when it last checked ATC’s updates.'
          : `OurHike last checked ATC’s updates on ${longDate(reviewedAt)}.`}
      </p>
    </div>
  )
}
