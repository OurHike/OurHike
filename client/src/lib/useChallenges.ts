// Challenges for the shell (#1780, features/CHALLENGES.md): the published
// list, the hiker's own record of it, and the one place a tag becomes an
// outbox item.
//
// TWO READS FOR THE LIST, in lib/useSuggestedHikes.ts's order and for its
// reasons: the kept copy first so the list is there with no signal, then the
// release when there is signal. Never a request with no signal.
//
// THE RECORD IS localStorage, `ourhike:challenge-state`, read once and
// written on change - small (joined ids, tags, section intervals), and read
// synchronously on launch so the Today card and the place card never flash
// an empty state first. It is the hiker's own content and belongs in
// ACCOUNT_SYNC.md's "follows the account" column; until a sync for it is
// built it is device-only, and the tags themselves also reach the server.
//
// A TAG LEAVES THE PHONE WHEN ITS ITEM COMPLETES, and only then: a Triple
// Crown's first two peaks queue nothing. What leaves is the challenge id, the
// item id, how it was tagged, and when (lib/challengeDrafts.ts). The private
// register line never does.

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { DATA_CONFIGURED } from './config'
import type { Challenge, ChallengeItem } from './challenges'
import { NO_CHALLENGES, fetchChallenges, recallChallenges } from './challenges'
import {
  autoTags,
  hideSuggestion,
  join,
  joinedChallenges,
  leave,
  readChallengeState,
  setRegisterNote,
  tag,
  untag,
  writeChallengeState,
  type AutoInput,
  type ChallengeState,
  type DayCandidate,
  type TagHow,
} from './challengeProgress'
import type { ChallengeEntryDraft } from './challengeDrafts'
import { enqueueChallengeEntry, enqueueChallengeTag } from './outbox'

export interface ChallengesApi {
  /** Every challenge this phone holds, joined or not. */
  all: readonly Challenge[]
  /** The ones this hiker joined, in the published order. */
  joined: readonly Challenge[]
  state: ChallengeState
  join: (challengeId: string) => void
  leave: (challengeId: string) => void
  tagItem: (challenge: Challenge, item: ChallengeItem, how: TagHow, poi?: string) => void
  untagItem: (challenge: Challenge, item: ChallengeItem) => void
  setNote: (challenge: Challenge, item: ChallengeItem, note: string) => void
  /** Tags every camp-card row and marks today's card answered. */
  tagAll: (candidates: readonly DayCandidate[], today: string) => void
  /** "Not tonight": the card does not come back today, and the rows stay
   *  tag-able from the challenge's own page. */
  notTonight: (today: string) => void
  hideSuggestion: (hikeKey: string, challengeId: string) => void
  setLayerShown: (shown: boolean) => void
  sendEntry: (entry: ChallengeEntryDraft) => void
}

/**
 * @param online the shell's online flag - no request is made without signal.
 * @param ready whether the launch is past its first frame (#1302).
 * @param onQueued called after anything is enqueued, so the shell can flush.
 * @param auto today's walk, for the items that tag themselves - null while
 *   there is nothing to judge (no trail index yet, no walking today).
 */
