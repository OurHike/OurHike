// The pointer (decision 44): `channels.json`, which release a phone reads.
//
// pipeline/ELT.md, "Versions and channels (decision 44), as stage 4 builds
// them": on launch, when online, the app reads `channels.json` and takes its
// environment's entry for its schema version; offline or unreachable, the
// release it last read; on a first run with no record, the compiled
// DATA_RELEASE; and an entry naming a release that does not resolve keeps the
// last good one.
//
// THE PROPERTY EVERY CASE BELOW IS HELD TO: a phone never ends with no data
// because a pointer was missing, malformed or unreachable. Each failure is
// asserted three ways - what the read reports, that the record still holds the
// last good release (or none), and that the NEXT launch's release, read the way
// the app reads it, is a release folder that exists rather than nothing.
//
// Every launch here is a fresh evaluation of lib/dataRelease.ts, because the
// session's release is decided once when the module loads.

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
}))

const BASE = 'https://data.example'
const UA_BASE = `${BASE}/environments/ua`
const KEY = 'ourhike:data-channel'
// The compiled pin, read out of lib/dataRelease.ts the way pages.yml's guard
// reads it, so moving the pin is one line in that file and not two.
const COMPILED = /^export const DATA_RELEASE = '([^']+)'$/m.exec(
  readFileSync(
    [
      join(cwd(), 'src/lib/dataRelease.ts'),
      join(cwd(), 'client/src/lib/dataRelease.ts'),
    ].find((candidate) => existsSync(candidate)) as string,
    'utf-8',
  ),
)?.[1] as string
const LAST_GOOD = '2026-10-01'
const NEWER = '2026-10-03-2'

/** One launch of the app: lib/dataRelease.ts and the pointer reader it is
 *  split from, lib/dataChannel.ts, evaluated afresh against `base`. */
async function launch(base = BASE) {
  vi.resetModules()
  vi.stubEnv('VITE_DATA_BASE_URL', base)
  return { ...(await import('./dataRelease')), ...(await import('./dataChannel')) }
}

function record(release: string, environment = 'production') {
  return { release, schema: 'v1', environment, at: 1_790_000_000_000 }
}

/** A phone that verified `release` at some earlier launch: the record and its
 *  mirror, as readDataChannel leaves them. */
function rememberPointer(release: string, environment = 'production') {
  idb.store.set(KEY, record(release, environment))
  window.localStorage.setItem(KEY, JSON.stringify(record(release, environment)))
}

function manifestOf(release: string) {
  return JSON.stringify({
    version: 'uuid',
    release,
    artifacts: { 'trails.geojson': { sha256: 'a' } },
  })
}

type Route = () => Response | Promise<Response>

/** fetch, answering each URL from `routes` and 404 for anything else. Honours
 *  the caller's abort signal, as a real fetch does. */
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

function pointer(body: string): Route {
  return () => new Response(body, { status: 200 })
}

function channels(entries: Record<string, Record<string, unknown>>): Route {
  return pointer(JSON.stringify(entries))
}

const releaseManifest =
  (release: string): Route =>
  () =>
    new Response(manifestOf(release), { status: 200 })

beforeEach(() => {
  idb.store.clear()
  idb.failGet = false
  idb.failSet = false
})

