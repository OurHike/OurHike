// What a hiker has done about the challenges they joined (#1780,
// features/CHALLENGES.md). Pure functions over a small state record; the
// storage and the outbox are lib/useChallenges.ts's.
//
// WHAT THIS KEEPS, AND WHAT IT REFUSES TO KEEP. Which challenges were joined,
// which items were tagged (when, and whether from the day's walk or by hand),
// the private register line a hiker may write, and for a "walk this section"
// item the mile intervals walked inside that section since joining. It keeps
// NO position, NO fix and NO track: day matching reads the day's walked mile
// ranges lib/passedToday.ts already keeps - "mile INTERVALS, merged - no
// fixes, no coordinates, no timestamps, no ordering" - and nothing here adds
// a finer record of where somebody went. That is design principle 6 ("the
// hiker's record is theirs") and it is also why a place off the trail (a
// town) can only be tagged by hand: a mile interval says nothing about one.
//
// NOTHING HERE COMPARES. Progress is the hiker's own count of the
// challenge's own unit against the club's own finish line; there is no
// composite score across challenges, no rank and no average, because
// features/VOLUNTEERING.md §5 rule 1 is kept rather than waived.

import type { MileRange } from './walkedMiles'
import { mergeRange, walkedWithin } from './walkedMiles'
import {
  isPlaceItem,
  isSealed,
  itemPlaces,
  type Challenge,
  type ChallengeItem,
  type ChallengePlace,
} from './challenges'

/** How a tag was made. `gps` means the day's walked miles put the hiker at
 *  the place, confirmed at camp or matched automatically; `hand` means a tap
 *  from the place card or the list. An entry carries it to the club, so the
 *  club decides what a hand tag is worth. */
export type TagHow = 'gps' | 'hand'

export interface ChallengeTag {
  challengeId: string
  itemId: string
  /** For a `places_all` item, which of its places. Absent otherwise. */
  poi?: string
  /** ISO instant, the hiker's clock. */
  at: string
  how: TagHow
  /** The one-line register note - private, never sent anywhere. */
  note?: string
}

export interface JoinedChallenge {
  challengeId: string
  at: string
}

export interface ChallengeState {
  joined: readonly JoinedChallenge[]
  tags: readonly ChallengeTag[]
  /** Mile intervals walked inside a `section_walked` item's range since the
   *  hiker joined, keyed `challengeId/itemId`. The same privacy class as
   *  lib/walkedMiles.ts: merged intervals, no times, no order. */
  sectionWalked: Readonly<Record<string, readonly MileRange[]>>
  /** Plan suggestions a hiker hid, per hike key - "Hide is remembered per
   *  hike" (handoff revision 6). */
  hiddenSuggestions: Readonly<Record<string, readonly string[]>>
  /** The local day the Today camp card was last answered (Tag all or Not
   *  tonight). The card does not come back that day. */
  answeredDay: string | null
  /** The Legend's "Challenge places" switch. Off by default (principle 2). */
  layerShown: boolean
  /** Challenges this hiker has sent an entry for, or told the club they
   *  finished - so the finish screen can say it went. */
  sent: readonly { challengeId: string; at: string; kind: 'entry' | 'finished' }[]
}

export const EMPTY_CHALLENGE_STATE: ChallengeState = {
  joined: [],
  tags: [],
  sectionWalked: {},
  hiddenSuggestions: {},
  answeredDay: null,
  layerShown: false,
  sent: [],
}

export const CHALLENGE_STATE_KEY = 'ourhike:challenge-state'

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

/** A stored state, or the empty one - never throws, and a malformed entry
 *  costs that entry rather than the hiker's whole record. */
