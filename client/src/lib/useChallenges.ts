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
//
// AND IS TAKEN BACK WHEN IT STOPS BEING DONE: an un-tag, a "Remove this tag"
// or a Leave queues the removal behind the tag, and the flush is in order, so
// the server ends where the phone did. Rejoining sends the kept tags again.

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { DATA_CONFIGURED } from './config'
import type { Challenge, ChallengeItem } from './challenges'
import { NO_CHALLENGES } from './challenges'
import {
  autoTags,
  completionHow,
  hideSuggestion,
  isItemDone,
  itemDoneAt,
  join,
  joinedChallenges,
  leave,
  readChallengeState,
  removeTag,
  setRegisterNote,
  tag,
  tagsFor,
  untag,
  writeChallengeState,
  type AutoInput,
  type ChallengeState,
  type DayCandidate,
  type TagHow,
} from './challengeProgress'
import type { ChallengeEntryDraft } from './challengeDrafts'
import {
  enqueueChallengeEntry,
  enqueueChallengeTag,
  enqueueChallengeUntag,
  removeQueued,
} from './outbox'

export interface ChallengesApi {
  /** Every challenge this phone holds, joined or not. */
  all: readonly Challenge[]
  /** Whether a list has been read at all - the kept copy or the release.
   *  Before then `all` is empty because nothing has been read, which is not
   *  the same as a release that publishes no challenges, and only the
   *  second means a joined one was withdrawn. */
  loaded: boolean
  /** The ones this hiker joined, in the published order. */
  joined: readonly Challenge[]
  state: ChallengeState
  join: (challengeId: string) => void
  leave: (challengeId: string) => void
  tagItem: (challenge: Challenge, item: ChallengeItem, how: TagHow, poi?: string) => void
  untagItem: (challenge: Challenge, item: ChallengeItem, poi?: string) => void
  /** Takes a tag back however it was made - the tagged-place sheet's
   *  "Remove this tag". */
  removeTag: (challenge: Challenge, item: ChallengeItem, poi?: string) => void
  setNote: (challenge: Challenge, item: ChallengeItem, note: string) => void
  /** Tags every camp-card row and marks today's card answered. */
  tagAll: (candidates: readonly DayCandidate[], today: string) => void
  /** "Not tonight": the card does not come back today, and the rows stay
   *  tag-able from the challenge's own page. */
  notTonight: (today: string) => void
  hideSuggestion: (hikeKey: string, challengeId: string) => void
  setLayerShown: (shown: boolean) => void
  sendEntry: (entry: ChallengeEntryDraft) => void
  /** Forgets a refused entry - its queued item and the "sent" record - so the
   *  finish screen shows the form again. */
  forgetEntry: (challengeId: string) => void
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
  const [loaded, setLoaded] = useState(false)
  const [state, setState] = useState<ChallengeState>(readChallengeState)
  const fetched = useRef(false)
  const queued = useRef(onQueued)
  queued.current = onQueued

  useEffect(() => {
    if (!ready) return
    let wanted = true
    // The parser is loaded here rather than imported: lib/challengeFeed.ts
    // says why (#1806).
    void import('./challengeFeed')
      .then((feed) => feed.recallChallenges())
      .then((kept) => {
        if (wanted && !fetched.current && kept !== null) {
          setAll(kept)
          setLoaded(true)
        }
      })
      // No kept copy readable: the release fetch below is the other read.
      .catch(() => {})
    return () => {
      wanted = false
    }
  }, [ready])

  useEffect(() => {
    if (!DATA_CONFIGURED || !online || !ready) return
    const controller = new AbortController()
    let wanted = true
    void import('./challengeFeed')
      .then((feed) => feed.fetchChallenges(controller.signal))
      .then((fresh) => {
        if (!wanted || fresh === null) return
        fetched.current = true
        setAll(fresh)
        setLoaded(true)
      })
      // fetchChallenges catches its own network failures; this is the
      // chunk itself failing to load. The list keeps what it had.
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
        // IndexedDB refused the write (private mode, a full disk). The tag
        // stays in the phone's record and counts here; it never reaches the
        // club's numbers, and nothing retries it - rejoining is the only
        // path that queues done items again. Not surfaced: every other
        // outbox door fails the same quiet way.
        .catch(() => {})
    },
    [],
  )

  const enqueueUntag = useCallback((challengeId: string, itemId: string | null) => {
    void enqueueChallengeUntag({ challenge_id: challengeId, item_id: itemId })
      .then(() => queued.current())
      // As for a tag: the server keeps the tag it had, one more count in the
      // club's numbers and never in an entry, which reads the phone's record.
      .catch(() => {})
  }, [])

