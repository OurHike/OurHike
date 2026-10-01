import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, renderHook } from '@testing-library/react'
import { ATC_CHALLENGE } from './challenges.fixtures'

// What leaves the phone when a tag stops being true (review, 2026-09-30): an
// un-tag, a Leave and a rejoin each queue what makes the server agree with
// the phone. The outbox and the published list are stubbed; nothing else is.
const queued: { kind: string; body: unknown }[] = []
vi.mock('./outbox', () => ({
  enqueueChallengeTag: async (body: unknown) => {
    queued.push({ kind: 'tag', body })
    return { id: `t${queued.length}` }
  },
  enqueueChallengeUntag: async (body: unknown) => {
    queued.push({ kind: 'untag', body })
    return { id: `u${queued.length}` }
  },
  enqueueChallengeEntry: async (body: unknown) => {
    queued.push({ kind: 'entry', body })
    return { id: `e${queued.length}` }
  },
  removeQueued: async () => {},
}))
let kept: unknown[] = [ATC_CHALLENGE]
vi.mock('./challengeFeed', async (original) => ({
  ...(await original<typeof import('./challengeFeed')>()),
  recallChallenges: async () => kept,
  fetchChallenges: async () => null,
}))

afterEach(() => {
  queued.length = 0
  kept = [ATC_CHALLENGE]
  localStorage.clear()
})

async function hook() {
  const { useChallenges } = await import('./useChallenges')
  const rendered = renderHook(() => useChallenges(false, true, () => {}, null))
  await vi.waitFor(() => expect(rendered.result.current.all).toHaveLength(1))
  return rendered
}

const trivia = ATC_CHALLENGE.items.find((entry) => entry.id === 'trivia-quiz')!

describe('useChallenges keeps the server where the phone is', () => {
  it('queues a removal when a sent hand tag is pressed again', async () => {
    const { result } = await hook()
    act(() => result.current.join(ATC_CHALLENGE.id))
    act(() => result.current.tagItem(ATC_CHALLENGE, trivia, 'hand'))
    act(() => result.current.untagItem(ATC_CHALLENGE, trivia))
    await vi.waitFor(() => expect(queued).toHaveLength(2))
    expect(queued.map((entry) => entry.kind)).toEqual(['tag', 'untag'])
    expect(queued[1].body).toEqual({
      challenge_id: ATC_CHALLENGE.id,
      item_id: 'trivia-quiz',
    })
  })

  it('sends a Triple Crown as hand-tagged when any of its peaks was', async () => {
    const crown = ATC_CHALLENGE.items.find(
      (entry) => entry.id === 'virginia-triple-crown',
    )!
    const places = crown.match.kind === 'places_all' ? crown.match.places : []
    const { result } = await hook()
    act(() => result.current.join(ATC_CHALLENGE.id))
    act(() => result.current.tagItem(ATC_CHALLENGE, crown, 'hand', places[0].poi))
    act(() => result.current.tagItem(ATC_CHALLENGE, crown, 'hand', places[1].poi))
    act(() => result.current.tagItem(ATC_CHALLENGE, crown, 'gps', places[2].poi))
    await vi.waitFor(() => expect(queued).toHaveLength(1))
    expect(queued[0].body).toMatchObject({ item_id: crown.id, how: 'hand' })
  })

  it('takes every tag back on Leave, and sends them again on rejoining', async () => {
    const { result } = await hook()
    act(() => result.current.join(ATC_CHALLENGE.id))
    act(() => result.current.tagItem(ATC_CHALLENGE, trivia, 'hand'))
    act(() => result.current.leave(ATC_CHALLENGE.id))
    await vi.waitFor(() => expect(queued).toHaveLength(2))
    expect(queued[1]).toEqual({
      kind: 'untag',
      body: { challenge_id: ATC_CHALLENGE.id, item_id: null },
    })
    act(() => result.current.join(ATC_CHALLENGE.id))
    await vi.waitFor(() => expect(queued).toHaveLength(3))
    expect(queued[2].kind).toBe('tag')
  })

  it('records the queued id of an entry, so the finish screen can read what became of it', async () => {
    const { result } = await hook()
    act(() =>
      result.current.sendEntry({
        challenge_id: ATC_CHALLENGE.id,
        org_domain: 'appalachiantrail.org',
        name: 'Sam Roe',
        email: 'sam@example.org',
        item_ids: ['trivia-quiz'],
        consented: true,
      }),
    )
    await vi.waitFor(() => expect(result.current.state.sent[0]?.outboxId).toBeDefined())
  })
})

describe('useChallenges says when a list has been read', () => {
  it('counts a published list with no challenges in it as read', async () => {
    // So a joined challenge a release withdrew is reported missing, rather
    // than the empty list being mistaken for nothing read yet.
    kept = []
    const { useChallenges } = await import('./useChallenges')
    const { result } = renderHook(() => useChallenges(false, true, () => {}, null))
    expect(result.current.loaded).toBe(false)
    await vi.waitFor(() => expect(result.current.loaded).toBe(true))
    expect(result.current.all).toEqual([])
  })
})
