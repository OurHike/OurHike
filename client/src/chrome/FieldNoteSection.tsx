// The card's conditions section: what the field has said about this place,
// and the one-tap way to say something back (features/FIELD_NOTES.md,
// features/DATA_NUDGES.md, built as #759's card surface).
//
// This is the line PoiCard's header spent months declining to draw - "there
// is no 'last confirmed' line, because no published artifact carries a
// confirmation date yet" - drawn now that one does. The section renders
// only for the types the ask is scoped to (water, shelter, campsite,
// resupply); a viewpoint's card is exactly as it was.
//
// THE TAP FILES IMMEDIATELY. DATA_NUDGES.md's whole design is that the
// common case costs one tap, not a form - so tapping "Dry" enqueues the
// note right there (the shell saves it to the outbox before any question
// about accounts, contributionFlow.ts's ordering), and everything after the
// tap is optional: the escalation into a real Report when the answer is
// problem-shaped, and nothing else. A hiker who has opted in
// (contribute_conditions, #759) has consented to the longer version, so
// they get a text field ABOVE the buttons - type first if you have words,
// then tap the answer, and both travel in one note.
//
// NO COUNTS ANYWHERE. Not how many notes, not how many hikers passed
// without answering - the anti-gamification rule those docs state four
// times. Notes render as what they are: dated observations, newest first.

import { useEffect, useState } from 'react'
import {
  OBSERVATION_OPTIONS,
  escalationFor,
  isNoteScopedType,
  observationLabel,
  type FieldNoteDraft,
  type NoteObservation,
  type NoteSummary,
} from '../lib/fieldNotes'
import { rollUpNotes } from '../lib/noteRollup'
import { stalenessTier } from '../lib/staleness'
import { lastConfirmedText, stalenessPresentation } from '../lib/stalenessDisplay'
import type { ReporterType } from '../lib/userPreferences'
import { signReportAs } from '../lib/reporterIdentity'

/** Where a report started from this card lands (FIELD_NOTES.md step 1: the
 *  plumbing for `poi_id` runs end to end and nothing populated it). */
export interface ReportAnchor {
  poiId: string
  lat: number
  lon: number
  mile?: number
}

export interface FieldNoteContext {
  /**
   * This place's visible notes, or null when we could not ask - the same
   * null-vs-empty distinction every conditions surface keeps (#249). Today
   * this is the map's working set (each place's most recent few); the full
   * per-place history is a live read the card could grow later.
   */
  notesFor: (poiId: string) => readonly NoteSummary[] | null
  /** The stored answer, or null until the hiker says (#233). The note signs
   *  exactly as a report does - lib/reporterIdentity.ts's floor applies. */
  reporterType: ReporterType | null
  /** The #759 opt-in: asked more thoroughly when already looking. */
  contributeConditions: boolean
  /** Queue the note. The shell owns everything after saving: the flush, and
   *  the sign-in/identity steps in contributionFlow.ts's order. */
  onAddNote: (draft: FieldNoteDraft) => void
  /** Open the report flow anchored here - the escalation's hand-off, and
   *  the card's own "report a problem" entry. */
  onReportProblem: (anchor: ReportAnchor, type?: 'shelter_repair') => void
  now: Date
}

export interface FieldNoteSectionProps {
  poiId: string
  poiType: string
  lat: number
  lon: number
  mile?: number
  context: FieldNoteContext
}

/** How many recent notes the card lists. The roll-up headline carries the
 *  newest; these are the story under it. The working set holds at most the
 *  server's per-place few anyway, so this is a display cap, not a claim. */
const NOTES_SHOWN = 3

