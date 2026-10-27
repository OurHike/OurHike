import { describe, expect, it, vi } from 'vitest'
import {
  ApiError,
  PHOTO_BUCKET,
  PHOTO_LINK_SECONDS,
  createApi,
  type DataClient,
} from './api'
import { isOffline } from './offline'

type Answer = { data?: unknown; error?: { message: string } | null; status?: number }
type StorageError = {
  name?: string
  message: string
  status?: number
  statusCode?: string
}

/** A supabase-js client that records what it is asked and answers from a script.
 *  `unsigned` are paths Storage will not sign; `signing` replaces the whole answer. */
function recording(
  answers: Record<string, Answer> = {},
  upload: StorageError | null = null,
  { unsigned = [] as string[], signing = null as null | (() => Promise<never>) } = {},
) {
  const calls: { fn: string; args: Record<string, unknown> }[] = []
  const uploads: { path: string; type: string; upsert: boolean; cache: string }[] = []
  const removed: string[][] = []
  const signed: { paths: string[]; seconds: number }[] = []
  const client: DataClient = {
    rpc: async (fn, args = {}) => {
      calls.push({ fn, args })
      const answer = answers[fn] ?? (fn === 'photo_folder' ? { data: 'folder-1' } : {})
      return {
        data: answer.data ?? null,
        error: answer.error ?? null,
        status: answer.status ?? 200,
      }
    },
    storage: {
      from: (bucket) => {
        expect(bucket).toBe(PHOTO_BUCKET)
        return {
          upload: async (path, _body, options) => {
            uploads.push({
              path,
              type: options.contentType,
              upsert: options.upsert,
              cache: options.cacheControl,
            })
            return { error: upload }
          },
          remove: async (paths) => {
            removed.push(paths)
            return {}
          },
          createSignedUrls: async (paths, seconds) => {
            if (signing) return signing()
            signed.push({ paths, seconds })
            return {
              data: paths.map((path) =>
                unsigned.includes(path)
                  ? { path, signedUrl: null, error: 'Either the object does not exist' }
                  : {
                      path,
                      signedUrl: `https://p.example/sign/${path}?token=${signed.length}`,
                      error: null,
                    },
              ),
              error: null,
            }
          },
        }
      },
    },
  }
  return { api: createApi(client), calls, uploads, removed, signed }
}

const claimRow = (
  photos: { path: string }[] = [],
  extra: Record<string, unknown> = {},
) => ({
  id: 'claim-1',
  photos: photos.map((p, i) => ({
    id: `photo-${i}`,
    phase: 'extra',
    point: null,
    created_at: '',
    ...p,
  })),
  ...extra,
})

it('each call is the steward function of that name, with its arguments named', async () => {
  const { api, calls } = recording()
  await api.claimSites(['site-a', 'site-b'])
  await api.addToList('list-1', 'site-a')
  await api.changeWeights(
    'Example Trail Club',
    { deficit: 50, water: 24, trail: 6, cluster: 8, restricted: 10 },
    'Water first',
  )
  await api.openShared('a-share-token-value')
  expect(calls).toEqual([
    { fn: 'claim_sites', args: { p_rims_ids: ['site-a', 'site-b'] } },
    { fn: 'add_to_list', args: { p_id: 'list-1', p_rims_id: 'site-a' } },
    {
      fn: 'change_weights',
      args: {
        p_club: 'Example Trail Club',
        p_deficit: 50,
        p_water: 24,
        p_trail: 6,
        p_cluster: 8,
        p_restricted: 10,
        p_note: 'Water first',
      },
    },
    { fn: 'open_shared_list', args: { p_token: 'a-share-token-value' } },
  ])
})

it("a function's refusal reaches the screen as its status and its own sentence", async () => {
  const { api } = recording({
    claim_sites: { error: { message: 'Already claimed: site-a' }, status: 409 },
  })
  await expect(api.claimSites(['site-a'])).rejects.toEqual(
    new ApiError(409, 'Already claimed: site-a'),
  )
})

it('a call that never got an answer is no signal, so screens fall back to the phone', async () => {
  const { api } = recording({
    read_claim: { error: { message: 'TypeError: Failed to fetch' }, status: 0 },
  })
  const failure = await api.claim('claim-1').catch((error: unknown) => error)
  expect(isOffline(failure)).toBe(true)
})