  // An item that was done and no longer is - its last hand tag pressed
  // again, a Triple Crown peak taken back - leaves the server too. One that
  // never completed never left, so there is nothing to take back.
  const takeBack = useCallback(
    (challenge: Challenge, item: ChallengeItem, next: ChallengeState) => {
      const before = stateRef.current
      commit(next)
      if (
        next !== before &&
        isItemDone(item, challenge.id, before.tags) &&
        !isItemDone(item, challenge.id, next.tags)
      )
        enqueueUntag(challenge.id, item.id)
    },
    [commit, enqueueUntag],
  )

  const tagItem = useCallback(
    (challenge: Challenge, item: ChallengeItem, how: TagHow, poi?: string) => {
      const at = new Date()
      const result = tag(stateRef.current, challenge, item, { poi, at, how })
      commit(result.state)
      // A double tap that changes nothing completes nothing, so cannot queue.
      if (result.completed)
        enqueueTag(
          challenge.id,
          item.id,
          completionHow(item, challenge.id, result.state.tags),
          at,
        )
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
      for (const done of completed)
        enqueueTag(
          done.challenge.id,
          done.item.id,
          completionHow(done.item, done.challenge.id, next.tags),
          at,
        )
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
    const result = autoTags({ ...input, joined, state: stateRef.current }, new Date())
    commit(result.state)
    for (const done of result.completed) {
      // The tag's own time - a workday is stamped on the day worked.
      const made = itemDoneAt(
        done.item,
        done.challenge.id,
        tagsFor(result.state, done.challenge.id),
      )
      enqueueTag(
        done.challenge.id,
        done.item.id,
        completionHow(done.item, done.challenge.id, result.state.tags),
        made ? new Date(made.at) : new Date(),
      )
    }
  }, [autoKey, joined, commit, enqueueTag])

  return {
    all,
    loaded,
    joined,
    state,
    join: useCallback(
      (challengeId: string) => {
        const before = stateRef.current
        const next = join(before, challengeId, new Date())
        commit(next)
        if (next === before) return
        // Rejoining: the tags kept on the phone were taken back on the
        // server when the hiker left, so each done item goes again.
        const challenge = all.find((entry) => entry.id === challengeId)
        if (challenge === undefined) return
        const tags = tagsFor(next, challengeId)
        for (const item of challenge.items) {
          const made = itemDoneAt(item, challengeId, tags)
          if (made !== null)
            enqueueTag(
              challengeId,
              item.id,
              completionHow(item, challengeId, tags),
              new Date(made.at),
            )
        }
      },
      [commit, enqueueTag, all],
    ),
    leave: useCallback(
      (challengeId: string) => {
        const before = stateRef.current
        const next = leave(before, challengeId)
        commit(next)
        if (next !== before && tagsFor(before, challengeId).length > 0)
          enqueueUntag(challengeId, null)
      },
      [commit, enqueueUntag],
    ),
    tagItem,
    untagItem: useCallback(
      (challenge: Challenge, item: ChallengeItem, poi?: string) =>
        takeBack(challenge, item, untag(stateRef.current, challenge.id, item.id, poi)),
      [takeBack],
    ),
    removeTag: useCallback(
      (challenge: Challenge, item: ChallengeItem, poi?: string) =>
        takeBack(
          challenge,
          item,
          removeTag(stateRef.current, challenge.id, item.id, poi),
        ),
      [takeBack],
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
          .then((item) => {
            // The queued id, so the finish screen reads the outbox for what
            // happened to it rather than saying it went.
            const current = stateRef.current
            commit({
              ...current,
              sent: current.sent.map((sent) =>
                sent.challengeId === entry.challenge_id && sent.at === at.toISOString()
                  ? { ...sent, outboxId: item.id }
                  : sent,
              ),
            })
            queued.current()
          })
          .catch(() => {
            // Never queued, so never going: take the "sent" record back, and
            // the finish screen shows the form again rather than "waiting"
            // for an entry the outbox does not hold.
            const current = stateRef.current
            commit({
              ...current,
              sent: current.sent.filter(
                (sent) =>
                  !(
                    sent.challengeId === entry.challenge_id &&
                    sent.at === at.toISOString()
                  ),
              ),
            })
          })
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
    forgetEntry: useCallback(
      (challengeId: string) => {
        const current = stateRef.current
        const sent = current.sent.find((entry) => entry.challengeId === challengeId)
        if (sent?.outboxId !== undefined) void removeQueued(sent.outboxId).catch(() => {})
        commit({
          ...current,
          sent: current.sent.filter((entry) => entry.challengeId !== challengeId),
        })
      },
      [commit],
    ),
  }
}
