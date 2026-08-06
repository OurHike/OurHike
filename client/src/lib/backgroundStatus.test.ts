import { describe, it, expect } from 'vitest'
import { combineBackgroundStatus, type ArchiveState } from './backgroundStatus'

// The background is one thing to a hiker and several archives in the store
// (#192), and this is where the two meet. What matters in every case below is
// that the sentence the screen ends up showing is TRUE of the whole
// background - not of whichever archive happened to be first.

const MB = 1_000_000

const absent = (sizeBytes: number): ArchiveState => ({
  status: { state: 'not-downloaded' },
  sizeBytes,
})

const done = (sizeBytes: number, completedAt = new Date('2026-08-01T08:00:00Z')) => ({
  status: { state: 'downloaded' as const, totalBytes: sizeBytes, completedAt },
  sizeBytes,
})

const transferring = (received: number, sizeBytes: number): ArchiveState => ({
  status: { state: 'downloading', receivedBytes: received, totalBytes: sizeBytes },
  sizeBytes,
})

const stopped = (received: number, sizeBytes: number): ArchiveState => ({
  status: { state: 'failed', receivedBytes: received, totalBytes: sizeBytes },
  sizeBytes,
})

const evicted = (
  sizeBytes: number,
  completedAt: Date | null = new Date('2026-07-20T08:00:00Z'),
): ArchiveState => ({
  status: { state: 'evicted', completedAt },
  sizeBytes,
})

describe('one archive', () => {
  it('is handed straight back, which is every case the shipped app has', () => {
    // Only the raster sheet is published today (#185/#186 are the other two),
    // so the app always combines exactly one status.
    const only = stopped(100 * MB, 314 * MB)

    expect(combineBackgroundStatus([only])).toEqual(only.status)
  })

  it('says nothing is downloaded when there is nothing to combine', () => {
    expect(combineBackgroundStatus([])).toEqual({ state: 'not-downloaded' })
  })
})

describe('several archives, one answer', () => {
  it('adds up a transfer across all of them', () => {
    const combined = combineBackgroundStatus([
      transferring(100 * MB, 314 * MB),
      absent(480 * MB),
    ])

    // The untouched archive contributes its published size to the total, so
    // the figure does not grow as each piece begins - a download that keeps
    // getting bigger reads as one that will never end.
    expect(combined).toEqual({
      state: 'downloading',
      receivedBytes: 100 * MB,
      totalBytes: 794 * MB,
    })
  })

  it('is downloaded only when every archive is', () => {
    const combined = combineBackgroundStatus([done(314 * MB), done(480 * MB)])

    expect(combined).toEqual({
      state: 'downloaded',
      totalBytes: 794 * MB,
      completedAt: new Date('2026-08-01T08:00:00Z'),
    })
  })

  it('dates a finished background by the last piece to land', () => {
    const combined = combineBackgroundStatus([
      done(314 * MB, new Date('2026-07-01T08:00:00Z')),
      done(480 * MB, new Date('2026-08-01T08:00:00Z')),
    ])

    expect(combined).toMatchObject({ completedAt: new Date('2026-08-01T08:00:00Z') })
  })

  it('offers to carry on when one archive finished and another never started', () => {
    // Not "downloaded" - that would promise terrain a hiker does not have -
    // and not "not downloaded", which would offer to re-fetch bytes already
    // on the phone. Partly here, and resumable, is the true answer.
    const combined = combineBackgroundStatus([done(314 * MB), absent(480 * MB)])

    expect(combined).toEqual({
      state: 'failed',
      receivedBytes: 314 * MB,
      totalBytes: 794 * MB,
    })
  })

  it('counts what is really here when one archive stopped partway', () => {
    const combined = combineBackgroundStatus([
      done(314 * MB),
      stopped(100 * MB, 480 * MB),
    ])

    expect(combined).toEqual({
      state: 'failed',
      receivedBytes: 414 * MB,
      totalBytes: 794 * MB,
    })
  })

  it('is not downloaded when none of it is here', () => {
    expect(combineBackgroundStatus([absent(314 * MB), absent(480 * MB)])).toEqual({
      state: 'not-downloaded',
    })
  })
})

