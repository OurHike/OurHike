// A tile, opened (#1963, features/CHALLENGES_BLAZE_CARD.md slice 3; the
// frame is features/design/blaze-card/Tile.dc.html): one item of a
// challenge, read in full and earned from here. Replaces the tagged-place
// sheet of #1780's frame #4b, keeping what it kept - the hiker's own photo
// where they have one, the moment, the club's note, the private register
// line, and the one-tap "Take it back".
//
// THE PHOTO LEADS WHEN THERE IS ONE, the item's glyph otherwise; a tile
// with no reviewed photo never shows a stock one (the brief, "What this is
// not"). Item photos arrive in slice 7; until then this header is the glyph
// for every ATC item.
//
// EARNING IS ONE TAP, AND IT NEVER TOGGLES: "Earn some karma" earns (through
// "Where did it happen?" when that can mean something - the caller decides,
// lib/wherePlace.ts asksWhere), and an earned tile offers "Take it back".
// Nothing here waits on the network.
//
// "NEAR YOU" says only what the phone knows for certain: that today's walk
// covered the place's mile, or how far along the trail the fix is from it.
// It never says how far the hiker is from anything when there is no fix,
// and never asks for one.
//
// "USE MY OWN PHOTO INSTEAD · STAYS ON THIS PHONE" (maintainer, poll
// 2026-11-04: build it now rather than with slice 7's photos) is the place
// card's own-photo rung (features/POI_PHOTOS.md source 2, lib/useOwnPhotos.ts)
// reached from the tile: the same store, so a photo added here is the one
// the waypoint card shows, and the reverse. Only an item with a place has
// one - the store is per waypoint. The 640 px rendering is all this app
// holds; the original stays in the hiker's library.

import { useEffect, useRef, useState } from 'react'
import { CHALLENGE_WORDS } from '../lib/challengeWords'
import { exifCaptureDate } from '../lib/exifDate'
import { CARD_PHOTO_EDGE } from '../lib/poiPhotos'
import { PhotoUnusable, preparePhoto } from '../lib/reportPhoto'
import { useOwnPhotos } from '../lib/useOwnPhotos'
import {
  isPlaceItem,
  itemTitle,
  itemsAtPoi,
  type Challenge,
  type ChallengeItem,
} from '../lib/challenges'
import { isItemDone, itemDoneAt, type ChallengeTag } from '../lib/challengeProgress'
import {
  formatDay,
  formatMoment,
  mileLabel,
  mysteryTeaser,
  placeWords,
  titleOrSealed,
} from '../lib/challengeText'
import type { MileRange } from '../lib/walkedMiles'
import { asksWhere } from '../lib/wherePlace'
import { BlazeTile } from './BlazeTile'
import '../screens/challenges.css'

export interface TileSheetProps {
  challenge: Challenge
  item: ChallengeItem
  /** Its place in the club's list, from 1. */
  number: number
  today: string
  tags: readonly ChallengeTag[]
  /** Whether a tap here may earn it: joined, inside the window, and a kind
   *  a hand may earn. */
  earnable: boolean
  /** Today's walked miles (lib/passedToday.ts), for "Near you". */
  todayRanges?: readonly MileRange[]
  /** The fix snapped to the trail, or null; never asked for here. */
  fixMile?: number | null
  onEarn: () => void
  /** Takes the earned item back - `poi` for one peak of a Triple Crown. */
  onTakeBack?: (poi?: string) => void
  onSetNote: (note: string) => void
  onClose: () => void
}

