// Lets pmtiles read the downloaded corridor archive out of IndexedDB.
//
// The archive is one whole-corridor package (WIREFRAMES.md Known Deviations #1
// - not a per-section list), read as byte ranges. Slicing a Blob does not pull
// it into memory, so range reads stay cheap even against the 1.18 GB Fine
// archive.
//
// Where those bytes actually live is lib/archiveStore.ts's business, not this
// file's: since #553 an archive is stored as append-only segment records, and
// `readArchive` assembles them by reference into the same Blob this always
// sliced. That is the whole reason the tile path did not have to change.
//
// This never falls back to the network. OurHike's premise is that the map works
// with no signal at all (TECHNICAL_ARCHITECTURE.md), so a missing archive is a
// real, reportable state - not something to paper over with empty bytes, which
// would render a convincingly blank map and hide the actual problem.

import type { RangeResponse, Source } from 'pmtiles'
import { readArchive } from '../lib/archiveStore'

export const CORRIDOR_ARCHIVE_KEY = 'ourhike:corridor-archive'

export class ArchiveNotDownloadedError extends Error {
  constructor(key: string) {
    super(
      `No offline map archive found in IndexedDB under "${key}". ` +
        `Download the corridor package before rendering the map.`,
    )
    this.name = 'ArchiveNotDownloadedError'
  }
}

export class IndexedDbArchiveSource implements Source {
  private handle: Promise<Blob> | null = null
  private readonly key: string

  constructor(key: string = CORRIDOR_ARCHIVE_KEY) {
    this.key = key
  }

  getKey(): string {
    return this.key
  }

  async getBytes(offset: number, length: number): Promise<RangeResponse> {
    const blob = await this.archive()
    const slice = blob.slice(offset, offset + length)

    return { data: await slice.arrayBuffer() }
  }

  private archive(): Promise<Blob> {
    if (this.handle !== null) return this.handle

    this.handle = readArchive(this.key)
      .then((stored) => {
        if (!(stored instanceof Blob)) throw new ArchiveNotDownloadedError(this.key)
        return stored
      })
      .catch((error: unknown) => {
        // Never memoise a failure. The usual reason to land here is that the
        // download simply hasn't finished yet, and a read after it completes
        // has to be able to succeed - caching the rejected promise would keep
        // the map broken for the rest of the session.
        this.handle = null
        throw error
      })

    return this.handle
  }
}