describe('precedence, ordered by what a hiker needs to know', () => {
  it('reports a live transfer over everything else', () => {
    const combined = combineBackgroundStatus([
      evicted(314 * MB),
      transferring(50 * MB, 480 * MB),
    ])

    expect(combined.state).toBe('downloading')
  })

  it('says the phone removed part of the map before saying part is missing', () => {
    // #190's sentence explains WHY something is gone, and "some of it is
    // missing" does not. A hiker who is told only the second re-downloads
    // and watches it vanish again.
    const combined = combineBackgroundStatus([evicted(314 * MB), done(480 * MB)])

    expect(combined).toEqual({
      state: 'evicted',
      completedAt: new Date('2026-08-01T08:00:00Z'),
    })
  })

  it('still says it when the completion date did not survive', () => {
    const combined = combineBackgroundStatus([evicted(314 * MB, null), absent(480 * MB)])

    expect(combined).toEqual({ state: 'evicted', completedAt: null })
  })
})

describe('checking bytes already held (#197)', () => {
  const checking = (checkedBytes: number, totalBytes: number): ArchiveState => ({
    status: { state: 'checking', checkedBytes, totalBytes },
    sizeBytes: totalBytes,
  })

  it('reports the check when that is what the phone is doing', () => {
    const combined = combineBackgroundStatus([checking(40 * MB, 100 * MB)])

    expect(combined).toEqual({
      state: 'checking',
      checkedBytes: 40 * MB,
      totalBytes: 100 * MB,
    })
  })

  it('adds up only the archives actually being checked', () => {
    const combined = combineBackgroundStatus([
      checking(40 * MB, 100 * MB),
      checking(10 * MB, 50 * MB),
      absent(200 * MB),
    ])

    expect(combined).toEqual({
      state: 'checking',
      checkedBytes: 50 * MB,
      totalBytes: 150 * MB,
    })
  })

  it('yields to a live transfer, which is the more informative figure', () => {
    const combined = combineBackgroundStatus([
      checking(40 * MB, 100 * MB),
      transferring(10 * MB, 200 * MB),
    ])

    expect(combined.state).toBe('downloading')
  })

  it('outranks a resting state - the phone is already busy doing the thing', () => {
    // Offering "Resume" underneath a check invites a second tap on work
    // that is already under way.
    expect(
      combineBackgroundStatus([checking(1 * MB, 10 * MB), stopped(5 * MB, 50 * MB)])
        .state,
    ).toBe('checking')
    expect(
      combineBackgroundStatus([checking(1 * MB, 10 * MB), evicted(50 * MB)]).state,
    ).toBe('checking')
  })
})

describe('a refused archive, kept out of the Resume slot (#238)', () => {
  const refused = (sizeBytes: number): ArchiveState => ({
    status: { state: 'hash-mismatch' },
    sizeBytes,
  })

  const checking = (checkedBytes: number, totalBytes: number): ArchiveState => ({
    status: { state: 'checking', checkedBytes, totalBytes },
    sizeBytes: totalBytes,
  })

  it('is handed straight back alone', () => {
    expect(combineBackgroundStatus([refused(314 * MB)])).toEqual({
      state: 'hash-mismatch',
    })
  })

  it('outranks a downloaded sibling - "Stopped at X of Y" would be false of it', () => {
    // Before this state existed, a mismatched archive read as absent and the
    // combine offered Resume beside finished siblings: a promise to carry on
    // from bytes that were deliberately not kept.
    const combined = combineBackgroundStatus([refused(480 * MB), done(314 * MB)])

    expect(combined).toEqual({ state: 'hash-mismatch' })
  })

  it('outranks an eviction, which explains an older loss than this one', () => {
    expect(combineBackgroundStatus([refused(480 * MB), evicted(314 * MB)]).state).toBe(
      'hash-mismatch',
    )
  })

  it('yields to a live transfer and to checking - work in progress wins', () => {
    expect(
      combineBackgroundStatus([refused(480 * MB), transferring(10 * MB, 314 * MB)]).state,
    ).toBe('downloading')
    expect(
      combineBackgroundStatus([refused(480 * MB), checking(1 * MB, 314 * MB)]).state,
    ).toBe('checking')
  })

  it('owes its whole published size to a combined transfer total', () => {
    // Nothing was kept, so its contribution is an absent archive's: zero
    // received, full size still to come.
    const combined = combineBackgroundStatus([
      transferring(100 * MB, 314 * MB),
      refused(480 * MB),
    ])

    expect(combined).toEqual({
      state: 'downloading',
      receivedBytes: 100 * MB,
      totalBytes: 794 * MB,
    })
  })
})
