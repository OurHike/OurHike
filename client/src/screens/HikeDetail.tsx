// The hike detail (#1290, wireframe `1g`): one published route, in the
// publisher's words, with this phone's own measurement beside theirs.
//
// Reached by opening a card - on the Today shelf, in the finder's results,
// anywhere SuggestedHikeCard is a button. Pushed over Today, so Today stays
// the selected tab; this is not a fifth tab.
//
// WHAT THIS SCREEN IS FOR, and it is not "everything we know about the
// route". It answers three questions a hiker has while deciding, in the
// order they have them: is this walk within me today, how do I get to the
// start, and whose route is this. Everything else - the turn-by-turn, the
// publisher's page - is one tap away rather than in the way.
//
// THE TWO FIGURES ARE THE POINT OF THE SCREEN, and they are allowed to
// disagree. `hike.miles` is what THIS phone measures on the trail lines it
// holds, by the same arithmetic it will use to draw the route; the
// publisher's own stated length sits beside it. On the routes shipping
// today they differ by up to a fifth (pipeline's
// reference/nynjtc_hike_routes.json records which and why), and printing
// one dressed as the other would be the display outrunning its source -
// CLAUDE.md's fourth failure. So both, labelled, side by side, and the
// reviewed `hikerNote` underneath saying what a person found when they
// looked.
//
// WHAT IS DELIBERATELY NOT HERE:
//
//  - No map plate. The design canvas sketched one, and drawing it truthfully
//    means resolving the route against the graph this phone holds and
//    rendering that geometry - which is exactly what "Open on map" does, on
//    the real map, with the real lines. A decorative sketch of a route is a
//    picture of a walk that may not be the walk, and this screen already
//    carries two figures whose whole job is to not overstate.
//  - No pace judgement, no comparison, no count of anything. #982's rule,
//    and value #1: a screen about walking is exactly where gamification
//    creeps in.
//  - No Avenza link, on the maintainer's instruction, though the publisher's
//    own pages carry one.

import { useState } from 'react'
import { Badge } from '../design-system/components'
import { shortDate } from '../lib/hikeText'
import type { PaceProfile } from '../lib/pace'
import {
  authorLine,
  difficultyLabel,
  hikeEstimate,
  type SuggestedHike,
} from '../lib/suggestedHikes'
import { formatDistance, formatElevation, type UnitSystem } from '../lib/units'
import './hikeDetail.css'

/** How many paragraphs of the turn-by-turn show before the button. Two is
 *  enough to see whose voice it is and how detailed it gets, which is what
 *  the decision "do I want to read this" needs. */
const DESCRIPTION_PREVIEW = 2

export interface HikeDetailProps {
  hike: SuggestedHike
  pace: PaceProfile
  units: UnitSystem
  onBack: () => void
  /** Saves the route into the hiker's own day hikes. Absent while the store
   *  is not ready, and then no button is drawn - a control that cannot do
   *  its job is not offered (chrome/LineSheet.tsx's rule). */
  onSave?: (hike: SuggestedHike) => void
  /** Already in their hikes, with the dates they have walked it - newest
   *  first. Empty means saved but never logged; undefined means not saved. */
  savedWalks?: string[]
  /** Draws the route on the real map. Absent until the hiker has saved it,
   *  because what the map draws is a record in their own hikes - see the
   *  shell's `showSavedHikeOnMap`. Absent is the honest state, not a
   *  degraded one: Save is the button beside it. */
  onShowOnMap?: (hike: SuggestedHike) => void
}

function figures(hike: SuggestedHike, pace: PaceProfile, units: UnitSystem): string {
  const estimate = hikeEstimate(hike, pace)
  const parts = [formatDistance(hike.miles, units)]
  if (estimate === null) {
    // The climb is what prices a walk's time, and #1313 has it absent on
    // every route shipping today. "No time" rather than a time computed
    // from a climb of zero, which would read as flat ground.
    parts.push('no time — climb unmeasured')
  } else {
    parts.push(estimate.text)
    const climb = hike.climb
    if (climb !== undefined && climb !== null) {
      parts.push(`+${formatElevation(climb.gainFt, units)}`)
    }
  }
  return parts.join(' · ')
}

