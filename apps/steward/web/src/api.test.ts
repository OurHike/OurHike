import { expect, it, vi } from 'vitest'
import { ApiError, createApi } from './api'
import { isOffline } from './offline'

function respond(status: number, body?: unknown) {
  return new Response(body === undefined ? null : JSON.stringify(body), { status })
}

it('createApi sends the access token and JSON, and escapes ids in the path', async () => {
  const fetchImpl = vi.fn(async () => respond(204))
  const api = createApi('https://api.example/', async () => 'access-token', fetchImpl)
  await api.addToList('list/1', 'site 2')
  const [url, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit]
  expect(url).toBe('https://api.example/lists/list%2F1/items/site%202')
  expect(init.method).toBe('PUT')
  expect((init.headers as Record<string, string>).Authorization).toBe(
    'Bearer access-token',
  )
})

it("createApi turns the API's error detail into the message a screen shows", async () => {
  const api = createApi(
    'https://api.example',
    async () => 't',
    async () => respond(409, { detail: 'A list holds at most 500 sites' }),
  )
  await expect(api.addToList('l', 's')).rejects.toEqual(
    new ApiError(409, 'A list holds at most 500 sites'),
  )
})

it('createApi sends nothing without a token, rather than an anonymous request', async () => {
  const fetchImpl = vi.fn()
  const api = createApi('https://api.example', async () => null, fetchImpl)
  await expect(api.lists()).rejects.toBeInstanceOf(ApiError)
  expect(fetchImpl).not.toHaveBeenCalled()
})

it('createApi puts a share token in the POST body, never in the URL', async () => {
  const fetchImpl = vi.fn(async () =>
    respond(200, { name: 'x', owner: null, rims_ids: [], updated_at: '' }),
  )
  const api = createApi('https://api.example', async () => 't', fetchImpl)
  await api.openShared('secret-token-value')
  const [url, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit]
  expect(url).not.toContain('secret-token-value')
  expect(init.body).toBe(JSON.stringify({ token: 'secret-token-value' }))
})

it('createApi sends a photo as the raw body with its own type', async () => {
  const fetchImpl = vi.fn(async () => respond(201, {}))
  const api = createApi('https://api.example', async () => 't', fetchImpl)
  const photo = new Blob(['jpeg bytes'], { type: 'image/jpeg' })
  await api.uploadPhoto('claim-1', 'before', 1, photo)
  const [url, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit]
  expect(url).toBe('https://api.example/claims/claim-1/photos?phase=before&point=1')
  expect((init.headers as Record<string, string>)['Content-Type']).toBe('image/jpeg')
  expect(init.body).toBe(photo)
})

it("createApi sends a queued photo's id and the slot it was taken over", async () => {
  const fetchImpl = vi.fn(async () => respond(201, {}))
  const api = createApi('https://api.example', async () => 't', fetchImpl)
  await api.uploadPhoto('claim-1', 'after', 2, new Blob(['x']), {
    clientId: '0001761550000000-000001-abc123',
    replaces: 'nothing',
  })
  const [url] = fetchImpl.mock.calls[0] as unknown as [string]
  expect(url).toBe(
    'https://api.example/claims/claim-1/photos?phase=after&point=2&client_id=0001761550000000-000001-abc123&replaces=nothing',
  )
})

it('a sign-in that cannot be renewed for lack of signal reaches a screen as no signal, so it falls back to what the phone kept', async () => {
  // The fourth pass's A: it reached the screen as 401, "Sign in first."
  const fetchImpl = vi.fn()
  const api = createApi(
    'https://api.example',
    async () => {
      throw new TypeError('No signal to renew the sign-in.')
    },
    fetchImpl,
  )
  const failure = await api.claim('claim-1').catch((error: unknown) => error)
  expect(isOffline(failure)).toBe(true)
  expect(fetchImpl).not.toHaveBeenCalled()
})
