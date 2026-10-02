// One challenge (#1780, frames 5, 7, 4b, 8b and 8c).
//
// The pine header names it, its window and - only when the club set one - the
// finish line; a strip lays its places along the trail in mile order. Filter
// pills split the list the way the handoff draws it: "On the trail" for the
// named places and walked sections, then each of the club's own sections for
// the rest, then Mystery.
//
// WHAT A ROW NEVER SAYS: what the hiker has not done. No "you haven't", no
// count of what is left, no days remaining - features/VOLUNTEERING.md §5 rule
// 2, and ChallengeDetail.test.tsx holds the words out.
//
// A DRAFT TAKES NO ENTRY. The maintainer's condition for publishing one
// (poll, 2026-09-30) is that it is labelled everywhere; the finish screen
// adds that there is nobody yet to send an entry to, rather than collecting a
// sweepstakes entry the club never agreed to run.

import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { API_CONFIGURED } from '../lib/api'
import { CHALLENGE_WORDS } from '../lib/challengeWords'
import type { ChallengeEntryDraft } from '../lib/challengeDrafts'
import {
  isOpen,
  isPlaceItem,
  isSealed,
  itemTitle,
  shortDate,
  windowLine,
  type Challenge,
  type ChallengeItem,
  type ChallengePlace,
} from '../lib/challenges'
import {
  doneItems,
  isItemDone,
  itemDoneAt,
  progress,
  tagsFor,
  type ChallengeState,
  type ChallengeTag,
} from '../lib/challengeProgress'
import type { MileRange } from '../lib/walkedMiles'
import { localDay } from '../lib/passedToday'
import { Diamond, DraftLabel, FinishBar, TagPill } from '../chrome/ChallengeParts'
import {
  formatDay,
  formatMoment,
  handTaggable,
  itemMeta,
  itemTrailing,
  mileLabel,
  titleOrSealed,
  trailLabel,
} from '../lib/challengeText'

export interface ChallengeDetailProps {
  challenge: Challenge
  state: ChallengeState
  /** The hiker's local YYYY-MM-DD. */
  today: string
  /** All-time walked miles, lib/walkedMiles.ts - "your line" on a tagged
   *  place. Never uploaded, never stored here. */
  walked: readonly MileRange[]
  /** The hiker's own photo of a place, if they added one on its card
   *  (features/POI_PHOTOS.md) - kept on the phone, never uploaded. */
  ownPhotoFor?: (poiId: string) => string | null
  signedIn: boolean
  /** For the entry form's name field; the hiker can change it. */
  defaultName?: string
  onJoin: () => void
  onLeave: () => void
  /** `poi` names one place of a Triple-Crown-style item. */
  onTag: (item: ChallengeItem, poi?: string) => void
  onUntag: (item: ChallengeItem, poi?: string) => void
  /** "Remove this tag" on the tagged-place sheet - however it was made. */
  onRemoveTag?: (item: ChallengeItem, poi?: string) => void
  onSetNote: (item: ChallengeItem, note: string) => void
  onSendEntry: (entry: ChallengeEntryDraft) => void
  /** What happened to a sent entry, read from the outbox by the shell:
   *  still waiting to leave, or refused with the server's sentence. Absent
   *  once it has left. */
  entryState?: { kind: 'waiting' } | { kind: 'refused'; reason: string }
  /** Clears a refused entry so the form comes back. */
  onForgetEntry?: () => void
  onSignIn?: () => void
  onOpenWorkdays?: () => void
}

type Filter = { key: string; label: string; items: ChallengeItem[] }