/** The line under the figures naming whose number is whose. Never printed
 *  without the phone's own half, because "NYNJTC says 3.8 mi" alone would
 *  read as the app's measurement. */
function measurementLine(hike: SuggestedHike, units: UnitSystem): string {
  const ours = 'measured on the trail lines this phone holds'
  const theirs = hike.detail?.publishedMiles
  if (theirs === undefined) return ours
  return `${ours} · ${hike.author.name} says ${formatDistance(theirs, units)}`
}

/** "Walked 12 Mar, and twice before" - the dates on the hiker's own record,
 *  counted but never scored. No streak, no total, no comparison: the count
 *  is here so the sentence can be short, not so anybody can be measured by
 *  it (#982, value #1). */
function walkedLine(walks: readonly string[]): string | null {
  if (walks.length === 0) return null
  // `shortDate` rather than a fresh formatter: it pins the locale and reads
  // the ISO day as UTC, where `new Date('2026-03-14T00:00:00')` reads it as
  // local midnight and prints the 13th for every hiker west of Greenwich.
  const latest = shortDate(walks[0])
  if (walks.length === 1) return `You walked this on ${latest}.`
  if (walks.length === 2) return `You walked this on ${latest}, and once before.`
  return `You walked this on ${latest}, and ${walks.length - 1} times before.`
}

/** What the one save button says, and there are three answers because there
 *  are three states. Saving a route is not walking it: a hiker who saves a
 *  plan has logged nothing, so the middle state offers a FIRST walk rather
 *  than "another" - the count in that word would be a lie about them. */
function saveLabel(walks: readonly string[] | undefined): string {
  if (walks === undefined) return 'Save to my hikes'
  return walks.length === 0 ? 'Log a walk' : 'Log another walk'
}

