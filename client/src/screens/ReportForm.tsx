// The report form (WIREFRAMES.md §6), shared by condition reports and by a
// thanks - which is a report type, not a separate model
// (features/SAYING_THANKS.md).
//
// The authoring time is taken at MOUNT, not at submit. Someone can start a
// report, walk on, and finish it twenty minutes later; and an offline report
// may not send for days. What matters is when they saw the thing, so that is
// the moment recorded - matching the `authored_at` field the reports API
// accepts and the authored timestamp the outbox carries.
//
// Nothing here blocks on network. Submitting while offline queues the report
// and says so, because on this trail that is the ordinary path.

import { useEffect, useRef, useState } from 'react'
import type { ReportDraft } from '../lib/outbox'
import { MAX_REPORT_PHOTOS, PhotoUnusable, prepareReportPhoto } from '../lib/reportPhoto'
import './reporting.css'

export type ReportFormType = ReportDraft['type']

/** What each kind of report calls itself. Exported since #1439 because the
 *  shell's modal wrapper needs the same words for its `aria-label` - one home
 *  for them, rather than the window and the heading drifting apart. */
export const REPORT_FORM_TITLES: Record<ReportFormType, string> = {
  blowdown: 'Blow down',
  flooding: 'Flooding',
  trash: 'Trash',
  shelter_repair: 'Shelter repair',
  animals: 'Animals',
  invasive_species: 'Invasive species',
  bad_hikers: 'Something unsafe happened',
  thanks: 'Say thanks',
}

export interface ReportFormLocation {
  lat: number
  lon: number
  /**
   * Omitted when the fix cannot be placed on the centerline - off the trail,
   * or before the trail index has been downloaded. The coordinates are still
   * worth sending; only the mile is unknown.
   */
  mile?: number
}

export interface ReportFormSubmission extends ReportDraft {
  authoredAt: Date
  /**
   * The prepared JPEGs, in the order they were picked - bytes rather than
   * URLs, see `OutboxItem.photos`. Empty is the ordinary case.
   *
   * A LIST RATHER THAN ONE (#1439, D17), because a blowdown is three trunks
   * and one photo rarely shows it. Only the picks that finished shrinking are
   * here: a tile that failed reports under itself and sends nothing, which is
   * what lets Send stay live over it.
   */
  photos: Blob[]
}

/**
 * What the form says about where the report will land.
 *
 * "mi 0.0" is Springer Mountain and 0,0 is the Atlantic off West Africa, so
 * neither is a stand-in for "we don't know yet" - this is the same rule the
 * header already keeps about the mile readout (chrome/Header.tsx). A
 * maintainer reading a queue of blowdowns needs to be able to tell the reports
 * with a place from the ones without, and both wrong answers hide that.
 */
function describeLocation(location: ReportFormLocation | null): string {
  if (location === null) return 'No GPS fix — this report will have no location'
  if (location.mile === undefined)
    return 'Location saved, but not matched to a trail mile'

  return `mi ${location.mile.toLocaleString('en-US', {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })}`
}

/**
 * One picked photo, and the whole state machine it can be in (#1439, D17).
 *
 * A union rather than a record with three optional fields, so a tile that is
 * both "preparing" and "failed" cannot be described - which is the shape the
 * old single `photo` plus `preparing` plus `photoError` triple could, and did
 * for the length of one slow HEIC pick.
 */
type Pick =
  | { id: string; state: 'preparing' }
  | { id: string; state: 'ready'; blob: Blob; url: string }
  | { id: string; state: 'failed'; message: string }

/** `3 photos · 180 KB so far` - what is attached, and what it weighs, which
 *  is the figure a hiker about to send over one bar of EDGE is owed. Only the
 *  ready ones count: a tile still shrinking has no size yet, and a failed one
 *  will never have a size at all. */
function photoSummary(ready: readonly { blob: Blob }[]): string {
  const kb = Math.round(ready.reduce((total, pick) => total + pick.blob.size, 0) / 1024)
  return `${ready.length} ${ready.length === 1 ? 'photo' : 'photos'} · ${kb} KB so far`
}

