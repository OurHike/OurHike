import { describe, it, expect, vi, afterEach } from 'vitest'
import { getAuthClient } from './supabase'
import type { OutboxItem } from './outbox'

// A field note's photo on the wire (#879). The harness is
// api.closures.test.ts's, duplicated deliberately the way
// api.photoActions.test.ts duplicates it: API_CONFIGURED is read at import
// time, so each of these files stubs the env and imports the module fresh.

vi.mock('./supabase', () => ({ getAuthClient: vi.fn() }))

const mockedGetAuthClient = vi.mocked(getAuthClient)

async function configuredApi() {
  vi.stubEnv('VITE_API_BASE_URL', 'https://api.example.org')
  vi.resetModules()
  return import('./api')
}

function withSession(token: string | null) {
  mockedGetAuthClient.mockReturnValue({
    auth: {
      getSession: async () => ({
        data: { session: token === null ? null : { access_token: token } },
      }),
    },
  } as unknown as ReturnType<typeof getAuthClient>)
}

function mockFetch(status = 201) {
  return vi.spyOn(globalThis, 'fetch').mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: async () => ({}),
  } as Response)
}

afterEach(() => {
  vi.unstubAllEnvs()
  vi.restoreAllMocks()
  vi.clearAllMocks()
})

// --- A field note's photo (#879) ------------------------------------------
//
// The same two-phase flush, one cargo along. What matters here is the ORDER:
// the note carries the observation, so a photo that never uploads costs the
// picture and never the sentence about the spring.

describe('sendOutboxItem with a field note that has a photo', () => {
  function noteItem(over: Partial<OutboxItem> = {}): OutboxItem {
    return {
      id: 'outbox-note-1',
      authoredAt: '2026-08-20T09:00:00.000Z',
      fieldNote: {
        poi_id: 'osm_water:1',
        observation: 'dry',
        reporter_type: 'thru',
        photo_flagged: 'faces',
      },
      photo: new Blob([new Uint8Array(8)], { type: 'image/jpeg' }),
      ...over,
    }
  }

  it('posts the note first and the bytes second', async () => {
    const api = await configuredApi()
    withSession('token-1')
    const fetchSpy = mockFetch()

    await api.sendOutboxItem(noteItem())

    const urls = fetchSpy.mock.calls.map(([url]) => String(url))
    expect(urls).toEqual([
      'https://api.example.org/field-notes',
      'https://api.example.org/field-notes/outbox-note-1/photo',
    ])
    // The screening verdict rides on the NOTE, not with the bytes: a hold
    // that arrived after the photo would be applied to something already
    // public.
    const body = JSON.parse(String((fetchSpy.mock.calls[0][1] as RequestInit).body))
    expect(body.photo_flagged).toBe('faces')
  })

  it('sends no second request for a note with no photo', async () => {
    const api = await configuredApi()
    withSession('token-1')
    const fetchSpy = mockFetch()

    await api.sendOutboxItem(noteItem({ photo: undefined }))

    expect(fetchSpy.mock.calls).toHaveLength(1)
  })
})