export function HikeDetail({
  hike,
  pace,
  units,
  onBack,
  onSave,
  savedWalks,
  onShowOnMap,
}: HikeDetailProps) {
  const [wholeDescription, setWholeDescription] = useState(false)
  const detail = hike.detail
  const description = detail?.description ?? []
  const shown = wholeDescription ? description : description.slice(0, DESCRIPTION_PREVIEW)
  const rest = description.length - DESCRIPTION_PREVIEW
  const walked = savedWalks === undefined ? null : walkedLine(savedWalks)

  const facets = [detail?.routeType, detail?.park].filter(
    (part): part is string => part !== undefined,
  )

  return (
    <div className="hike-detail">
      <div className="hike-detail__hero">
        {hike.photo === undefined ? (
          <div className="hike-detail__hero-blank" aria-hidden="true" />
        ) : (
          <img className="hike-detail__hero-photo" src={hike.photo.url} alt="" />
        )}
        {/* The same crumb the finder uses, over the photo rather than under
            a header - one glyph and a word, no icon set to extend. */}
        <button type="button" className="hike-detail__back" onClick={onBack}>
          ‹ Back
        </button>
        {hike.photo !== undefined && (
          // The credit is the licence's condition, not decoration
          // (features/POI_PHOTOS.md), so it rides on the photo itself and
          // cannot be scrolled away from it.
          <span className="hike-detail__credit">{hike.photo.credit}</span>
        )}
      </div>

      <div className="hike-detail__body">
        <h1 className="hike-detail__name">{hike.name}</h1>
        <p className="hike-detail__author">{authorLine(hike.author)}</p>
        {detail?.publication?.verifiedOn != null && (
          <p className="hike-detail__verified">
            Route last verified by them on {detail.publication.verifiedOn}
          </p>
        )}

        <p className="hike-detail__figures">{figures(hike, pace, units)}</p>
        <p className="hike-detail__measurement">{measurementLine(hike, units)}</p>

        {(hike.difficulty !== null || facets.length > 0) && (
          <p className="hike-detail__facets">
            {hike.difficulty !== null && (
              // The design system's own badge, not a copy of its ramp:
              // SuggestedHikeCard draws the same five tones from the same
              // component, so a card and the screen it opens cannot come to
              // disagree about what "moderate" looks like.
              <Badge tone={hike.difficulty}>{difficultyLabel(hike.difficulty)}</Badge>
            )}
            {facets.length > 0 && (
              <span className="hike-detail__facet-line">{facets.join(' · ')}</span>
            )}
          </p>
        )}

        {detail?.hikerNote !== undefined && (
          // A reviewed sentence about how this route differs from the
          // publisher's page. It sits ABOVE the actions on purpose: it is
          // part of deciding, not a footnote to be found afterwards.
          <p className="hike-detail__hiker-note">{detail.hikerNote}</p>
        )}

        {walked !== null && <p className="hike-detail__walked">{walked}</p>}

        <div className="hike-detail__actions">
          {onSave !== undefined && (
            <button
              type="button"
              className="hike-detail__save"
              onClick={() => onSave(hike)}
            >
              {saveLabel(savedWalks)}
            </button>
          )}
          {onShowOnMap !== undefined && (
            <button
              type="button"
              className="hike-detail__map"
              onClick={() => onShowOnMap(hike)}
            >
              Open on map
            </button>
          )}
        </div>

        {detail?.start !== undefined && (
          <section className="hike-detail__section">
            <h2 className="hike-detail__rule">Getting there</h2>
            <div className="hike-detail__card">
              <p className="hike-detail__coords">
                {detail.start.lat.toFixed(4)}, {detail.start.lon.toFixed(4)}
              </p>
              {detail.start.basis === 'map_centre' && (
                // The weaker reading, and it says so. A place-card map's
                // centre is not a placed pin, and a hiker driving to it
                // should know which they were given.
                <p className="hike-detail__start-basis">
                  Read from the centre of the map on their page rather than a placed pin,
                  so check it against the parking their description names.
                </p>
              )}
              <a
                className="hike-detail__directions"
                href={`geo:${detail.start.lat},${detail.start.lon}`}
              >
                Directions ›
              </a>
              <p className="hike-detail__aside">
                Opens your phone’s maps app. Nothing here plans the drive.
              </p>
            </div>
          </section>
        )}

        {(detail?.overview ?? []).length > 0 && (
          <section className="hike-detail__section">
            <h2 className="hike-detail__rule">The hike</h2>
            {detail!.overview!.map((paragraph, at) => (
              <p key={at} className="hike-detail__prose">
                {paragraph}
              </p>
            ))}
          </section>
        )}

        {description.length > 0 && (
          <section className="hike-detail__section">
            <h2 className="hike-detail__rule">Turn by turn</h2>
            {detail?.publication !== undefined && (
              <p className="hike-detail__publication">
                Written by {detail.publication.submittedBy}
                {detail.publication.submittedOn != null &&
                  ` on ${detail.publication.submittedOn}`}
                {detail.publication.verifiedOn != null &&
                  `, last verified ${detail.publication.verifiedOn}`}
                .
              </p>
            )}
            {shown.map((paragraph, at) => (
              <p key={at} className="hike-detail__prose">
                {paragraph}
              </p>
            ))}
            {!wholeDescription && rest > 0 && (
              <button
                type="button"
                className="hike-detail__more"
                onClick={() => setWholeDescription(true)}
              >
                Read all {description.length} paragraphs
              </button>
            )}
          </section>
        )}

        <footer className="hike-detail__provenance">
          <p>
            {hike.author.name}’s route and words, published here with their permission.
            {detail?.trails !== undefined && ` Uses ${detail.trails.join(', ')}.`}
          </p>
          {detail?.url !== undefined && (
            <a className="hike-detail__source" href={detail.url}>
              Read it on their page ›
            </a>
          )}
          <p className="hike-detail__aside">
            The line a map draws is OurHike’s, built from their description on the trail
            data this phone holds — not a track anybody walked with a GPS.
          </p>
        </footer>
      </div>
    </div>
  )
}
