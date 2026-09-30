// One challenge (#1780, frames #5, #7, #4b, #8b and #8c).
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

import { useMemo, useState, type ReactNode } from 'react'
import { API_CONFIGURED } from '../lib/api'
import { CHALLENGE_WORDS } from '../lib/challengeWords'
import type { ChallengeEntryDraft } from '../lib/challengeDrafts'
import {
  isPlaceItem,
  isSealed,
  itemTitle,
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
  onTag: (item: ChallengeItem) => void
  onUntag: (item: ChallengeItem) => void
  onSetNote: (item: ChallengeItem, note: string) => void
  onSendEntry: (entry: ChallengeEntryDraft) => void
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
        <h1 className="challenges__title" id="challenge-title">
          {challenge.name}
        </h1>
        <DraftLabel challenge={challenge} />
        {challenge.summary !== null && (
          <p className="challenge-head__summary">{challenge.summary}</p>
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
            onTag={() => props.onTag(item)}
            onUntag={() => props.onUntag(item)}
            onOpen={() => setSheetItem(item.id)}
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
            {API_CONFIGURED
              ? `Saved on this phone. With signal, OurHike counts it for the ${challenge.orgShort} - they see a number, never your name.`
              : `Saved on this phone. It waits here until OurHike’s server is running, then the ${challenge.orgShort} sees a count - never your name.`}
          </p>
          <div className="challenge-actions">
            <button
              type="button"
              className="challenge-button challenge-button--ghost"
              onClick={props.onLeave}
            >
              Leave this challenge
            </button>
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
          onOpenWorkdays={props.onOpenWorkdays}
          onClose={() => setSheetItem(null)}
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
  onTag,
  onUntag,
  onOpen,
}: {
  challenge: Challenge
  item: ChallengeItem
  tags: readonly ChallengeTag[]
  today: string
  joined: boolean
  onTag: () => void
  onUntag: () => void
  onOpen: () => void
}) {
  const sealed = isSealed(item, today)
  const done = isItemDone(item, challenge.id, tags)
  const doneTag = itemDoneAt(item, challenge.id, tags)
  const title = titleOrSealed(item, challenge, today)
  const trailing = itemTrailing(item)
  const revealed = item.mystery !== null && !sealed
  // A place row opens its tagged-place sheet once there is something to
  // show; nothing else opens.
  const opens = done && isPlaceItem(item)

  let right: ReactNode = null
  if (!sealed && joined) {
    if (done && doneTag?.how === 'gps') {
      right = <span className="challenge-row__done">done</span>
    } else if (item.match.kind === 'places_all') {
      right = null
    } else if (handTaggable(item)) {
      right = (
        <TagPill
          tagged={done}
          label={`${done ? CHALLENGE_WORDS.done : CHALLENGE_WORDS.act}: ${title}`}
          onPress={done ? onUntag : onTag}
        />
      )
    } else if (done) {
      right = <span className="challenge-row__done">done</span>
    }
  }

  const places = item.match.kind === 'places_all' ? item.match.places : []
  const placesDone = places.filter((place) =>
    tags.some((tag) => tag.itemId === item.id && tag.poi === place.poi),
  )

  return (
    <li className={sealed ? 'challenge-row challenge-row--sealed' : 'challenge-row'}>
      <button
        type="button"
        className="challenge-row__open"
        disabled={!opens}
        onClick={onOpen}
      >
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
              {places.length > 0
                ? places
                    .map(
                      (place) => `${place.name}${placesDone.includes(place) ? ' ✓' : ''}`,
                    )
                    .join(' · ')
                : itemMeta(item)}
              {doneTag !== null
                ? ` · ${CHALLENGE_WORDS.past} ${formatDay(doneTag.at)}`
                : ''}
            </span>
          )}
        </span>
        {trailing !== undefined && !sealed && (
          <span className="challenge-row__trailing">{trailing}</span>
        )}
      </button>
      {right}
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
  onOpenWorkdays?: () => void
  onClose: () => void
}) {
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
        </div>
      </div>
    </div>
  )
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

/** The finish (#8b with a reward, #8c without). */
function Finish(props: ChallengeDetailProps & { onDone: () => void }) {
  const { challenge, state, today } = props
  const done = doneItems(challenge, state)
  const days = new Set(done.map((entry) => entry.tag.at.slice(0, 10))).size
  const sent = state.sent.find((entry) => entry.challengeId === challenge.id) ?? null
  const draft = challenge.status === 'draft'
  const closed = challenge.window.closes !== null && today > challenge.window.closes
  const reward = challenge.reward
  const words = reward === null ? null : REWARD_WORDS[reward.kind]
  const [name, setName] = useState(props.defaultName ?? '')
  const [contact, setContact] = useState('')
  const [consented, setConsented] = useState(false)
  const [telling, setTelling] = useState(false)
  const summary = `${done.length} ${done.length === 1 ? 'place' : 'places'} over ${days} ${days === 1 ? 'day' : 'days'}.`

  const header = (
    <header className="challenge-head">
      <p className="challenges__eyebrow">{challenge.orgName}</p>
      <h1 className="challenges__title">You walked {challenge.name}</h1>
      <DraftLabel challenge={challenge} />
    </header>
  )

  // Why an entry cannot be sent, in one sentence, or null when it can.
  const refusal = draft
    ? `The ${challenge.orgShort} has not confirmed this list yet, so there is nobody to send an entry to through OurHike.`
    : closed && challenge.window.closes !== null
      ? `Entries closed on ${formatDay(challenge.window.closes)}.`
      : null

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
        <div className="challenge-actions">
          <button type="button" className="challenge-button" onClick={props.onDone}>
            Done
          </button>
          {refusal === null &&
            (sent !== null ? (
              <span className="challenges__note">
                Told the club {formatDay(sent.at)}.
              </span>
            ) : !props.signedIn ? (
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
        {telling && sent === null && refusal === null && props.signedIn && (
          <>
            <label className="challenge-field">
              <span className="challenges__eyebrow">
                Your name, as the club will see it
              </span>
              <input
                type="text"
                value={name}
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
  const ready = name.trim() !== '' && contact.trim() !== '' && consented

  return (
    <section className="challenges" aria-label={`You walked ${challenge.name}`}>
      {header}
      <p className="challenges__note">
        {done.length} {CHALLENGE_WORDS.past} · {summary}
      </p>
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
        <p className="challenges__note">
          Sent {formatDay(sent.at)}. It leaves this phone next time you have signal.
        </p>
      ) : refusal !== null ? (
        <p className="challenges__empty">{refusal}</p>
      ) : !props.signedIn ? (
        props.onSignIn !== undefined && (
          <div className="challenge-actions">
            <button type="button" className="challenge-button" onClick={props.onSignIn}>
              Sign in to send your entry
            </button>
          </div>
        )
      ) : (
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
              autoComplete="name"
              onChange={(event) => setName(event.target.value)}
            />
          </label>
          <label className="challenge-field">
            <span className="challenges__eyebrow">{contactLabel}</span>
            {words.physical ? (
              <textarea
                value={contact}
                autoComplete="street-address"
                rows={3}
                onChange={(event) => setContact(event.target.value)}
              />
            ) : (
              <input
                type="email"
                value={contact}
                autoComplete="email"
                onChange={(event) => setContact(event.target.value)}
              />
            )}
          </label>
          <label className="challenge-consent">
            <input
              type="checkbox"
              checked={consented}
              onChange={(event) => setConsented(event.target.checked)}
            />
            <span>
              Send these to the {challenge.orgName} for {words.thing}. OurHike keeps
              nothing it did not need to send.
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