export function storedChallengeState(value: unknown): ChallengeState {
  if (!isRecord(value)) return EMPTY_CHALLENGE_STATE
  const joined = Array.isArray(value.joined)
    ? value.joined.filter(
        (entry): entry is JoinedChallenge =>
          isRecord(entry) &&
          typeof entry.challengeId === 'string' &&
          typeof entry.at === 'string',
      )
    : []
  const tags = Array.isArray(value.tags)
    ? value.tags.filter(
        (tag): tag is ChallengeTag =>
          isRecord(tag) &&
          typeof tag.challengeId === 'string' &&
          typeof tag.itemId === 'string' &&
          typeof tag.at === 'string' &&
          (tag.how === 'gps' || tag.how === 'hand'),
      )
    : []
  const sectionWalked: Record<string, MileRange[]> = {}
  if (isRecord(value.sectionWalked)) {
    for (const [key, ranges] of Object.entries(value.sectionWalked)) {
      if (!Array.isArray(ranges)) continue
      sectionWalked[key] = ranges.filter(
        (range): range is MileRange =>
          isRecord(range) &&
          Number.isFinite(range.startMile) &&
          Number.isFinite(range.endMile),
      )
    }
  }
  const hiddenSuggestions: Record<string, string[]> = {}
  if (isRecord(value.hiddenSuggestions)) {
    for (const [key, ids] of Object.entries(value.hiddenSuggestions)) {
      if (Array.isArray(ids))
        hiddenSuggestions[key] = ids.filter((id) => typeof id === 'string')
    }
  }
  const sent = Array.isArray(value.sent)
    ? value.sent.filter(
        (entry): entry is ChallengeState['sent'][number] =>
          isRecord(entry) &&
          typeof entry.challengeId === 'string' &&
          typeof entry.at === 'string' &&
          (entry.kind === 'entry' || entry.kind === 'finished'),
      )
    : []
  return {
    joined,
    tags,
    sectionWalked,
    hiddenSuggestions,
    answeredDay: typeof value.answeredDay === 'string' ? value.answeredDay : null,
    layerShown: value.layerShown === true,
    sent,
  }
}

export function readChallengeState(): ChallengeState {
  try {
    const raw = localStorage.getItem(CHALLENGE_STATE_KEY)
    return raw === null ? EMPTY_CHALLENGE_STATE : storedChallengeState(JSON.parse(raw))
  } catch {
    return EMPTY_CHALLENGE_STATE
  }
}

export function writeChallengeState(state: ChallengeState): void {
  try {
    localStorage.setItem(CHALLENGE_STATE_KEY, JSON.stringify(state))
  } catch {
    // Ignored on purpose, lib/walkedMiles.readWalked's reason: a full or
    // refused localStorage costs the persistence, never the session.
  }
}

// ---------------------------------------------------------------------------
// Joining and leaving

export function isJoined(state: ChallengeState, challengeId: string): boolean {
  return state.joined.some((entry) => entry.challengeId === challengeId)
}

export function join(
  state: ChallengeState,
  challengeId: string,
  now: Date,
): ChallengeState {
  if (isJoined(state, challengeId)) return state
  return { ...state, joined: [...state.joined, { challengeId, at: now.toISOString() }] }
}

/**
 * Leaving takes the challenge off every surface at once - its pins, its Place
 * card rows, its Today card candidates - because every one of those derives
 * from `joined`. The tags themselves are kept: they are the hiker's record of
 * places they went, and rejoining shows them again.
 */
export function leave(state: ChallengeState, challengeId: string): ChallengeState {
  if (!isJoined(state, challengeId)) return state
  return {
    ...state,
    joined: state.joined.filter((entry) => entry.challengeId !== challengeId),
  }
}

export function joinedChallenges(
  challenges: readonly Challenge[],
  state: ChallengeState,
): Challenge[] {
  const ids = new Set(state.joined.map((entry) => entry.challengeId))
  return challenges.filter((challenge) => ids.has(challenge.id))
}

// ---------------------------------------------------------------------------
// Tags

function sameTag(
  a: Pick<ChallengeTag, 'challengeId' | 'itemId' | 'poi'>,
  b: typeof a,
): boolean {
  return (
    a.challengeId === b.challengeId &&
    a.itemId === b.itemId &&
    (a.poi ?? null) === (b.poi ?? null)
  )
}

export function tagsFor(state: ChallengeState, challengeId: string): ChallengeTag[] {
  return state.tags.filter((tag) => tag.challengeId === challengeId)
}

/** Whether an item is done: every place of a `places_all` tagged, otherwise
 *  one tag for the item. */
export function isItemDone(
  item: ChallengeItem,
  challengeId: string,
  tags: readonly ChallengeTag[],
): boolean {
  if (item.match.kind === 'places_all') {
    return item.match.places.every((place) =>
      tags.some(
        (tag) =>
          tag.challengeId === challengeId &&
          tag.itemId === item.id &&
          tag.poi === place.poi,
      ),
    )
  }
  return tags.some((tag) => tag.challengeId === challengeId && tag.itemId === item.id)
}

