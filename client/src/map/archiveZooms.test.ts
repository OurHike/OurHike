import { describe, it, expect, vi, beforeEach } from 'vitest'
import { readArchiveZooms } from './archiveZooms'

// The client used to have no idea what the archive on the phone contained -
// it pointed a raster source at it and hoped, which is how #216 survived. What
// matters here is that not knowing is reported as not knowing, never as an
// absence of coverage.

const getHeader = vi.fn()

vi.mock('pmtiles', () => ({
  PMTiles: class {
    getHeader() {
      return getHeader()
    }
  },
}))

beforeEach(() => {
  getHeader.mockReset()
})

describe('readArchiveZooms', () => {
  it('reports the range the archive declares', async () => {
    getHeader.mockResolvedValue({ minZoom: 6, maxZoom: 12 })

    expect(await readArchiveZooms('ourhike:corridor-archive')).toEqual({
      minZoom: 6,
      maxZoom: 12,
    })
  })

  it('reports null rather than a guess when the archive is not there', async () => {
    // IndexedDbArchiveSource throws ArchiveNotDownloadedError on a missing
    // key. Answering "minZoom 0" here would be an invented fact, and callers
    // would use it to claim the download covers ground it does not.
    getHeader.mockRejectedValue(new Error('No offline map archive found'))

    expect(await readArchiveZooms('ourhike:corridor-archive')).toBeNull()
  })

  it('reports null on a header too damaged to parse, rather than throwing', async () => {
    // This runs on app start, off the back of a download that may have been
    // interrupted (#197). An unhandled rejection here would be a broken app
    // rather than a map with one fewer refinement.
    getHeader.mockRejectedValue(new SyntaxError('bad magic number'))

    expect(await readArchiveZooms('ourhike:corridor-archive')).toBeNull()
  })
})
