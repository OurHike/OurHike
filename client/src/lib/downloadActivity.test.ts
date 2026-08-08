import { describe, it, expect } from 'vitest'
import { activeDownload, downloadPercent } from './downloadActivity'
import type { DownloadStatus } from '../screens/DownloadCard'

// The question the footer link asks: is anything happening right now, and how
// far along is it. What is worth asserting here is that "nothing" and
// "something" are told apart correctly - a bar over a download that has
// stopped is a phone claiming to be working, and silence over one that is
// running is the whole defect this exists to fix.

const DOWNLOADING: DownloadStatus = {
  state: 'downloading',
  receivedBytes: 40,
  totalBytes: 100,
}
const CHECKING: DownloadStatus = { state: 'checking', checkedBytes: 25, totalBytes: 100 }

describe('activeDownload', () => {
  it('reports nothing when nothing is moving', () => {
    expect(activeDownload([])).toBeNull()
    expect(activeDownload([{ state: 'not-downloaded' }])).toBeNull()
    expect(
      activeDownload([{ state: 'downloaded', totalBytes: 100, completedAt: new Date() }]),
    ).toBeNull()
  })

  it('reports a transfer, with what is here against what is owed', () => {
    expect(activeDownload([DOWNLOADING])).toEqual({
      kind: 'downloading',
      doneBytes: 40,
      totalBytes: 100,
    })
  })

  it('says nothing about a download that has STOPPED', () => {
    // "Stopped at 40 MB of 100" is the card's sentence, and it is not this
    // one. A bar in the footer over a failed transfer would tell a hiker the
    // phone is still working on something it has given up on - and the tap
    // that would fix it is the one they would not make.
    expect(
      activeDownload([{ state: 'failed', receivedBytes: 40, totalBytes: 100 }]),
    ).toBeNull()
    expect(activeDownload([{ state: 'hash-mismatch' }])).toBeNull()
    expect(activeDownload([{ state: 'evicted', completedAt: null }])).toBeNull()
  })

  it('reports the phone reading its own disk as its own kind of wait', () => {
    // #197's distinction, carried to the footer: checking looks exactly like a
    // stalled transfer and asks the opposite thing of someone in a dead spot.
    expect(activeDownload([CHECKING])).toEqual({
      kind: 'checking',
      doneBytes: 25,
      totalBytes: 100,
    })
  })

  it('lets a live transfer outrank a check', () => {
    // lib/backgroundStatus.ts's precedence, for its reason: one figure in a
    // footer, and the one spending signal is the one worth the room.
    expect(activeDownload([CHECKING, DOWNLOADING])?.kind).toBe('downloading')
  })

  it('sums the sheets that are moving and ignores the ones that are not', () => {
    // A hiker downloading two sheets is waiting on both, and two bars in a
    // footer is a footer nobody reads. The resting sheet contributes nothing:
    // counting a map somebody is not downloading towards a total would put the
    // bar at a figure no transfer is working towards.
    expect(
      activeDownload([
        DOWNLOADING,
        { state: 'downloading', receivedBytes: 10, totalBytes: 300 },
        { state: 'not-downloaded' },
      ]),
    ).toEqual({ kind: 'downloading', doneBytes: 50, totalBytes: 400 })
  })

  it('counts a finished piece of a sheet that is still arriving', () => {
    // Not this module's doing - lib/backgroundStatus.ts has already folded the
    // archives of one sheet into one figure, which is exactly why this is fed
    // sheet statuses and not archives. Asserted anyway, because the property
    // it buys is the visible one: a bar that never travels backwards when a
    // piece of a multi-archive sheet completes.
    expect(
      activeDownload([{ state: 'downloading', receivedBytes: 700, totalBytes: 1000 }]),
    ).toEqual({ kind: 'downloading', doneBytes: 700, totalBytes: 1000 })
  })
})

describe('downloadPercent', () => {
  it('rounds to a whole percent', () => {
    expect(downloadPercent(1, 3)).toBe(33)
    expect(downloadPercent(2, 3)).toBe(67)
  })

  it('calls an undeclared length the start of something, not the end', () => {
    // A server that sent no content-length leaves totalBytes at zero. 0% is
    // true of a transfer that has begun; a division by zero would render
    // "NaN%", and 100% would be a finished download that is not finished.
    expect(downloadPercent(0, 0)).toBe(0)
    expect(downloadPercent(500, 0)).toBe(0)
  })
})
