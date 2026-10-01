/**
 * Org home → Challenges: the club's lists of places, and the one being edited
 * (#1780, features/CHALLENGES.md, the handoff's frame #2a).
 *
 * **A PLACE IS NEVER TYPED HERE.** A challenge item names a published POI id
 * and the exporter copies that record's own mile, coordinate and name into
 * the artifact (features/CHALLENGES.md, "Items name published POI ids, never
 * typed miles or coordinates") - so a figure a club typed can never become a
 * position a hiker's phone matches a GPS track against. The console has no
 * list of an organization's published waypoints to pick from, and building a
 * free-text picker in its place would be exactly the typed coordinate the
 * design forbids. So the editor says what counts and leaves the places to the
 * review of the file, and says so on screen. Reasoned from the design doc,
 * not a maintainer's ruling on this screen: when the console can read a
 * club's published POIs, a picker over THOSE ids is the thing to build.
 *
 * **"HIKERS IN" IS A COUNT THE CLUB SEES, NEVER A HIKER.** Below the floor the
 * server sends no number at all (EVENTING.md's k = 25), and this screen says
 * "fewer than 25" rather than a zero - features/CHALLENGES.md's placeholder,
 * which its open questions say is nobody's decision yet. Nothing here ranks,
 * compares or names anybody; the names arrive only in an entry a hiker chose
 * to send, and only inside the file Finishers downloads.
 *
 * **PUBLISHING IS A PULL REQUEST, NOT A SAVE.** A challenge ships in the
 * regular data refresh, like trail notices, which is what makes it work with
 * no signal. So the button says when it goes live - "with next refresh" -
 * rather than implying the phones change when it is pressed.
 */

import { useState } from 'react'
import { isSafeLink } from '../../lib/safeLink'
import { CHALLENGE_WORDS } from '../../lib/challengeWords'
import { PageHeader } from '../components'
import type {
  ChallengeDefinition,
  ChallengeDefinitionItem,
  ChallengeMatchKind,
  ChallengePublishResult,
  ChallengeRewardKind,
  ChallengeWindow,
  OrgChallengeRow,
  OrgTrail,
} from '../orgApi'

/** The four kinds of item a club picks from, in the order frame #2a draws
 *  them. `places_all` counts as a named place (it is several of them, all
 *  required); `elevation_min_ft` and `self_report` are not offered here -
 *  the first is the ATC's own "reach 4,000 feet" line, the second is the
 *  at-home exception - and are kept, untouched, when a file already has them. */
export const WHAT_COUNTS: readonly { kind: ChallengeMatchKind; label: string }[] = [
  { kind: 'section_walked', label: 'Sections walked' },
  { kind: 'place', label: 'Named places' },
  { kind: 'poi_type', label: 'Waypoint types' },
  { kind: 'workday', label: 'Workdays' },
]

/** The reward choices, with what each asks a finisher for.
 *
 *  A physical reward needs somewhere to send it and a drawing needs a way to
 *  tell the winner, so the entry asks for exactly that and nothing more
 *  (design principle 6: one entry, name and a way to reach them). */
export const REWARDS: readonly {
  kind: ChallengeRewardKind | null
  label: string
}[] = [
  { kind: null, label: 'Nothing' },
  { kind: 'patch', label: 'Send a patch · ask for a mailing address' },
  { kind: 'postcard', label: 'Send a postcard · ask for a mailing address' },
  { kind: 'sticker', label: 'Send a sticker · ask for a mailing address' },
  { kind: 'drawing', label: 'Enter a drawing · ask for an email' },
]

/** The family an item's match belongs to, for "what counts". */
function family(kind: ChallengeMatchKind): ChallengeMatchKind | null {
  if (kind === 'places_all') return 'place'
  return WHAT_COUNTS.some((entry) => entry.kind === kind) ? kind : null
}

/** What a club said counts, or - for a file written before the console
 *  carried that - what its items are made of. */
