// First run, pointer first: a phone with no recorded release reads its
// environment's channels.json before the app renders, and takes the release
// it names once that release's manifest resolves (the maintainer,
// 2026-10-16). lib/dataChannel.ts's firstRunRelease is the read and
// lib/dataRelease.ts's adoptFirstRunRelease the switch; main.tsx awaits the
// first and renders after it.
//
// THE PROPERTY EVERY FAILURE BELOW IS HELD TO: offline, a pointer missing,
// malformed or slow, a release whose manifest does not resolve, or a record
// IndexedDB will not keep each leave the session on the compiled floor,
// DATA_RELEASE, whose manifest every deploy checks resolves. And a phone that
// already holds data is never moved by this: it keeps the floor this launch,
// and the pointer is recorded for the next, where the hiker is asked before
// anything they hold is replaced (#919 — A published data fix reaches no
// phone that already has the app, because the download asks whether there
// is trail data and never which).

import { existsSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { cwd } from 'node:process'

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const idb = vi.hoisted(() => ({
  store: new Map<string, unknown>(),
  failGet: false,
  failSet: false,
}))

vi.mock('idb-keyval', () => ({
  get: vi.fn(async (key: string) => {
    if (idb.failGet) throw new Error('IndexedDB is unavailable')
    return idb.store.get(key)
  }),
  set: vi.fn(async (key: string, value: unknown) => {
    if (idb.failSet) throw new Error('QuotaExceededError')
    idb.store.set(key, value)
  }),
  del: vi.fn(async (key: string) => {
    idb.store.delete(key)
  }),
}))

const BASE = 'https://data.example'
const UA_BASE = `${BASE}/environments/ua`
const KEY = 'ourhike:data-channel'
// Read out of lib/dataRelease.ts the way the deploy guards read it.
const FLOOR = /^export const DATA_RELEASE = '([^']+)'$/m.exec(
  readFileSync(
    [
      join(cwd(), 'src/lib/dataRelease.ts'),
      join(cwd(), 'client/src/lib/dataRelease.ts'),
    ].find((candidate) => existsSync(candidate)) as string,
    'utf-8',
  ),
)?.[1] as string
// A release no build pins, so taking it is seen to move a session off the floor.
const POINTED = '2026-10-15'

/** One launch: lib/dataRelease.ts and lib/dataChannel.ts evaluated afresh. */
async function launch(base = BASE) {
  vi.resetModules()
  vi.stubEnv('VITE_DATA_BASE_URL', base)
  const release = await import('./dataRelease')
  const channel = await import('./dataChannel')
  // Read through to the module namespaces rather than spread into a copy:
  // SESSION_RELEASE is a live binding, and adoption is the change under test.
  return new Proxy({} as typeof release & typeof channel, {
    get: (_, key: string) =>
      key in release
        ? release[key as keyof typeof release]
        : channel[key as keyof typeof channel],
  })
}

type Route = () => Response | Promise<Response>

/** fetch, answering from `routes` and 404 for anything else, honouring abort. */
function serve(routes: Record<string, Route>) {
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input)
    return new Promise<Response>((resolveResponse, reject) => {
      if (init?.signal?.aborted) {
        reject(new DOMException('Aborted', 'AbortError'))
        return
      }
      init?.signal?.addEventListener('abort', () =>
        reject(new DOMException('Aborted', 'AbortError')),
      )
      const route = routes[url]
      if (route === undefined) resolveResponse(new Response('', { status: 404 }))
      else Promise.resolve(route()).then(resolveResponse, reject)
    })
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

const body =
  (text: string): Route =>
  () =>
    new Response(text, { status: 200 })

/** channels.json as pipeline/channels.py writes it: one environment's entries. */
const pointerTo = (release: string, environment = 'production') =>
  body(JSON.stringify({ [environment]: { v1: release } }))

const manifestOf = (release: string) =>
  body(JSON.stringify({ release, artifacts: { 'trails.geojson': { sha256: 'a' } } }))

function bucket(release = POINTED, base = BASE, environment = 'production') {
  return {
    [`${base}/channels.json`]: pointerTo(release, environment),
    [`${base}/releases/${release}/manifest.json`]: manifestOf(release),
  }
}