afterEach(() => {
  vi.unstubAllEnvs()
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

describe('which release a session reads', () => {
  it('is the compiled DATA_RELEASE on a first run, with no pointer recorded', async () => {
    const release = await launch()

    expect(release.SESSION_RELEASE).toBe(release.DATA_RELEASE)
    expect(release.SESSION_RELEASE).toBe(COMPILED)
    expect(release.SESSION_FOLLOWS_POINTER).toBe(false)
    expect(release.releasePath('trails.geojson')).toBe(
      `releases/${COMPILED}/trails.geojson`,
    )
  })

  it('is the release this phone last verified from the pointer, read synchronously from the mirror', async () => {
    rememberPointer(LAST_GOOD)

    const release = await launch()

    expect(release.SESSION_RELEASE).toBe(LAST_GOOD)
    expect(release.SESSION_FOLLOWS_POINTER).toBe(true)
    expect(release.releasePath('trails.geojson')).toBe(
      `releases/${LAST_GOOD}/trails.geojson`,
    )
    expect(release.RELEASE_MANIFEST_PATH).toBe(`releases/${LAST_GOOD}/manifest.json`)
    // Root keys stay where they are whichever release the session reads.
    expect(release.releasePath('conditions/closures.json')).toBe(
      'conditions/closures.json',
    )
  })

  it.each([
    ['not JSON', '{release'],
    [
      'an id that is not a release id',
      JSON.stringify({ ...record(LAST_GOOD), release: '../../latest' }),
    ],
    ['another schema version', JSON.stringify({ ...record(LAST_GOOD), schema: 'v2' })],
    ['another data environment', JSON.stringify(record(LAST_GOOD, 'ua'))],
    [
      'no time it was read',
      JSON.stringify({ release: LAST_GOOD, schema: 'v1', environment: 'production' }),
    ],
  ])('reads the compiled fallback when the mirror holds %s', async (_, mirror) => {
    window.localStorage.setItem(KEY, mirror)

    const release = await launch()

    expect(release.SESSION_RELEASE).toBe(COMPILED)
    expect(release.SESSION_FOLLOWS_POINTER).toBe(false)
  })

  it('reads the compiled fallback when localStorage itself throws', async () => {
    rememberPointer(LAST_GOOD)
    const denied = vi.spyOn(window, 'localStorage', 'get').mockImplementation(() => {
      throw new DOMException('denied', 'SecurityError')
    })
    try {
      const release = await launch()

      expect(release.SESSION_RELEASE).toBe(COMPILED)
    } finally {
      denied.mockRestore()
    }
  })

  it('takes a UA build to the entry recorded for UA', async () => {
    rememberPointer(LAST_GOOD, 'ua')

    const release = await launch(UA_BASE)

    expect(release.SESSION_RELEASE).toBe(LAST_GOOD)
  })
})

describe('reading the pointer', () => {
  it('records a new entry once its release resolves, for the next launch and never this one', async () => {
    const release = await launch()
    serve({
      [`${BASE}/channels.json`]: channels({
        production: { v1: NEWER },
        ua: { v1: LAST_GOOD },
      }),
      [`${BASE}/releases/${NEWER}/manifest.json`]: releaseManifest(NEWER),
    })

    const answer = await release.readDataChannel(BASE)

    expect(answer).toEqual({ outcome: 'recorded', recorded: NEWER })
    expect(idb.store.get(KEY)).toMatchObject({
      release: NEWER,
      schema: 'v1',
      environment: 'production',
    })
    expect(JSON.parse(window.localStorage.getItem(KEY) ?? 'null')).toMatchObject({
      release: NEWER,
    })
    // Never mid-session: this launch keeps building every URL from one release.
    expect(release.SESSION_RELEASE).toBe(COMPILED)
    expect(release.releasePath('trails.geojson')).toBe(
      `releases/${COMPILED}/trails.geojson`,
    )

    const next = await launch()
    expect(next.SESSION_RELEASE).toBe(NEWER)
    expect(next.SESSION_FOLLOWS_POINTER).toBe(true)
  })

  it('asks for the pointer uncached, because it is what says which release is current', async () => {
    const release = await launch()
    const fetchMock = serve({})

    await release.readDataChannel(BASE)

    const [url, init] = fetchMock.mock.calls[0]
    expect(String(url)).toBe(`${BASE}/channels.json`)
    expect(init?.cache).toBe('no-store')
  })

  it("reads its own environment's entry and no other", async () => {
    const release = await launch(UA_BASE)
    serve({
      [`${UA_BASE}/channels.json`]: channels({
        production: { v1: LAST_GOOD },
        ua: { v1: NEWER },
      }),
      [`${UA_BASE}/releases/${NEWER}/manifest.json`]: releaseManifest(NEWER),
    })

    expect(await release.readDataChannel(UA_BASE)).toEqual({
      outcome: 'recorded',
      recorded: NEWER,
    })
    expect(idb.store.get(KEY)).toMatchObject({ release: NEWER, environment: 'ua' })
  })

  it('does not fetch the release manifest again for an entry it already recorded', async () => {
    rememberPointer(LAST_GOOD)
    const release = await launch()
    const fetchMock = serve({
      [`${BASE}/channels.json`]: channels({ production: { v1: LAST_GOOD } }),
    })

    expect(await release.readDataChannel(BASE)).toEqual({
      outcome: 'unchanged',
      recorded: LAST_GOOD,
    })
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('follows a rollback like any other move: the pointer is what the train moves', async () => {
    rememberPointer(NEWER)
    const release = await launch()
    serve({
      [`${BASE}/channels.json`]: channels({ production: { v1: LAST_GOOD } }),
      [`${BASE}/releases/${LAST_GOOD}/manifest.json`]: releaseManifest(LAST_GOOD),
    })

    expect(await release.readDataChannel(BASE)).toEqual({
      outcome: 'recorded',
      recorded: LAST_GOOD,
    })
    expect((await launch()).SESSION_RELEASE).toBe(LAST_GOOD)
  })

  it('reads nothing and records nothing with no data base configured', async () => {
    const release = await launch('')
    const fetchMock = serve({})

    expect(await release.readDataChannel('')).toEqual({
      outcome: 'unconfigured',
      recorded: null,
    })
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('repairs a mirror the record does not match, for the next launch', async () => {
    idb.store.set(KEY, record(LAST_GOOD))
    const release = await launch()
    expect(release.SESSION_RELEASE).toBe(COMPILED)
    serve({})

    await release.readDataChannel(BASE)

    expect((await launch()).SESSION_RELEASE).toBe(LAST_GOOD)
  })
})

describe('a phone never ends with no data because of the pointer', () => {
  // The cases the pointer can fail in. Each returns the routes a launch meets.
  const missing = (): Record<string, Route> => ({})
  const failures: [string, () => Record<string, Route>, string][] = [
    ['missing (404 before the first upload)', missing, 'unreachable'],
    [
      'unreachable (the request fails)',
      () => ({
        [`${BASE}/channels.json`]: () => Promise.reject(new TypeError('Failed to fetch')),
      }),
      'unreachable',
    ],
    [
      'answering a server error',
      () => ({ [`${BASE}/channels.json`]: () => new Response('', { status: 503 }) }),
      'unreachable',
    ],
    [
      'not JSON',
      () => ({ [`${BASE}/channels.json`]: pointer('<html>captive portal</html>') }),
      'malformed',
    ],
    ['a bare list', () => ({ [`${BASE}/channels.json`]: pointer('[]') }), 'malformed'],
    [
      'without this environment',
      () => ({ [`${BASE}/channels.json`]: channels({ ua: { v1: NEWER } }) }),
      'malformed',
    ],
    [
      'without this schema version',
      () => ({ [`${BASE}/channels.json`]: channels({ production: { v2: NEWER } }) }),
      'malformed',
    ],
    [
      'naming something that is not a release id',
      () => ({
        [`${BASE}/channels.json`]: channels({ production: { v1: '../../latest' } }),
      }),
      'malformed',
    ],
    [
      'naming a number',
      () => ({ [`${BASE}/channels.json`]: channels({ production: { v1: 20261003 } }) }),
      'malformed',
    ],
    [
      'naming a release whose manifest is not there',
      () => ({ [`${BASE}/channels.json`]: channels({ production: { v1: NEWER } }) }),
      'unresolved',
    ],
    [
      'naming a release whose manifest is not a manifest',
      () => ({
        [`${BASE}/channels.json`]: channels({ production: { v1: NEWER } }),
        [`${BASE}/releases/${NEWER}/manifest.json`]: pointer('{"artifacts": []}'),
      }),
      'unresolved',
    ],
    [
      "naming a release whose manifest is another release's",
      () => ({
        [`${BASE}/channels.json`]: channels({ production: { v1: NEWER } }),
        [`${BASE}/releases/${NEWER}/manifest.json`]: releaseManifest(LAST_GOOD),
      }),
      'unresolved',
    ],
  ]

  it.each(failures)(
    'keeps the last good release when the pointer is %s',
    async (_, routes, outcome) => {
      rememberPointer(LAST_GOOD)
      const release = await launch()
      serve(routes())

      expect(await release.readDataChannel(BASE)).toEqual({
        outcome,
        recorded: LAST_GOOD,
      })
      expect(idb.store.get(KEY)).toMatchObject({ release: LAST_GOOD })

      const next = await launch()
      expect(next.SESSION_RELEASE).toBe(LAST_GOOD)
      expect(next.releasePath('trails.geojson')).toBe(
        `releases/${LAST_GOOD}/trails.geojson`,
      )
    },
  )

  it.each(failures)(
    'keeps the compiled fallback on a phone with no record when the pointer is %s',
    async (_, routes, outcome) => {
      const release = await launch()
      serve(routes())

      expect(await release.readDataChannel(BASE)).toEqual({ outcome, recorded: null })
      expect(idb.store.has(KEY)).toBe(false)
      expect(window.localStorage.getItem(KEY)).toBeNull()

      const next = await launch()
      expect(next.SESSION_RELEASE).toBe(COMPILED)
      expect(next.releasePath('trails.geojson')).toBe(
        `releases/${COMPILED}/trails.geojson`,
      )
    },
  )

  it('gives up on a pointer that never answers, rather than waiting on a captive portal', async () => {
    vi.useFakeTimers()
    rememberPointer(LAST_GOOD)
    const release = await launch()
    serve({ [`${BASE}/channels.json`]: () => new Promise<Response>(() => {}) })

    const answer = release.readDataChannel(BASE)
    await vi.advanceTimersByTimeAsync(release.CHANNEL_READ_TIMEOUT_MS)

    expect(await answer).toEqual({ outcome: 'unreachable', recorded: LAST_GOOD })
  })

  it('reports an aborted read as unreachable and keeps the record', async () => {
    rememberPointer(LAST_GOOD)
    const release = await launch()
    serve({ [`${BASE}/channels.json`]: () => new Promise<Response>(() => {}) })
    const controller = new AbortController()

    const answer = release.readDataChannel(BASE, { signal: controller.signal })
    controller.abort()

    expect(await answer).toEqual({ outcome: 'unreachable', recorded: LAST_GOOD })
  })

  // Headers, then nothing: a 200 whose body never ends. The deadline and the
  // caller's abort have to cover the body too, or the read never settles.
  const bodyRead = { started: false }
  const stalled: Route = () => {
    const response = new Response(new ReadableStream({ start() {} }))
    const text = response.text.bind(response)
    response.text = () => {
      bodyRead.started = true
      return text()
    }
    return response
  }
  beforeEach(() => {
    bodyRead.started = false
  })

  /** What `answer` has settled to so far, without waiting on it. */
  function settledSoFar<T>(answer: Promise<T>): { value?: T } {
    const seen: { value?: T } = {}
    void answer.then((value) => {
      seen.value = value
    })
    return seen
  }

  it('gives up on a pointer whose body never ends, at the same deadline', async () => {
    vi.useFakeTimers()
    rememberPointer(LAST_GOOD)
    const release = await launch()
    serve({ [`${BASE}/channels.json`]: stalled })

    const seen = settledSoFar(release.readDataChannel(BASE))
    await vi.advanceTimersByTimeAsync(release.CHANNEL_READ_TIMEOUT_MS)

    expect(seen.value).toEqual({ outcome: 'unreachable', recorded: LAST_GOOD })
  })

  it('gives up on a release manifest whose body never ends, and records nothing', async () => {
    vi.useFakeTimers()
    rememberPointer(LAST_GOOD)
    const release = await launch()
    serve({
      [`${BASE}/channels.json`]: channels({ production: { v1: NEWER } }),
      [`${BASE}/releases/${NEWER}/manifest.json`]: stalled,
    })

    const seen = settledSoFar(release.readDataChannel(BASE))
    await vi.advanceTimersByTimeAsync(release.CHANNEL_READ_TIMEOUT_MS)

    expect(seen.value).toEqual({ outcome: 'unresolved', recorded: LAST_GOOD })
    expect(idb.store.get(KEY)).toMatchObject({ release: LAST_GOOD })
  })

  it('settles when the caller aborts while the body is still arriving', async () => {
    rememberPointer(LAST_GOOD)
    const release = await launch()
    serve({ [`${BASE}/channels.json`]: stalled })
    const controller = new AbortController()

    const answer = release.readDataChannel(BASE, { signal: controller.signal })
    // Past the headers and reading the body before the abort lands.
    await vi.waitFor(() => expect(bodyRead.started).toBe(true))
    const seen = settledSoFar(answer)
    controller.abort()
    await vi.waitFor(() => expect(seen.value).toBeDefined(), { timeout: 1_000 })

    expect(seen.value).toEqual({ outcome: 'unreachable', recorded: LAST_GOOD })
  })

  it('never rejects when fetch throws before it starts, as an unstubbed test fetch does', async () => {
    const release = await launch()
    vi.stubGlobal('fetch', () => {
      throw new Error('no network here')
    })

    await expect(release.readDataChannel(BASE)).resolves.toEqual({
      outcome: 'unreachable',
      recorded: null,
    })
  })

  it('writes neither the record nor its mirror when IndexedDB refuses the write', async () => {
    idb.failSet = true
    const release = await launch()
    serve({
      [`${BASE}/channels.json`]: channels({ production: { v1: NEWER } }),
      [`${BASE}/releases/${NEWER}/manifest.json`]: releaseManifest(NEWER),
    })

    expect(await release.readDataChannel(BASE)).toEqual({
      outcome: 'unstorable',
      recorded: null,
    })
    expect(window.localStorage.getItem(KEY)).toBeNull()
    expect((await launch()).SESSION_RELEASE).toBe(COMPILED)
  })

  it('still reads and records the pointer when IndexedDB cannot be read, starting from the mirror', async () => {
    rememberPointer(LAST_GOOD)
    idb.failGet = true
    const release = await launch()
    serve({
      [`${BASE}/channels.json`]: channels({ production: { v1: NEWER } }),
      [`${BASE}/releases/${NEWER}/manifest.json`]: releaseManifest(NEWER),
    })

    expect(await release.readDataChannel(BASE)).toEqual({
      outcome: 'recorded',
      recorded: NEWER,
    })
  })
})

describe('the committed pointer, /channels.json', () => {
  // From the working directory, as lib/buildInfo.test.ts resolves
  // package.json: vitest hands back no file:// import.meta.url, and the suite
  // runs from client/ or from the repository root.
  const path = [join(cwd(), '..', 'channels.json'), join(cwd(), 'channels.json')].find(
    (candidate) => existsSync(candidate),
  ) as string
  const committed = JSON.parse(readFileSync(path, 'utf-8')) as Record<
    string,
    Record<string, string>
  >

  it('names a release id for this build schema version in both data environments', () => {
    for (const environment of ['production', 'ua']) {
      expect(committed[environment]?.v1).toMatch(/^\d{4}-\d{2}-\d{2}(-\d+)?$/)
    }
  })

  it('is read by the same code a phone runs', async () => {
    const release = await launch()
    const entry = committed.production.v1
    serve({
      [`${BASE}/channels.json`]: pointer(JSON.stringify(committed)),
      [`${BASE}/releases/${entry}/manifest.json`]: releaseManifest(entry),
    })

    expect(await release.readDataChannel(BASE)).toEqual({
      outcome: 'recorded',
      recorded: entry,
    })
  })
})

describe('which environment a base URL serves', () => {
  it.each([
    ['https://data.ourhike.org', 'production'],
    ['https://data.ourhike.org/', 'production'],
    ['https://data.ourhike.org/environments/ua', 'ua'],
    ['https://data.ourhike.org/environments/ua/', 'ua'],
    ['https://data.ourhike.org/environments/dev', 'dev'],
    ['http://localhost:8080', 'production'],
  ])('%s is %s', async (base, environment) => {
    const { environmentOf } = await launch()
    expect(environmentOf(base)).toBe(environment)
  })
})
