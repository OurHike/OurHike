// An in-memory stand-in for the steward API and the sign-in it sits behind, so
// screen tests exercise lists, sharing, weights and claims without Supabase or a
// server. It keeps the API's rules that a screen can observe: owner-only lists,
// share and invite tokens that are replaced, an append-only weights history, one
// live claim per site, four photos before submitting, and no review by the crew.

import type { ReactNode } from 'react'
import { AccountContext, type Account, type Session } from '../account'
import {
  ApiError,
  type ClaimDetail,
  type ClaimSummary,
  type ClubWeights,
  type ListDetail,
  type StewardApi,
  type WeightsEntry,
} from '../api'
import type { Weights } from '../types'

const DEFAULTS: Weights = { deficit: 60, water: 12, trail: 6, cluster: 8, restricted: 10 }

const DAY_MS = 24 * 60 * 60 * 1000

/** An invented stand-in for a site photo: a flat colour with a label, never a picture of anywhere. */
function placeholderPhoto(label: string, colour: string): string {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="400" height="300"><rect width="400" height="300" fill="${colour}"/><text x="200" y="160" font-family="sans-serif" font-size="22" fill="#fff" text-anchor="middle">Example photo: ${label}</text></svg>`
  return `data:image/svg+xml,${encodeURIComponent(svg)}`
}
const HOLDING = ['claimed', 'in_progress', 'submitted']

export type FakeApi = StewardApi & {
  calls: string[]
  /** A claim someone else made and submitted, waiting for a reviewer. */
  seedSubmittedByOther(rimsId: string, name?: string): Promise<string>
}

export function fakeApi(): FakeApi {
  const calls: string[] = []
  const clientIds = new Set<string>()
  let displayName: string | null = null
  const lists = new Map<string, ListDetail>()
  const shares = new Map<string, string>()
  const history = new Map<string, WeightsEntry[]>()
  let nextId = 1
  const now = () => new Date().toISOString()
  const view = (club: string): ClubWeights => {
    const entries = history.get(club) ?? []
    const current = entries[0]
    return {
      club,
      current: current
        ? {
            deficit: current.deficit,
            water: current.water,
            trail: current.trail,
            cluster: current.cluster,
            restricted: current.restricted,
          }
        : DEFAULTS,
      defaults: DEFAULTS,
      history: entries,
    }
  }
  const claims = new Map<string, ClaimDetail>()
  const invites = new Map<string, string>()
  const summary = (claim: ClaimDetail): ClaimSummary => ({
    id: claim.id,
    rims_id: claim.rims_id,
    state: claim.state,
    claimed_at: claim.claimed_at,
    due_at: claim.due_at,
    submitted_at: claim.submitted_at,
    claimer: claim.claimer,
    crew_size: claim.crew.length,
    you_are_crew: claim.you_are_crew,
  })
  // The steward schema's _claim_detail: all of it for the crew, a reviewer,
  // whoever reviewed it last and once verified; for anyone else what the
  // open views show.
  const reviewedByYou = new Set<string>()
  const detail = (claim: ClaimDetail): ClaimDetail => {
    const full =
      claim.you_are_crew ||
      claim.state === 'verified' ||
      claim.state === 'submitted' ||
      reviewedByYou.has(claim.id)
    return {
      ...claim,
      full,
      crew_size: claim.crew.length,
      you_may_review: claim.state === 'submitted' && !claim.you_are_crew,
      photos: full ? [...claim.photos] : [],
      crew: full ? claim.crew.map((member) => ({ ...member })) : [],
      steps_done: full ? claim.steps_done : [],
      notes: full ? claim.notes : null,
      review_note: full ? claim.review_note : null,
      reviewed_by: full ? claim.reviewed_by : null,
    }
  }
  const findClaim = (id: string) => {
    const claim = claims.get(id)
    if (!claim) throw new ApiError(404, 'No such claim')
    return claim
  }
  const crewClaim = (id: string) => {
    const claim = findClaim(id)
    if (!claim.you_are_crew) throw new ApiError(403, "Only this claim's crew can do that")
    if (claim.state !== 'claimed' && claim.state !== 'in_progress') {
      throw new ApiError(409, 'This claim cannot be changed now')
    }
    return claim
  }
  const newClaim = (
    rimsId: string,
    claimer: string | null,
    youAreCrew: boolean,
  ): ClaimDetail => {
    const claimed = Date.parse(now())
    return {
      id: `claim-${nextId++}`,
      rims_id: rimsId,
      state: 'claimed',
      claimed_at: new Date(claimed).toISOString(),
      due_at: new Date(claimed + 14 * DAY_MS).toISOString(),
      submitted_at: null,
      claimer,
      crew_size: 1,
      you_are_crew: youAreCrew,
      started_at: null,
      sent_back_at: null,
      verified_at: null,
      released_at: null,
      steps_done: [],
      notes: null,
      review_note: null,
      reviewed_by: null,
      crew: [{ name: claimer, you: youAreCrew, hours: null }],
      photos: [],
      you_may_review: false,
      full: true,
    }
  }
  // A real object URL in the browser (dev:account's screenshots); under vitest,
  // whose createObjectURL cannot read jsdom's Blob, a blank page instead.
  const photoUrl = (photo: Blob) => {
    try {
      return URL.createObjectURL(photo)
    } catch {
      return 'about:blank'
    }
  }

  const own = (id: string) => {
    const list = lists.get(id)
    if (!list) throw new ApiError(404, 'No such list')
    return list
  }
  return {
    calls,
    async me() {
      return { display_name: displayName }
    },
    async setDisplayName(name) {
      displayName = name
      return { display_name: name }
    },
    async deleteMe() {
      lists.clear()
    },
    async lists() {
      return [...lists.values()]
    },
    async list(id) {
      return { ...own(id), rims_ids: [...own(id).rims_ids] }
    },
    async createList(name, rimsIds = []) {
      const list: ListDetail = {
        id: `list-${nextId++}`,
        name,
        item_count: rimsIds.length,
        shared: false,
        created_at: now(),
        updated_at: now(),
        rims_ids: [...new Set(rimsIds)],
      }
      lists.set(list.id, list)
      calls.push(`createList ${name}`)
      return list
    },
    async renameList(id, name) {
      own(id).name = name
      return own(id)
    },
    async deleteList(id) {
      lists.delete(id)
    },
    async addToList(id, rimsId) {
      const list = own(id)
      if (!list.rims_ids.includes(rimsId)) list.rims_ids.push(rimsId)
      list.item_count = list.rims_ids.length
      calls.push(`addToList ${id} ${rimsId}`)
    },
    async removeFromList(id, rimsId) {
      const list = own(id)
      list.rims_ids = list.rims_ids.filter((r) => r !== rimsId)
      list.item_count = list.rims_ids.length
    },
    async share(id) {
      own(id).shared = true
      for (const [token, listId] of shares) if (listId === id) shares.delete(token)
      const token = `token-${nextId++}-0123456789abcdef`
      shares.set(token, id)
      return { token }
    },
    async unshare(id) {
      own(id).shared = false
      for (const [token, listId] of shares) if (listId === id) shares.delete(token)
    },
    async openShared(token) {
      const id = shares.get(token)
      if (!id) throw new ApiError(404, 'This share link is not valid.')
      const list = own(id)
      return {
        name: list.name,
        owner: displayName,
        rims_ids: list.rims_ids,
        updated_at: now(),
      }
    },
    async weights(club) {
      return view(club)
    },
    async changeWeights(club, weights, note) {
      const entry: WeightsEntry = {
        id: nextId++,
        ...weights,
        note,
        restored_from: null,
        changed_by: displayName,
        by_you: true,
        changed_at: now(),
      }
      history.set(club, [entry, ...(history.get(club) ?? [])])
      return view(club)
    },
    async seedSubmittedByOther(rimsId, name = 'Another volunteer') {
      const claim = newClaim(rimsId, name, false)
      claim.state = 'submitted'
      claim.started_at = now()
      claim.submitted_at = now()
      claim.steps_done = ['Hide the site', 'Block the way in']
      claim.notes =
        'Two big logs across the pad, and the side path is blocked at the trail.'
      claim.crew[0].hours = 3
      for (const point of [1, 2]) {
        for (const phase of ['before', 'after'] as const) {
          claim.photos.push({
            id: `photo-${nextId++}`,
            phase,
            point,
            url: placeholderPhoto(
              `${phase} · point ${point}`,
              phase === 'before' ? '#b9a27a' : '#7d9b6f',
            ),
            created_at: now(),
          })
        }
      }
      claims.set(claim.id, claim)
      return claim.id
    },
    async claimSites(rimsIds) {
      const held = rimsIds.filter((r) =>
        [...claims.values()].some((c) => c.rims_id === r && HOLDING.includes(c.state)),
      )
      if (held.length) throw new ApiError(409, `Already claimed: ${held.join(', ')}`)
      return rimsIds.map((rimsId) => {
        const claim = newClaim(rimsId, displayName, true)
        claims.set(claim.id, claim)
        calls.push(`claim ${rimsId}`)
        return summary(claim)
      })
    },
    async claimForSite(rimsId) {
      const claim = [...claims.values()].find(
        (c) => c.rims_id === rimsId && HOLDING.includes(c.state),
      )
      return claim ? summary(claim) : null
    },
    async myClaims() {
      return [...claims.values()].filter((c) => c.you_are_crew).map(summary)
    },
    async claim(id) {
      return detail(findClaim(id))
    },
    async releaseClaim(id) {
      const claim = crewClaim(id)
      claim.state = 'released'
      claim.released_at = now()
      return detail(claim)
    },
    async invite(id) {
      crewClaim(id)
      for (const [token, claimId] of invites) if (claimId === id) invites.delete(token)
      const token = `invite-${nextId++}-0123456789abcdef`
      invites.set(token, id)
      return { token }
    },
    async joinClaim(token) {
      const id = invites.get(token)
      if (!id)
        throw new ApiError(
          404,
          'This invite is not valid any more. Ask the crew for a new one.',
        )
      const claim = findClaim(id)
      if (!claim.you_are_crew) {
        claim.you_are_crew = true
        claim.crew.push({ name: displayName, you: true, hours: null })
      }
      return summary(claim)
    },
    async uploadPhoto(id, phase, point, photo, { clientId, replaces } = {}) {
      // As the API does: a photo received under this id before is not stored
      // again, and a queued photo is not put over a slot that changed since.
      if (clientId && clientIds.has(`${id}/${clientId}`)) return detail(crewClaim(id))
      const claim = crewClaim(id)
      const current = claim.photos.find((p) => p.phase === phase && p.point === point)
      if (replaces && point !== null && replaces !== (current?.id ?? 'nothing'))
        throw new ApiError(
          412,
          'This point has a newer photo than this phone had seen when it took this one, so it was not put over it',
        )
      if (clientId) clientIds.add(`${id}/${clientId}`)
      claim.photos = claim.photos.filter(
        (p) => point === null || !(p.phase === phase && p.point === point),
      )
      claim.photos.push({
        id: `photo-${nextId++}`,
        phase,
        point,
        url: photoUrl(photo),
        created_at: now(),
      })
      if (phase === 'before' && claim.state === 'claimed') {
        claim.state = 'in_progress'
        claim.started_at = now()
      }
      calls.push(`photo ${phase} ${point ?? 'extra'} ${photo.type}`)
      return detail(claim)
    },
    async deletePhoto(id, photoId) {
      const claim = crewClaim(id)
      claim.photos = claim.photos.filter((p) => p.id !== photoId)
      return detail(claim)
    },
    async logHours(id, hours) {
      const claim = crewClaim(id)
      const you = claim.crew.find((m) => m.you)
      if (you) you.hours = hours
      return detail(claim)
    },
    async submit(id, stepsDone, notes) {
      const claim = crewClaim(id)
      const have = new Set(claim.photos.map((p) => `${p.phase} ${p.point}`))
      const missing = [1, 2]
        .flatMap((point) => ['before', 'after'].map((phase) => `${phase} ${point}`))
        .filter((k) => !have.has(k))
      if (missing.length)
        throw new ApiError(422, `Still needed before submitting: ${missing.join(', ')}`)
      claim.state = 'submitted'
      claim.submitted_at = now()
      claim.steps_done = stepsDone
      claim.notes = notes
      return detail(claim)
    },
    async reviews() {
      return [...claims.values()]
        .filter((c) => c.state === 'submitted' && !c.you_are_crew)
        .map(summary)
    },
    async review(id, verdict, note) {
      const claim = findClaim(id)
      if (claim.you_are_crew)
        throw new ApiError(403, 'Someone off the crew has to review this')
      if (verdict !== 'verify' && !note) {
        throw new ApiError(422, 'Say what is missing when sending back or rejecting')
      }
      claim.reviewed_by = displayName
      claim.review_note = note
      reviewedByYou.add(claim.id)
      if (verdict === 'verify') {
        claim.state = 'verified'
        claim.verified_at = now()
      } else if (verdict === 'send_back') {
        claim.state = 'in_progress'
        claim.sent_back_at = now()
        claim.submitted_at = null
        claim.due_at = new Date(Date.parse(now()) + 7 * DAY_MS).toISOString()
      } else {
        claim.state = 'released'
        claim.released_at = now()
      }
      return detail(claim)
    },
    async myHours() {
      const mine = [...claims.values()].filter((c) => c.you_are_crew)
      const hoursOf = (c: ClaimDetail) => c.crew.find((m) => m.you)?.hours ?? 0
      return {
        verified: mine
          .filter((c) => c.state === 'verified')
          .reduce((t, c) => t + hoursOf(c), 0),
        waiting: mine
          .filter((c) => c.state !== 'verified')
          .reduce((t, c) => t + hoursOf(c), 0),
        claims: mine.filter((c) => hoursOf(c) > 0).length,
      }
    },
    async restoreWeights(entryId, note) {
      for (const [club, entries] of history) {
        const earlier = entries.find((e) => e.id === entryId)
        if (earlier) {
          const entry = {
            ...earlier,
            id: nextId++,
            note,
            restored_from: entryId,
            by_you: true,
          }
          history.set(club, [entry, ...entries])
          return view(club)
        }
      }
      throw new ApiError(404, 'No such weights entry')
    },
  }
}

export function fakeAccount(
  session: Session,
  api: StewardApi | null = null,
): Account & { sent: string[] } {
  const sent: string[] = []
  return {
    session,
    api: session.state === 'signed_in' ? (api ?? fakeApi()) : null,
    sent,
    async sendCode(email) {
      sent.push(`code to ${email}`)
      return null
    },
    async verifyCode(email, code) {
      sent.push(`verify ${email} ${code}`)
      return code === '123456'
        ? null
        : 'That code is wrong or has expired. Ask for a new one.'
    },
    async signOut() {
      sent.push('sign out')
    },
  }
}

export const SIGNED_IN: Session = {
  state: 'signed_in',
  userId: 'user-1',
  email: 'volunteer@example.com',
}
export const SIGNED_OUT: Session = { state: 'signed_out' }

export function withAccount(account: Account, children: ReactNode) {
  return <AccountContext.Provider value={account}>{children}</AccountContext.Provider>
}
