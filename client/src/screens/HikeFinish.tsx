// The finish (#1317) - the one celebratory screen in the app.
//
// AND THE ONE MOST LIKELY TO BREAK THE RULE THE REST OF THE APP KEEPS. A
// finish screen is where percentages, ranks, streaks and "you beat 80% of
// hikers" arrive, because every other app's does. This one has none of them,
// the guard test asserts it, and the closing line says why out loud: "No
// badge, no rank, nobody to compare with. It is your own log, and it is
// yours to keep offline." OurHikeValues.md #1.
//
// FOUR FIGURES, ALL OF THEM RECORDS OF WHAT HAPPENED. Miles walked, days
// walking, feet climbed, sections walked. Not one of them is a comparison,
// a rate or a placing, and the difference matters more here than anywhere:
// a hiker reads this screen once, at the end of years, and whatever it says
// is what they will remember the app said.
//
// OFFERED, NEVER DECLARED. The trigger is the hiker tapping "I finished it"
// or reaching the final point - and a hiker standing at the terminus with no
// fix must still be able to say so themselves. The app does not get to
// decide that somebody's hike is over.
//
// PHOTOS. Every place photo needs its own attribution path
// (features/POI_PHOTOS.md), and a photo the hiker added is theirs: it never
// leaves the device unless they share it. The sixth tile is a dashed slot
// rather than a fifth photo, which is what says so on screen.

import { formatDistance, formatElevation, type UnitSystem } from '../lib/units'
import { shortDate } from '../lib/hikeText'
import './today.css'
import './plan.css'

export interface FinishPhoto {
  id: string
  src: string
  /** Who this is by - never absent, because a photo with no attribution path
   *  is one this screen may not show (features/POI_PHOTOS.md). */
  credit: string
}

export interface HikeFinishProps {
  hikeName: string
  /** One sentence: what was walked, and between which dates. */
  sentence: string
  finishedOn: string
  walkedMi: number
  daysWalking: number
  /** Null on a download with no elevation profile - and then the tile is
   *  absent rather than reading zero, because nobody climbed zero feet. */
  climbedFt: number | null
  sections: number
  /** How the seasons are described, e.g. "three seasons". Null when the
   *  dates cannot say. */
  seasons: string | null
  photos: readonly FinishPhoto[]
  /** How many clubs maintain the trail, and what the hiker sent - the crews
   *  line. Null when this phone cannot say, and then the card is absent
   *  rather than claiming a number. */
  crews: { clubs: number; fieldNotes: number; thanks: number } | null
  units: UnitSystem
  onSayThanks: () => void
  onShare: () => void
  onKeepTheRecord: () => void
}

export function HikeFinish({
  hikeName,
  sentence,
  finishedOn,
  walkedMi,
  daysWalking,
  climbedFt,
  sections,
  seasons,
  photos,
  crews,
  units,
  onSayThanks,
  onShare,
  onKeepTheRecord,
}: HikeFinishProps) {
  return (
    <div className="finish">
      <header className="finish__hero">
        {photos[0] !== undefined && (
          <img className="finish__hero-photo" src={photos[0].src} alt="" />
        )}
        <div className="finish__hero-words">
          <p className="finish__eyebrow">Finished · {shortDate(finishedOn)}</p>
          <h1 className="finish__name">{hikeName}</h1>
          <p className="finish__sentence">{sentence}</p>
        </div>
      </header>

      <div className="finish__body">
        <div className="finish__figures">
          <Figure value={formatDistance(walkedMi, units)} label="walked" />
          <Figure
            value={String(daysWalking)}
            label={seasons === null ? 'days walking' : `days walking, ${seasons}`}
          />
          {climbedFt !== null && (
            <Figure value={formatElevation(climbedFt, units)} label="climbed" />
          )}
          <Figure
            value={String(sections)}
            label={sections === 1 ? 'section walked' : 'sections walked'}
          />
        </div>

        {photos.length > 0 && (
          <section className="finish__places" aria-label="What you walked past">
            <p className="finish__rule">What you walked past</p>
            <div className="finish__tiles">
              {photos.map((photo) => (
                <figure className="finish__tile" key={photo.id}>
                  <img src={photo.src} alt="" />
                  <figcaption className="visually-hidden">{photo.credit}</figcaption>
                </figure>
              ))}
              {/* Dashed, and empty. What says on screen that a hiker's own
                  photos stay on their phone unless they share them. */}
              <div className="finish__tile finish__tile--slot">
                your photos drop in here
              </div>
            </div>
            <p className="finish__caption">
              The places on your route with photos in the app, plus whatever you add.
              Yours stay on your phone unless you share them.
            </p>
          </section>
        )}

        {crews !== null && (
          <section className="finish__crews" aria-label="Who kept it walkable">
            <p className="finish__crews-line">
              {crews.clubs} clubs maintain the trail you just walked. You sent{' '}
              {crews.fieldNotes} field notes and {crews.thanks} thanks along the way.
            </p>
            <button type="button" className="finish__crews-button" onClick={onSayThanks}>
              Say thanks to the crews
            </button>
          </section>
        )}

        <div className="finish__actions">
          <button type="button" className="plan__primary" onClick={onShare}>
            Share this hike
          </button>
          <button type="button" className="finish__outline" onClick={onKeepTheRecord}>
            Keep the record
          </button>
        </div>

        <p className="finish__closing">
          No badge, no rank, nobody to compare with. It is your own log, and it is yours
          to keep offline.
        </p>
      </div>
    </div>
  )
}

function Figure({ value, label }: { value: string; label: string }) {
  return (
    <div className="finish__figure">
      <span className="finish__figure-value">{value}</span>
      <span className="finish__figure-label">{label}</span>
    </div>
  )
}