export function FieldNoteSection({
  poiId,
  poiType,
  lat,
  lon,
  mile,
  context,
}: FieldNoteSectionProps) {
  const [text, setText] = useState('')
  // The observation just filed, so the section can acknowledge it and offer
  // the escalation. Reset when the card swaps to another part.
  const [filed, setFiled] = useState<NoteObservation | null>(null)
  useEffect(() => {
    setFiled(null)
    setText('')
  }, [poiId])

  if (!isNoteScopedType(poiType)) return null

  const notes = context.notesFor(poiId)
  const rollup = rollUpNotes(notes ?? [], context.now)
  const tier = stalenessTier(rollup.lastConfirmedAt)
  const presentation = stalenessPresentation(poiType, tier)
  const options = OBSERVATION_OPTIONS[poiType]
  const escalation = filed === null ? null : escalationFor(filed)
  const anchor: ReportAnchor = {
    poiId,
    lat,
    lon,
    ...(mile !== undefined ? { mile } : {}),
  }

  // Null means the notes could not be read - offline before any baseline
  // landed - which is NOT the same claim as "no one has said anything"
  // (#249's distinction, again). The card must not print "No recent word"
  // about a silence that is its own: it says it could not check, and the
  // ask below stays, because WRITING a note is the one thing that works
  // everywhere (the outbox is the whole design).
  const couldNotCheck = notes === null

  const file = (observation: NoteObservation) => {
    const trimmed = text.trim()
    context.onAddNote({
      poi_id: poiId,
      // The place's own coordinates, not the phone's: it is the place being
      // described, and the card path must not wait on a GPS fix
      // (lib/fieldNotes.ts on the fallback anchor).
      lat,
      lon,
      ...(mile !== undefined ? { mile } : {}),
      observation,
      ...(trimmed === '' ? {} : { note: trimmed }),
      reporter_type: signReportAs(context.reporterType),
    })
    setFiled(observation)
    setText('')
  }

  return (
    <div className="poi-card__conditions" data-testid="poi-card-conditions">
      {/* The words, always - WIREFRAMES.md §11's rule that the visual
          channel never carries the meaning alone. "No recent word" for
          never-confirmed water is the maintainer's day-one wording (#256);
          everything with a history gets the dated sentence; and a failed
          read says so rather than wearing either claim. */}
      <p className="poi-card__last-confirmed">
        {couldNotCheck
          ? 'Recent notes unavailable — no signal.'
          : tier === 'never'
            ? (presentation?.words ?? 'Never confirmed')
            : lastConfirmedText(rollup.lastConfirmedAt, context.now)}
      </p>

      {/* Both sides of a live disagreement, labelled, never averaged
          (FIELD_NOTES.md §3): a hiker who knows two people disagree about a
          spring carries water. */}
      {rollup.contested !== null ? (
        <div className="poi-card__contested" role="note">
          <p>Recent notes disagree:</p>
          <p>{rollup.contested[0].text}</p>
          <p>{rollup.contested[1].text}</p>
        </div>
      ) : (
        rollup.headline !== null && (
          <p className="poi-card__note-headline">{rollup.headline.text}</p>
        )
      )}

      {(notes ?? []).slice(0, NOTES_SHOWN).map((note) => (
        <p key={note.id} className="poi-card__note">
          {note.observation !== null && (
            <span className="poi-card__note-tag">
              {observationLabel(note.observation)}
            </span>
          )}
          {note.note !== null && (
            <span className="poi-card__note-text">“{note.note}”</span>
          )}
        </p>
      ))}

      {filed === null ? (
        <>
          {/* The longer version, for the hiker who asked for it: the words
              travel WITH the tap, in one note, rather than as a second
              interaction (#759's opt-in delta). Skippable, never required. */}
          {context.contributeConditions && (
            <textarea
              className="poi-card__note-input"
              data-testid="poi-card-note-input"
              placeholder="Anything the next hiker should know? (optional)"
              value={text}
              rows={2}
              onChange={(event) => setText(event.target.value)}
            />
          )}
          <div
            className="poi-card__observations"
            role="group"
            aria-label={`How is it right now?`}
          >
            {options.map((option) => (
              <button
                key={option.id}
                type="button"
                className="poi-card__observation"
                data-testid={`poi-card-observe-${option.id}`}
                onClick={() => file(option.id)}
              >
                {option.label}
              </button>
            ))}
          </div>
        </>
      ) : (
        <div className="poi-card__noted" role="status">
          {/* No thanks-count, no streak - an acknowledgement and, where the
              answer is problem-shaped, the hand-off into the real report
              queue (FIELD_NOTES.md §5). */}
          <p>{`Noted: ${observationLabel(filed).toLowerCase()}. It sends when there’s signal.`}</p>
          {escalation !== null && (
            <button
              type="button"
              className="poi-card__escalate"
              data-testid="poi-card-escalate"
              onClick={() =>
                context.onReportProblem(
                  anchor,
                  escalation.kind === 'form' ? escalation.type : undefined,
                )
              }
            >
              Report a problem here too
            </button>
          )}
        </div>
      )}

      {/* The quiet, always-there entry: a report started from a place card
          carries the place (FIELD_NOTES.md step 1). */}
      {filed === null && (
        <button
          type="button"
          className="poi-card__report-here"
          data-testid="poi-card-report-here"
          onClick={() => context.onReportProblem(anchor)}
        >
          Report a problem here
        </button>
      )}
    </div>
  )
}