export function ChallengeDetail(props: ChallengeDetailProps) {
  const { challenge, state, today } = props
  const joined = state.joined.some((entry) => entry.challengeId === challenge.id)
  const tags = tagsFor(state, challenge.id)
  const { tagged, finish, eligible } = progress(challenge, state)
  const [view, setView] = useState<'list' | 'finish'>('list')
  const [sheetItem, setSheetItem] = useState<string | null>(null)
  const [confirmingLeave, setConfirmingLeave] = useState(false)
  // Where focus goes back to when the sheet closes - the row that opened it,
  // or the page's title when that row is gone.
  const opener = useRef<HTMLElement | null>(null)
  const title = useRef<HTMLHeadingElement | null>(null)
  const [refocus, setRefocus] = useState(false)
  useEffect(() => {
    if (!refocus) return
    setRefocus(false)
    if (opener.current?.isConnected) opener.current.focus()
    else title.current?.focus()
  }, [refocus])
  // Tags only count inside the window, so nothing offers one outside it
  // (review, 2026-09-30: the ATC's 2027 draft is on phones in 2026).
  const open = isOpen(challenge, today)

  const filters = useMemo<Filter[]>(() => {
    // South to north - the order a hiker meets them, and the strip's order.
    const firstMile = (item: ChallengeItem) =>
      isPlaceItem(item)
        ? item.match.places[0].mile
        : item.match.kind === 'section_walked'
          ? item.match.fromMile
          : 0
    const onTrail = challenge.items
      .filter(
        (item) =>
          item.mystery === null &&
          (isPlaceItem(item) || item.match.kind === 'section_walked'),
      )
      .sort((a, b) => firstMile(a) - firstMile(b))
    const out: Filter[] = [{ key: 'trail', label: 'On the trail', items: onTrail }]
    for (const section of challenge.sections) {
      out.push({
        key: section.id,
        label: section.short,
        items: challenge.items.filter(
          (item) => item.section === section.id && !onTrail.includes(item),
        ),
      })
    }
    return out.filter((filter) => filter.items.length > 0)
  }, [challenge])
  const [filterKey, setFilterKey] = useState<string>(() => filters[0]?.key ?? 'trail')
  const shown = filters.find((filter) => filter.key === filterKey) ?? filters[0]

  if (view === 'finish' && finish !== null) {
    return <Finish {...props} onDone={() => setView('list')} />
  }

  const closeSheet = () => {
    setSheetItem(null)
    setRefocus(true)
  }
  // After the render that closed the sheet, not in the handler: "Remove this
  // tag" leaves an item that is no longer done, and that same render turns
  // its row from a button into text. Focus sent to the button before it was
  // replaced fell to <body> (second Challenges review, 2026-10-01); the title
  // is always there.

  const sheet =
    sheetItem === null
      ? null
      : (challenge.items.find((item) => item.id === sheetItem) ?? null)

  return (
    <section className="challenges" aria-labelledby="challenge-title">
      <header className="challenge-head">
        <p className="challenges__eyebrow">
          {challenge.orgShort} · {trailLabel(challenge.trail)} · {windowLine(challenge)}
        </p>
        <h1 className="challenges__title" id="challenge-title" ref={title} tabIndex={-1}>
          {challenge.name}
        </h1>
        <DraftLabel challenge={challenge} />
        {challenge.summary !== null && (
          <p className="challenge-head__summary">{challenge.summary}</p>
        )}
        {challenge.reward?.rulesUrl != null && (
          <a
            href={challenge.reward.rulesUrl}
            target="_blank"
            rel="noreferrer"
            className="challenge-head__rules"
          >
            The {challenge.orgShort}’s rules
          </a>
        )}
        {finish !== null && joined && (
          <>
            <div className="challenge-head__line">
              <span>
                {tagged} of {finish}
                {challenge.finish?.label ? ` ${challenge.finish.label}` : ''}
              </span>
            </div>
            <FinishBar tagged={tagged} finish={finish} />
          </>
        )}
        <PlaceStrip challenge={challenge} tags={tags} today={today} />
      </header>

      {/* To everyone, not only a hiker who joined: somebody deciding whether
          to join a list that does not open until May is the one this is for
          (second Challenges review, 2026-10-01). */}
      {!open && (
        <p className="challenges__note">
          {challenge.window.opens !== null && today < challenge.window.opens
            ? `Opens ${shortDate(challenge.window.opens)}. ${capitalised(CHALLENGE_WORDS.nounPlural)} count from then.`
            : joined
              ? `Closed ${shortDate(challenge.window.closes ?? today)}. What you ${CHALLENGE_WORDS.past} stays here as a record.`
              : `Closed ${shortDate(challenge.window.closes ?? today)}.`}
        </p>
      )}

      {!joined ? (
        <div className="challenge-actions">
          <button type="button" className="challenge-button" onClick={props.onJoin}>
            Join
          </button>
          <p className="challenges__note">
            Joining keeps this list on your phone. Nothing is sent until you{' '}
            {CHALLENGE_WORDS.noun} a place.
          </p>
        </div>
      ) : (
        eligible && (
          <div className="challenge-actions">
            <button
              type="button"
              className="challenge-button"
              onClick={() => setView('finish')}
            >
              {challenge.reward === null ? 'See your finish' : 'Your finish'}
            </button>
          </div>
        )
      )}

      <div className="challenge-pills" role="group" aria-label="Show">
        {filters.map((filter) => (
          <button
            key={filter.key}
            type="button"
            className="challenge-pill"
            aria-pressed={filter.key === shown?.key}
            onClick={() => setFilterKey(filter.key)}
          >
            {filter.label}
          </button>
        ))}
      </div>

      <ul className="challenge-rows">
        {(shown?.items ?? []).map((item) => (
          <ItemRow
            key={item.id}
            challenge={challenge}
            item={item}
            tags={tags}
            today={today}
            joined={joined}
            open={open}
            onTag={(poi) => props.onTag(item, poi)}
            onUntag={(poi) => props.onUntag(item, poi)}
            onOpen={(from) => {
              opener.current = from
              setSheetItem(item.id)
            }}
          />
        ))}
      </ul>

      {shown?.key === 'mystery' && (
        <p className="challenges__note">
          Mystery items arrive with the data refresh. A dated one opens on this phone on
          its day, with no signal needed.
        </p>
      )}

      {joined && (
        <>
          <p className="challenges__note">
            {!API_CONFIGURED
              ? `Saved on this phone. It waits here until OurHike’s server is running, then the ${challenge.orgShort} sees a count - never your name.`
              : props.signedIn
                ? `Saved on this phone. With signal, OurHike counts it for the ${challenge.orgShort} - they see a number, never your name.`
                : `Saved on this phone. Once you sign in and have signal, OurHike counts it for the ${challenge.orgShort} - they see a number, never your name.`}
          </p>
          <div className="challenge-actions">
            {confirmingLeave ? (
              <>
                <p className="challenges__note" role="status">
                  Leave {challenge.name}? Its places come off your map and the{' '}
                  {challenge.orgShort} stops counting you. What you {CHALLENGE_WORDS.past}{' '}
                  stays on this phone if you join again.
                </p>
                <button
                  type="button"
                  className="challenge-button challenge-button--ghost"
                  onClick={() => {
                    setConfirmingLeave(false)
                    props.onLeave()
                  }}
                >
                  Leave
                </button>
                <button
                  type="button"
                  className="challenge-button"
                  onClick={() => setConfirmingLeave(false)}
                >
                  Stay
                </button>
              </>
            ) : (
              <button
                type="button"
                className="challenge-button challenge-button--ghost"
                onClick={() => setConfirmingLeave(true)}
              >
                Leave this challenge
              </button>
            )}
          </div>
        </>
      )}

      {sheet !== null && (
        <TaggedPlace
          challenge={challenge}
          item={sheet}
          tag={itemDoneAt(sheet, challenge.id, tags)}
          tags={tags}
          walked={props.walked}
          today={today}
          ownPhotoFor={props.ownPhotoFor}
          onSetNote={(note) => props.onSetNote(sheet, note)}
          onRemove={
            props.onRemoveTag === undefined
              ? undefined
              : (poi) => {
                  props.onRemoveTag?.(sheet, poi)
                  closeSheet()
                }
          }
          onOpenWorkdays={props.onOpenWorkdays}
          onClose={closeSheet}
        />
      )}
    </section>
  )
}

