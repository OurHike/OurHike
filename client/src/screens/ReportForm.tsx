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
//
// WHERE THE REPORT IS comes from the same control the window and the closure
// form use (reporting/LocationPicker.tsx, #1563), stated on one line and
// changeable from it in a sheet of its own (reporting/LocationSheet.tsx).
// This form used to hold its own three-state sentence and its own "Where was
// this?" field; both are the picker's now, so the two surfaces cannot
// describe one place differently. And a report that nothing can place - no
// fix, no named place, no marked spot, no words - is refused at Send rather
// than filed as "no location". A thanks is the exception: it is not a
// problem, and a thanks with no place is still a complete thanks
// (backend/app/routers/reports.py resolves who it is for from what it has).
//
// WHO SIGNS IT is asked above Send (reporting/ReporterDetails.tsx): the trail
// name, as every report was signed before, or the hiker's real name for this
// one report, and whether a club may contact them about it. The line that
// used to state the signature is that block's summary now.

import { useEffect, useRef, useState } from 'react'
import type { ReportDraft } from '../lib/outbox'
import { signatureFields, type SignedAs } from '../lib/reporterSignature'
import {
  hasPlace,
  locationWords,
  reportLocationFields,
  type FixSnapshot,
  type LocationChoice,
  type NearbyPlace,
  type SearchPlacesOptions,
} from '../lib/reportLocation'
import { MAX_REPORT_PHOTOS, PhotoUnusable, prepareReportPhoto } from '../lib/reportPhoto'
import type { UnitSystem } from '../lib/units'
import { LocationSheet, ReporterDetails } from './deferred'
import './reporting.css'

export type ReportFormType = ReportDraft['type']

