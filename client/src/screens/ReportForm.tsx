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

import { useState } from 'react'
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
import type { UnitSystem } from '../lib/units'
import { LocationSheet, ReporterDetails } from './deferred'
import { PhotoTiles } from '../reporting/PhotoTiles'
import { useReportPhotos } from '../reporting/useReportPhotos'
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
  /**
   * True while the crosshair is out over the map (#1439). The shell hides
   * this form and makes it inert; the sheet inside it takes the same word
   * and hears no keys, so an Escape meant for the crosshair does not dismiss
   * a sheet nobody can see (review of #1571).
   */
  standingAside?: boolean
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
  standingAside = false,
  onSubmit,
  onCancel,
  online = true,
  stewards = null,
  now,
}: ReportFormProps) {
  // Captured once, on mount - see the note above.
  const [authoredAt] = useState(() => now ?? new Date())
  const [note, setNote] = useState('')
  // The photos, over the state machine the receipt shares (#1563).
  const photos = useReportPhotos()
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

  const { ready, preparing } = photos

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
        <PhotoTiles
          picks={photos.picks}
          ready={photos.ready}
          full={photos.full}
          choosePhoto={photos.choosePhoto}
          removePick={photos.removePick}
        />
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
          active={!standingAside}
        />
      )}
    </main>
  )
}