export function TileSheet({
  challenge,
  item,
  number,
  today,
  tags,
  earnable,
  todayRanges = [],
  fixMile = null,
  onEarn,
  onTakeBack,
  onSetNote,
  onClose,
}: TileSheetProps) {
  const closeButton = useRef<HTMLButtonElement | null>(null)
  useEffect(() => {
    closeButton.current?.focus()
  }, [])
  const done = isItemDone(item, challenge.id, tags)
  const doneTag = itemDoneAt(item, challenge.id, tags)
  const places = isPlaceItem(item) ? item.match.places : []
  const place =
    places.find((candidate) => candidate.poi === doneTag?.poi) ??
    places[places.length - 1]
  // The hiker's own photos of this place, the same store as the waypoint
  // card's; an item with no place has no store, and the hook reads none.
  const ownPhotos = useOwnPhotos(place?.poi ?? '')
  const own = place !== undefined ? (ownPhotos.photos[0] ?? null) : null
  const photo = own?.url ?? item.photo
  const chip = own !== null ? 'your photo' : item.photo !== null ? 'club photo' : null
  const libraryInput = useRef<HTMLInputElement | null>(null)
  const [photoNote, setPhotoNote] = useState<string | null>(null)
  const [preparing, setPreparing] = useState(false)
  const pickOwnPhoto = async (file: File | null) => {
    if (file === null) return
    setPhotoNote(null)
    setPreparing(true)
    try {
      // The capture date comes off the original, beside the re-encode that
      // destroys it (lib/exifDate.ts), as the waypoint card does it.
      const [blob, taken] = await Promise.all([
        preparePhoto(file, CARD_PHOTO_EDGE),
        exifCaptureDate(file),
      ])
      await ownPhotos.add({ blob, taken, source: 'library' })
    } catch (error) {
      setPhotoNote(
        error instanceof PhotoUnusable
          ? error.message
          : 'That photo could not be prepared. Try another.',
      )
    } finally {
      setPreparing(false)
    }
  }
  const section = challenge.sections.find((entry) => entry.id === item.section)
  const [note, setNote] = useState(
    () =>
      tags.find((existing) => existing.itemId === item.id && existing.note)?.note ?? '',
  )

  // What the phone knows about the place, said only when it knows it.
  let nearYou: string | null = null
  if (place !== undefined) {
    const passedToday = todayRanges.some(
      (range) => range.startMile <= place.mile && place.mile <= range.endMile,
    )
    if (passedToday) nearYou = 'You passed it today.'
    else if (fixMile !== null) {
      const along = Math.abs(fixMile - place.mile)
      nearYou = `${along.toLocaleString('en-US', { maximumFractionDigits: 1 })} mi along the trail from you.`
    }
  }
  // Other items of this list at the same place, and a Triple Crown's peaks.
  const alsoHere: string[] = []
  if (place !== undefined) {
    for (const other of itemsAtPoi(challenge, place.poi)) {
      if (other.id === item.id) continue
      const title = itemTitle(other, today)
      if (title !== null) alsoHere.push(title)
    }
  }
  if (item.match.kind === 'places_all') {
    const earnedPeaks = tags.filter((tag) => tag.itemId === item.id).length
    alsoHere.unshift(`${earnedPeaks} of ${places.length} peaks ${CHALLENGE_WORDS.past}`)
  }

  const close = () => {
    onSetNote(note)
    onClose()
  }

  return (
    <div
      className="challenge-sheet tile-sheet"
      role="dialog"
      aria-modal="true"
      aria-labelledby="tile-sheet-title"
      onKeyDown={(event) => {
        if (event.key === 'Escape') {
          event.stopPropagation()
          close()
        }
      }}
    >
      <div
        className={`challenge-sheet__photo${photo === null ? ' tile-sheet__glyph' : ''}`}
        style={
          photo !== null
            ? { backgroundImage: `url(${JSON.stringify(photo)})` }
            : undefined
        }
      >
        {photo === null && (
          <span className="tile-sheet__tile" aria-hidden="true">
            <BlazeTile
              icon={item.icon}
              done={done}
              sealed={item.mystery !== null && itemTitle(item, today) === null}
            />
          </span>
        )}
        <div className="challenge-sheet__top">
          <span className="challenges__eyebrow">
            {section?.short ?? challenge.name} · {number} of {challenge.items.length}
          </span>
          <button
            ref={closeButton}
            type="button"
            className="challenge-sheet__close"
            aria-label="Close"
            onClick={close}
          >
            ×
          </button>
        </div>
        <div className="challenge-sheet__bottom">
          <h2 className="challenge-sheet__name" id="tile-sheet-title">
            {titleOrSealed(item, challenge, today)}
          </h2>
          {mysteryTeaser(item, today) !== null && (
            <span className="challenge-sheet__moment tile-sheet__line">
              {mysteryTeaser(item, today)}
            </span>
          )}
          {place !== undefined && (
            <span className="challenge-sheet__moment tile-sheet__line">
              ◆ {place.name} · {mileLabel(place.mile)}
            </span>
          )}
          {doneTag !== null && (
            <span className="challenge-sheet__moment tile-sheet__line">
              {CHALLENGE_WORDS.past} {formatMoment(doneTag.at)}
              {doneTag.place !== undefined ? ` · ${placeWords(doneTag.place)}` : ''}
            </span>
          )}
        </div>
        {chip !== null && <span className="challenge-sheet__chip">{chip}</span>}
      </div>
      <div className="challenge-sheet__body">
        <div className="challenge-actions tile-sheet__actions">
          {done ? (
            <>
              <span className="tile-sheet__earned" role="status">
                {CHALLENGE_WORDS.done}
                {doneTag !== null ? ` · ${formatDay(doneTag.at)}` : ''}
              </span>
              {onTakeBack !== undefined && doneTag !== null && (
                // One tap, for the hiker who pressed Earn all after walking
                // past the junction without going up. A tag already sent is
                // taken back on the server too (lib/useChallenges.ts).
                <button
                  type="button"
                  className="challenge-button challenge-button--ghost"
                  onClick={() =>
                    onTakeBack(
                      item.match.kind === 'places_all'
                        ? (doneTag.poi ?? undefined)
                        : undefined,
                    )
                  }
                >
                  {CHALLENGE_WORDS.takeBack}
                </button>
              )}
            </>
          ) : (
            earnable && (
              <button type="button" className="challenge-button" onClick={onEarn}>
                {CHALLENGE_WORDS.verb.charAt(0).toUpperCase()}
                {CHALLENGE_WORDS.verb.slice(1)} {CHALLENGE_WORDS.some}
              </button>
            )
          )}
        </div>
        {place !== undefined && (
          <div className="tile-sheet__own-photo">
            {own === null ? (
              <button
                type="button"
                className="challenge-button challenge-button--ghost"
                disabled={preparing}
                onClick={() => libraryInput.current?.click()}
              >
                {preparing
                  ? 'Preparing…'
                  : 'Use my own photo instead · stays on this phone'}
              </button>
            ) : (
              <button
                type="button"
                className="challenge-link"
                onClick={() => void ownPhotos.remove(own.id)}
              >
                Not this photo
              </button>
            )}
            <input
              ref={libraryInput}
              type="file"
              accept="image/jpeg,image/png,image/webp,image/heic"
              hidden
              data-testid="tile-sheet-library-input"
              onChange={(event) => {
                const file = event.target.files?.[0] ?? null
                event.target.value = ''
                void pickOwnPhoto(file)
              }}
            />
            {photoNote !== null && (
              <p className="challenges__note" role="status">
                {photoNote}
              </p>
            )}
          </div>
        )}
        {(nearYou !== null || alsoHere.length > 0) && (
          <div className="tile-sheet__cards">
            {nearYou !== null && (
              <div className="tile-sheet__card">
                <span className="challenges__eyebrow">Near you</span>
                <span>{nearYou}</span>
              </div>
            )}
            {alsoHere.length > 0 && (
              <div className="tile-sheet__card">
                <span className="challenges__eyebrow">Also here</span>
                <span>{alsoHere.join(' · ')}</span>
              </div>
            )}
          </div>
        )}
        {item.note !== null && (
          <div className="challenge-note">
            <span className="challenges__eyebrow">
              From {item.noteBy ?? challenge.orgName}
            </span>
            <p>{item.note}</p>
          </div>
        )}
        {done && (
          <label className="challenge-field">
            <span className="challenges__eyebrow">One line for the register</span>
            <input
              type="text"
              maxLength={200}
              value={note}
              onChange={(event) => setNote(event.target.value)}
              onBlur={() => onSetNote(note)}
            />
            <span className="challenges__note">Stays on this phone.</span>
          </label>
        )}
        <p className="challenges__note">
          Honor system, like the {challenge.orgShort}’s paper list.
          {asksWhere(item, 'hand')
            ? ` ${CHALLENGE_WORDS.verb.charAt(0).toUpperCase()}${CHALLENGE_WORDS.verb.slice(1)}ing it asks where it happened - one tap, and that answer stays on this phone.`
            : ''}
        </p>
      </div>
    </div>
  )
}
