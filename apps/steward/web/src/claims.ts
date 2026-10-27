// Small pure pieces of the claim screens (#1910), kept apart so they are tested
// without rendering anything.

import type { ClaimDetail, ClaimState } from './api'

const DAY_MS = 24 * 60 * 60 * 1000

export const STATE_LABEL: Record<ClaimState, string> = {
  claimed: 'Claimed',
  in_progress: 'In progress',
  submitted: 'Waiting for review',
  verified: 'Verified',
  released: 'Released',
}

/** Whole days left before the claim is released, rounded up: 13.2 days is 14. */
export function daysLeft(dueAt: string, now: number = Date.now()): number {
  return Math.max(0, Math.ceil((Date.parse(dueAt) - now) / DAY_MS))
}

/**
 * The in-app reminder PLAN.md §6 puts on days 10 and 13 of 14, by days left:
 * from day 10 on (4 left) a nudge, and from day 13 on (1 left) a warning. Email
 * reminders need an email provider, which is not set up (#1910).
 */
export function reminder(
  dueAt: string,
  now: number = Date.now(),
): 'warning' | 'nudge' | null {
  const left = daysLeft(dueAt, now)
  if (left <= 1) return 'warning'
  if (left <= 4) return 'nudge'
  return null
}

export const PHOTO_POINTS = [1, 2] as const

/** The photo at a point, counting an after photo only if it was taken since
 *  the last send-back, as the API does: a crew sent back must retake its afters. */
export function photoAt(claim: ClaimDetail, phase: 'before' | 'after', point: number) {
  return (
    claim.photos.find(
      (p) =>
        p.phase === phase &&
        p.point === point &&
        !(phase === 'after' && claim.sent_back_at && p.created_at <= claim.sent_back_at),
    ) ?? null
  )
}

/** The photos a submission still needs, in words. */
export function missingPhotos(claim: ClaimDetail): string[] {
  return PHOTO_POINTS.flatMap((point) =>
    (['before', 'after'] as const)
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
    const raw = window.localStorage.getItem(`steward.before-you-go.${claimId}`)
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
    window.localStorage.setItem(`steward.before-you-go.${claimId}`, JSON.stringify(ticks))
  } catch {
    // Not kept; the ticks still hold for this visit.
  }
}