export function whatCounts(definition: ChallengeDefinition): ChallengeMatchKind[] {
  if (definition.what_counts) return definition.what_counts
  const kinds = new Set<ChallengeMatchKind>()
  for (const item of definition.items) {
    const found = family(item.match.kind)
    if (found) kinds.add(found)
  }
  return WHAT_COUNTS.map((entry) => entry.kind).filter((kind) => kinds.has(kind))
}

/** One ISO day as "Jun 1", read in UTC so the day never moves with the
 *  reader's own timezone. */
function day(iso: string, withYear: boolean): string {
  const date = new Date(`${iso}T00:00:00Z`)
  if (Number.isNaN(date.getTime())) return iso
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    timeZone: 'UTC',
    ...(withYear ? { year: 'numeric' } : {}),
  })
}

/** A window as the table's column says it.
 *
 *  The year is carried where the frame's "Jun 1–Oct 31" leaves it off: a
 *  club's list outlives one season, and a window with no year is one a reader
 *  has to guess at in the spring. */
export function windowLabel(window: ChallengeWindow | null): string {
  if (window === null) return '—'
  const { opens, closes } = window
  if (opens === null && closes === null) return 'no end'
  if (opens !== null && closes === null) return `from ${day(opens, true)}`
  if (opens === null && closes !== null) return `until ${day(closes, true)}`
  const from = opens as string
  const to = closes as string
  return from.slice(0, 4) === to.slice(0, 4)
    ? `${day(from, false)}–${day(to, false)}, ${from.slice(0, 4)}`
    : `${day(from, true)}–${day(to, true)}`
}

function onTrail(items: readonly ChallengeDefinitionItem[]): ChallengeDefinitionItem[] {
  return items.filter((item) => item.match.kind !== 'self_report')
}

/** The Places column: how many items move only by being somewhere. */
export function placesLabel(definition: ChallengeDefinition | null | undefined): string {
  if (!definition) return '—'
  const counted = onTrail(definition.items)
  if (definition.items.length === 0) return 'at review'
  if (counted.length > 0 && counted.every((item) => item.match.kind === 'workday')) {
    return counted.length === 1 ? '1 workday' : `${counted.length} workdays`
  }
  return `${counted.length}`
}

/** The Finished at column: the club's own threshold, not a count of anybody. */
export function finishLabel(definition: ChallengeDefinition | null | undefined): string {
  if (!definition) return '—'
  if (definition.finish === null) return 'record only'
  const total = definition.items.length
  return total > 0 && definition.finish.count === total
    ? `all ${total}`
    : `${definition.finish.count}`
}

/** The Hikers in column. Never zero for "below the floor", and never a
 *  number for a challenge no phone has. */
export function hikersInLabel(row: OrgChallengeRow): string {
  if (row.live === false) return 'not live'
  if (row.hikers_in === null) return `fewer than ${row.hikers_in_floor}`
  return row.hikers_in.toLocaleString('en-US')
}

function trailName(trails: readonly OrgTrail[], id: string): string {
  return trails.find((trail) => trail.id === id)?.name ?? id
}

/** The mono line under a challenge's name: trail · what counts · draft. */
function subLine(
  row: OrgChallengeRow,
  definition: ChallengeDefinition | null | undefined,
  trails: readonly OrgTrail[],
): string {
  const parts: string[] = []
  if (definition) {
    if (definition.trail) parts.push(trailName(trails, definition.trail))
    const counts = whatCounts(definition)
      .map((kind) => WHAT_COUNTS.find((entry) => entry.kind === kind)?.label ?? kind)
      .map((label) => label.toLowerCase())
    if (counts.length > 0) parts.push(counts.join(' and '))
  }
  if (row.status === 'draft') parts.push('draft')
  return parts.join(' · ')
}

/** What an item is, in the words a club would use - never a figure.
 *
 *  `elevation_min_ft` is described rather than printed: its value is feet,
 *  and a height on this screen would have to go through lib/units.ts to be
 *  shown at all. */
