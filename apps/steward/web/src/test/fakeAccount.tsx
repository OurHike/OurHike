// An in-memory stand-in for the steward API and the sign-in it sits behind, so
// screen tests exercise lists, sharing and weights without Supabase or a server.
// It keeps the API's rules that a screen can observe: owner-only lists, share
// tokens that are replaced, and an append-only weights history.

import type { ReactNode } from 'react'
import { AccountContext, type Account, type Session } from '../account'
import {
  ApiError,
  type ClubWeights,
  type ListDetail,
  type StewardApi,
  type WeightsEntry,
} from '../api'
import type { Weights } from '../types'

const DEFAULTS: Weights = { deficit: 60, water: 12, trail: 6, cluster: 8, restricted: 10 }

export function fakeApi(): StewardApi & { calls: string[] } {
  const calls: string[] = []
  let displayName: string | null = null
  const lists = new Map<string, ListDetail>()
  const shares = new Map<string, string>()
  const history = new Map<string, WeightsEntry[]>()
  let nextId = 1
  const now = () => new Date('2026-10-27T12:00:00Z').toISOString()
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