function ItemRow({
  challenge,
  item,
  tags,
  today,
  joined,
  open,
  onTag,
  onUntag,
  onOpen,
}: {
  challenge: Challenge
  item: ChallengeItem
  tags: readonly ChallengeTag[]
  today: string
  joined: boolean
  /** Inside the window - the only time a new tag is offered. */
  open: boolean
  onTag: (poi?: string) => void
  onUntag: (poi?: string) => void
  /** Opens the tagged-place sheet; `from` is where focus returns. */
  onOpen: (from: HTMLElement) => void
}) {
  const sealed = isSealed(item, today)
  const done = isItemDone(item, challenge.id, tags)
  const doneTag = itemDoneAt(item, challenge.id, tags)
  const title = titleOrSealed(item, challenge, today)
  const trailing = itemTrailing(item)
  const revealed = item.mystery !== null && !sealed
  // A row opens its sheet once it is done and holds a tag the hiker can look
  // at or take back: a place, or "any shelter". The kinds that tag
  // themselves would be put straight back by the day's walk, so they do not.
  const opens = done && (isPlaceItem(item) || item.match.kind === 'poi_type')

  let right: ReactNode = null
  if (!sealed && joined) {
    if (done && doneTag?.how === 'gps') {
      right = <span className="challenge-row__done">done</span>
    } else if (item.match.kind === 'places_all') {
      right = null
    } else if (handTaggable(item) && (open || done)) {
      right = (
        <TagPill
          tagged={done}
          label={`${done ? CHALLENGE_WORDS.done : CHALLENGE_WORDS.act}: ${title}`}
          onPress={() => (done ? onUntag() : onTag())}
        />
      )
    } else if (done) {
      right = <span className="challenge-row__done">done</span>
    }
  }

  const places = item.match.kind === 'places_all' ? item.match.places : []
  const text = (
    <>
      {!sealed && <Diamond done={done} />}
      <span className="challenge-row__text">
        {revealed && (
          <span className="challenge-row__mystery">
            Mystery #{item.mystery?.number}
            {item.mystery?.revealOn
              ? ` · revealed ${formatDay(item.mystery.revealOn)}`
              : ''}
          </span>
        )}
        <span className="challenge-row__title">{title}</span>
        {!sealed && (
          <span className="challenge-row__meta">
            {itemMeta(item)}
            {doneTag !== null
              ? ` · ${CHALLENGE_WORDS.past} ${formatDay(doneTag.at)}`
              : ''}
          </span>
        )}
      </span>
      {trailing !== undefined && !sealed && (
        <span className="challenge-row__trailing">{trailing}</span>
      )}
    </>
  )

  return (
    <li className={sealed ? 'challenge-row challenge-row--sealed' : 'challenge-row'}>
      {/* A button only when it does something: a disabled button on every
          row that cannot open yet read each one out as "unavailable". */}
      {opens ? (
        <button
          type="button"
          className="challenge-row__open"
          onClick={(event) => onOpen(event.currentTarget)}
        >
          {text}
        </button>
      ) : (
        <div className="challenge-row__open">{text}</div>
      )}
      {right}
      {places.length > 0 && joined && !sealed && (
        // Each peak of a Triple Crown is its own tag: the row says which are
        // done and offers the rest, rather than waiting for all three.
        <ul className="challenge-subrows">
          {places.map((place) => {
            const placeTag = tags.find(
              (entry) => entry.itemId === item.id && entry.poi === place.poi,
            )
            return (
              <li key={place.poi} className="challenge-subrow">
                <Diamond done={placeTag !== undefined} />
                <span className="challenge-subrow__name">{place.name}</span>
                <span className="challenge-row__trailing">{mileLabel(place.mile)}</span>
                {placeTag?.how === 'gps' ? (
                  <span className="challenge-row__done">done</span>
                ) : open || placeTag !== undefined ? (
                  <TagPill
                    tagged={placeTag !== undefined}
                    label={`${placeTag !== undefined ? CHALLENGE_WORDS.done : CHALLENGE_WORDS.act}: ${place.name}`}
                    onPress={() =>
                      placeTag !== undefined ? onUntag(place.poi) : onTag(place.poi)
                    }
                  />
                ) : null}
              </li>
            )
          })}
        </ul>
      )}
    </li>
  )
}

