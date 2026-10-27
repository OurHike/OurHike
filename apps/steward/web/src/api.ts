// Campsite Steward's data, read and written in OurHike's Supabase project
// (apps/steward/db; PLAN.md, decided 2026-10-27: no API server). Every change
// is a call to one of the `steward` schema's functions, which hold the rules;
// photos go to its public Storage bucket first and are then put on the claim.
// The screens see only StewardApi, so they do not know which.

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
  /** `clientId` is the phone's own id for the photo (src/offline.ts): it names
   *  the photo's object in the bucket, and the claim takes a photo once
   *  however many times it is sent under one id. `replaces`, for a queued
   *  before or after photo, is the id of the photo in its slot when it was
   *  taken, or 'nothing': if someone has photographed the point since, the
   *  answer is 412 rather than this one put over theirs. */
  uploadPhoto(
    id: string,
    phase: PhotoPhase,
    point: number | null,
    photo: Blob,
    send?: { clientId?: string; replaces?: string },
  ): Promise<ClaimDetail>
  deletePhoto(id: string, photoId: string): Promise<ClaimDetail>
  logHours(id: string, hours: number): Promise<ClaimDetail>
  submit(id: string, stepsDone: string[], notes: string | null): Promise<ClaimDetail>
  reviews(): Promise<ClaimSummary[]>
  review(id: string, verdict: Verdict, note: string | null): Promise<ClaimDetail>
  myHours(): Promise<HoursTotals>
}

/** As much of a supabase-js client as this uses: functions and the photo bucket. */
export interface DataClient {
  rpc(
    fn: string,
    args?: Record<string, unknown>,
  ): PromiseLike<{ data: unknown; error: { message: string } | null; status: number }>
  storage: {
    from(bucket: string): {
      upload(
        path: string,
        body: Blob,
        options: { contentType: string; upsert: boolean; cacheControl: string },
      ): Promise<{ error: StorageFailure | null }>
      remove(paths: string[]): Promise<unknown>
      getPublicUrl(path: string): { data: { publicUrl: string } }
    }
  }
}

/** storage-js's errors: StorageApiError carries the HTTP status;
 *  StorageUnknownError is a request that never got an answer. */
interface StorageFailure {
  name?: string
  message: string
  status?: number
  statusCode?: string
}

export const PHOTO_BUCKET = 'steward-photos'

type Raw = Record<string, unknown>

/**
 * The steward API over a supabase-js client whose schema is `steward`.
 *
 * Statuses mean what they meant when this was an HTTP API: the functions
 * raise SQLSTATE PTnnn, which PostgREST sends as HTTP status nnn, and a
 * request that never got an answer is 0, which offline.isOffline reads as no
 * signal. So the offline queue and every screen work unchanged.
 */
