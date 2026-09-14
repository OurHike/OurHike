// Your photos and notes (#1373, D5) - a list of the hiker's own work on this
// phone, and the door to a place that is no longer on the map.
//
// THE DOOR IS THE POINT. A waypoint retired upstream keeps a card
// (chrome/RemovedPoiCard.tsx, #831) so a hiker's photos of it have somewhere
// to live - and until this list the only way to that card was tapping a pin
// that is not there. The review's reachability audit called it encounter-
// only; this is the summonable door. A row opens the place: the waypoint
// card if the place is live, the removed-place card if it is not, both
// through the same `handleSelectPoi`, because the shell already resolves a
// retired id to its tombstone (App.tsx's `removedPoi`).
//
// WHAT THE PHONE CAN TRUTHFULLY LIST. Photos: every one, because the phone
// holds them (lib/poiPhotos.ts) whether or not they were shared. Notes: the
// ones still waiting in the outbox, because a note leaves with the send and
// the phone keeps no copy - the notes endpoint returns everybody's notes with
// no author on them (#252). Saying so is part of the screen; **#967 — Decide
// what a phone keeps of the notes and photos its hiker has sent** is where
// that changes, if it does.
//
// EVERY ROW IS THE REVIEW'S PoiRow - the map's own pin at row scale - so the
// glyph a hiker learned on the map is the glyph in the list. No count of
// photos, no "N places", no streak: a list of a hiker's own contributions is
// exactly where a score would arrive uninvited (D12; POI_PHOTOS.md's own
// rule against counting shares).

import { PoiRow } from '../chrome/PoiRow'
import { observationLabel } from '../lib/fieldNotes'
import { agoLabel } from '../lib/hikeText'
import { dayLongDateLabel } from '../lib/planDisplay'
import './plan.css'
import './settings.css'

export interface OwnWorkPhoto {
  poiId: string
  id: string
  /** The place's waypoint type, for the glyph - a retired place's from its
   *  tombstone, so it keeps the shape it had. */
  kind: string
  place: string
  /** YYYY-MM-DD: capture where the original carried one, else the day it
   *  was kept - `listOwnPhotos`' own fallback, so the card and this row
   *  agree. */
  date: string
  shared: boolean
  /** True for a place that has left the map - the row says so. */
  removed: boolean
}

export interface OwnWorkNote {
  id: string
  poiId: string | null
  kind: string
  place: string
  observation: string | null
  /** ISO timestamp - the moment of the tap. */
  authoredAt: string
}

export interface YourWorkProps {
  photos: readonly OwnWorkPhoto[]
  notes: readonly OwnWorkNote[]
  /** YYYY-MM-DD, the phone's local day. */
  today: string
  onOpenPlace: (poiId: string) => void
}

export function YourWork({ photos, notes, today, onOpenPlace }: YourWorkProps) {
  return (
    <section className="settings__group" aria-label="Your photos and notes">
      <h2 className="settings__heading">Your photos and notes</h2>

      {photos.length > 0 && (
        <section className="plan-home__section" aria-label="Photos">
          <span className="plan-home__title">Photos</span>
          {photos.map((photo) => (
            <PoiRow
              key={`${photo.poiId}/${photo.id}`}
              kind={photo.kind}
              title={photo.place}
              meta={[
                `photo · kept ${dayLongDateLabel(photo.date)}`,
                photo.shared ? 'shared' : 'private to this phone',
                photo.removed ? 'a place no longer on the map' : null,
              ]
                .filter((part) => part !== null)
                .join(' · ')}
              onOpen={() => onOpenPlace(photo.poiId)}
            />
          ))}
        </section>
      )}

      {notes.length > 0 && (
        <section className="plan-home__section" aria-label="Notes waiting to send">
          <span className="plan-home__title">Notes waiting to send</span>
          {notes.map((note) => {
            const ago = agoLabel(note.authoredAt.slice(0, 10), today)
            return (
              <PoiRow
                key={note.id}
                kind={note.kind}
                title={note.place}
                meta={[
                  'note',
                  note.observation === null ? null : observationLabel(note.observation),
                  ago === null ? 'written' : `written ${ago}`,
                  'waiting to send',
                ]
                  .filter((part) => part !== null)
                  .join(' · ')}
                onOpen={note.poiId === null ? undefined : () => onOpenPlace(note.poiId!)}
              />
            )
          })}
        </section>
      )}

      {photos.length === 0 && notes.length === 0 && (
        <p className="settings__note">
          Nothing here yet. A photo or a note starts from a waypoint’s card on the map.
        </p>
      )}

      {/* Said whether or not the list is empty, because it is the rule the
          list is built on rather than a description of one state. */}
      <p className="settings__note">
        Notes leave with the send and are not kept here once they have gone — this list
        holds the ones still waiting. Your photos stay on this phone whether or not you
        shared them, and a place that has left the map keeps them too.
      </p>
    </section>
  )
}