function itemKind(item: ChallengeDefinitionItem): string {
  switch (item.match.kind) {
    case 'place':
      return item.match.off_trail ? 'a named place, off the trail' : 'a named place'
    case 'places_all':
      return `all ${item.match.pois.length} of a set of places`
    case 'poi_type':
      return `any ${item.match.type.replace(/_/g, ' ')}`
    case 'elevation_min_ft':
      return 'a height on the profile'
    case 'section_walked':
      return 'a walked section'
    case 'workday':
      return 'a workday on this trail'
    case 'self_report':
      return 'at home, and never on the map'
  }
}

function itemTitle(item: ChallengeDefinitionItem): string {
  if (item.title) return item.title
  return item.mystery ? `Mystery item ${item.mystery.number}, sealed` : item.id
}

/** Sentences in a note, roughly: terminal punctuation followed by a space or
 *  the end. A hint, not a gate - an abbreviation's full stop counts too. */
export function sentenceCount(text: string): number {
  const trimmed = text.trim()
  if (trimmed === '') return 0
  return trimmed.split(/[.!?]+(?:\s+|$)/).filter((part) => part.trim() !== '').length
}

/** A new challenge's id, from its name: the reviewed file's id grammar,
 *  lowercase words joined by hyphens (`pipeline/lib/challenges.py`). */
export function challengeId(name: string): string {
  return name
    .toLowerCase()
    .normalize('NFKD')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
}

/** A new challenge's id: the org's slug, then its name.
 *
 *  Prefixed because challenge ids are unique across EVERY organization, not
 *  within one - `resolve` in `pipeline/lib/challenges.py` drops the second
 *  file carrying an id it has already seen, so two clubs each naming theirs
 *  "Workdays" would silently lose one. The ATC's own file follows the same
 *  shape (`atc-summer-bucket-list-2027`). */
export function newChallengeId(orgSlug: string, name: string): string {
  const org = challengeId(orgSlug)
  const own = challengeId(name)
  if (own === '') return ''
  // Always a hyphen after the slug: the backend refuses an id that is only
  // the slug, or does not start with `<slug>-` (_checked_definition).
  return own.startsWith(`${org}-`) ? own : `${org}-${own}`
}

/** Why the editor's Publish button cannot be pressed yet, or null. */
export function publishBlocker(
  definition: ChallengeDefinition,
  unreadable: boolean,
): string | null {
  if (unreadable) {
    return 'This challenge arrived without its list, so it cannot be changed here without losing its items.'
  }
  if (definition.name.trim() === '' || challengeId(definition.name) === '') {
    return 'Give it a name first.'
  }
  if (definition.trail === '') return 'Pick the trail it lives on.'
  const { opens, closes } = definition.window
  // Both days are inclusive, so opening and closing on one day is a window.
  if (opens !== null && closes !== null && closes < opens) {
    return 'It closes before the day it opens.'
  }
  if (definition.finish !== null) {
    const { count } = definition.finish
    if (!Number.isInteger(count) || count < 1) {
      return 'Finished at is a whole number from 1, or blank.'
    }
    const total = definition.items.length
    if (total > 0 && count > total) {
      return `It has ${total} items, so a finish at ${count} could never be reached.`
    }
  }
  const badPhoto = definition.items.find(
    (item) =>
      item.photo && !(item.photo.startsWith('https://') && isSafeLink(item.photo)),
  )
  if (badPhoto)
    return `The photo for "${itemTitle(badPhoto)}" must be an https:// address.`
  return null
}

type Outcome =
  | { tone: 'good'; detail: string; pullRequest: string }
  | { tone: 'info'; detail: string }
  | { tone: 'stop'; detail: string }

const NEW = '__new__'

