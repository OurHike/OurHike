// Serves a built client same-origin and forwards the data bucket through it,
// so a browser that cannot reach the bucket directly can still read real data.
//
// WHY THIS IS COMMITTED RATHER THAN A SCRATCH FILE. Headless Chromium in the
// agent sandbox cannot reach data.ourhike.org at all — measured 2026-09-11:
// ERR_CONNECTION_RESET on every artifact, while `curl` to the same URL returns
// 200, because the egress proxy is a shell-level thing the browser does not
// use. That makes `e2e/data/` — the flow suite's data-backed half — unrunnable
// here without this, and an unrunnable suite is the "a test nobody runs is a
// comment with a longer syntax" failure the flow job was created to fix. CI
// does not need it: a GitHub runner reaches the bucket directly, and the job
// there points VITE_DATA_BASE_URL straight at it.
//
// SAME-ORIGIN IS THE OTHER HALF. The bucket's CORS allowlist carries vite's
// two default ports and nothing else (scripts/screenshot.mjs's SHOT_HOST
// comment), so a browser on any other port gets silence. Serving the app and
// the data from one origin sidesteps that entirely: the app is built with
// VITE_DATA_BASE_URL=/data/environments/ua and never makes a cross-origin
// request at all.
//
//   npm run build   (with VITE_DATA_BASE_URL=/data/environments/ua)
//   node scripts/data-proxy.mjs dist 8787
//   FLOW_DATA=1 FLOW_DATA_ORIGIN=http://localhost:8787 npx playwright test
//
// It forwards three upstreams, because a map needs more than its own data:
//   /data/*      -> https://data.ourhike.org/*
//   /ofm/*       -> https://tiles.openfreemap.org/*   (TileJSON rewritten)
//   /terrarium/* -> https://s3.amazonaws.com/elevation-tiles-prod/terrarium/*
//
// A DEV TOOL, AND NOT A SERVER. No auth, no caching, one curl per request. It
// binds loopback and is meant to live for the length of a test run.
import http from 'node:http'
import { spawn } from 'node:child_process'
import { readFile, stat } from 'node:fs/promises'
import { join, extname } from 'node:path'

const DIST = process.argv[2]
// Files under OVERRIDE shadow the upstream data: a re-cut tileset the bucket does not have yet.
const OVERRIDE = process.argv[4] ?? null
const PORT = Number(process.argv[3] ?? 8787)
const UPSTREAM = {
  '/data/': 'https://data.ourhike.org/',
  '/ofm/': 'https://tiles.openfreemap.org/',
  '/terrarium/': 'https://s3.amazonaws.com/elevation-tiles-prod/terrarium/',
}
const TYPES = {
  '.html': 'text/html',
  '.js': 'text/javascript',
  '.css': 'text/css',
  '.json': 'application/json',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.pbf': 'application/x-protobuf',
  '.woff2': 'font/woff2',
  '.webmanifest': 'application/manifest+json',
}

import { mkdtempSync, readFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
let seq = 0
function curl(url, range) {
  return new Promise((resolve) => {
    const dir = mkdtempSync(join(tmpdir(), 'rp-'))
    const bodyFile = join(dir, 'body'),
      headFile = join(dir, 'head')
    const args = ['-sS', '-L', '--max-time', '60', '-o', bodyFile, '-D', headFile, url]
    if (range) args.push('-H', `Range: ${range}`)
    const child = spawn('curl', args)
    child.on('close', () => {
      let body = Buffer.alloc(0),
        head = ''
      try {
        body = readFileSync(bodyFile)
      } catch {}
      try {
        head = readFileSync(headFile, 'latin1')
      } catch {}
      rmSync(dir, { recursive: true, force: true })
      // The LAST header block is the final response (the ones before it are
      // the egress proxy's CONNECT answer and any redirect hops).
      const blocks = head
        .split(/\r\n\r\n/)
        .map((b) => b.trim())
        .filter((b) => b.length > 0)
      const last = blocks[blocks.length - 1] ?? 'HTTP/1.1 502 x'
      const lines = last.split(/\r\n/)
      const status = Number((lines[0].match(/^HTTP\/\S+ (\d+)/) ?? [])[1] ?? 502)
      const h = {}
      for (const line of lines.slice(1)) {
        const j = line.indexOf(':')
        if (j > 0) h[line.slice(0, j).toLowerCase()] = line.slice(j + 1).trim()
      }
      resolve({ status, headers: h, body })
    })
  })
}

http
  .createServer(async (req, res) => {
    const url = new URL(req.url, 'http://x')
    if (OVERRIDE !== null) {
      const local = join(OVERRIDE, decodeURIComponent(url.pathname))
      let size = null
      try {
        const st = await stat(local)
        if (st.isFile()) size = st.size
      } catch {}
      if (size !== null) {
        const range = /^bytes=(\d+)-(\d*)$/.exec(req.headers.range ?? '')
        const start = range ? Number(range[1]) : 0
        const end = range
          ? range[2] === ''
            ? size - 1
            : Math.min(Number(range[2]), size - 1)
          : size - 1
        const fh = await (await import('node:fs/promises')).open(local, 'r')
        const body = Buffer.alloc(end - start + 1)
        await fh.read(body, 0, body.length, start)
        await fh.close()
        const headers = {
          'content-type': 'application/octet-stream',
          'accept-ranges': 'bytes',
          'content-length': String(body.length),
        }
        if (range) headers['content-range'] = `bytes ${start}-${end}/${size}`
        res.writeHead(range ? 206 : 200, headers)
        res.end(body)
        return
      }
    }
    for (const [prefix, base] of Object.entries(UPSTREAM)) {
      if (url.pathname.startsWith(prefix)) {
        const target = base + url.pathname.slice(prefix.length) + url.search
        const r = await curl(target, req.headers.range)
        let body = r.body
        const out = {}
        for (const k of [
          'content-type',
          'content-range',
          'etag',
          'accept-ranges',
          'cache-control',
        ])
          if (r.headers[k]) out[k] = r.headers[k]
        if (prefix === '/ofm/' && /json/.test(r.headers['content-type'] ?? '')) {
          body = Buffer.from(
            body
              .toString('utf8')
              .replaceAll(
                'https://tiles.openfreemap.org/',
                `http://127.0.0.1:${PORT}/ofm/`,
              ),
          )
          delete out['content-range']
        }
        out['content-length'] = String(body.length)
        res.writeHead(r.status, out)
        res.end(body)
        return
      }
    }
    // Static: the build, with SPA fallback to index.html.
    let path = join(DIST, decodeURIComponent(url.pathname))
    try {
      if ((await stat(path)).isDirectory()) path = join(path, 'index.html')
    } catch {
      path = join(DIST, 'index.html')
    }
    try {
      const body = await readFile(path)
      res.writeHead(200, {
        'content-type': TYPES[extname(path)] ?? 'application/octet-stream',
        'content-length': String(body.length),
      })
      res.end(body)
    } catch {
      res.writeHead(404)
      res.end('not found')
    }
  })
  .listen(PORT, '127.0.0.1', () =>
    console.log(`render proxy on http://127.0.0.1:${PORT} serving ${DIST}`),
  )