const TITLES: Record<ReportFormType, string> = {
  blowdown: 'Blow down',
  flooding: 'Flooding',
  trash: 'Trash',
  shelter_repair: 'Shelter repair',
  animals: 'Animals',
  invasive_species: 'Invasive species',
  bad_hikers: 'Something unsafe happened',
  thanks: 'Say thanks',
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
  reporterType: ReportDraft['reporter_type']
  /** The two names the report can be signed with, from the preferences
   *  (lib/reporterSignature.ts's `namesOnOffer`) - null where none is set. */
  names: Record<SignedAs, string | null>
  /** Keep a real name typed here, so the next report offers it. A
   *  preference write, made by the shell. */
  onRealName: (name: string) => void
  /**
   * Where the report is (lib/reportLocation.ts): the card's waypoint when it
   * started from one, the pressed point from the map's plate, or the fix.
   * Owned by the shell, which is what lets the map's crosshair change it
   * while this form stands aside holding a typed note and attached photos.
   */
  location: LocationChoice
  /** The phone's fix as it is right now, or null - what a `fix` choice
   *  files at, and what the location line prints for one. */
  fix: FixSnapshot | null
  /** Named places worth offering, nearest first. Empty is ordinary. */
  places: readonly NearbyPlace[]
  onSearchPlaces?: (
    query: string,
    options?: SearchPlacesOptions,
  ) => readonly NearbyPlace[]
  /** Whether a trail index is on the phone, for the words a marked spot gets. */
  knowsTrail: boolean
  /** The hiker's unit system, for the picker's distances and the fix's radius. */
  units: UnitSystem
  onChooseLocation: (choice: LocationChoice) => void
  /**
   * Correct where this report goes on the map (#1439, D16): stands this form
   * aside and drops a crosshair, naming the mile before it is kept.
   *
   * Optional, and absent draws no map row in the picker - a control that
   * opened nothing would be the refusal-as-dead-control D10 forbids. The
   * shell owns it because the map is the shell's.
   */
  onPointOnMap?: () => void
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
  reporterType,
  names,
  onRealName,
  location,
  fix,
  places,
  onSearchPlaces,
  knowsTrail,
  units,
  onChooseLocation,
  onPointOnMap,
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
   *  (#1439, D16). Asked for by the picker only in that state, and sent only
   *  then (lib/reportLocation.ts). */
  const [placeWords, setPlaceWords] = useState('')
  /** Whether the location sheet is up. Only on demand - Change, or a Send
   *  refused for want of a place - never by itself: the sheet is modal, and
   *  a thanks needs no place at all. The refusal opens it with the alert. */
  const [picking, setPicking] = useState(false)
  /** Whether Send was just refused for want of a place - what turns the
   *  picker's opening from an offer into an alert. */
  const [refused, setRefused] = useState(false)
  /** Which name signs this report and whether the hiker may be contacted
   *  (#1563). The trail name and an unticked box unless changed, so a hiker
   *  who never touches the block sends exactly what they sent before. */
  const [signedAs, setSignedAs] = useState<SignedAs>('trail')
  const [contactOk, setContactOk] = useState(false)
  /** The real name as typed, seeded from the preference. The draft is the
   *  form's rather than the field's so Send can read it whether or not the
   *  field was ever left (review of #1571); it is persisted when the field
   *  is left and again at Send. */
  const [realName, setRealName] = useState(names.real ?? '')

  // A point kept on the map arrives as a new `location` from the shell, and
  // the picker closes on it as it closes on one of its own rows. Adjusted
  // during render, React's own pattern for reacting to a prop change.
  const [seenLocation, setSeenLocation] = useState(location)
  if (seenLocation !== location) {
    setSeenLocation(location)
    if (location.kind === 'point') {
      setPicking(false)
      setRefused(false)
    }
  }

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

  const isThanks = type === 'thanks'

  /** Whether the report can be placed at all: a fix, a named place, a marked
   *  spot, or - when none of those - the hiker's own words. */
  const placed = hasPlace(location, fix) || placeWords.trim() !== ''
  const words = locationWords(
    location,
    fix,
    units,
    knowsTrail,
    now ?? new Date(),
    placeWords,
  )

  const send = () => {
    // A PROBLEM REPORT NEEDS A PLACE (#1563). Refused rather than filed as
    // "no location" - the picker opens, says why, and Send works once it is
    // answered. A thanks goes without one: see the header.
    if (!isThanks && !placed) {
      setPicking(true)
      setRefused(true)
      return
    }
    // A real name typed and sent without leaving the field is still the
    // name: kept for next time here, since no blur will.
    if (signedAs === 'real') onRealName(realName)
    onSubmit({
      type,
      reporter_type: reporterType,
      note: note.trim() === '' ? undefined : note.trim(),
      // Who signed it, as the block above Send has it: both keys or neither
      // (lib/reporterSignature.ts), and the consent only when given. A
      // report nobody touched is signed with the trail name, which is what
      // the block shows, and carries no consent key at all.
      ...signatureFields({
        kind: signedAs,
        name:
          signedAs === 'real'
            ? realName.trim() === ''
              ? null
              : realName.trim()
            : names.trail,
      }),
      ...(contactOk ? { contact_ok: true } : {}),
      // The place, as one function spells it for every surface that files
      // (lib/reportLocation.ts): a waypoint's id and coordinates, a marked
      // spot's coordinates, or the fix with its radius and its age as of this
      // moment - and the hiker's words only when nothing else can say. The
      // mile is omitted rather than zeroed wherever it is unknown (#244): mi
      // 0.0 is Springer Mountain, and the serious-warnings banner filters on
      // it.
      // The age of the fix is measured at Send, against the same injectable
      // clock the authoring stamp uses, so a test can pin it.
      ...reportLocationFields(location, fix, now ?? new Date(), placeWords),
      authoredAt,
      // Only what actually shrank. A tile still preparing cannot be here -
      // Send is held while any is - and a failed one never will be, which is
      // what lets Send stay live over it.
      photos: ready.map((pick) => pick.blob),
    })
  }

  return (
    // A MODAL, SAID OUT LOUD, AND SAID HERE (#1439). As a `flowScreen` this
    // form replaced the screen, so there was nothing behind it to reach; as
    // an overlay there is - the tab bar and whichever tab screen was up.
    // `inert` cannot go on those without a wrapper App.tsx does not have and
    // a remount it must not cause, so the claim is made from this side:
    // `aria-modal` is what tells assistive technology that everything outside
    // this subtree is out of play while it is open.
    //
    // ON THE FORM RATHER THAN ON THE SHELL'S POSITIONING DIV, which is the
    // detail worth keeping: naming it from up there meant lifting these
    // titles into App.tsx, and that one value import pulled this whole
    // deferred screen into the eager bundle and put the launch budget 2,972
    // bytes over (features/LAUNCH_BUDGET.md §3). `aria-labelledby` on the
    // heading this form already renders costs nothing and is the more
    // correct spelling anyway - the dialog is the form, not the box holding
    // it.
    <main
      className="reporting"
      role="dialog"
      aria-modal="true"
      aria-labelledby="reporting-title"
    >
      <h1 className="reporting__title" id="reporting-title">
        {TITLES[type]}
      </h1>

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

      {/* WHERE THIS WILL LAND, AND A WAY TO CORRECT IT (#1439, D16; #1563).

          The line states the place and HOW it is known - a named place at
          its mile, the fix with its radius and age, a spot marked on the
          map - and "Change" opens the same picker the report window uses,
          in a sheet over this form: a place nearby, where you are, the map,
          and words when nothing else can say. The three states
          describeLocation used to spell are still here, spelled by
          lib/reportLocation.ts for every surface at once; "mi 0.0" is
          Springer Mountain and 0,0 is the Atlantic off West Africa, and
          neither is a stand-in for "we do not know". */}
      <div className="reporting__field">
        <p className="reporting__location">
          <span className="reporting__meta" data-testid="report-form-location">
            {words.detail === null ? words.label : `${words.label} · ${words.detail}`}
          </span>
          <button
            type="button"
            className="reporting__change"
            data-testid="report-form-change"
            aria-haspopup="dialog"
            onClick={() => {
              setPicking(true)
              setRefused(false)
            }}
          >
            Change ›
          </button>
        </p>
      </div>

      {/* WHO SIGNED IT (#1563) - the whole signature in one sentence, as the
          static line here used to say it, and the two choices under it. */}
      <ReporterDetails
        trailName={names.trail}
        signedAs={signedAs}
        onSignedAs={setSignedAs}
        realName={realName}
        onRealNameChange={setRealName}
        onRealNameSettle={() => onRealName(realName)}
        contactOk={contactOk}
        onContactOk={setContactOk}
        reporterType={reporterType}
      />

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
          onClick={send}
        >
          {online ? 'Send' : 'Save to outbox'}
        </button>
        <button type="button" className="reporting__secondary" onClick={onCancel}>
          Cancel
        </button>
      </div>

      {/* THE SHEET, over this form, while Change is open or nothing has
          placed the report yet. Inside the form's own element so it stands
          aside with the form when the crosshair goes out (#1439). */}
      {picking && (
        <LocationSheet
          choice={location}
          fix={fix}
          places={places}
          onSearch={onSearchPlaces}
          units={units}
          knowsTrail={knowsTrail}
          onChoose={(choice) => {
            onChooseLocation(choice)
            setPicking(false)
            setRefused(false)
          }}
          onPointOnMap={onPointOnMap}
          // The hiker's words, sent exactly as typed and only in the one
          // state that asks for them. Never turned into a pin: a typed name
          // geocoded into coordinates would be a confident wrong dot on
          // every phone that downloads the report. A moderator places it.
          words={{
            value: placeWords,
            onChange: (value) => {
              setPlaceWords(value)
              setRefused(false)
            },
          }}
          needed={refused}
          now={now}
          onClose={() => {
            setPicking(false)
            setRefused(false)
          }}
        />
      )}
    </main>
  )
}