/** When an item was done - its last component tag for `places_all`. */
export function itemDoneAt(
  item: ChallengeItem,
  challengeId: string,
  tags: readonly ChallengeTag[],
): ChallengeTag | null {
  if (!isItemDone(item, challengeId, tags)) return null
  const own = tags.filter(
    (tag) => tag.challengeId === challengeId && tag.itemId === item.id,
  )
  return own.reduce<ChallengeTag | null>(
    (latest, tag) => (latest === null || tag.at > latest.at ? tag : latest),
    null,
  )
}

/**
 * Adds a tag and says whether that completed its item - which is the moment
 * a tag leaves the phone (lib/useChallenges.ts enqueues it). A `places_all`
 * item completes on its last place, so Dragon's Tooth on Monday and McAfee
 * Knob on Tuesday queue nothing until Tinker Cliffs on Wednesday.
 *
 * Tagging something already tagged changes nothing: optimistic toggles and a
 * double tap must not mint a second record.
 */
export function tag(
  state: ChallengeState,
  challenge: Challenge,
  item: ChallengeItem,
  entry: { poi?: string; at: Date; how: ChallengeTag['how'] },
): { state: ChallengeState; completed: boolean } {
  const poi = item.match.kind === 'places_all' ? entry.poi : undefined
  if (item.match.kind === 'places_all' && poi === undefined) {
    return { state, completed: false }
  }
  const key = { challengeId: challenge.id, itemId: item.id, poi }
  if (state.tags.some((existing) => sameTag(existing, key)))
    return { state, completed: false }
  const wasDone = isItemDone(item, challenge.id, state.tags)
  const next: ChallengeTag = { ...key, at: entry.at.toISOString(), how: entry.how }
  if (poi === undefined) delete next.poi
  const tags = [...state.tags, next]
  return {
    state: { ...state, tags },
    completed: !wasDone && isItemDone(item, challenge.id, tags),
  }
}

/** Un-tags a hand-made tag, the "Tag it" pill pressed twice. A tag the day's
 *  walk made is not undone by a tap - the pill reads done, not Tagged. */
export function untag(
  state: ChallengeState,
  challengeId: string,
  itemId: string,
): ChallengeState {
  const tags = state.tags.filter(
    (tag) =>
      !(tag.challengeId === challengeId && tag.itemId === itemId && tag.how === 'hand'),
  )
  return tags.length === state.tags.length ? state : { ...state, tags }
}

/** The private register line. Never enqueued, never in an entry. */
export function setRegisterNote(
  state: ChallengeState,
  challengeId: string,
  itemId: string,
  note: string,
): ChallengeState {
  const trimmed = note.trim().slice(0, 200)
  return {
    ...state,
    tags: state.tags.map((existing) =>
      existing.challengeId === challengeId && existing.itemId === itemId
        ? trimmed === ''
          ? (({ note: _dropped, ...rest }) => rest)(existing)
          : { ...existing, note: trimmed }
        : existing,
    ),
  }
}

// ---------------------------------------------------------------------------
// Progress

export interface Progress {
  /** Items done, in the challenge's own unit. */
  tagged: number
  /** The club's finish line, or null for a record with none. */
  finish: number | null
  /** Past the finish line. Always false for a record. */
  eligible: boolean
}

/**
 * One challenge's progress, against its own finish line and nothing else.
 * There is deliberately no function taking two challenges: a total across
 * them would be the composite score §5 rule 4 forbids.
 */
export function progress(challenge: Challenge, state: ChallengeState): Progress {
  const tags = tagsFor(state, challenge.id)
  const tagged = challenge.items.filter((item) =>
    isItemDone(item, challenge.id, tags),
  ).length
  const finish = challenge.finish?.count ?? null
  return { tagged, finish, eligible: finish !== null && tagged >= finish }
}

