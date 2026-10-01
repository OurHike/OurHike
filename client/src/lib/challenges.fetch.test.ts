import { afterEach, describe, expect, it, vi } from 'vitest'

// A release whose document has no list - `{}`, or an exporter that broke -
// must not replace the kept copy: keeping it took every joined challenge off
// every screen (review, 2026-09-30).
const remembered: unknown[] = []
vi.mock('./config', async (original) => ({
  ...(await original<typeof import('./config')>()),
  DATA_CONFIGURED: true,
  dataUrl: (key: string) => `https://data.example/${key}`,
}))
vi.mock('./conditionsCache', () => ({
  rememberPublished: async (_key: string, document: unknown) => {
    remembered.push(document)
  },
  recallPublished: async () => null,
}))

afterEach(() => {
  remembered.length = 0
  vi.unstubAllGlobals()
})

describe('fetchChallenges', () => {
  it('keeps nothing from a document with no list in it', async () => {
    vi.stubGlobal('fetch', async () => new Response(JSON.stringify({}), { status: 200 }))
    const { fetchChallenges } = await import('./challenges')
    expect(await fetchChallenges()).toBeNull()
    expect(remembered).toEqual([])
  })

  it('keeps a document that carries a list, even an empty one', async () => {
    vi.stubGlobal(
      'fetch',
      async () => new Response(JSON.stringify({ challenges: [] }), { status: 200 }),
    )
    const { fetchChallenges } = await import('./challenges')
    expect(await fetchChallenges()).toEqual([])
    expect(remembered).toHaveLength(1)
  })
})