export function useChallenges(
  online: boolean,
  ready: boolean,
  onQueued: () => void,
  auto: Omit<AutoInput, 'joined' | 'state'> | null,
): ChallengesApi {
  const [all, setAll] = useState<readonly Challenge[]>(NO_CHALLENGES)
  const [state, setState] = useState<ChallengeState>(readChallengeState)
  const fetched = useRef(false)
  const queued = useRef(onQueued)
  queued.current = onQueued

  useEffect(() => {
    if (!ready) return
    let wanted = true
    void Promise.resolve()
      .then(recallChallenges)
      .then((kept) => {
        if (wanted && !fetched.current && kept !== null) setAll(kept)
      })
      .catch(() => {})
    return () => {
      wanted = false
    }
  }, [ready])

  useEffect(() => {
    if (!DATA_CONFIGURED || !online || !ready) return
    const controller = new AbortController()
    let wanted = true
    void fetchChallenges(controller.signal)
      .then((fresh) => {
        if (!wanted || fresh === null) return
        fetched.current = true
        setAll(fresh)
      })
      .catch(() => {})
    return () => {
      wanted = false
      controller.abort()
    }
  }, [online, ready])

  useEffect(() => {
    writeChallengeState(state)
  }, [state])

  const joined = useMemo(() => joinedChallenges(all, state), [all, state])

  // Every change goes through `commit`, computed from the ref rather than
  // inside a setState updater: an updater may run twice (StrictMode does
  // exactly that), and one that enqueued a tag would queue it twice.
  const stateRef = useRef(state)
  const commit = useCallback((next: ChallengeState) => {
    if (next === stateRef.current) return
    stateRef.current = next
    setState(next)
  }, [])

  const enqueueTag = useCallback(
    (challengeId: string, itemId: string, how: TagHow, at: Date) => {
      void enqueueChallengeTag({ challenge_id: challengeId, item_id: itemId, how }, at)
        .then(() => queued.current())
        .catch(() => {})
    },
    [],
  )

  const tagItem = useCallback(
    (challenge: Challenge, item: ChallengeItem, how: TagHow, poi?: string) => {
      const at = new Date()
      const result = tag(stateRef.current, challenge, item, { poi, at, how })
      commit(result.state)
      // A double tap that changes nothing completes nothing, so cannot queue.
      if (result.completed) enqueueTag(challenge.id, item.id, how, at)
    },
    [commit, enqueueTag],
  )

  const tagAll = useCallback(
    (candidates: readonly DayCandidate[], today: string) => {
      const at = new Date()
      let next = stateRef.current
      const completed: DayCandidate[] = []
      for (const candidate of candidates) {
        const result = tag(next, candidate.challenge, candidate.item, {
          poi:
            candidate.item.match.kind === 'places_all' ? candidate.place.poi : undefined,
          at,
          how: 'gps',
        })
        if (result.completed) completed.push(candidate)
        next = result.state
      }
      commit({ ...next, answeredDay: today })
      for (const done of completed) enqueueTag(done.challenge.id, done.item.id, 'gps', at)
    },
    [commit, enqueueTag],
  )

  // The items that tag themselves, re-judged whenever today's walk or the
  // hiker's hours move. Nothing on screen changes while walking (principle
  // 2): the record updates, and the camp card and the list read it later.
  const autoKey =
    auto === null
      ? null
      : JSON.stringify([auto.todayRanges, auto.hours, auto.today, auto.trail])
  const autoRef = useRef(auto)
  autoRef.current = auto
  useEffect(() => {
    const input = autoRef.current
    if (input === null || joined.length === 0) return
    const at = new Date()
    const result = autoTags({ ...input, joined, state: stateRef.current }, at)
    commit(result.state)
    for (const done of result.completed)
      enqueueTag(done.challenge.id, done.item.id, 'gps', at)
  }, [autoKey, joined, commit, enqueueTag])

  return {
    all,
    joined,
    state,
    join: useCallback(
      (challengeId: string) => commit(join(stateRef.current, challengeId, new Date())),
      [commit],
    ),
    leave: useCallback(
      (challengeId: string) => commit(leave(stateRef.current, challengeId)),
      [commit],
    ),
    tagItem,
    untagItem: useCallback(
      (challenge: Challenge, item: ChallengeItem) =>
        commit(untag(stateRef.current, challenge.id, item.id)),
      [commit],
    ),
    setNote: useCallback(
      (challenge: Challenge, item: ChallengeItem, note: string) =>
        commit(setRegisterNote(stateRef.current, challenge.id, item.id, note)),
      [commit],
    ),
    tagAll,
    notTonight: useCallback(
      (today: string) => commit({ ...stateRef.current, answeredDay: today }),
      [commit],
    ),
    hideSuggestion: useCallback(
      (hikeKey: string, challengeId: string) =>
        commit(hideSuggestion(stateRef.current, hikeKey, challengeId)),
      [commit],
    ),
    setLayerShown: useCallback(
      (shown: boolean) => commit({ ...stateRef.current, layerShown: shown }),
      [commit],
    ),
    sendEntry: useCallback(
      (entry: ChallengeEntryDraft) => {
        const at = new Date()
        void enqueueChallengeEntry(entry, at)
          .then(() => queued.current())
          .catch(() => {})
        const current = stateRef.current
        commit({
          ...current,
          sent: [
            ...current.sent.filter((sent) => sent.challengeId !== entry.challenge_id),
            {
              challengeId: entry.challenge_id,
              at: at.toISOString(),
              kind: entry.finished_only === true ? 'finished' : 'entry',
            },
          ],
        })
      },
      [commit],
    ),
  }
}