/** The done items, in the order a finish screen lists them - by when. */
export function doneItems(
  challenge: Challenge,
  state: ChallengeState,
): { item: ChallengeItem; tag: ChallengeTag }[] {
  const tags = tagsFor(state, challenge.id)
  return challenge.items
    .map((item) => ({ item, tag: itemDoneAt(item, challenge.id, tags) }))
    .filter(
      (entry): entry is { item: ChallengeItem; tag: ChallengeTag } => entry.tag !== null,
    )
    .sort((a, b) => a.tag.at.localeCompare(b.tag.at))
}

// ---------------------------------------------------------------------------
// The day's walk

function inRanges(mile: number, ranges: readonly MileRange[]): boolean {
  return ranges.some(
    (range) =>
      mile >= Math.min(range.startMile, range.endMile) &&
      mile <= Math.max(range.startMile, range.endMile),
  )
}

export interface DayCandidate {
  challenge: Challenge
  item: ChallengeItem
  /** The place passed - for `poi_type`, the waypoint of that type. */
  place: Pick<ChallengePlace, 'poi' | 'name' | 'mile'>
}

export interface DayInput {
  /** Joined challenges only - leaving one removes its candidates at once. */
  joined: readonly Challenge[]
  state: ChallengeState
  /** Today's walked miles, lib/passedToday.ts. */
  todayRanges: readonly MileRange[]
  /** Which trail those miles are measured on. A mile only means something
   *  relative to one trail (features/NEARBY_TRAILS.md). */
  trail: string
  /** Published waypoints, for `poi_type` items. */
  pois: readonly { id: string; type: string; name: string; mile?: number }[]
  /** The hiker's local YYYY-MM-DD. */
  today: string
}

/**
 * The items a hiker walked past today and has not tagged - the Today camp
 * card's rows, and nothing else.
 *
 * ONLY WHAT WAS PASSED. Nothing about what was missed is computed here at
 * all, so no screen can show it: the card's own rule is "never mention items
 * that were not passed; never show a count of missed items".
 *
 * Off-trail places are never candidates (a mile interval says nothing about
 * a town), sealed mystery items never are, and neither are the kinds that
 * tag themselves or are done at home.
 */
export function matchDay(input: DayInput): DayCandidate[] {
  const { state, todayRanges, trail, pois, today } = input
  if (todayRanges.length === 0) return []
  const out: DayCandidate[] = []
  for (const challenge of input.joined) {
    if (challenge.trail !== trail) continue
    const tags = tagsFor(state, challenge.id)
    for (const item of challenge.items) {
      if (isSealed(item, today) || isItemDone(item, challenge.id, tags)) continue
      if (isPlaceItem(item)) {
        if (item.match.offTrail) continue
        for (const place of item.match.places) {
          const already =
            item.match.kind === 'places_all' &&
            tags.some(
              (existing) => existing.itemId === item.id && existing.poi === place.poi,
            )
          if (!already && inRanges(place.mile, todayRanges)) {
            out.push({ challenge, item, place })
            // One row per place kind; a Triple Crown can offer two peaks
            // walked in one day, a single place only ever one.
            if (item.match.kind === 'place') break
          }
        }
      } else if (item.match.kind === 'poi_type') {
        const type = item.match.type
        const passed = pois
          .filter(
            (poi) =>
              poi.type === type &&
              poi.mile !== undefined &&
              inRanges(poi.mile, todayRanges),
          )
          .sort((a, b) => (a.mile as number) - (b.mile as number))
        if (passed.length > 0) {
          const first = passed[0]
          out.push({
            challenge,
            item,
            place: { poi: first.id, name: first.name, mile: first.mile as number },
          })
        }
      }
    }
  }
  return out.sort((a, b) => a.place.mile - b.place.mile)
}

export interface AutoInput {
  joined: readonly Challenge[]
  state: ChallengeState
  todayRanges: readonly MileRange[]
  trail: string
  today: string
  /** The highest profile elevation over some miles, or null when the
   *  profile does not cover them. */
  maxElevationFt: (ranges: readonly MileRange[]) => number | null
  /** The hiker's own logged hours, lib/volunteerHours.ts, with the mile they
   *  name (their own or their workday's) and the workday's club. */
  hours: readonly {
    workedOn: string
    mile: number | null
    clubName: string | null
    disputed: boolean
  }[]
}

