import { expect, it, vi } from 'vitest'
import { ApiError, createApi } from './api'

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
