import { describe, it, expect, vi, beforeEach } from 'vitest'
import { get, set } from 'idb-keyval'
import { beginContribution, stepAfterSaving, REPORTER_TYPES } from './contributionFlow'
import { listQueued } from './outbox'

// WIREFRAMES.md §6: "Sign-in happens at the first contribution, not in
// onboarding. The report is written and saved first; then Google / Apple /
// email, then trail name + reporter type."
//
// "Written and saved FIRST" is the whole design, not a sequencing detail.
// Someone standing at a blowdown with one bar of signal, who is then asked to
// authenticate with Google, can very easily end up with neither an account
// nor their report. Saving to the outbox before authentication is ever
// mentioned means the worst case is an unsent report rather than a lost one.
//
// TESTING.md item 12 asks for exactly this: the report survives the sign-in
// detour intact, with the authoring time rather than the send time.

vi.mock('idb-keyval', () => ({ get: vi.fn(), set: vi.fn() }))

const mockedGet = vi.mocked(get)
const mockedSet = vi.mocked(set)

function withStore() {
  let stored: unknown[] = []
  mockedGet.mockImplementation(async () => stored)
  mockedSet.mockImplementation(async (_k, v) => {
    stored = v as unknown[]
  })
  return () => stored
}

const DRAFT = {
  type: 'blowdown' as const,
  reporter_type: 'thru' as const,
  note: 'Tree across the trail.',
  lat: 35.6,
  lon: -83.5,
}

const WRITTEN_AT = new Date('2026-07-27T08:00:00Z')

beforeEach(() => {
  vi.clearAllMocks()
})

describe('beginContribution', () => {
  it('saves the report before anything else happens', async () => {
    const read = withStore()

    await beginContribution(DRAFT, WRITTEN_AT)

    expect(read()).toHaveLength(1)
  })

  it('saves it with the time it was written, not the time it will send', async () => {
    withStore()

    await beginContribution(DRAFT, WRITTEN_AT)
    const [queued] = await listQueued()

    expect(queued.authoredAt).toBe(WRITTEN_AT.toISOString())
  })

  it('saves even when the contributor has no account at all', async () => {
    // The case that matters: no account is exactly when the detour happens,
    // and exactly when a report is easiest to lose.
    const read = withStore()

    await beginContribution(DRAFT, WRITTEN_AT)

    expect(read()).toHaveLength(1)
  })

  it('hands back the queued item so the flow can find it again afterwards', async () => {
    withStore()

    const item = await beginContribution(DRAFT, WRITTEN_AT)
    const [queued] = await listQueued()

    expect(item.id).toBe(queued.id)
  })

  it('leaves the report intact across a sign-in detour', async () => {
    withStore()

    const item = await beginContribution(DRAFT, WRITTEN_AT)
    // ...user goes off to Google, comes back...
    const [afterAuth] = await listQueued()

    expect(afterAuth.id).toBe(item.id)
    expect(afterAuth.payload).toEqual(DRAFT)
    expect(afterAuth.authoredAt).toBe(WRITTEN_AT.toISOString())
  })
})

describe('stepAfterSaving', () => {
  it('asks for sign-in when there is no account', () => {
    expect(stepAfterSaving({ hasAccount: false, hasIdentity: false })).toBe('sign-in')
  })

  it('asks for a trail name once signed in but not yet introduced', () => {
    expect(stepAfterSaving({ hasAccount: true, hasIdentity: false })).toBe('identity')
  })

  it('goes straight to sending for a returning contributor', () => {
    expect(stepAfterSaving({ hasAccount: true, hasIdentity: true })).toBe('send')
  })

  it('never asks for identity before an account exists', () => {
    // Ordering matters: trail name belongs to a profile, so asking for it
    // first would mean collecting something with nowhere to put it.
    expect(stepAfterSaving({ hasAccount: false, hasIdentity: true })).toBe('sign-in')
  })
})

describe('REPORTER_TYPES', () => {
  it('offers exactly the four the docs name', () => {
    expect(REPORTER_TYPES.map((r) => r.id)).toEqual([
      'thru',
      'section',
      'day',
      'maintainer',
    ])
  })

  it('marks maintainer as club-granted rather than self-declared', () => {
    // WIREFRAMES.md: "maintainer is club-granted and stays unverified until
    // confirmed." Anyone may claim it; it just does not mean anything until a
    // club says so, which is what keeps it from being a self-assigned badge.
    const maintainer = REPORTER_TYPES.find((r) => r.id === 'maintainer')

    expect(maintainer?.clubGranted).toBe(true)
  })

  it('leaves the three hiker types self-declared, needing nobody’s approval', () => {
    const hikers = REPORTER_TYPES.filter((r) => r.id !== 'maintainer')

    expect(hikers.every((r) => r.clubGranted === false)).toBe(true)
  })
})