/**
 * The walked-section coverage today's miles add, and the items that complete
 * themselves - `section_walked`, `elevation_min_ft` and `workday` - which are
 * tagged without asking because there is nothing for the hiker to confirm:
 * the section was walked, the height was reached, the hours were logged.
 *
 * A section counts miles walked SINCE JOINING, because the coverage is only
 * accumulated here, from the day's ranges, after the join. Walking a section
 * last summer is a fact about last summer.
 */
export function autoTags(
  input: AutoInput,
  now: Date,
): { state: ChallengeState; completed: DayCandidate[] } {
  const { todayRanges, trail, today } = input
  let state = input.state
  const completed: DayCandidate[] = []
  for (const challenge of input.joined) {
    if (challenge.trail !== trail) continue
    const joinedAt =
      state.joined.find((entry) => entry.challengeId === challenge.id)?.at ?? ''
    for (const item of challenge.items) {
      if (
        isSealed(item, today) ||
        isItemDone(item, challenge.id, tagsFor(state, challenge.id))
      )
        continue
      const match = item.match
      let done = false
      let place: DayCandidate['place'] | null = null
      if (match.kind === 'section_walked') {
        const key = `${challenge.id}/${item.id}`
        let covered = state.sectionWalked[key] ?? []
        for (const range of todayRanges) {
          const low = Math.max(Math.min(range.startMile, range.endMile), match.fromMile)
          const high = Math.min(Math.max(range.startMile, range.endMile), match.toMile)
          if (high > low) covered = mergeRange(covered, { startMile: low, endMile: high })
        }
        if (covered !== (state.sectionWalked[key] ?? [])) {
          state = { ...state, sectionWalked: { ...state.sectionWalked, [key]: covered } }
        }
        const length = match.toMile - match.fromMile
        done =
          length > 0 &&
          walkedWithin(covered, { startMile: match.fromMile, endMile: match.toMile }) /
            length >=
            match.minFraction
        place = {
          poi: '',
          name: `${match.fromName} to ${match.toName}`,
          mile: match.fromMile,
        }
      } else if (match.kind === 'elevation_min_ft') {
        const highest = todayRanges.length > 0 ? input.maxElevationFt(todayRanges) : null
        done = highest !== null && highest >= match.valueFt
        place = { poi: '', name: item.title ?? '', mile: todayRanges[0]?.startMile ?? 0 }
      } else if (match.kind === 'workday') {
        const joinedDay = joinedAt.slice(0, 10)
        done = input.hours.some(
          (record) =>
            !record.disputed &&
            record.mile !== null &&
            record.workedOn >= joinedDay &&
            (challenge.window.opens === null ||
              record.workedOn >= challenge.window.opens) &&
            (challenge.window.closes === null ||
              record.workedOn <= challenge.window.closes) &&
            // A match naming the challenge's own org can be checked against
            // the workday's club; one naming another org cannot be yet, and
            // is left for a later build rather than guessed.
            (match.org === null ||
              (match.org === challenge.org && record.clubName === challenge.orgName)),
        )
        place = { poi: '', name: item.title ?? '', mile: 0 }
      }
      if (done && place !== null) {
        const result = tag(state, challenge, item, { at: now, how: 'gps' })
        state = result.state
        if (result.completed) completed.push({ challenge, item, place })
      }
    }
  }
  return { state, completed }
}

// ---------------------------------------------------------------------------
// Plan

export interface PlanDayRange {
  dayNumber: number | null
  startMile: number
  endMile: number
}

export interface PlanRow {
  challenge: Challenge
  item: ChallengeItem
  place: ChallengePlace
  dayNumber: number | null
}

/**
 * A challenge's places that fall on a planned route, by day. Place kinds
 * only - "any shelter" is on every route and would list itself on every
 * day. Off-trail places are included: a hiker planning a town stop is
 * exactly who wants to know the Monson visitor centre is on the list.
 */
export function planRows(
  challenge: Challenge,
  days: readonly PlanDayRange[],
  today: string,
): PlanRow[] {
  const rows: PlanRow[] = []
  for (const item of challenge.items) {
    if (!isPlaceItem(item) || isSealed(item, today)) continue
    for (const place of item.match.places) {
      const day = days.find(
        (candidate) =>
          place.mile >= Math.min(candidate.startMile, candidate.endMile) &&
          place.mile <= Math.max(candidate.startMile, candidate.endMile),
      )
      if (day !== undefined)
        rows.push({ challenge, item, place, dayNumber: day.dayNumber })
    }
  }
  return rows.sort((a, b) => a.place.mile - b.place.mile)
}

