// The steward API (apps/steward/api/, #1906): lists, share links and club weights.
// Every call carries the signed-in person's Supabase access token.

import type { Weights } from './types'

export class ApiError extends Error {
  readonly status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

export interface ListSummary {
  id: string
  name: string
  item_count: number
  shared: boolean
  created_at: string
  updated_at: string
}

export interface ListDetail extends ListSummary {
  rims_ids: string[]
}

export interface SharedList {
  name: string
  owner: string | null
  rims_ids: string[]
  updated_at: string
}

export interface WeightsEntry extends Weights {
  id: number
  note: string | null
  restored_from: number | null
  changed_by: string | null
  by_you: boolean
  changed_at: string
}

export interface ClubWeights {
  club: string
  current: Weights
  defaults: Weights
  history: WeightsEntry[]
}

export interface StewardApi {
  me(): Promise<{ display_name: string | null }>
  setDisplayName(name: string | null): Promise<{ display_name: string | null }>
  deleteMe(): Promise<void>
  lists(): Promise<ListSummary[]>
  list(id: string): Promise<ListDetail>
  createList(name: string, rimsIds?: string[]): Promise<ListDetail>
  renameList(id: string, name: string): Promise<ListDetail>
  deleteList(id: string): Promise<void>
  addToList(id: string, rimsId: string): Promise<void>
  removeFromList(id: string, rimsId: string): Promise<void>
  share(id: string): Promise<{ token: string }>
  unshare(id: string): Promise<void>
  openShared(token: string): Promise<SharedList>
  weights(club: string): Promise<ClubWeights>
  changeWeights(club: string, weights: Weights, note: string | null): Promise<ClubWeights>
  restoreWeights(entryId: number, note: string | null): Promise<ClubWeights>
}

/** What the API's error body says, as a sentence a person can read. */
async function errorMessage(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown }
    if (typeof body.detail === 'string') return body.detail
    if (Array.isArray(body.detail)) return 'Some of what was entered is not allowed.'
  } catch {
    // not JSON: fall through
  }
  return `The server answered ${response.status}.`
}

export function createApi(
  baseUrl: string,
  token: () => Promise<string | null>,
  fetchImpl: typeof fetch = (...args) => fetch(...args),
): StewardApi {
  const root = baseUrl.replace(/\/+$/, '')

  async function call<T>(method: string, path: string, body?: unknown): Promise<T> {
    const access = await token()
    if (!access) throw new ApiError(401, 'Sign in first.')
    const response = await fetchImpl(`${root}${path}`, {
      method,
      headers: {
        Authorization: `Bearer ${access}`,
        ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
    if (!response.ok) throw new ApiError(response.status, await errorMessage(response))
    return (response.status === 204 ? undefined : await response.json()) as T
  }

  const listPath = (id: string) => `/lists/${encodeURIComponent(id)}`
  const itemPath = (id: string, rimsId: string) =>
    `${listPath(id)}/items/${encodeURIComponent(rimsId)}`

  return {
    me: () => call('GET', '/me'),
    setDisplayName: (name) => call('PATCH', '/me', { display_name: name }),
    deleteMe: () => call('DELETE', '/me'),
    lists: () => call('GET', '/lists'),
    list: (id) => call('GET', listPath(id)),
    createList: (name, rimsIds = []) =>
      call('POST', '/lists', { name, rims_ids: rimsIds }),
    renameList: (id, name) => call('PATCH', listPath(id), { name }),
    deleteList: (id) => call('DELETE', listPath(id)),
    addToList: (id, rimsId) => call('PUT', itemPath(id, rimsId)),
    removeFromList: (id, rimsId) => call('DELETE', itemPath(id, rimsId)),
    share: (id) => call('POST', `${listPath(id)}/share`),
    unshare: (id) => call('DELETE', `${listPath(id)}/share`),
    openShared: (token) => call('POST', '/shared', { token }),
    weights: (club) => call('GET', `/weights?club=${encodeURIComponent(club)}`),
    changeWeights: (club, weights, note) =>
      call('POST', '/weights', { club, ...weights, note }),
    restoreWeights: (entryId, note) =>
      call('POST', `/weights/${encodeURIComponent(String(entryId))}/restore`, { note }),
  }
}