/** Every place on the list along the trail, in mile order, ends named for
 *  the first and last place - positions, never a count. */
function PlaceStrip({
  challenge,
  tags,
  today,
}: {
  challenge: Challenge
  tags: readonly ChallengeTag[]
  today: string
}) {
  const points: { place: ChallengePlace; done: boolean; key: string }[] = []
  for (const item of challenge.items) {
    if (!isPlaceItem(item) || isSealed(item, today)) continue
    for (const place of item.match.places) {
      const done =
        item.match.kind === 'places_all'
          ? tags.some((tag) => tag.itemId === item.id && tag.poi === place.poi)
          : isItemDone(item, challenge.id, tags)
      points.push({ place, done, key: `${item.id}/${place.poi}` })
    }
  }
  if (points.length < 2) return null
  points.sort((a, b) => a.place.mile - b.place.mile)
  const low = points[0].place.mile
  const high = points[points.length - 1].place.mile
  const span = high - low || 1
  return (
    <div aria-hidden="true">
      <div className="challenge-strip">
        {points.map((point) => (
          <span
            key={point.key}
            className="challenge-strip__point"
            style={{ left: `${((point.place.mile - low) / span) * 100}%` }}
          >
            <Diamond done={point.done} />
          </span>
        ))}
      </div>
      <div className="challenge-strip__ends">
        <span>{points[0].place.name}</span>
        <span>{points[points.length - 1].place.name}</span>
      </div>
    </div>
  )
}

/** The tagged place (#4b): the hiker's own photo or the club's, labelled
 *  which; the moment; the club's note; the line walked; a private register
 *  line. No stamp, no animation. */
