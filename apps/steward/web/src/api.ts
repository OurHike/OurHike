// Campsite Steward's data, read and written in OurHike's Supabase project
// (apps/steward/db; PLAN.md, decided 2026-10-27: no API server). Every change
// is a call to one of the `steward` schema's functions, which hold the rules;
// photos go to its private Storage bucket first and are then put on the
// claim, and are shown through links Storage signs for whoever the bucket's
// policy lets read them. The screens see only StewardApi, so they do not
// know which.

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
  /** A link Storage signed, good for PHOTO_LINK_SECONDS; null when it would
   *  not sign one just now, which a screen shows as not loaded, never as no
   *  photo. */
  url: string | null
  created_at: string
}

export interface ClaimDetail extends ClaimSummary {
  /** False when this account sees only what anyone may: until a claim is
   *  submitted its photos, report and crew are its crew's (the steward
   *  schema's _claim_detail). The lists are then empty, which says nothing
   *  about the claim's own. */
  full: boolean
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
      createSignedUrls(
        paths: string[],
        expiresIn: number,
      ): Promise<{
        data:
          { path: string | null; signedUrl: string | null; error: string | null }[] | null
        error: StorageFailure | null
      }>
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

/** How long a photo link lasts, and how long the bucket tells a browser or
 *  CDN to keep a photo: a retake or a removed photo (someone was in the
 *  frame) stops being served within the hour (the SQL review's sixth pass,
 *  finding 6, against the year it was). A reasoned bound, not a measured
 *  need: nothing here needs a photo cached longer, and the service worker
 *  keeps the ones a phone has shown for use with no signal (vite.config.ts). */
export const PHOTO_LINK_SECONDS = 3600

type Raw = Record<string, unknown>

/**
 * The steward API over a supabase-js client whose schema is `steward`.
 *
 * Statuses mean what they meant when this was an HTTP API: the functions
 * raise SQLSTATE PTnnn, which PostgREST sends as HTTP status nnn, and a
 * request that never got an answer is 0, which offline.isOffline reads as no
 * signal. So the offline queue and every screen work unchanged.
 *
 * `userId` is the signed-in account's: a photo is uploaded under it, as the
 * bucket's insert policy requires.
 */
export function createApi(client: DataClient, userId: string): StewardApi {
  async function call<T>(fn: string, args: Raw = {}): Promise<T> {
    const { data, error, status } = await client.rpc(fn, args)
    if (error)
      throw new ApiError(status, error.message || `The server answered ${status}.`)
    return data as T
  }

  const bucket = () => client.storage.from(PHOTO_BUCKET)

  // Links already signed, reused while a quarter of their hour is left: the
  // same link is the same image to the browser's cache, so a claim opened
  // again does not download its photos again.
  const links = new Map<string, { url: string; until: number }>()
  const REUSE_MS = (PHOTO_LINK_SECONDS * 1000) / 4

  async function sign(paths: string[]): Promise<Map<string, string | null>> {
    const now = Date.now()
    const usable = (path: string, margin: number) => {
      const link = links.get(path)
      return link && link.until - now > margin ? link.url : null
    }
    const wanted = [...new Set(paths)].filter((path) => !usable(path, REUSE_MS))
    if (wanted.length > 0) {
      const { data } = await bucket()
        .createSignedUrls(wanted, PHOTO_LINK_SECONDS)
        .catch(() => ({ data: null }))
      for (const signed of data ?? [])
        if (signed.path && signed.signedUrl)
          links.set(signed.path, {
            url: signed.signedUrl,
            until: now + PHOTO_LINK_SECONDS * 1000,
          })
    }
    return new Map(paths.map((path) => [path, usable(path, 0)]))
  }

  /** A claim as the functions return it, with a signed link to each photo. */
  async function withUrls(raw: Raw): Promise<ClaimDetail> {
    const { unused_path: _, ...claim } = raw
    const photos = (claim.photos as (Omit<ClaimPhoto, 'url'> & { path: string })[]) ?? []
    const urls = await sign(photos.map((photo) => photo.path))
    return {
      ...(claim as unknown as ClaimDetail),
      photos: photos.map(({ path, ...photo }) => ({
        ...photo,
        url: urls.get(path) ?? null,
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
    const { error } = await bucket().upload(
      `${claimId}/${userId}/${clientId}.jpg`,
      photo,
      {
        contentType: 'image/jpeg',
        upsert: false,
        cacheControl: String(PHOTO_LINK_SECONDS),
      },
    )
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