/**
 * The one challenge to suggest under a plan, or null (handoff revision 6).
 *
 * Only when the hiker has joined NO challenge touching this route; never more
 * than one; the most place rows on the route wins, a tie goes to the
 * organization that maintains the most of the route (`maintainedMiles`), and
 * a tie after that to the name - so the answer is stable rather than an
 * accident of file order. Hidden ones are skipped for this hike only.
 */
export function suggestion(input: {
  challenges: readonly Challenge[]
  state: ChallengeState
  days: readonly PlanDayRange[]
  hikeKey: string
  today: string
  maintainedMiles: (challenge: Challenge) => number
}): { challenge: Challenge; rows: PlanRow[] } | null {
  const { challenges, state, days, hikeKey, today } = input
  if (days.length === 0) return null
  const scored = challenges.map((challenge) => ({
    challenge,
    rows: planRows(challenge, days, today),
  }))
  if (
    scored.some(({ challenge, rows }) => rows.length > 0 && isJoined(state, challenge.id))
  )
    return null
  const hidden = new Set(state.hiddenSuggestions[hikeKey] ?? [])
  const candidates = scored.filter(
    ({ challenge, rows }) =>
      rows.length > 0 && !hidden.has(challenge.id) && !isJoined(state, challenge.id),
  )
  if (candidates.length === 0) return null
  candidates.sort(
    (a, b) =>
      b.rows.length - a.rows.length ||
      input.maintainedMiles(b.challenge) - input.maintainedMiles(a.challenge) ||
      a.challenge.name.localeCompare(b.challenge.name),
  )
  return candidates[0]
}

export function hideSuggestion(
  state: ChallengeState,
  hikeKey: string,
  challengeId: string,
): ChallengeState {
  const hidden = state.hiddenSuggestions[hikeKey] ?? []
  if (hidden.includes(challengeId)) return state
  return {
    ...state,
    hiddenSuggestions: {
      ...state.hiddenSuggestions,
      [hikeKey]: [...hidden, challengeId],
    },
  }
}

// ---------------------------------------------------------------------------
// Browse

export interface BrowseFilters {
  /** A trail id, or null for every trail. */
  trail: string | null
  /** An org key, or null for every club. */
  org: string | null
  openNow: boolean
}

export interface BrowseGroups {
  onPlan: { challenge: Challenge; placesOnPlan: number }[]
  elsewhere: { challenge: Challenge; milesFromPlan: number | null }[]
  /** How many the trail filter is hiding - the footer's "M more". */
  hiddenByTrail: number
}

/**
 * Browse's two groups (handoff revision 5): what touches the planned route
 * first, then the rest by distance from the plan. NO popularity sort and NO
 * hiker counts - the only orderings are the hiker's own plan and the map.
 */
export function browse(input: {
  challenges: readonly Challenge[]
  filters: BrowseFilters
  days: readonly PlanDayRange[]
  today: string
}): BrowseGroups {
  const { filters, days, today } = input
  const byClubAndOpen = input.challenges.filter(
    (challenge) =>
      (filters.org === null || challenge.org === filters.org) &&
      (!filters.openNow || isOpenOn(challenge, today)),
  )
  const shown = byClubAndOpen.filter(
    (challenge) => filters.trail === null || challenge.trail === filters.trail,
  )
  const planLow =
    days.length > 0
      ? Math.min(...days.map((day) => Math.min(day.startMile, day.endMile)))
      : null
  const planHigh =
    days.length > 0
      ? Math.max(...days.map((day) => Math.max(day.startMile, day.endMile)))
      : null
  const onPlan: BrowseGroups['onPlan'] = []
  const elsewhere: BrowseGroups['elsewhere'] = []
  for (const challenge of shown) {
    const placesOnPlan = planRows(challenge, days, today).length
    if (placesOnPlan > 0) {
      onPlan.push({ challenge, placesOnPlan })
      continue
    }
    let milesFromPlan: number | null = null
    if (planLow !== null && planHigh !== null) {
      for (const item of challenge.items) {
        for (const place of itemPlaces(item)) {
          const distance =
            place.mile < planLow ? planLow - place.mile : place.mile - planHigh
          if (milesFromPlan === null || distance < milesFromPlan) milesFromPlan = distance
        }
      }
    }
    elsewhere.push({ challenge, milesFromPlan })
  }
  onPlan.sort(
    (a, b) =>
      b.placesOnPlan - a.placesOnPlan || a.challenge.name.localeCompare(b.challenge.name),
  )
  elsewhere.sort(
    (a, b) =>
      (a.milesFromPlan ?? Number.POSITIVE_INFINITY) -
        (b.milesFromPlan ?? Number.POSITIVE_INFINITY) ||
      a.challenge.name.localeCompare(b.challenge.name),
  )
  return { onPlan, elsewhere, hiddenByTrail: byClubAndOpen.length - shown.length }
}