export function createApi(client: DataClient): StewardApi {
  async function call<T>(fn: string, args: Raw = {}): Promise<T> {
    const { data, error, status } = await client.rpc(fn, args)
    if (error)
      throw new ApiError(status, error.message || `The server answered ${status}.`)
    return data as T
  }

  const bucket = () => client.storage.from(PHOTO_BUCKET)

  /** A claim as the functions return it, with each photo's public address. */
  function withUrls(raw: Raw): ClaimDetail {
    const { unused_path: _, ...claim } = raw
    const photos = (claim.photos as (Omit<ClaimPhoto, 'url'> & { path: string })[]) ?? []
    return {
      ...(claim as unknown as ClaimDetail),
      photos: photos.map(({ path, ...photo }) => ({
        ...photo,
        url: bucket().getPublicUrl(path).data.publicUrl,
      })),
    }
  }

  /** Calls a claim function, and deletes the object it says no photo uses
   *  now. Best effort: an object left behind is only an orphan in the bucket. */
  async function claimCall(fn: string, args: Raw): Promise<ClaimDetail> {
    const raw = await call<Raw>(fn, args)
    if (typeof raw.unused_path === 'string') {
      try {
        await bucket().remove([raw.unused_path])
      } catch {
        // Kept for the sweep PLAN.md §11 names.
      }
    }
    return withUrls(raw)
  }

  async function upload(claimId: string, clientId: string, photo: Blob): Promise<void> {
    const { error } = await bucket().upload(`${claimId}/${clientId}.jpg`, photo, {
      contentType: 'image/jpeg',
      upsert: false,
      cacheControl: '31536000',
    })
    if (!error) return
    // Already there: an earlier send of this same photo arrived and its
    // answer did not. The id is this photo's alone, so it is this photo.
    if (
      error.status === 409 ||
      error.statusCode === '409' ||
      /already exists|duplicate/i.test(error.message)
    )
      return
    if (error.name === 'StorageUnknownError' || error.status === undefined)
      throw new ApiError(0, error.message)
    throw new ApiError(
      error.status,
      error.status === 413
        ? 'That photo is too large'
        : error.status === 403 || error.status === 400
          ? 'This photo could not be stored for this claim. It may have closed.'
          : error.message,
    )
  }

  return {
    me: () => call('me'),
    setDisplayName: (name) => call('set_display_name', { p_name: name }),
    deleteMe: () => call('delete_my_data'),
    lists: () => call('my_lists'),
    list: (id) => call('read_list', { p_id: id }),
    createList: (name, rimsIds = []) =>
      call('create_list', { p_name: name, p_rims_ids: rimsIds }),
    renameList: (id, name) => call('rename_list', { p_id: id, p_name: name }),
    deleteList: (id) => call('delete_list', { p_id: id }),
    addToList: (id, rimsId) => call('add_to_list', { p_id: id, p_rims_id: rimsId }),
    removeFromList: (id, rimsId) =>
      call('remove_from_list', { p_id: id, p_rims_id: rimsId }),
    share: (id) => call('share_list', { p_id: id }),
    unshare: (id) => call('unshare_list', { p_id: id }),
    openShared: (token) => call('open_shared_list', { p_token: token }),
    weights: (club) => call('read_weights', { p_club: club }),
    changeWeights: (club, weights, note) =>
      call('change_weights', {
        p_club: club,
        p_deficit: weights.deficit,
        p_water: weights.water,
        p_trail: weights.trail,
        p_cluster: weights.cluster,
        p_restricted: weights.restricted,
        p_note: note,
      }),
    restoreWeights: (entryId, note) =>
      call('restore_weights', { p_entry_id: entryId, p_note: note }),
    claimSites: (rimsIds) => call('claim_sites', { p_rims_ids: rimsIds }),
    claimForSite: (rimsId) => call('claim_for_site', { p_rims_id: rimsId }),
    myClaims: () => call('my_claims'),
    claim: async (id) => withUrls(await call<Raw>('read_claim', { p_id: id })),
    releaseClaim: (id) => claimCall('release_claim', { p_id: id }),
    invite: (id) => call('make_invite', { p_id: id }),
    joinClaim: (token) => call('join_claim', { p_token: token }),
    uploadPhoto: async (id, phase, point, photo, send = {}) => {
      const clientId = send.clientId ?? newClientId()
      await upload(id, clientId, photo)
      return claimCall('add_photo', {
        p_claim_id: id,
        p_phase: phase,
        p_point: point,
        p_client_id: clientId,
        p_replaces: send.replaces ?? null,
      })
    },
    deletePhoto: (id, photoId) =>
      claimCall('remove_photo', { p_claim_id: id, p_photo_id: photoId }),
    logHours: (id, hours) => claimCall('log_hours', { p_claim_id: id, p_hours: hours }),
    submit: (id, stepsDone, notes) =>
      claimCall('submit_claim', { p_id: id, p_steps_done: stepsDone, p_notes: notes }),
    reviews: () => call('reviews'),
    review: (id, verdict, note) =>
      claimCall('review_claim', { p_id: id, p_verdict: verdict, p_note: note }),
    myHours: () => call('my_hours'),
  }
}

/** For a photo sent with no id of its own (src/offline.ts gives every photo one). */
function newClientId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
}