export interface ChallengesProps {
  /** Written into a new challenge's `org`. */
  readonly orgSlug: string
  readonly rows: readonly OrgChallengeRow[]
  /** The list could not be read. Nothing is offered that could overwrite a
   *  challenge this page cannot see. */
  readonly rowsUnread?: boolean
  /**
   * The organization's own trails, and only those.
   *
   * **THIS IS THE CONSOLE'S REGISTRY, WHICH CANNOT YET TELL A TRAIL THAT WAS
   * READ FROM ONE THAT WAS PUBLISHED**, and its ids are the console's rather
   * than the ones the pipeline's POIs carry (the A.T. is `AT` there). So this
   * list keeps a club from naming somebody else's trail and is not what makes
   * that true: `pipeline/reference/challenges/publishers.json`, reviewed row
   * by row, is the gate the exporter holds every challenge to (design
   * principle 5).
   */
  readonly trails: readonly OrgTrail[]
  /** The challenge to open on, from `?challenge=`. */
  readonly initialId?: string | null
  readonly canEdit: boolean
  /** Save the definition, then open its pull request. */
  readonly onPublish: (
    challengeId: string,
    definition: ChallengeDefinition,
  ) => Promise<ChallengePublishResult>
  readonly onPreview: () => void
  readonly onOpenFinishers: (challengeId: string) => void
}

