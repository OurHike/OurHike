import { describe, it, expect, vi, afterEach } from 'vitest'
import { getAuthClient } from './supabase'
import type { OutboxItem } from './outbox'

// The outbox's second cargo (#577/#579): photo actions dispatch through the
// same seam reports always used. What these cases hold: a share is the
// two-phase flush (row, then bytes), and the two idempotent actions treat
// "already gone" as a wish already granted rather than a failure that
// strands the queue.

vi.mock('./supabase', () => ({ getAuthClient: vi.fn() }))

const mockedGetAuthClient = vi.mocked(getAuthClient)

/** The configured-backend module, the way api.test.ts builds one:
 *  API_CONFIGURED is read at import time, so the env is stubbed and the
 *  module imported fresh. */
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

function mockFetch(...statuses: number[]) {
  const spy = vi.spyOn(globalThis, 'fetch')
  for (const status of statuses) {
    spy.mockResolvedValueOnce({
      ok: status >= 200 && status < 300,
      status,
      json: async () => ({ detail: 'refused' }),
    } as Response)
  }
  return spy
}

function shareItem(over: Partial<OutboxItem> = {}): OutboxItem {
  return {
    id: 'outbox-1',
    authoredAt: '2026-08-20T00:00:00.000Z',
    action: {
      kind: 'poi_photo_share',
      poiId: 'atc_shelters:abc',
      taken: '2026-06-01',
      flagged: null,
    },
    photo: new Blob([new Uint8Array(8)], { type: 'image/jpeg' }),
    ...over,
  }
}

afterEach(() => {
  vi.unstubAllEnvs()
  vi.restoreAllMocks()
  vi.clearAllMocks()
})

describe('sendOutboxItem with a share', () => {
  it('posts the row, then puts the bytes at /mine', async () => {
    const api = await configuredApi()
    withSession('token-1')
    const fetched = mockFetch(201, 200)

    await api.sendOutboxItem(shareItem())

    expect(fetched).toHaveBeenCalledTimes(2)
    const [rowUrl, rowInit] = fetched.mock.calls[0]
    expect(String(rowUrl)).toContain('/waypoints/atc_shelters%3Aabc/photos')
    expect(rowInit?.method).toBe('POST')
    expect(JSON.parse(String(rowInit?.body))).toEqual({
      taken: '2026-06-01',
      flagged: null,
    })
    const [bytesUrl, bytesInit] = fetched.mock.calls[1]
    expect(String(bytesUrl)).toContain('/photos/mine')
    expect(bytesInit?.method).toBe('PUT')
  })

  it('keeps a no-trail-name 409 retryable rather than borrowing the report sentence', async () => {
    const api = await configuredApi()
    withSession('token-1')
    mockFetch(409, 409)

    // A plain Error, not an ApiError: the generic classifier's 409 entry
    // was written for duplicate report ids, and marking this share stuck
    // with that sentence would tell the hiker something false. Retrying is
    // right - the share succeeds the moment the account has a trail name.
    await expect(api.sendOutboxItem(shareItem())).rejects.toThrow(/trail name/)
    await expect(
      api.sendOutboxItem(shareItem()).catch((error) => error instanceof api.ApiError),
    ).resolves.toBe(false)
  })
})

describe('the idempotent actions', () => {
  it('treats a 404 on withdrawal as a wish already granted', async () => {
    const api = await configuredApi()
    withSession('token-1')
    mockFetch(404)

    await expect(
      api.sendOutboxItem({
        id: 'outbox-2',
        authoredAt: '2026-08-20T00:00:00.000Z',
        action: { kind: 'poi_photo_withdraw', poiId: 'atc_shelters:abc' },
      }),
    ).resolves.toBeUndefined()
  })

  it('treats a 404 on a report as served - whatever removed the photo, it is gone', async () => {
    const api = await configuredApi()
    withSession('token-1')
    mockFetch(404)

    await expect(
      api.sendOutboxItem({
        id: 'outbox-3',
        authoredAt: '2026-08-20T00:00:00.000Z',
        action: {
          kind: 'poi_photo_report',
          poiId: 'atc_shelters:abc',
          photoId: 'p1',
          reason: 'person',
        },
      }),
    ).resolves.toBeUndefined()
  })

  it('still throws on a failure that retrying can fix', async () => {
    const api = await configuredApi()
    withSession('token-1')
    mockFetch(500)

    await expect(
      api.sendOutboxItem({
        id: 'outbox-4',
        authoredAt: '2026-08-20T00:00:00.000Z',
        action: { kind: 'poi_photo_withdraw', poiId: 'atc_shelters:abc' },
      }),
    ).rejects.toBeInstanceOf(api.ApiError)
  })
})
