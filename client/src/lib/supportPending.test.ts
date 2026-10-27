import { beforeEach, describe, expect, it } from 'vitest'
import {
  PENDING_TIER_MAX_AGE_MS,
  holdPendingSupportTier,
  takePendingSupportTier,
} from './supportPending'

// The paid tier held across a sign-in round trip (#1876).

beforeEach(() => sessionStorage.clear())

describe('the tier held across sign-in', () => {
  it('comes back once, after the round trip', () => {
    holdPendingSupportTier(6000, 0)
    expect(takePendingSupportTier(60_000)).toBe(6000)
    expect(takePendingSupportTier(60_000)).toBeNull()
  })

  it('is forgotten once stale, so a later unrelated sign-in is not hijacked', () => {
    holdPendingSupportTier(12000, 0)
    expect(takePendingSupportTier(PENDING_TIER_MAX_AGE_MS + 1)).toBeNull()
  })

  it('reads anything that is not one of the three tiers as nothing held', () => {
    sessionStorage.setItem('ourhike:support-pending', '{"tier":500,"at":0}')
    expect(takePendingSupportTier(1)).toBeNull()
  })
})
