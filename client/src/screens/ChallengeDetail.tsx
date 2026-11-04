// One challenge (#1780, frames 5, 7, 4b, 8b and 8c).
//
// The pine header names it, its window and - only when the club set one - the
// finish line; under them the blaze card (chrome/BlazeCard.tsx, #1962): the
// club's items as tiles in the club's sections, one white blaze per earned
// item, in place of the strip that laid the places along the trail by mile.
// A tap on a section of the card opens the list at that section; the card
// can be made bigger, and only then is a tile itself a button, which opens
// its row. Filter
// pills are the club's own sections, in the club's order - for the ATC, Learn
// · Experience · Protect · Mystery - and then Done, the hiker's own (#1961,
// the blaze card brief: the list in the ATC's sections is the accessible,
// findable form of the card, and it is numbered 1-100 in the ATC's order so a
// hiker holding the ATC's paper list finds the same line).
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
  isSealed,
  itemTitle,
  shortDate,
  windowLine,
  type Challenge,
  type ChallengeItem,
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
import { BlazeCard } from '../chrome/BlazeCard'
import { TileSheet } from '../chrome/TileSheet'
import { WhereSheet } from '../chrome/WhereSheet'
import type { SearchablePoi } from '../lib/searchPoi'
import { asksWhere, whereOptions, type TagPlace } from '../lib/wherePlace'
import {
  formatDay,
  handTaggable,
  itemMeta,
  itemTrailing,
  mileLabel,
  mysteryTeaser,
  statusLine,
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
  /** `poi` names one place of a Triple-Crown-style item; `place` is where
   *  the hiker said it happened when the Where sheet asked (#1963),
   *  kept on this phone only. */
  onTag: (item: ChallengeItem, poi?: string, place?: TagPlace) => void
  /** The fix snapped to the trail, or null - for "Here" and "Near you".
   *  Never asked for by any challenge screen. */
  fixMile?: number | null
  /** Today's walked miles (lib/passedToday.ts), for "Somewhere I walked
   *  today" and "Near you". */
  todayRanges?: readonly MileRange[]
  /** The phone's own waypoints by name, for "Pick a place". */
  places?: readonly SearchablePoi[]
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
  // The card's two sizes (#1962): its own, where a section is the tap
  // target, and bigger, where a tile is. A button rather than a pinch: the
  // brief's open thumb question, which the maintainer answered by poll on
  // 2026-11-04 from the two shots - one pill, usable by any hand and a screen
  // reader; a pinch stays a possible follow-up, not a plan.
  const [bigger, setBigger] = useState(false)
  // "Where did it happen?" (#1963): the item being earned by hand, when
  // that can mean something (lib/wherePlace.ts asksWhere); null otherwise.
  const [where, setWhere] = useState<{ item: ChallengeItem; poi?: string } | null>(null)
  const requestEarn = (item: ChallengeItem, poi?: string) => {
    if (asksWhere(item, 'hand')) setWhere({ item, poi })
    else props.onTag(item, poi)
  }
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

  // The club's sections in the club's order, each in the published item
  // order, then Done - what this hiker has earned, in the same order. No
  // "On the trail" filter any more (#1961): the ATC's four sections are the
  // card's rows and the list's pills, so a tile and a row are found the same
  // way. A pill with nothing under it is not drawn, which is why Done is
  // absent until something is earned and never says "0".
  const filters = useMemo<Filter[]>(() => {
    const out: Filter[] = challenge.sections.map((section) => ({
      key: section.id,
      label: section.short,
      items: challenge.items.filter((item) => item.section === section.id),
    }))
    out.push({
      key: 'done',
      label: 'Done',
      items: challenge.items.filter((item) => isItemDone(item, challenge.id, tags)),
    })
    return out.filter((filter) => filter.items.length > 0)
  }, [challenge, tags])
  const [filterKey, setFilterKey] = useState<string>(
    () => challenge.sections[0]?.id ?? 'done',
  )
  const shown = filters.find((filter) => filter.key === filterKey) ?? filters[0]
  // 1-100 in the ATC's order: the number a hiker's paper list carries.
  const numberOf = useMemo(
    () => new Map(challenge.items.map((item, index) => [item.id, index + 1])),
    [challenge],
  )

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
        <BlazeCard
          challenge={challenge}
          tags={tags}
          today={today}
          size={bigger ? 'expanded' : 'card'}
          onOpenSection={(sectionId) => setFilterKey(sectionId)}
          onOpenItem={(item) => {
            setFilterKey(item.section)
            setSheetItem(item.id)
          }}
        />
        <button
          type="button"
          className="challenge-button challenge-button--ghost blaze-card__zoom"
          aria-pressed={bigger}
          onClick={() => setBigger((current) => !current)}
        >
          {bigger ? 'Smaller tiles' : 'Bigger tiles'}
        </button>
      </header>

      {/* To everyone, not only a hiker who joined: somebody deciding whether
          to join a list that does not open until May is the one this is for
          (second Challenges review, 2026-10-01). */}
      {!open && (
        <p className="challenges__note">
          {challenge.window.opens !== null && today < challenge.window.opens
            ? `Opens ${shortDate(challenge.window.opens)}. ${capitalised(CHALLENGE_WORDS.noun)} counts from then.`
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
            {CHALLENGE_WORDS.verb} {CHALLENGE_WORDS.some}.
          </p>
        </div>
      ) : (
        // Reachable from the day of joining (#1964): what the club receives
        // and its rule are worth reading before a single blaze, not after
        // twenty-five. A record with no finish line has nothing to open.
        (finish !== null || eligible) && (
          <div className="challenge-actions">
            <button
              type="button"
              className="challenge-button"
              onClick={() => setView('finish')}
            >
              {challenge.reward === null
                ? eligible
                  ? 'See your finish'
                  : 'Your finish line'
                : eligible
                  ? 'Your finish'
                  : 'Your entry'}
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
            number={numberOf.get(item.id) ?? 0}
            tags={tags}
            today={today}
            joined={joined}
            open={open}
            onTag={(poi) => requestEarn(item, poi)}
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
          {/* One status line (#1961), in place of a paragraph that branched
              three ways on the same facts. lib/challengeText.ts chooses it. */}
          <p className="challenge-status" role="status">
            {statusLine(challenge, {
              apiConfigured: API_CONFIGURED,
              signedIn: props.signedIn,
            })}
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
        <TileSheet
          challenge={challenge}
          item={sheet}
          number={numberOf.get(sheet.id) ?? 0}
          today={today}
          tags={tags}
          earnable={
            joined && open && handTaggable(sheet) && sheet.match.kind !== 'places_all'
          }
          todayRanges={props.todayRanges}
          fixMile={props.fixMile}
          onEarn={() => requestEarn(sheet)}
          onTakeBack={
            props.onRemoveTag === undefined
              ? undefined
              : (poi) => {
                  props.onRemoveTag?.(sheet, poi)
                  closeSheet()
                }
          }
          onSetNote={(note) => props.onSetNote(sheet, note)}
          onClose={closeSheet}
        />
      )}
      {where !== null && (
        <WhereSheet
          challenge={challenge}
          item={where.item}
          today={today}
          options={whereOptions({
            fixMile: props.fixMile ?? null,
            todayRanges: props.todayRanges ?? [],
          })}
          places={props.places ?? []}
          onChoose={(place) => {
            const asked = where
            setWhere(null)
            if (sheet !== null) closeSheet()
            props.onTag(asked.item, asked.poi, place)
          }}
          onBack={() => setWhere(null)}
        />
      )}
    </section>
  )
}

function ItemRow({
  challenge,
  item,
  number,
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
  /** Its place in the club's list, from 1 - the ATC's own numbering. */
  number: number
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
  // Every row opens its tile (#1963): read it in full, earn it from there,
  // or take it back. A sealed mystery item opens too, and says it is sealed.
  const opens = true

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
  // A place or a walk under the title, and the day it was earned; an at-home
  // item has no sub-line at all (lib/challengeText.ts).
  const meta = sealed
    ? (mysteryTeaser(item, today) ?? '')
    : [
        itemMeta(item),
        doneTag !== null ? `${CHALLENGE_WORDS.past} ${formatDay(doneTag.at)}` : '',
      ]
        .filter((part) => part !== '')
        .join(' · ')
  const text = (
    <>
      <span className="challenge-row__number">{number}</span>
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
        {meta !== '' && <span className="challenge-row__meta">{meta}</span>}
      </span>
      {trailing !== undefined && !sealed && (
        <span className="challenge-row__trailing">{trailing}</span>
      )}
    </>
  )

  return (
    <li
      id={`challenge-item-${item.id}`}
      tabIndex={-1}
      className={sealed ? 'challenge-row challenge-row--sealed' : 'challenge-row'}
    >
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
  const { finish: finishCount, eligible } = progress(challenge, state)
  // The ATC's own rules, said as rules: one entry per person, and each
  // mystery item with a drawing of its own (features/CHALLENGES_BLAZE_CARD.md).
  const hasMystery = challenge.items.some((item) => item.mystery !== null)
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

      {reward.kind === 'drawing' && (
        <p className="challenges__note">
          One entry per person — use the email you signed up with.
          {hasMystery ? ' Each mystery item has a drawing of its own.' : ''}
        </p>
      )}
      {sent !== null ? (
        sentLine
      ) : !eligible && finishCount !== null ? (
        // Day one (#1964): what the club will receive, before anything can
        // be sent. The count is the club's rule, the finish line it set. A
        // draft's "nobody to send it to" is said under it, not instead of it.
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
                The items you {CHALLENGE_WORDS.past}, and whether each was from your walk
                or by hand
              </li>
            </ul>
            <span>
              No GPS track, no photos, no register lines. Nothing has been sent.
            </span>
          </div>
          <p className="challenges__note">
            The entry opens at {finishCount} {challenge.finish?.label ?? ''} — the{' '}
            {challenge.orgShort}’s rule.
          </p>
          {refusal !== null && <p className="challenges__empty">{refusal}</p>}
        </>
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