export interface ReportFormProps {
  type: ReportFormType
  trailName: string | null
  reporterType: ReportDraft['reporter_type']
  /** Null when there is no GPS fix at all - see the note above. */
  location: ReportFormLocation | null
  /**
   * The place this report is about, when it started from a place's card
   * (FIELD_NOTES.md step 1). The soft reference `reports.poi_id` has carried
   * end to end since the schema landed, with nothing in the client
   * populating it - this is what does. Absent on every report that starts
   * from Settings, which is anchored by the fix alone exactly as before.
   */
  poiId?: string
  /**
   * Correct where this report goes (#1439, D16): stands this form aside and
   * drops a crosshair on the map, naming the mile before it is kept.
   *
   * Optional, and absent draws no control - a "Change" that opened nothing
   * would be the refusal-as-dead-control D10 forbids. The shell owns it
   * because the map is the shell's, and because this form is holding a typed
   * note and attached photos that a remount would cost.
   */
  onChangeLocation?: () => void
  onSubmit: (submission: ReportFormSubmission) => void
  onCancel: () => void
  online?: boolean
  /** One line naming who looks after this stretch; only for a thanks. */
  stewards?: string | null
  /** Injectable so the authoring stamp is testable. */
  now?: Date
}

export function ReportForm({
  type,
  trailName,
  reporterType,
  location,
  poiId,
  onChangeLocation,
  onSubmit,
  onCancel,
  online = true,
  stewards = null,
  now,
}: ReportFormProps) {
  // Captured once, on mount - see the note above.
  const [authoredAt] = useState(() => now ?? new Date())
  const [note, setNote] = useState('')
  const [picks, setPicks] = useState<readonly Pick[]>([])
  /** The hiker's own words for where this was, when nothing else can say
   *  (#1439, D16). Only asked for, and only sent, in the one state below. */
  const [placeWords, setPlaceWords] = useState('')

  /**
   * Shrink and re-encode one picked file under its own tile.
   *
   * **THE RACE IS GONE BY CONSTRUCTION, not by a token.** It used to be one
   * `photo` and a `livePick` ref: pick A (a slow HEIC), then B before it
   * finished, and B attached first, then A resolved and overwrote it - so the
   * hiker sent the photo they believed they had replaced (#657). The ref was
   * the fix and it was a fix for a shape that should not have existed. Each
   * pick now owns a tile, keyed by its own id, so nothing can land on top of
   * anything: a slow first pick resolves into ITS tile, whatever has arrived
   * since.
   *
   * **A failure costs its own tile and nothing else.** The entry goes to
   * `failed` with the words a hiker can act on, and the ready ones stay
   * attached - which is the whole argument for tiles over one field.
   */
  const choosePhoto = async (file: File | null) => {
    if (file === null) return
    const id = crypto.randomUUID()
    setPicks((current) => [...current, { id, state: 'preparing' }])

    try {
      const blob = await prepareReportPhoto(file)
      setPicks((current) =>
        // Replaced by id, and skipped entirely if the hiker removed the tile
        // while it was shrinking - a pick taken back must not come back.
        current.map((pick) =>
          pick.id === id
            ? { id, state: 'ready', blob, url: URL.createObjectURL(blob) }
            : pick,
        ),
      )
    } catch (error) {
      // The message is written for a hiker to read (lib/reportPhoto.ts);
      // anything else that got this far is not, so it does not get shown.
      const message =
        error instanceof PhotoUnusable
          ? error.message
          : 'That photo could not be prepared. Try taking another.'
      setPicks((current) =>
        current.map((pick) => (pick.id === id ? { id, state: 'failed', message } : pick)),
      )
    }
  }

  const removePick = (id: string) =>
    setPicks((current) => {
      const going = current.find((pick) => pick.id === id)
      if (going?.state === 'ready') URL.revokeObjectURL(going.url)
      return current.filter((pick) => pick.id !== id)
    })

  // Every thumbnail this form minted, released when the form goes. An object
  // URL is a reference the browser holds until it is told otherwise, and this
  // screen is opened from a ridge on a phone with the map already resident.
  //
  // Through a ref rather than by listing `picks` in the cleanup's deps: a
  // deps list would revoke on every pick, taking down the thumbnail of the
  // photo that is still attached.
  const picksRef = useRef<readonly Pick[]>([])
  useEffect(() => {
    picksRef.current = picks
  }, [picks])
  useEffect(
    () => () => {
      for (const pick of picksRef.current) {
        if (pick.state === 'ready') URL.revokeObjectURL(pick.url)
      }
    },
    [],
  )

  const ready = picks.flatMap((pick) => (pick.state === 'ready' ? [pick] : []))
  const preparing = picks.some((pick) => pick.state === 'preparing')
  const full = picks.length >= MAX_REPORT_PHOTOS

  /**
   * The one state in which the report can say where it was in words: no fix,
   * and not started from a place's card (#1439, D16).
   *
   * With a `poiId` the report is anchored to a named place and the question
   * is already answered; with a fix there are coordinates, however coarse.
   * Asking in either case would collect prose nobody needs beside a location
   * the report already has.
   */
  const asksForPlace = location === null && poiId === undefined

  const isThanks = type === 'thanks'

  return (
    <main className="reporting">
      <h1 className="reporting__title">{REPORT_FORM_TITLES[type]}</h1>

      {isThanks && stewards !== null && <p className="reporting__stewards">{stewards}</p>}

      <label className="reporting__field">
        <span className="reporting__field-label">
          {isThanks ? 'What made the difference?' : 'Note'}
        </span>
        <textarea
          className="reporting__note"
          value={note}
          rows={4}
          onChange={(event) => setNote(event.target.value)}
        />
      </label>

      {/* SEVERAL PHOTOS, EACH SHRUNK ON PICK, EACH ITS OWN TILE (#1439, D17).

          WHAT THIS REPLACES. One `<input type="file">` behind one `photo`
          state, plus a `livePick` ref (#657) whose only job was to stop a
          slow first pick overwriting a fast second one. The ref was a correct
          fix for a shape that should not have existed: with one slot, two
          picks have to fight over it. With a tile each, nothing lands on top
          of anything and the race is gone by construction.

          WHY SEVERAL AT ALL. A blowdown is three trunks and one photo rarely
          shows it. The field was built for "a note and an optional photo"
          (REPORT_A_PROBLEM.md) and a hiker standing in front of a washout has
          more than one thing to show.

          THE SHRINK STAYS ON PICK, per #234's reasoning and now once per
          tile: the only failure a hiker can do anything about is "take
          another one", and they can only do that while still standing in
          front of the thing they photographed. Independently, so one that
          will not go says so under its own tile and the rest stay attached -
          which is the difference between losing a photo and losing them
          all. */}
      <div className="reporting__field">
        <span className="reporting__field-label">Photos</span>
        <ul className="reporting__photos">
          {picks.map((pick) => (
            <li
              key={pick.id}
              className={
                pick.state === 'failed'
                  ? 'reporting__tile reporting__tile--failed'
                  : 'reporting__tile'
              }
            >
              {pick.state === 'ready' && (
                <img className="reporting__thumb" src={pick.url} alt="" />
              )}
              {pick.state === 'preparing' && (
                <span className="reporting__tile-state" role="status">
                  shrinking…
                </span>
              )}
              {pick.state === 'failed' && (
                <span className="reporting__tile-state" role="alert">
                  {pick.message}
                </span>
              )}
              {/* One remove per tile, and it works in every state: a hiker
                  who picked the wrong photo must not have to wait for the
                  wrong photo to finish shrinking before they can take it
                  back. A pick removed mid-shrink never returns - the resolve
                  below matches by id and finds nothing. */}
              <button
                type="button"
                className="reporting__tile-remove"
                aria-label={`Remove photo ${picks.indexOf(pick) + 1}`}
                onClick={() => removePick(pick.id)}
              >
                ×
              </button>
            </li>
          ))}
          {!full && (
            <li className="reporting__tile reporting__tile--add">
              <label className="reporting__add">
                <span aria-hidden="true">+</span>
                <span className="reporting__add-label">Add a photo</span>
                <input
                  type="file"
                  accept="image/jpeg,image/png,image/webp,image/heic"
                  className="reporting__photo"
                  onChange={(event) => {
                    void choosePhoto(event.target.files?.[0] ?? null)
                    // Cleared so picking the SAME file twice still fires a
                    // change - a hiker retaking a photo that failed is the
                    // commonest second pick there is.
                    event.target.value = ''
                  }}
                />
              </label>
            </li>
          )}
        </ul>
        {/* THE CEILING IS A SENTENCE, NOT A GREYED TILE (D10): a control that
            looks pressable and is not teaches a hiker at a junction that the
            app is broken. Past the cap the `+` is gone and this says why. */}
        {full && (
          <span className="reporting__meta">
            {`That is ${MAX_REPORT_PHOTOS} photos, which is as many as one report carries. Remove one to add another.`}
          </span>
        )}
        {ready.length > 0 && (
          <span className="reporting__meta">
            {`${photoSummary(ready)}. Location and camera details are not included.`}
          </span>
        )}
      </div>

      {/* WHERE THIS WILL LAND, AND A WAY TO CORRECT IT (#1439, D16).

          The three states are `describeLocation`'s, unchanged and verbatim -
          they are the whole reason that function exists, and "mi 0.0" is
          Springer Mountain while 0,0 is the Atlantic off West Africa.

          What is new is that the line is no longer only a readout. A hiker
          who walked on before filing, or whose phone never got a fix, had no
          way to say where the tree actually is; "Change" drops a crosshair on
          the map and names the mile before it is kept, through the same
          placement function the long-press plate uses (lib/placement.ts), so
          the plate and the form cannot come to answer differently. */}
      <p className="reporting__location">
        <span className="reporting__meta">{describeLocation(location)}</span>
        {onChangeLocation !== undefined && (
          <button type="button" className="reporting__change" onClick={onChangeLocation}>
            Change ›
          </button>
        )}
      </p>

      {/* A PLACE IN WORDS, WHEN NOTHING ELSE CAN SAY (#1439, D16).

          Only with no fix AND no place's card behind the report - see
          `asksForPlace`. It travels as the hiker's OWN WORDS and is never
          turned into a pin: a typed name geocoded into coordinates would be a
          confident wrong dot on every phone that downloads the report, which
          is exactly what the omitted-not-zeroed rule on lat/lon/mile exists
          to prevent. A moderator can place it; the app will not guess. */}
      {asksForPlace && (
        <label className="reporting__field">
          <span className="reporting__field-label">Where was this?</span>
          <textarea
            className="reporting__note"
            value={placeWords}
            rows={2}
            onChange={(event) => setPlaceWords(event.target.value)}
          />
          <span className="reporting__meta">
            A landmark, a road, a shelter you passed — however you would say it to
            somebody.
          </span>
        </label>
      )}

      <p className="reporting__meta">
        {`Signed as ${trailName ?? 'not set'} · ${reporterType}`}
      </p>

      {!online && (
        <p className="reporting__queued" role="status">
          No signal — this will wait in your outbox and sync later, keeping the time you
          wrote it.
        </p>
      )}

      <div className="reporting__actions">
        <button
          type="button"
          className="reporting__primary"
          // Disabled only while the shrink is running, and only then. A photo
          // that failed leaves the button live on purpose: the note is what
          // carries the report, and refusing to send it because the picture
          // did not work would lose the words over the image.
          disabled={preparing}
          onClick={() =>
            onSubmit({
              type,
              reporter_type: reporterType,
              // Present exactly when the report started from a place's card
              // - the anchor a re-measured mile cannot move (FIELD_NOTES.md
              // step 1). Spread so an unanchored report has no key at all.
              ...(poiId !== undefined ? { poi_id: poiId } : {}),
              note: note.trim() === '' ? undefined : note.trim(),
              // Both omitted rather than zeroed with no fix. The reports API
              // takes lat and lon as optional for exactly this case, and a
              // report pinned at 0,0 is not a report with a missing location -
              // it is a report at a confident, wrong place in the Atlantic.
              lat: location?.lat,
              lon: location?.lon,
              // The mile this form has been computing all along, and used to
              // throw away here (#244). It is the value the serious-warnings
              // banner filters on, and nothing server-side can re-derive it -
              // the backend holds no centerline. Same omitted-not-zeroed rule
              // as the coordinates: mi 0 is Springer Mountain, not "unknown".
              mile: location?.mile,
              // The hiker's words, sent exactly as typed and only in the one
              // state that asks for them. Trimmed to nothing means absent -
              // an empty string is a claim that somebody answered.
              ...(asksForPlace && placeWords.trim() !== ''
                ? { place_words: placeWords.trim() }
                : {}),
              authoredAt,
              // Only what actually shrank. A tile still preparing cannot be
              // here - Send is held while any is - and a failed one never
              // will be, which is what lets Send stay live over it.
              photos: ready.map((pick) => pick.blob),
            })
          }
        >
          {online ? 'Send' : 'Save to outbox'}
        </button>
        <button type="button" className="reporting__secondary" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </main>
  )
}