function isOpenOn(challenge: Challenge, today: string): boolean {
  const { opens, closes } = challenge.window
  return (opens === null || today >= opens) && (closes === null || today <= closes)
}

// ---------------------------------------------------------------------------
// Adapters from the shell's own shapes

/**
 * The highest profile elevation over some walked miles, or null when the
 * profile does not reach them - for `elevation_min_ft`. Reads the same
 * samples the elevation ribbon draws (lib/elevationProfile.ts), so "you
 * reached 4,000 ft" and the ribbon cannot disagree.
 */
export function profileMaxFt(
  profile: { distanceMi: ArrayLike<number>; elevationFt: ArrayLike<number> } | null,
  ranges: readonly MileRange[],
): number | null {
  if (profile === null || profile.distanceMi.length === 0) return null
  const miles = profile.distanceMi
  let best: number | null = null
  for (const range of ranges) {
    const low = Math.min(range.startMile, range.endMile)
    const high = Math.max(range.startMile, range.endMile)
    // Samples are in ascending mile order; find the first at or past `low`.
    let lo = 0
    let hi = miles.length
    while (lo < hi) {
      const mid = (lo + hi) >> 1
      if (miles[mid] < low) lo = mid + 1
      else hi = mid
    }
    for (let index = lo; index < miles.length && miles[index] <= high; index++) {
      const feet = profile.elevationFt[index]
      if (Number.isFinite(feet) && (best === null || feet > best)) best = feet
    }
  }
  return best
}

/** A plan's days as the mile ranges Plan's card and Browse lay places on. */
export function planDayRanges(
  days: readonly {
    dayNumber: number | null
    start: { mile: number }
    end: { mile: number }
  }[],
): PlanDayRange[] {
  return days.map((day) => ({
    dayNumber: day.dayNumber,
    startMile: Math.min(day.start.mile, day.end.mile),
    endMile: Math.max(day.start.mile, day.end.mile),
  }))
}

// ---------------------------------------------------------------------------
// When the camp card may ask

/**
 * The hour, local time, after which a day with no explicit end counts as
 * over for the camp card. @unvalidated - a guess at "at camp", not a
 * measurement. The app has no automatic end-of-day signal on purpose (a long
 * hike's day ends when the hiker calls it, a day hike when they finish the
 * walk), and a hiker using neither would otherwise never be asked. What would
 * settle it: when hikers who DO call their days actually call them - the
 * distribution of that hour, which nobody has looked at.
 */
export const CAMP_CARD_EVENING_HOUR = 18

/**
 * Whether today's walk is over, so the camp card may ask (principle 3,
 * "asked at camp"). The hiker's own act first - a long-hike day called, a
 * day hike's walk logged - and the evening hour only when neither exists.
 */
export function dayHasEnded(input: {
  now: Date
  calledToday: boolean
  walkLoggedToday: boolean
}): boolean {
  if (input.calledToday || input.walkLoggedToday) return true
  return input.now.getHours() >= CAMP_CARD_EVENING_HOUR
}

/**
 * Whether Today shows the camp card: the day is over, today's card has not
 * been answered (Tag all or Not tonight both answer it), and the day's walk
 * passed something. Never shown for nothing - an empty "you passed nothing"
 * card would be a lack-state.
 */
export function campCardShows(input: {
  dayEnded: boolean
  answeredDay: string | null
  today: string
  candidates: readonly DayCandidate[]
}): boolean {
  return (
    input.dayEnded && input.answeredDay !== input.today && input.candidates.length > 0
  )
}