function TaggedPlace({
  challenge,
  item,
  tag,
  tags,
  walked,
  today,
  ownPhotoFor,
  onSetNote,
  onRemove,
  onOpenWorkdays,
  onClose,
}: {
  challenge: Challenge
  item: ChallengeItem
  tag: ChallengeTag | null
  tags: readonly ChallengeTag[]
  walked: readonly MileRange[]
  today: string
  ownPhotoFor?: (poiId: string) => string | null
  onSetNote: (note: string) => void
  /** Takes the tag back - `poi` for one peak of a Triple Crown. */
  onRemove?: (poi?: string) => void
  onOpenWorkdays?: () => void
  onClose: () => void
}) {
  // A dialog takes focus and gives it back (ChallengeDetail's `opener`), and
  // Escape closes it, as every sheet in this app does.
  const closeButton = useRef<HTMLButtonElement | null>(null)
  useEffect(() => {
    closeButton.current?.focus()
  }, [])
  const places = isPlaceItem(item) ? item.match.places : []
  const place =
    places.find((candidate) => candidate.poi === tag?.poi) ?? places[places.length - 1]
  const own =
    place !== undefined && ownPhotoFor !== undefined ? ownPhotoFor(place.poi) : null
  const photo = own ?? item.photo
  const chip = own !== null ? 'your photo' : item.photo !== null ? 'club photo' : null
  const [note, setNote] = useState(
    () =>
      tags.find((existing) => existing.itemId === item.id && existing.note)?.note ?? '',
  )

  // "Your line": ten miles either side of the place, the hiker's own walked
  // miles filled, the challenge's places on it as diamonds.
  const centre = place?.mile ?? 0
  const low = Math.max(0, centre - 10)
  const high = centre + 10
  const at = (mile: number) =>
    `${((Math.min(high, Math.max(low, mile)) - low) / (high - low)) * 100}%`
  const nearby: { mile: number; done: boolean; key: string }[] = []
  for (const other of challenge.items) {
    if (!isPlaceItem(other) || isSealed(other, today)) continue
    for (const candidate of other.match.places) {
      if (candidate.mile < low || candidate.mile > high) continue
      nearby.push({
        mile: candidate.mile,
        done: isItemDone(other, challenge.id, tags),
        key: `${other.id}/${candidate.poi}`,
      })
    }
  }

  return (
    <div
      className="challenge-sheet"
      role="dialog"
      aria-modal="true"
      aria-labelledby="tagged-place-name"
      onKeyDown={(event) => {
        if (event.key === 'Escape') {
          event.stopPropagation()
          onSetNote(note)
          onClose()
        }
      }}
    >
      <div
        className="challenge-sheet__photo"
        style={
          photo !== null
            ? { backgroundImage: `url(${JSON.stringify(photo)})` }
            : undefined
        }
      >
        <div className="challenge-sheet__top">
          <span className="challenges__eyebrow">{challenge.name}</span>
          <button
            ref={closeButton}
            type="button"
            className="challenge-sheet__close"
            aria-label="Close"
            onClick={onClose}
          >
            ×
          </button>
        </div>
        <div className="challenge-sheet__bottom">
          <h2 className="challenge-sheet__name" id="tagged-place-name">
            {place?.name ?? itemTitle(item, today)}
          </h2>
          {tag !== null && (
            <span className="challenge-sheet__moment">{formatMoment(tag.at)}</span>
          )}
        </div>
        {chip !== null && <span className="challenge-sheet__chip">{chip}</span>}
      </div>
      <div className="challenge-sheet__body">
        {item.note !== null && (
          <div className="challenge-note">
            <span className="challenges__eyebrow">
              From {item.noteBy ?? challenge.orgName}
            </span>
            <p>{item.note}</p>
            {onOpenWorkdays !== undefined && (
              <button type="button" className="challenge-link" onClick={onOpenWorkdays}>
                Workdays on this section
              </button>
            )}
          </div>
        )}
        {place !== undefined && (
          <div>
            <p className="challenges__eyebrow">
              Your line · {trailLabel(challenge.trail)}
            </p>
            <div className="challenge-line" aria-hidden="true">
              <span className="challenge-line__track" />
              {walked
                .filter((range) => range.endMile > low && range.startMile < high)
                .map((range) => (
                  <span
                    key={`${range.startMile}-${range.endMile}`}
                    className="challenge-line__walked"
                    style={{
                      left: at(range.startMile),
                      width: `calc(${at(range.endMile)} - ${at(range.startMile)})`,
                    }}
                  />
                ))}
              {nearby.map((point) => (
                <span
                  key={point.key}
                  className="challenge-strip__point"
                  style={{ left: at(point.mile) }}
                >
                  <Diamond done={point.done} />
                </span>
              ))}
            </div>
            <div className="challenge-line__ends">
              <span>{mileLabel(low)}</span>
              <span>{mileLabel(high)}</span>
            </div>
          </div>
        )}
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
        <div className="challenge-actions">
          <button
            type="button"
            className="challenge-button"
            onClick={() => {
              onSetNote(note)
              onClose()
            }}
          >
            Done
          </button>
          {onRemove !== undefined && tag !== null && (
            // For the hiker who pressed Tag all after walking past the
            // junction without going up. A tag already sent is taken back on
            // the server too (lib/useChallenges.ts).
            <button
              type="button"
              className="challenge-button challenge-button--ghost"
              onClick={() =>
                onRemove(
                  item.match.kind === 'places_all' ? (tag.poi ?? undefined) : undefined,
                )
              }
            >
              Remove this {CHALLENGE_WORDS.noun}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

function capitalised(word: string): string {
  return word.charAt(0).toUpperCase() + word.slice(1)
}

const REWARD_WORDS: Record<
  NonNullable<Challenge['reward']>['kind'],
  { act: string; thing: string; physical: boolean }
> = {
  drawing: { act: 'Enter the drawing', thing: 'the drawing', physical: false },
  patch: { act: 'Claim your patch', thing: 'a patch', physical: true },
  postcard: { act: 'Claim your postcard', thing: 'a postcard', physical: true },
  sticker: { act: 'Claim your sticker', thing: 'a sticker', physical: true },
}

/** The server's own email check (backend/app/schemas/common.py's `_EMAIL`),
 *  so the phone refuses on the form what the server would refuse after a
 *  week in the outbox. */
const EMAIL_SHAPE = /^[^@\s,;<>"]{1,64}@[A-Za-z0-9-]{1,63}(?:\.[A-Za-z0-9-]{1,63}){1,8}$/
/** backend/app/schemas/trail_challenge.py's ENTRY_NAME_MAX_CHARS and
 *  MAILING_ADDRESS_MAX_CHARS. */
const NAME_MAX_CHARS = 200
const ADDRESS_MAX_CHARS = 1000

/** The finish (#8b with a reward, #8c without). */
function Finish(props: ChallengeDetailProps & { onDone: () => void }) {
  const { challenge, state, today } = props
  const done = doneItems(challenge, state)
  // The hiker's own days: a tag at 9 pm and one at 7 am the next morning are
  // two days on the trail, which their UTC dates were not.
  const days = new Set(done.map((entry) => localDay(new Date(entry.tag.at)))).size
  const sent = state.sent.find((entry) => entry.challengeId === challenge.id) ?? null
  const refused =
    sent !== null && props.entryState?.kind === 'refused' ? props.entryState : null
  const draft = challenge.status === 'draft'
  const closed = challenge.window.closes !== null && today > challenge.window.closes
  // Reachable only if the published window moved after the tags were made;
  // the server would take the entry, and the club would count it early.
  const early = challenge.window.opens !== null && today < challenge.window.opens
  const reward = challenge.reward
  const words = reward === null ? null : REWARD_WORDS[reward.kind]
  const [name, setName] = useState(props.defaultName ?? '')
  const [contact, setContact] = useState('')
  const [consented, setConsented] = useState(false)
  const [telling, setTelling] = useState(false)
  const heading = useRef<HTMLHeadingElement | null>(null)
  // Arriving here is a new view: focus its heading, not <body>.
  useEffect(() => {
    heading.current?.focus()
  }, [])
  const summary = `${done.length} ${CHALLENGE_WORDS.past} over ${days} ${days === 1 ? 'day' : 'days'}.`
  const orgDomain = challenge.orgDomain

  const header = (
    <header className="challenge-head">
      <p className="challenges__eyebrow">{challenge.orgName}</p>
      <h1 className="challenges__title" ref={heading} tabIndex={-1}>
        You walked {challenge.name}
      </h1>
      <DraftLabel challenge={challenge} />
    </header>
  )

  // Why nothing can be sent, in one sentence, or null when it can.
  const refusal = draft
    ? `The ${challenge.orgShort} has not confirmed this list yet, so there is nobody to send anything to through OurHike.`
    : closed && challenge.window.closes !== null
      ? `Entries closed on ${formatDay(challenge.window.closes)}.`
      : early && challenge.window.opens !== null
        ? `Entries open on ${formatDay(challenge.window.opens)}.`
        : orgDomain === null
          ? `This phone's copy of the list is too old to send anything to the ${challenge.orgShort}. It updates with the next data refresh.`
          : null

  // Where a sent entry stands: refused (with the server's own sentence and a
  // way back to the form), waiting in the outbox, or gone.
  const sentLine =
    sent === null ? null : refused !== null ? (
      <div className="challenge-actions">
        <p className="challenges__empty">
          The {challenge.orgShort} did not take it: {refused.reason}
        </p>
        {props.onForgetEntry !== undefined && (
          <button
            type="button"
            className="challenge-button challenge-button--ghost"
            onClick={props.onForgetEntry}
          >
            Change it and send again
          </button>
        )}
      </div>
    ) : props.entryState?.kind === 'waiting' ? (
      <p className="challenges__note">
        {API_CONFIGURED
          ? `Saved ${formatDay(sent.at)}. It leaves this phone next time you have signal.`
          : `Saved ${formatDay(sent.at)}. It waits on this phone until OurHike’s server is running.`}
      </p>
    ) : (
      <p className="challenges__note">
        {sent.kind === 'finished' ? 'Told the club' : 'Sent'} {formatDay(sent.at)}.
      </p>
    )

  if (reward === null || words === null) {
    return (
      <section className="challenges" aria-label={`You walked ${challenge.name}`}>
        {header}
        <ul className="challenge-rows">
          {done.map(({ item, tag }) => (
            <li key={item.id} className="challenge-row">
              <Diamond done big />
              <span className="challenge-row__text">
                <span className="challenge-row__title">
                  {titleOrSealed(item, challenge, today)}
                </span>
              </span>
              <span className="challenge-row__trailing">{formatDay(tag.at)}</span>
            </li>
          ))}
        </ul>
        <p className="challenges__note">
          {summary} It stays in your challenges as a record of the trip.
        </p>
        {sentLine}
        {sent === null && refusal !== null && (
          // Said, rather than the button silently vanishing.
          <p className="challenges__note">{refusal}</p>
        )}
        <div className="challenge-actions">
          <button type="button" className="challenge-button" onClick={props.onDone}>
            Done
          </button>
          {refusal === null &&
            sent === null &&
            (!props.signedIn ? (
              props.onSignIn !== undefined && (
                <button
                  type="button"
                  className="challenge-button challenge-button--ghost"
                  onClick={props.onSignIn}
                >
                  Sign in to let the club know
                </button>
              )
            ) : !telling ? (
              <button
                type="button"
                className="challenge-button challenge-button--ghost"
                onClick={() => setTelling(true)}
              >
                Let the club know you finished
              </button>
            ) : null)}
        </div>
        {telling &&
          sent === null &&
          refusal === null &&
          props.signedIn &&
          orgDomain !== null && (
            <>
              <label className="challenge-field">
                <span className="challenges__eyebrow">
                  Your name, as the club will see it
                </span>
                <input
                  type="text"
                  value={name}
                  maxLength={NAME_MAX_CHARS}
                  autoComplete="name"
                  onChange={(event) => setName(event.target.value)}
                />
              </label>
              <p className="challenges__note">
                The {challenge.orgShort} receives your name and the day you finished.
                Nothing else.
              </p>
              <div className="challenge-actions">
                <button
                  type="button"
                  className="challenge-button"
                  disabled={name.trim() === ''}
                  onClick={() =>
                    props.onSendEntry({
                      challenge_id: challenge.id,
                      org_domain: orgDomain,
                      name: name.trim(),
                      item_ids: [],
                      consented: true,
                      finished_only: true,
                    })
                  }
                >
                  Send
                </button>
              </div>
            </>
          )}
      </section>
    )
  }

  const tiles = done.slice(0, 5)
  const more = done.length - tiles.length
  const contactLabel = words.physical ? 'Mailing address' : 'Email'
  const contactOk = words.physical
    ? contact.trim() !== '' && contact.trim().length <= ADDRESS_MAX_CHARS
    : EMAIL_SHAPE.test(contact.trim())
  const ready = name.trim() !== '' && contactOk && consented

  return (
    <section className="challenges" aria-label={`You walked ${challenge.name}`}>
      {header}
      <p className="challenges__note">{summary}</p>
      <div className="challenge-grid" aria-hidden="true">
        {tiles.map(({ item }) => (
          <span
            key={item.id}
            className="challenge-grid__tile"
            style={
              item.photo !== null
                ? { backgroundImage: `url(${JSON.stringify(item.photo)})` }
                : undefined
            }
          >
            {item.photo === null ? itemTitle(item, today) : null}
          </span>
        ))}
        {more > 0 && (
          <span className="challenge-grid__tile challenge-grid__tile--more">+{more}</span>
        )}
      </div>
      <div className="challenge-reward">
        <span className="challenge-reward__art" aria-hidden="true" />
        <span className="challenge-row__text">
          <span className="challenge-row__title">
            {challenge.finish?.count} {challenge.finish?.label ?? ''}
          </span>
          {reward.rulesUrl !== null && (
            <a
              href={reward.rulesUrl}
              target="_blank"
              rel="noreferrer"
              className="challenge-row__meta"
            >
              The {challenge.orgShort}’s rules
            </a>
          )}
        </span>
      </div>

      {sent !== null ? (
        sentLine
      ) : refusal !== null ? (
        <p className="challenges__empty">{refusal}</p>
      ) : !challenge.takesEntries ? (
        // The club runs its own entries. Asking for a name and an address
        // here would only queue something its server refuses.
        <p className="challenges__note">
          The {challenge.orgShort} collects entries itself
          {reward.rulesUrl !== null ? ' - its rules above say how' : ''}. OurHike sends
          nothing for this one.
        </p>
      ) : !props.signedIn ? (
        props.onSignIn !== undefined && (
          <div className="challenge-actions">
            <button type="button" className="challenge-button" onClick={props.onSignIn}>
              Sign in to send your entry
            </button>
          </div>
        )
      ) : (
        orgDomain !== null && (
          <>
            <div className="challenge-receives">
              <span className="challenges__eyebrow">
                What the {challenge.orgShort} receives
              </span>
              <ul>
                <li>Your name</li>
                <li>
                  {words.physical
                    ? 'Your mailing address, to send ' + words.thing
                    : 'Your email, for ' + words.thing}
                </li>
                <li>
                  The {done.length} items you {CHALLENGE_WORDS.past}, and whether each was
                  from your walk or by hand
                </li>
              </ul>
              <span>No GPS track, no photos, no register lines.</span>
            </div>
            <label className="challenge-field">
              <span className="challenges__eyebrow">Name</span>
              <input
                type="text"
                value={name}
                maxLength={NAME_MAX_CHARS}
                autoComplete="name"
                onChange={(event) => setName(event.target.value)}
              />
            </label>
            <label className="challenge-field">
              <span className="challenges__eyebrow">{contactLabel}</span>
              {words.physical ? (
                <textarea
                  value={contact}
                  maxLength={ADDRESS_MAX_CHARS}
                  autoComplete="street-address"
                  rows={3}
                  onChange={(event) => setContact(event.target.value)}
                />
              ) : (
                <input
                  type="email"
                  value={contact}
                  autoComplete="email"
                  aria-invalid={contact.trim() !== '' && !contactOk}
                  // The reason, read with the field: aria-invalid alone says
                  // only that something is wrong.
                  aria-describedby={
                    contact.trim() !== '' && !contactOk
                      ? 'challenge-email-error'
                      : undefined
                  }
                  onChange={(event) => setContact(event.target.value)}
                />
              )}
            </label>
            {!words.physical && contact.trim() !== '' && !contactOk && (
              <p className="challenges__note" id="challenge-email-error">
                That does not look like an email address.
              </p>
            )}
            <label className="challenge-consent">
              <input
                type="checkbox"
                checked={consented}
                onChange={(event) => setConsented(event.target.checked)}
              />
              {/* What happens to them, said as the server does it rather than
                  as a promise: the entry is stored for the club to download,
                  and only deleting the account or the club's organization
                  removes it (app/core/account_deletion.py, routers/clubs.py's
                  delete_org). It used to read "OurHike keeps nothing it did
                  not need to send", which the stored copy outlived (second
                  Challenges review, 2026-10-01). */}
              <span>
                Send these to the {challenge.orgName} for {words.thing}. OurHike holds
                them for the club, and deleting your account removes them here; a copy the
                club has downloaded is the club&rsquo;s to keep.
              </span>
            </label>
            <div className="challenge-actions">
              <button
                type="button"
                className="challenge-button"
                disabled={!ready}
                onClick={() =>
                  props.onSendEntry({
                    challenge_id: challenge.id,
                    org_domain: orgDomain,
                    name: name.trim(),
                    ...(words.physical
                      ? { mailing_address: contact.trim() }
                      : { email: contact.trim() }),
                    item_ids: done.map(({ item }) => item.id),
                    consented: true,
                  })
                }
              >
                {words.act}
              </button>
            </div>
          </>
        )
      )}
      <div className="challenge-actions">
        <button
          type="button"
          className="challenge-button challenge-button--ghost"
          onClick={props.onDone}
        >
          Back to the list
        </button>
      </div>
    </section>
  )
}
