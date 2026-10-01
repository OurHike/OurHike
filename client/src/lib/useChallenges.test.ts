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
vi.mock('./challengeFeed', async (original) => ({
  ...(await original<typeof import('./challengeFeed')>()),
  recallChallenges: async () => [ATC_CHALLENGE],
  fetchChallenges: async () => null,
}))

afterEach(() => {
  queued.length = 0
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
