// The steward API (apps/steward/api/): lists, share links and club weights (#1906),
// and claims, crews, photos and reviews (#1910).
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

export type ClaimState = 'claimed' | 'in_progress' | 'submitted' | 'verified' | 'released'
export type PhotoPhase = 'before' | 'after' | 'extra'
export type Verdict = 'verify' | 'send_back' | 'reject'

export interface ClaimSummary {
  id: string
  rims_id: string
  state: ClaimState
  claimed_at: string
  due_at: string
  submitted_at: string | null
  claimer: string | null
  crew_size: number
  you_are_crew: boolean
}

export interface ClaimPhoto {
  id: string
  phase: PhotoPhase
  point: number | null
  url: string
  created_at: string
}

export interface ClaimDetail extends ClaimSummary {
  started_at: string | null
  /** After photos older than this do not count toward the next submission. */
  sent_back_at: string | null
  verified_at: string | null
  released_at: string | null
  steps_done: string[]
  notes: string | null
  review_note: string | null
  reviewed_by: string | null
  crew: { name: string | null; you: boolean; hours: number | null }[]
  photos: ClaimPhoto[]
  you_may_review: boolean
}

export interface HoursTotals {
  verified: number
  waiting: number
  claims: number
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
  claimSites(rimsIds: string[]): Promise<ClaimSummary[]>
  claimForSite(rimsId: string): Promise<ClaimSummary | null>
  myClaims(): Promise<ClaimSummary[]>
  claim(id: string): Promise<ClaimDetail>
  releaseClaim(id: string): Promise<ClaimDetail>
  invite(id: string): Promise<{ token: string }>
  joinClaim(token: string): Promise<ClaimSummary>
  /** `clientId` is the phone's own id for a queued photo (src/offline.ts): the
   *  API stores a photo once however many times it is sent under one id. */
  uploadPhoto(
    id: string,
    phase: PhotoPhase,
    point: number | null,
    photo: Blob,
    clientId?: string,
  ): Promise<ClaimDetail>
  deletePhoto(id: string, photoId: string): Promise<ClaimDetail>
  logHours(id: string, hours: number): Promise<ClaimDetail>
  submit(id: string, stepsDone: string[], notes: string | null): Promise<ClaimDetail>
  reviews(): Promise<ClaimSummary[]>
  review(id: string, verdict: Verdict, note: string | null): Promise<ClaimDetail>
  myHours(): Promise<HoursTotals>
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
    // A photo goes as the raw body with its own type; everything else as JSON.
    const raw = body instanceof Blob
    const response = await fetchImpl(`${root}${path}`, {
      method,
      headers: {
        Authorization: `Bearer ${access}`,
        ...(body === undefined
          ? {}
          : {
              'Content-Type': raw
                ? body.type || 'application/octet-stream'
                : 'application/json',
            }),
      },
      body: body === undefined ? undefined : raw ? body : JSON.stringify(body),
    })
    if (!response.ok) throw new ApiError(response.status, await errorMessage(response))
    return (response.status === 204 ? undefined : await response.json()) as T
  }

  const listPath = (id: string) => `/lists/${encodeURIComponent(id)}`
  const claimPath = (id: string) => `/claims/${encodeURIComponent(id)}`
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
    claimSites: (rimsIds) => call('POST', '/claims', { rims_ids: rimsIds }),
    claimForSite: (rimsId) => call('GET', `/claims/site/${encodeURIComponent(rimsId)}`),
    myClaims: () => call('GET', '/claims/mine'),
    claim: (id) => call('GET', claimPath(id)),
    releaseClaim: (id) => call('POST', `${claimPath(id)}/release`),
    invite: (id) => call('POST', `${claimPath(id)}/invite`),
    joinClaim: (token) => call('POST', '/claims/join', { token }),
    uploadPhoto: (id, phase, point, photo, clientId) =>
      call(
        'POST',
        `${claimPath(id)}/photos?phase=${phase}${point === null ? '' : `&point=${point}`}${clientId ? `&client_id=${encodeURIComponent(clientId)}` : ''}`,
        photo,
      ),
    deletePhoto: (id, photoId) =>
      call('DELETE', `${claimPath(id)}/photos/${encodeURIComponent(photoId)}`),
    logHours: (id, hours) => call('PUT', `${claimPath(id)}/hours`, { hours }),
    submit: (id, stepsDone, notes) =>
      call('POST', `${claimPath(id)}/submit`, { steps_done: stepsDone, notes }),
    reviews: () => call('GET', '/reviews'),
    review: (id, verdict, note) =>
      call('POST', `${claimPath(id)}/review`, { verdict, note }),
    myHours: () => call('GET', '/hours/mine'),
  }
}