export function Challenges({
  orgSlug,
  rows,
  rowsUnread = false,
  trails,
  initialId = null,
  canEdit,
  onPublish,
  onPreview,
  onOpenFinishers,
}: ChallengesProps) {
  const [selectedId, setSelectedId] = useState<string | null>(
    rows.find((row) => row.challenge_id === initialId)?.challenge_id ??
      rows[0]?.challenge_id ??
      null,
  )
  // Edits are kept per challenge, so clicking another row and back does not
  // throw away what somebody typed. Nothing is sent until Publish.
  const [edits, setEdits] = useState<Record<string, ChallengeDefinition>>({})
  const [fresh, setFresh] = useState<ChallengeDefinition | null>(null)
  const [openItem, setOpenItem] = useState<string | null>(null)
  const [outcome, setOutcome] = useState<Outcome | null>(null)
  const [busy, setBusy] = useState(false)

  const row = rows.find((candidate) => candidate.challenge_id === selectedId) ?? null
  const unreadable = row !== null && !row.definition
  const definition: ChallengeDefinition | null =
    selectedId === NEW
      ? fresh
      : row === null
        ? null
        : (edits[row.challenge_id] ??
          row.definition ?? {
            // A placeholder to draw the row's own fields in, never to send:
            // `unreadable` holds Publish shut while this is what is showing.
            id: row.challenge_id,
            org: orgSlug,
            trail: '',
            name: row.name,
            status: row.status,
            window: row.window ?? { opens: null, closes: null },
            finish: null,
            reward: null,
            sections: [],
            items: [],
          })

  const select = (id: string) => {
    setSelectedId(id)
    setOpenItem(null)
    setOutcome(null)
  }

  const update = (change: (current: ChallengeDefinition) => ChallengeDefinition) => {
    if (definition === null) return
    const next = change(definition)
    if (selectedId === NEW) setFresh(next)
    else if (row !== null) setEdits((all) => ({ ...all, [row.challenge_id]: next }))
    setOutcome(null)
  }

  const updateItem = (id: string, change: Partial<ChallengeDefinitionItem>) =>
    update((current) => ({
      ...current,
      items: current.items.map((item) =>
        item.id === id ? { ...item, ...change } : item,
      ),
    }))

  const startNew = () => {
    setFresh({
      id: '',
      org: orgSlug,
      trail: trails[0]?.id ?? '',
      name: '',
      status: 'draft',
      window: { opens: null, closes: null },
      finish: null,
      reward: null,
      sections: [],
      items: [],
      what_counts: [],
    })
    select(NEW)
  }

  // A new challenge whose id is already taken would overwrite that one on
  // save, so it is refused here rather than by the PUT.
  const clash =
    selectedId === NEW &&
    definition !== null &&
    rows.some((r) => r.challenge_id === newChallengeId(orgSlug, definition.name))
  const blocker = definition
    ? (publishBlocker(definition, unreadable) ??
      (clash ? 'A challenge with that name already exists. Choose another.' : null))
    : null

  const publish = async () => {
    if (definition === null || blocker !== null) return
    const id =
      selectedId === NEW
        ? newChallengeId(orgSlug, definition.name)
        : (row?.challenge_id ?? definition.id)
    const sending: ChallengeDefinition = {
      ...definition,
      id,
      name: definition.name.trim(),
      // A reward with no finish line has no moment to be claimed at, and the
      // exporter refuses the pair - so clearing the finish clears it here.
      reward: definition.finish === null ? null : definition.reward,
      // Only a published challenge with a reward takes entries; the server
      // refuses the switch otherwise, so it is never sent on anything else.
      takes_entries:
        definition.takes_entries === true &&
        definition.status === 'published' &&
        definition.finish !== null &&
        definition.reward !== null,
    }
    setBusy(true)
    setOutcome(null)
    try {
      const result = await onPublish(id, sending)
      setOutcome(
        result.pull_request !== null
          ? { tone: 'good', detail: result.detail, pullRequest: result.pull_request }
          : { tone: 'info', detail: result.detail },
      )
    } catch (error) {
      setOutcome({
        tone: 'stop',
        detail: error instanceof Error ? error.message : 'The server did not answer.',
      })
    } finally {
      setBusy(false)
    }
  }

  const counts = definition ? whatCounts(definition) : []
  const finishTotal = definition?.items.length ?? 0

  return (
    <>
      <PageHeader
        eyebrow="Org home · challenges"
        title="Challenges"
        sub={
          <>
            Places on your trails, a window of dates, and what counts as finished. Hikers
            opt in; {CHALLENGE_WORDS.nounPlural} arrive here as a list you can export.
          </>
        }
        actions={
          canEdit && !rowsUnread ? (
            <button
              type="button"
              className="org-btn org-btn--ghost org-btn--small"
              onClick={startNew}
            >
              + New challenge
            </button>
          ) : null
        }
      />

      <div className="org-split">
        <div className="org-stack">
          {rowsUnread ? (
            <div className="org-empty">
              <h3>Could not read your challenges</h3>
              <p>
                OurHike did not answer with this organization’s challenges, so nothing can
                be added or changed here until it does. Reload the page to try again.
              </p>
            </div>
          ) : rows.length === 0 ? (
            <div className="org-empty">
              <h3>No challenges yet</h3>
              <p>
                A challenge is a list of places on one of your trails that hikers choose
                to walk. Nothing is listed here until your club makes one — most clubs
                never need more than a few.
              </p>
            </div>
          ) : (
            <div className="org-card org-card--flush">
              <div className="org-table__scroll">
                <table className="org-table">
                  <thead>
                    <tr>
                      <th scope="col">Challenge</th>
                      <th scope="col">Window</th>
                      <th scope="col">Places</th>
                      <th scope="col">Finished at</th>
                      <th scope="col">Hikers in</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((candidate) => {
                      const shown = edits[candidate.challenge_id] ?? candidate.definition
                      return (
                        <tr
                          key={candidate.challenge_id}
                          data-selectable=""
                          aria-selected={candidate.challenge_id === selectedId}
                          onClick={() => select(candidate.challenge_id)}
                        >
                          <td>
                            <button
                              type="button"
                              className="org-link org-table__name"
                              style={{ textAlign: 'left' }}
                              onClick={() => select(candidate.challenge_id)}
                            >
                              {candidate.name}
                            </button>
                            <div className="org-mono">
                              {subLine(candidate, shown, trails)}
                            </div>
                          </td>
                          <td className="org-mono">{windowLabel(candidate.window)}</td>
                          <td className="org-mono">{placesLabel(shown)}</td>
                          <td className="org-mono">{finishLabel(shown)}</td>
                          <td className="org-mono">{hikersInLabel(candidate)}</td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          <div className="org-grid org-grid--tiles">
            <div className="org-tile">
              <span className="org-tile__label">Your trails only</span>
              <span className="org-tile__value">
                A place can only come from a trail you publish. The ATC&rsquo;s list lives
                on the A.T.; yours lives on yours.
              </span>
            </div>
            <div className="org-tile">
              <span className="org-tile__label">Places, not taps</span>
              <span className="org-tile__value">
                Every item is a waypoint, a waypoint type, a section or a workday. There
                are no in-app tasks to farm.
              </span>
              <span className="org-tile__meta">
                At-home items are the one exception, and they never reach the map.
              </span>
            </div>
            <div className="org-tile">
              <span className="org-tile__label">Ships with the data</span>
              <span className="org-tile__value">
                Published in the regular data refresh like trail notices, so it works with
                no signal.
              </span>
            </div>
          </div>
        </div>

        {definition === null ? null : (
          <section className="org-card org-panel" aria-label="Editing">
            <div className="org-inline">
              <span className="org-eyebrow">Editing</span>
              {selectedId !== NEW && row !== null ? (
                <button
                  type="button"
                  className="org-link"
                  style={{ marginLeft: 'auto' }}
                  onClick={() => onOpenFinishers(row.challenge_id)}
                >
                  Finishers →
                </button>
              ) : null}
            </div>
            <div className="org-panel__head">
              <h2>{definition.name.trim() || 'A new challenge'}</h2>
            </div>

            {unreadable ? (
              <div className="org-callout" data-tone="warn">
                <span>
                  <strong>The list did not come with this challenge.</strong> The server
                  sent its name and counts but not its file, so nothing here can be
                  changed without losing its items.
                </span>
              </div>
            ) : null}

            <fieldset className="org-fieldset" disabled={!canEdit || unreadable || busy}>
              {selectedId === NEW ? (
                <label className="org-field">
                  <span className="org-field__label">Name</span>
                  <input
                    className="org-input"
                    value={definition.name}
                    onChange={(event) =>
                      update((current) => ({ ...current, name: event.target.value }))
                    }
                  />
                </label>
              ) : null}

              <label className="org-field">
                <span className="org-field__label">Trail</span>
                <select
                  className="org-select"
                  value={definition.trail}
                  onChange={(event) =>
                    update((current) => ({ ...current, trail: event.target.value }))
                  }
                >
                  {definition.trail === '' ? (
                    <option value="">Pick a trail</option>
                  ) : null}
                  {trails.map((trail) => (
                    <option key={trail.id} value={trail.id}>
                      {trail.name ?? trail.id}
                    </option>
                  ))}
                </select>
              </label>

              <div className="org-field">
                <span className="org-field__label" id="challenge-counts">
                  What counts
                </span>
                <div
                  className="org-chips"
                  role="group"
                  aria-labelledby="challenge-counts"
                >
                  {WHAT_COUNTS.map((entry) => {
                    const on = counts.includes(entry.kind)
                    return (
                      <button
                        key={entry.kind}
                        type="button"
                        className="org-chip"
                        aria-pressed={on}
                        onClick={() =>
                          update((current) => ({
                            ...current,
                            // Kept in the file for whoever reviews it and picks
                            // the places. `pipeline/lib/challenges.py` builds
                            // its record from named keys, so this one reaches
                            // the reviewer and never a phone.
                            what_counts: on
                              ? counts.filter((kind) => kind !== entry.kind)
                              : WHAT_COUNTS.map((w) => w.kind).filter(
                                  (kind) => kind === entry.kind || counts.includes(kind),
                                ),
                          }))
                        }
                      >
                        {entry.label}
                      </button>
                    )
                  })}
                </div>
                <span className="org-field__hint">
                  Places are chosen from your published waypoints when this file is
                  reviewed. Nothing here takes a typed position.
                </span>
              </div>

              <div className="org-row">
                <label className="org-field" style={{ flex: '1 1 120px' }}>
                  <span className="org-field__label">Opens</span>
                  <input
                    className="org-input"
                    type="date"
                    value={definition.window.opens ?? ''}
                    onChange={(event) =>
                      update((current) => ({
                        ...current,
                        window: { ...current.window, opens: event.target.value || null },
                      }))
                    }
                  />
                  <span className="org-field__hint">Blank opens any time.</span>
                </label>
                <label className="org-field" style={{ flex: '1 1 120px' }}>
                  <span className="org-field__label">Closes</span>
                  <input
                    className="org-input"
                    type="date"
                    value={definition.window.closes ?? ''}
                    onChange={(event) =>
                      update((current) => ({
                        ...current,
                        window: { ...current.window, closes: event.target.value || null },
                      }))
                    }
                  />
                  <span className="org-field__hint">Blank never closes.</span>
                </label>
              </div>

              <label className="org-field">
                <span className="org-field__label">Finished at</span>
                <input
                  className="org-input"
                  type="number"
                  min={1}
                  step={1}
                  inputMode="numeric"
                  value={definition.finish?.count ?? ''}
                  onChange={(event) => {
                    const raw = event.target.value
                    // The reward is kept while the field is blank, so clearing
                    // it to retype a number does not throw the reward away;
                    // `publish` is what drops a reward with no finish line.
                    update((current) => {
                      if (raw === '') return { ...current, finish: null }
                      const count = Number(raw)
                      return Number.isNaN(count)
                        ? current
                        : { ...current, finish: { ...current.finish, count } }
                    })
                  }}
                />
                <span className="org-field__hint">
                  {finishTotal > 0 ? `Out of ${finishTotal} items. ` : ''}
                  Or leave blank for a challenge with no finish, just a record.
                </span>
              </label>

              <label className="org-field">
                <span className="org-field__label">When someone finishes</span>
                <select
                  className="org-select"
                  value={
                    definition.finish === null ? '' : (definition.reward?.kind ?? '')
                  }
                  disabled={definition.finish === null}
                  onChange={(event) => {
                    const kind = (event.target.value ||
                      null) as ChallengeRewardKind | null
                    update((current) => ({
                      ...current,
                      reward: kind === null ? null : { ...current.reward, kind },
                    }))
                  }}
                >
                  {REWARDS.map((reward) => (
                    <option key={reward.kind ?? 'none'} value={reward.kind ?? ''}>
                      {reward.label}
                    </option>
                  ))}
                </select>
                <span className="org-field__hint">
                  {definition.finish === null
                    ? 'A reward needs a finish line to be claimed at.'
                    : 'Most challenges offer nothing. A patch, postcard or sticker asks the finisher for a mailing address; a drawing asks for an email. Nothing else is asked.'}
                </span>
              </label>

              <label className="org-inline">
                <input
                  type="checkbox"
                  checked={definition.status === 'draft'}
                  onChange={(event) =>
                    update((current) => ({
                      ...current,
                      status: event.target.checked ? 'draft' : 'published',
                    }))
                  }
                />
                <span className="org-field__label">Draft</span>
                <span className="org-field__hint">
                  Hikers see it labelled not yet confirmed, and it takes no entries.
                </span>
              </label>

              {definition.reward !== null && definition.finish !== null && (
                <label className="org-inline">
                  <input
                    type="checkbox"
                    checked={definition.takes_entries === true}
                    disabled={definition.status === 'draft'}
                    onChange={(event) =>
                      update((current) => ({
                        ...current,
                        takes_entries: event.target.checked,
                      }))
                    }
                  />
                  <span className="org-field__label">Take entries through OurHike</span>
                  <span className="org-field__hint">
                    {definition.status === 'draft'
                      ? 'A draft takes no entries.'
                      : 'Finishers send their name and an email or mailing address here, and you download them as a spreadsheet. Leave it off if you collect entries yourself; the app then points finishers at your rules.'}
                  </span>
                </label>
              )}

              {definition.items.length > 0 ? (
                // Folded by default: frame #2a draws no item list, and the
                // ATC's own file has 97 items, which unfolded would make the
                // editor a page long before anybody asked for a note.
                <details className="org-field">
                  <summary className="org-field__label" style={{ cursor: 'pointer' }}>
                    Items · {definition.items.length} · notes and photos
                  </summary>
                  <ul
                    className="org-stack"
                    style={{ listStyle: 'none', margin: 0, padding: 0 }}
                  >
                    {definition.items.map((item) => {
                      const open = openItem === item.id
                      const sentences = sentenceCount(item.note ?? '')
                      return (
                        <li key={item.id} className="org-stack" style={{ gap: 6 }}>
                          <button
                            type="button"
                            className="org-link"
                            style={{ textAlign: 'left' }}
                            aria-expanded={open}
                            onClick={() => setOpenItem(open ? null : item.id)}
                          >
                            {itemTitle(item)}
                          </button>
                          <span className="org-mono">
                            {itemKind(item)}
                            {item.note ? ' · has a note' : ''}
                          </span>
                          {open ? (
                            <>
                              <label className="org-field">
                                <span className="org-field__label">
                                  Your club&rsquo;s note
                                </span>
                                <textarea
                                  className="org-textarea"
                                  value={item.note ?? ''}
                                  onChange={(event) =>
                                    updateItem(item.id, {
                                      note: event.target.value || null,
                                    })
                                  }
                                />
                                <span className="org-field__hint">
                                  One to three sentences, in your own voice. A hiker reads
                                  it on the place once it is {CHALLENGE_WORDS.past}.
                                  {sentences > 3 ? ` This one has ${sentences}.` : ''}
                                </span>
                              </label>
                              <label className="org-field">
                                <span className="org-field__label">Photo address</span>
                                <input
                                  className="org-input"
                                  type="url"
                                  placeholder="https://"
                                  value={item.photo ?? ''}
                                  onChange={(event) =>
                                    updateItem(item.id, {
                                      photo: event.target.value.trim() || null,
                                    })
                                  }
                                />
                                <span className="org-field__hint">
                                  Shown labelled as your club&rsquo;s photo, beside the
                                  hiker&rsquo;s own.
                                </span>
                              </label>
                            </>
                          ) : null}
                        </li>
                      )
                    })}
                  </ul>
                </details>
              ) : null}
            </fieldset>

            {outcome?.tone === 'good' ? (
              <div className="org-callout" data-tone="good">
                <span>
                  <strong>Sent for review.</strong> {outcome.detail}{' '}
                  {isSafeLink(outcome.pullRequest) ? (
                    <a
                      className="org-link org-link--inline"
                      href={outcome.pullRequest}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Open the pull request ↗
                    </a>
                  ) : null}
                </span>
              </div>
            ) : null}
            {outcome?.tone === 'info' ? (
              <div className="org-callout" data-tone="info">
                <span>
                  <strong>Saved, and no pull request was opened.</strong> {outcome.detail}
                </span>
              </div>
            ) : null}
            {outcome?.tone === 'stop' ? (
              <div className="org-callout" data-tone="stop">
                <span>
                  <strong>Nothing was published.</strong> {outcome.detail}
                </span>
              </div>
            ) : null}

            {canEdit ? (
              <>
                {blocker !== null ? (
                  <span className="org-field__hint">{blocker}</span>
                ) : null}
                <div className="org-inline">
                  <button
                    type="button"
                    className="org-btn"
                    disabled={blocker !== null || busy}
                    onClick={() => void publish()}
                  >
                    {busy ? 'Publishing…' : 'Publish with next refresh'}
                  </button>
                  <button
                    type="button"
                    className="org-btn org-btn--ghost"
                    onClick={onPreview}
                  >
                    Preview
                  </button>
                </div>
              </>
            ) : (
              <span className="org-field__hint">
                Only an admin can change a challenge. What is here is what hikers get.
              </span>
            )}
          </section>
        )}
      </div>
    </>
  )
}
