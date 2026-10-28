// An in-memory stand-in for the remediation API and the sign-in it sits behind, so
// screen tests exercise lists, sharing, weights and claims without Supabase or a
// server. It keeps the API's rules that a screen can observe: owner-only lists,
// share tokens that are replaced, an append-only weights history, one live claim
// per site, the photos a claim needs before it is done, names and reports kept
// to the claimer until then, and a restored site's three follow-up visits.

import type { ReactNode } from 'react'
import { AccountContext, type Account, type Session } from '../account'
import {
  ApiError,
  type ClaimDetail,
  type ClaimSummary,
  type ClubWeights,
  type FollowUp,
  type ListDetail,
  type RemediationApi,
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
const HOLDING = ['claimed', 'in_progress']

/** The day after Labor Day, as the schema's _day_after_labor_day works it out. */
export function dayAfterLaborDay(year: number): string {
  const first = new Date(Date.UTC(year, 8, 1))
  const monday = 1 + ((8 - first.getUTCDay()) % 7)
  return new Date(Date.UTC(year, 8, monday + 1)).toISOString().slice(0, 10)
}

export type FakeApi = RemediationApi & {
  calls: string[]
  /** A restoration someone else finished, with its photos and its three
   *  follow-up visits; `openNow` opens the first today. */
  seedDoneByOther(rimsId: string, name?: string, openNow?: boolean): Promise<string>
  /** A claim someone else is working on, photos taken, not yet done. */
  seedWorkedByOther(rimsId: string, name?: string): Promise<string>
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
  const visits = new Map<string, Omit<FollowUp, 'state'> & { done_claim_id: string }>()
  const followUpOf = new Map<string, string>()
  const today = () => now().slice(0, 10)
  // The remediation schema's open_follow_ups state.
  const visitState = (f: Omit<FollowUp, 'state'>): FollowUp['state'] => {
    const taken = [...claims.values()].filter((c) => followUpOf.get(c.id) === f.id)
    if (taken.some((c) => c.state === 'done')) return 'done'
    if (taken.some((c) => HOLDING.includes(c.state))) return 'taken'
    if (today() < f.opens_on) return 'waiting'
    if (today() < f.closes_on) return 'open'
    return 'missed'
  }
  const schedule = (claim: ClaimDetail, openNow = false) => {
    let first = Number(claim.done_at!.slice(0, 4))
    if (dayAfterLaborDay(first) <= claim.done_at!.slice(0, 10)) first += 1
    for (const visit of [1, 2, 3]) {
      const id = `visit-${nextId++}`
      const opensOn =
        openNow && visit === 1 ? today() : dayAfterLaborDay(first + visit - 1)
      visits.set(id, {
        id,
        rims_id: claim.rims_id,
        done_claim_id: claim.id,
        visit,
        opens_on: opensOn,
        closes_on: dayAfterLaborDay(first + visit),
      })
    }
  }
  const summary = (claim: ClaimDetail): ClaimSummary => ({
    id: claim.id,
    rims_id: claim.rims_id,
    kind: claim.kind,
    visit: claim.visit,
    state: claim.state,
    claimed_at: claim.claimed_at,
    due_at: claim.due_at,
    done_at: claim.done_at,
    // The remediation schema's rule: the claimer's name is theirs until the
    // work is done (decided 2026-10-27, kept 2026-10-28).
    claimer: claim.yours || claim.state === 'done' ? claim.claimer : null,
    yours: claim.yours,
  })
  // The remediation schema's _claim_detail: all of it for the claimer and once
  // done; for anyone else what the open views show.
  const detail = (claim: ClaimDetail): ClaimDetail => {
    const full = claim.yours || claim.state === 'done'
    const visit = visits.get(followUpOf.get(claim.id) ?? '')
    const restoration = visit ? claims.get(visit.done_claim_id) : undefined
    return {
      ...claim,
      ...summary(claim),
      full,
      photos: full ? [...claim.photos] : [],
      steps_done: full ? claim.steps_done : [],
      notes: full ? claim.notes : null,
      hours: full ? claim.hours : null,
      reference: restoration ? restoration.photos.filter((p) => p.phase === 'after') : [],
    }
  }
  const findClaim = (id: string) => {
    const claim = claims.get(id)
    if (!claim) throw new ApiError(404, 'No such claim')
    return claim
  }
  const ownClaim = (id: string) => {
    const claim = findClaim(id)
    if (!claim.yours)
      throw new ApiError(403, 'Only the person who claimed this site can do that')
    if (!HOLDING.includes(claim.state)) {
      throw new ApiError(409, 'This claim cannot be changed now')
    }
    return claim
  }
  const newClaim = (
    rimsId: string,
    claimer: string | null,
    yours: boolean,
    visit: number | null = null,
  ): ClaimDetail => {
    const claimed = Date.parse(now())
    return {
      id: `claim-${nextId++}`,
      rims_id: rimsId,
      kind: visit === null ? 'restore' : 'follow_up',
      visit,
      state: 'claimed',
      claimed_at: new Date(claimed).toISOString(),
      due_at: new Date(claimed + 14 * DAY_MS).toISOString(),
      done_at: null,
      claimer,
      yours,
      started_at: null,
      released_at: null,
      steps_done: [],
      notes: null,
      hours: null,
      photos: [],
      reference: [],
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
    async seedWorkedByOther(rimsId, name = 'Another volunteer') {
      const id = await this.seedDoneByOther(rimsId, name)
      const claim = findClaim(id)
      claim.state = 'in_progress'
      claim.done_at = null
      for (const [visitId, visit] of visits)
        if (visit.done_claim_id === id) visits.delete(visitId)
      return id
    },
    async seedDoneByOther(rimsId, name = 'Another volunteer', openNow = false) {
      const claim = newClaim(rimsId, name, false)
      claim.state = 'done'
      claim.started_at = now()
      claim.done_at = now()
      claim.steps_done = ['Hide the site', 'Block the way in']
      claim.notes =
        'Two big logs across the pad, and the side path is blocked at the trail.'
      claim.hours = 3
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
      schedule(claim, openNow)
      return claim.id
    },
    async claimSites(rimsIds) {
      const held = rimsIds.filter((r) =>
        [...claims.values()].some((c) => c.rims_id === r && HOLDING.includes(c.state)),
      )
      if (held.length) throw new ApiError(409, `Already claimed: ${held.join(', ')}`)
      const restored = rimsIds.filter((r) =>
        [...visits.values()].some((v) => v.rims_id === r && v.closes_on > today()),
      )
      if (restored.length)
        throw new ApiError(
          409,
          `Restored already, and waiting for its follow-up visits: ${restored.join(', ')}`,
        )
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
      return [...claims.values()].filter((c) => c.yours).map(summary)
    },
    async claim(id) {
      return detail(findClaim(id))
    },
    async releaseClaim(id) {
      const claim = ownClaim(id)
      claim.state = 'released'
      claim.released_at = now()
      return detail(claim)
    },
    async followUps(rimsId) {
      const latest = [...claims.values()]
        .filter((c) => c.rims_id === rimsId && c.state === 'done' && c.kind === 'restore')
        .sort((a, b) => (a.done_at! < b.done_at! ? 1 : -1))[0]
      return [...visits.values()]
        .filter((v) => latest && v.done_claim_id === latest.id)
        .sort((a, b) => a.visit - b.visit)
        .map((v) => ({
          id: v.id,
          rims_id: v.rims_id,
          done_claim_id: v.done_claim_id,
          visit: v.visit,
          opens_on: v.opens_on,
          closes_on: v.closes_on,
          state: visitState(v),
        }))
    },
    async takeFollowUp(id) {
      const visit = visits.get(id)
      if (!visit) throw new ApiError(404, 'No such follow-up visit')
      const state = visitState(visit)
      if (state !== 'open') throw new ApiError(409, `This visit is ${state}`)
      const claim = newClaim(visit.rims_id, displayName, true, visit.visit)
      claims.set(claim.id, claim)
      followUpOf.set(claim.id, id)
      calls.push(`take follow-up ${visit.visit}`)
      return summary(claim)
    },
    async uploadPhoto(id, phase, point, photo, { clientId, replaces } = {}) {
      // As the API does: a photo received under this id before is not stored
      // again, and a queued photo is not put over a slot that changed since.
      if (clientId && clientIds.has(`${id}/${clientId}`)) return detail(findClaim(id))
      const claim = ownClaim(id)
      if (phase === 'before' && claim.kind === 'follow_up')
        throw new ApiError(
          422,
          'A follow-up visit takes the after photos again, not before photos',
        )
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
      if (
        claim.state === 'claimed' &&
        (phase === 'before' || claim.kind === 'follow_up')
      ) {
        claim.state = 'in_progress'
        claim.started_at = now()
      }
      calls.push(`photo ${phase} ${point ?? 'extra'} ${photo.type}`)
      return detail(claim)
    },
    async deletePhoto(id, photoId) {
      const claim = ownClaim(id)
      claim.photos = claim.photos.filter((p) => p.id !== photoId)
      return detail(claim)
    },
    async logHours(id, hours) {
      const claim = ownClaim(id)
      claim.hours = hours
      return detail(claim)
    },
    async finish(id, stepsDone, notes) {
      const claim = ownClaim(id)
      const have = new Set(claim.photos.map((p) => `${p.phase} ${p.point}`))
      const phases = claim.kind === 'follow_up' ? ['after'] : ['before', 'after']
      const missing = [1, 2]
        .flatMap((point) => phases.map((phase) => `${phase} ${point}`))
        .filter((k) => !have.has(k))
      if (missing.length)
        throw new ApiError(422, `Still needed before it is done: ${missing.join(', ')}`)
      claim.state = 'done'
      claim.done_at = now()
      claim.steps_done = stepsDone
      claim.notes = notes
      if (claim.kind === 'restore') schedule(claim)
      return detail(claim)
    },
    async myHours() {
      const mine = [...claims.values()].filter((c) => c.yours)
      return {
        done: mine
          .filter((c) => c.state === 'done')
          .reduce((t, c) => t + (c.hours ?? 0), 0),
        in_progress: mine
          .filter((c) => HOLDING.includes(c.state))
          .reduce((t, c) => t + (c.hours ?? 0), 0),
        claims: mine.filter((c) => c.state === 'done').length,
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
  api: RemediationApi | null = null,
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