beforeEach(() => {
  idb.store.clear()
  idb.failGet = false
  idb.failSet = false
  window.localStorage.clear()
})

afterEach(() => {
  vi.unstubAllEnvs()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
  vi.useRealTimers()
})

describe('a first run, online, with a pointer that resolves', () => {
  it('takes the release the pointer names before any release URL is built', async () => {
    const release = await launch()
    serve(bucket())
    expect(release.SESSION_RELEASE).toBe(FLOOR)

    expect(await release.firstRunRelease(BASE)).toBe('adopted')

    expect(release.SESSION_RELEASE).toBe(POINTED)
    expect(release.SESSION_FOLLOWS_POINTER).toBe(true)
    expect(release.releasePath('trails.geojson')).toBe(
      `releases/${POINTED}/trails.geojson`,
    )
    expect(release.releaseManifestPath()).toBe(`releases/${POINTED}/manifest.json`)
    expect(release.RELEASE_MANIFEST_PATH).toBe(`releases/${POINTED}/manifest.json`)
  })

  it('records it, record and mirror, so the next launch reads it without asking', async () => {
    const release = await launch()
    serve(bucket())
    await release.firstRunRelease(BASE)

    expect(idb.store.get(KEY)).toMatchObject({
      release: POINTED,
      environment: 'production',
    })
    expect(JSON.parse(window.localStorage.getItem(KEY) as string)).toMatchObject({
      release: POINTED,
    })
    const next = await launch()
    const fetchMock = serve({})
    expect(next.SESSION_RELEASE).toBe(POINTED)
    expect(await next.firstRunRelease(BASE)).toBe('not-first-run')
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it("takes a UA build to UA's own entry", async () => {
    const release = await launch(UA_BASE)
    serve(bucket(POINTED, UA_BASE, 'ua'))

    expect(await release.firstRunRelease(UA_BASE)).toBe('adopted')
    expect(release.SESSION_RELEASE).toBe(POINTED)
  })

  it('asks for the pointer uncached', async () => {
    const release = await launch()
    const fetchMock = serve(bucket())
    await release.firstRunRelease(BASE)

    const [url, init] = fetchMock.mock.calls[0]
    expect(String(url)).toBe(`${BASE}/channels.json`)
    expect(init?.cache).toBe('no-store')
  })
})

describe('a first run falls back to the compiled floor', () => {
  async function onFloor(
    outcome: string,
    routes: Record<string, Route>,
    setup: () => void = () => {},
  ) {
    const release = await launch()
    serve(routes)
    setup()

    expect(await release.firstRunRelease(BASE)).toBe(outcome)
    expect(release.SESSION_RELEASE).toBe(FLOOR)
    expect(release.SESSION_FOLLOWS_POINTER).toBe(false)
    expect(release.releasePath('trails.geojson')).toBe(`releases/${FLOOR}/trails.geojson`)
    return release
  }

  it('offline, asking nothing', async () => {
    const fetchMock = serve(bucket())
    const release = await launch()
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false)

    expect(await release.firstRunRelease(BASE)).toBe('offline')
    expect(release.SESSION_RELEASE).toBe(FLOOR)
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('when the network fails', async () => {
    await onFloor('unreachable', {
      [`${BASE}/channels.json`]: () => Promise.reject(new TypeError('Failed to fetch')),
    })
  })

  it('when no pointer is uploaded (a 404)', async () => {
    await onFloor('unreachable', {})
  })

  it.each([
    ['not JSON', '<html>captive portal</html>'],
    ['a bare list', '[]'],
    ["only another environment's entry", JSON.stringify({ ua: { v1: POINTED } })],
    ['only another schema version', JSON.stringify({ production: { v2: POINTED } })],
    [
      'an entry that is not a release id',
      JSON.stringify({ production: { v1: '../latest' } }),
    ],
  ])('when the pointer is malformed: %s', async (_, text) => {
    await onFloor('malformed', { [`${BASE}/channels.json`]: body(text) })
    expect(idb.store.has(KEY)).toBe(false)
  })

  it("when the named release's manifest answers 404, recording nothing", async () => {
    await onFloor('unresolved', { [`${BASE}/channels.json`]: pointerTo(POINTED) })
    expect(idb.store.has(KEY)).toBe(false)
    expect(window.localStorage.getItem(KEY)).toBeNull()
  })

  it('when IndexedDB will not keep the record', async () => {
    await onFloor('unstorable', bucket(), () => {
      idb.failSet = true
    })
    expect(window.localStorage.getItem(KEY)).toBeNull()
  })

  it('when the pointer never answers, at FIRST_RUN_READ_TIMEOUT_MS', async () => {
    vi.useFakeTimers()
    const release = await launch()
    serve({ [`${BASE}/channels.json`]: () => new Promise<Response>(() => {}) })

    const answer = release.firstRunRelease(BASE)
    await vi.advanceTimersByTimeAsync(release.FIRST_RUN_READ_TIMEOUT_MS)

    expect(await answer).toBe('unreachable')
    expect(release.SESSION_RELEASE).toBe(FLOOR)
  })

  it('when the manifest never answers, within the same deadline', async () => {
    vi.useFakeTimers()
    const release = await launch()
    serve({
      [`${BASE}/channels.json`]: pointerTo(POINTED),
      [`${BASE}/releases/${POINTED}/manifest.json`]: () =>
        new Promise<Response>(() => {}),
    })

    const answer = release.firstRunRelease(BASE)
    await vi.advanceTimersByTimeAsync(release.FIRST_RUN_READ_TIMEOUT_MS)

    expect(await answer).toBe('unresolved')
    expect(release.SESSION_RELEASE).toBe(FLOOR)
    expect(idb.store.has(KEY)).toBe(false)
  })

  it('with no data base configured, asking nothing', async () => {
    const fetchMock = serve(bucket())
    const release = await launch('')

    expect(await release.firstRunRelease('')).toBe('unconfigured')
    expect(fetchMock).not.toHaveBeenCalled()
  })
})

describe('a phone that is not on its first run is never moved by it', () => {
  it('holds a completed download: the floor this launch, nothing asked', async () => {
    idb.store.set('ourhike:trail-data-release', { version: 'v', hashes: {}, at: 1 })
    const release = await launch()
    const fetchMock = serve(bucket())

    expect(await release.firstRunRelease(BASE)).toBe('not-first-run')
    expect(release.SESSION_RELEASE).toBe(FLOOR)
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('holds a record its mirror lost: nothing asked here, readDataChannel repairs it', async () => {
    idb.store.set(KEY, {
      release: POINTED,
      schema: 'v1',
      environment: 'production',
      at: 1,
    })
    const release = await launch()
    const fetchMock = serve(bucket())

    expect(await release.firstRunRelease(BASE)).toBe('not-first-run')
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('cannot read IndexedDB, so cannot tell: the floor', async () => {
    idb.failGet = true
    const release = await launch()
    serve(bucket())

    expect(await release.firstRunRelease(BASE)).toBe('not-first-run')
    expect(release.SESSION_RELEASE).toBe(FLOOR)
  })

  it('built a release URL before the pointer answered: recorded for the next launch, this one stays', async () => {
    const release = await launch()
    serve(bucket())
    release.releasePath('trails.geojson')

    expect(await release.firstRunRelease(BASE)).toBe('recorded')
    expect(release.SESSION_RELEASE).toBe(FLOOR)
    expect((await launch()).SESSION_RELEASE).toBe(POINTED)
  })

  it('started rendering before the pointer answered: the same', async () => {
    const release = await launch()
    serve(bucket())
    release.sealSessionRelease()

    expect(await release.firstRunRelease(BASE)).toBe('recorded')
    expect(release.SESSION_RELEASE).toBe(FLOOR)
  })

  it('and adoptFirstRunRelease refuses a record that is not this build’s', async () => {
    const release = await launch()

    expect(
      release.adoptFirstRunRelease({
        release: POINTED,
        schema: 'v1',
        environment: 'ua',
        at: 1,
      }),
    ).toBe(false)
    expect(release.SESSION_RELEASE).toBe(FLOOR)
  })
})

describe('the download record a first run checks for', () => {
  it("is lib/dataRefresh.ts's RELEASE_KEY", async () => {
    const { DOWNLOAD_RECORD_KEY } = await import('./dataChannel')
    const { RELEASE_KEY } = await import('./dataRefresh')
    expect(DOWNLOAD_RECORD_KEY).toBe(RELEASE_KEY)
  })
})
