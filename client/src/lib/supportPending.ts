// A paid tier picked while signed out, held across the sign-in round trip
// (#1876). Google and Apple sign-in navigate away from the app and back, so
// React state does not survive it; sessionStorage does, and dies with the
// tab, which is the right lifetime for "I was in the middle of choosing".
//
// WITH A SHELF LIFE, because a hiker who opened sign-in from the ask and then
// backed out leaves the tier behind, and the next sign-in - for a report, an
// hour later - would otherwise land them on a support confirmation they did
// not ask for. @unvalidated: thirty minutes is comfortably longer than any
// sign-in round trip and much shorter than the gap before an unrelated one;
// nobody has measured either.

import { TIERS, type PaidTier } from './support'

const KEY = 'ourhike:support-pending'
export const PENDING_TIER_MAX_AGE_MS = 30 * 60 * 1000

export function holdPendingSupportTier(tier: PaidTier, now: number = Date.now()): void {
  try {
    sessionStorage.setItem(KEY, JSON.stringify({ tier, at: now }))
  } catch {
    // Refused: back from sign-in, the ask opens at the top instead.
  }
}

/** The held tier, removed as it is read, or null when absent or stale. */
export function takePendingSupportTier(now: number = Date.now()): PaidTier | null {
  try {
    const raw = sessionStorage.getItem(KEY)
    sessionStorage.removeItem(KEY)
    if (raw === null) return null
    const parsed: unknown = JSON.parse(raw)
    if (typeof parsed !== 'object' || parsed === null) return null
    const { tier, at } = parsed as { tier?: unknown; at?: unknown }
    if (typeof at !== 'number' || now - at > PENDING_TIER_MAX_AGE_MS) return null
    return (TIERS as readonly unknown[]).includes(tier) ? (tier as PaidTier) : null
  } catch {
    return null
  }
}
