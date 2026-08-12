// The server half of the storage probe: streams an arbitrary number of
// deterministic, incompressible bytes under a name that carries the size, with
// the ETag, Range and latest.json support the real download path expects.
//
// Deterministic so that `latest.json` can publish a real SHA-256 for a size
// nobody has a file of, which is what lets the probe exercise verification -
// the expensive half - rather than skipping it the way an unpublished artifact
// would.

import { createHash } from 'node:crypto'
import type { IncomingMessage, ServerResponse } from 'node:http'
import { defineConfig } from 'vite'

// A deterministic 1 MiB block: sha256-chained so the bytes are incompressible
// and every block differs, which is what a real pmtiles archive looks like to
// the transport.
const BLOCK = 1 << 20

function baseBlock(): Buffer {
  const parts: Buffer[] = []
  let seed = Buffer.from('ourhike-storage-probe')
  while (parts.reduce((n, p) => n + p.length, 0) < BLOCK) {
    seed = createHash('sha256').update(seed).digest()
    parts.push(seed)
  }
  return Buffer.concat(parts).subarray(0, BLOCK)
}

const BASE = baseBlock()

function blockAt(index: number): Buffer {
  const block = Buffer.from(BASE)
  block.writeUInt32BE(index, 0)
  return block
}

function* bytesOf(total: number): Generator<Buffer> {
  let sent = 0
  for (let i = 0; sent < total; i++) {
    const block = blockAt(i)
    const take = Math.min(BLOCK, total - sent)
    sent += take
    yield take === BLOCK ? block : block.subarray(0, take)
  }
}

const digests = new Map<number, string>()
function digestOf(total: number): string {
  const cached = digests.get(total)
  if (cached !== undefined) return cached
  const hash = createHash('sha256')
  for (const chunk of bytesOf(total)) hash.update(chunk)
  const hex = hash.digest('hex')
  digests.set(total, hex)
  return hex
}

/** Artifact name -> size, as latest.json would carry it. */
const ARTIFACTS: Record<string, number> = {}

function sizeFor(name: string): number | null {
  const match = /^probe_(\d+)\.pmtiles$/.exec(name)
  if (match === null) return null
  const size = Number(match[1])
  ARTIFACTS[name] = size
  return size
}

export default defineConfig({
  // No fixed port: run.mjs reads whatever this listens on, so two probes can
  // run side by side and neither fails on a port somebody else has.
  plugins: [
    {
      name: 'repro-data-server',
      configureServer(server) {
        server.middlewares.use('/data', (req: IncomingMessage, res: ServerResponse) => {
          const url = new URL(req.url ?? '/', 'http://localhost')
          const name = url.pathname.replace(/^\//, '')

          if (name === 'latest.json') {
            // Every size the page might ask for has to be answerable, so the
            // manifest is generated for whatever probe sizes were requested
            // plus the ones named in the query string.
            for (const asked of (url.searchParams.get('sizes') ?? '').split(',')) {
              if (asked !== '') sizeFor(`probe_${asked}.pmtiles`)
            }
            const artifacts = Object.fromEntries(
              Object.entries(ARTIFACTS).map(([key, size]) => [
                key,
                { sha256: digestOf(size) },
              ]),
            )
            res.setHeader('content-type', 'application/json')
            res.end(JSON.stringify({ version: 'repro', artifacts }))
            return
          }

          const total = sizeFor(name)
          if (total === null) {
            res.statusCode = 404
            res.end('no such artifact')
            return
          }

          // Range support, so the resume path is exercisable too.
          const range = /^bytes=(\d+)-(\d*)$/.exec(req.headers.range ?? '')
          const from = range === null ? 0 : Number(range[1])
          const to = range === null || range[2] === '' ? total - 1 : Number(range[2])

          if (from >= total) {
            res.statusCode = 416
            res.setHeader('content-range', `bytes */${total}`)
            res.end()
            return
          }

          res.setHeader('etag', `"probe-${total}"`)
          res.setHeader('content-type', 'application/octet-stream')
          res.setHeader('accept-ranges', 'bytes')
          res.setHeader('content-length', String(to - from + 1))
          if (range !== null) {
            res.statusCode = 206
            res.setHeader('content-range', `bytes ${from}-${to}/${total}`)
          }

          const wanted = to - from + 1
          let blockIndex = Math.floor(from / BLOCK)
          let skip = from % BLOCK
          let written = 0
          // Backpressure-aware streaming: the whole point is to look like a
          // real transfer to the page.
          const pump = () => {
            while (written < wanted) {
              const block = blockAt(blockIndex)
              const end = Math.min(block.length, skip + (wanted - written))
              const piece = block.subarray(skip, end)
              written += piece.length
              if (end >= block.length) {
                blockIndex += 1
                skip = 0
              } else {
                skip = end
              }
              if (!res.write(piece)) {
                res.once('drain', pump)
                return
              }
            }
            res.end()
          }
          pump()
        })
      },
    },
  ],
})
