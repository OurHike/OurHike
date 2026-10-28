// Small pure pieces of the claim screens (#1910), kept apart so they are tested
// without rendering anything.

import type { ClaimDetail, ClaimState, FollowUpState } from './api'

const DAY_MS = 24 * 60 * 60 * 1000

export const STATE_LABEL: Record<ClaimState, string> = {
  claimed: 'Claimed',
  in_progress: 'In progress',
  done: 'Done',
  released: 'Released',
}

export const FOLLOW_UP_LABEL: Record<FollowUpState, string> = {
  waiting: 'Not open yet',
  open: 'Open to take',
  taken: 'Someone is on it',
  done: 'Done',
  missed: 'Missed',
}

/** Whole days left before the claim is released, rounded up: 13.2 days is 14. */
export function daysLeft(dueAt: string, now: number = Date.now()): number {
  return Math.max(0, Math.ceil((Date.parse(dueAt) - now) / DAY_MS))
}

export const PHOTO_POINTS = [1, 2] as const

/** The photo at a point, or null. */
export function photoAt(claim: ClaimDetail, phase: 'before' | 'after', point: number) {
  return claim.photos.find((p) => p.phase === phase && p.point === point) ?? null
}

/** The phases a claim photographs: before and after for a restoration, the
 *  after again for a follow-up visit (the API's _missing_photos). */
export function phasesOf(claim: Pick<ClaimDetail, 'kind'>): ('before' | 'after')[] {
  return claim.kind === 'follow_up' ? ['after'] : ['before', 'after']
}

/** The photos still needed before the work can be marked done, in words. */
export function missingPhotos(claim: ClaimDetail): string[] {
  return PHOTO_POINTS.flatMap((point) =>
    phasesOf(claim)
      .filter((phase) => photoAt(claim, phase, point) === null)
      .map((phase) => `${phase} photo at point ${point}`),
  )
}

export function isWorking(claim: { state: ClaimState }): boolean {
  return claim.state === 'claimed' || claim.state === 'in_progress'
}

/** The before-you-go ticks, kept on this phone per claim. Storage can be missing
 *  or refuse (a private window); the checklist then simply starts empty. */
export function loadTicks(claimId: string): number[] {
  try {
    const raw = window.localStorage.getItem(`remediation.before-you-go.${claimId}`)
    const parsed: unknown = raw ? JSON.parse(raw) : []
    return Array.isArray(parsed)
      ? parsed.filter((n): n is number => typeof n === 'number')
      : []
  } catch {
    return []
  }
}

export function saveTicks(claimId: string, ticks: number[]): void {
  try {
    window.localStorage.setItem(
      `remediation.before-you-go.${claimId}`,
      JSON.stringify(ticks),
    )
  } catch {
    // Not kept; the ticks still hold for this visit.
  }
}