describe('photos', () => {
  it("go to the bucket under the claim, the uploader's folder on it and the phone's id for them, then onto the claim", async () => {
    const { api, calls, uploads } = recording({
      add_photo: { data: claimRow([{ path: 'claim-1/folder-1/queued-1.jpg' }]) },
    })
    const detail = await api.uploadPhoto('claim-1', 'after', 2, new Blob(['x']), {
      clientId: 'queued-1',
      replaces: 'nothing',
    })
    // The bucket's insert policy takes a photo only in its uploader's own
    // folder on the claim, a random id that names nobody, and caches it for
    // the hour a link lasts (the sixth pass, 2 and 6, and its re-check).
    expect(uploads).toEqual([
      {
        path: 'claim-1/folder-1/queued-1.jpg',
        type: 'image/jpeg',
        upsert: false,
        cache: String(PHOTO_LINK_SECONDS),
      },
    ])
    expect(calls).toEqual([
      { fn: 'photo_folder', args: { p_claim_id: 'claim-1' } },
      {
        fn: 'add_photo',
        args: {
          p_claim_id: 'claim-1',
          p_phase: 'after',
          p_point: 2,
          p_client_id: 'queued-1',
          p_replaces: 'nothing',
        },
      },
    ])
    expect(detail.photos[0].url).toBe(
      'https://p.example/sign/claim-1/folder-1/queued-1.jpg?token=1',
    )
  })

  it('ask for the folder once a claim, and again only after the asking failed', async () => {
    let failing = true
    const { api, calls } = recording({ add_photo: { data: claimRow() } })
    const real = calls.push.bind(calls)
    calls.push = (...entries) => {
      if (failing && entries[0].fn === 'photo_folder') {
        failing = false
        real(...entries)
        throw new TypeError('Failed to fetch')
      }
      return real(...entries)
    }
    const send = (clientId: string) =>
      api.uploadPhoto('claim-1', 'extra', null, new Blob(['x']), { clientId })
    await expect(send('a')).rejects.toThrow()
    await send('b')
    await send('c')
    expect(calls.map((c) => c.fn)).toEqual([
      'photo_folder',
      'photo_folder',
      'add_photo',
      'add_photo',
    ])
  })

  it('are shown through links Storage signs for an hour, reused while most of it is left', async () => {
    vi.useFakeTimers()
    try {
      const row = claimRow([
        { path: 'claim-1/folder-1/a.jpg' },
        { path: 'claim-1/folder-1/b.jpg' },
      ])
      const { api, signed } = recording({ read_claim: { data: row } })
      const first = await api.claim('claim-1')
      vi.advanceTimersByTime(30 * 60 * 1000)
      const again = await api.claim('claim-1')
      // The same link is the same image to the browser's cache.
      expect(again.photos.map((p) => p.url)).toEqual(first.photos.map((p) => p.url))
      vi.advanceTimersByTime(20 * 60 * 1000)
      const later = await api.claim('claim-1')
      expect(later.photos[0].url).not.toBe(first.photos[0].url)
      expect(signed).toEqual([
        { paths: ['claim-1/folder-1/a.jpg', 'claim-1/folder-1/b.jpg'], seconds: 3600 },
        { paths: ['claim-1/folder-1/a.jpg', 'claim-1/folder-1/b.jpg'], seconds: 3600 },
      ])
    } finally {
      vi.useRealTimers()
    }
  })

  it('a photo Storage would not sign is not loaded, and the claim still arrives', async () => {
    const row = claimRow([
      { path: 'claim-1/folder-1/a.jpg' },
      { path: 'claim-1/folder-1/gone.jpg' },
    ])
    const one = await recording({ read_claim: { data: row } }, null, {
      unsigned: ['claim-1/folder-1/gone.jpg'],
    }).api.claim('claim-1')
    expect(one.photos.map((p) => p.url === null)).toEqual([false, true])
    const none = await recording({ read_claim: { data: row } }, null, {
      signing: () => Promise.reject(new TypeError('Failed to fetch')),
    }).api.claim('claim-1')
    expect(none.photos.map((p) => p.url)).toEqual([null, null])
  })

  it('already in the bucket is already sent: the claim is still asked to take it', async () => {
    // An earlier send arrived and its answer did not; the id is this photo's alone.
    const { api, calls } = recording(
      { add_photo: { data: claimRow() } },
      {
        name: 'StorageApiError',
        message: 'The resource already exists',
        status: 409,
        statusCode: '409',
      },
    )
    await api.uploadPhoto('claim-1', 'extra', null, new Blob(['x']), {
      clientId: 'again',
    })
    expect(calls.map((c) => c.fn)).toEqual(['photo_folder', 'add_photo'])
  })

  it('an upload that never got an answer is no signal, and nothing is put on the claim', async () => {
    const { api, calls } = recording(
      {},
      { name: 'StorageUnknownError', message: 'Failed to fetch' },
    )
    const failure = await api
      .uploadPhoto('claim-1', 'extra', null, new Blob(['x']), { clientId: 'offline' })
      .catch((error: unknown) => error)
    expect(isOffline(failure)).toBe(true)
    expect(calls.map((c) => c.fn)).toEqual(['photo_folder'])
  })

  it('an upload the bucket refuses is refused, with a sentence a volunteer can act on', async () => {
    const { api } = recording(
      {},
      {
        name: 'StorageApiError',
        message: 'new row violates row-level security policy',
        status: 403,
      },
    )
    await expect(
      api.uploadPhoto('claim-1', 'extra', null, new Blob(['x']), { clientId: 'late' }),
    ).rejects.toEqual(
      new ApiError(
        403,
        'This photo could not be stored for this claim. It may have closed.',
      ),
    )
  })

  it('a retaken or removed photo is deleted from the bucket, so it does not stay readable', async () => {
    const { api, removed } = recording({
      add_photo: { data: claimRow([], { unused_path: 'claim-1/first.jpg' }) },
      remove_photo: { data: claimRow([], { unused_path: 'claim-1/extra.jpg' }) },
    })
    const retaken = await api.uploadPhoto('claim-1', 'before', 1, new Blob(['x']), {
      clientId: 'retake',
    })
    await api.deletePhoto('claim-1', 'photo-0')
    expect(removed).toEqual([['claim-1/first.jpg'], ['claim-1/extra.jpg']])
    expect('unused_path' in retaken).toBe(false)
  })
})
