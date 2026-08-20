// The corridor-view centerline, and the two things it must never do.
//
// It is a sketch with a short life (#869, and lib/config.ts's
// TRAILS_OVERVIEW_KEY for what 100 m of tolerance means at each zoom), so the
// cases below are not about drawing it. They are about the two ways a
// shortcut like this goes wrong:
//
//  - drawing something nobody checked, which on this map is a trail line
//    somewhere the trail is not;
//  - turning a nicety into a failure, when the hiker asked for none of it and
//    the real centerline is still on its way through the path that does
//    report.

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

vi.mock('./config', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./config')>()),
  DATA_BASE_URL: 'https://data.example',
  DATA_CONFIGURED: true,
  dataUrl: (key: string) => `https://data.example/${key}`,
}))

const { fetchTrailOverview } = await import('./trailOverview')
const { TRAILS_OVERVIEW_KEY } = await import('./config')

const SKETCH = '{"type":"FeatureCollection","features":[]}'

/** The sha256 of SKETCH, as the manifest would publish it - computed rather
 *  than pasted, so this file cannot drift from the bytes it serves. */
async function sketchHash(): Promise<string> {
  const digest = await crypto.subtle.digest(
    'SHA-256',
    new TextEncoder().encode(SKETCH) as unknown as BufferSource,
  )
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, '0')).join('')
}

function serve({
  overview,
  manifest,
}: {
  overview?: Partial<Response> | 'missing'
  manifest?: unknown
}) {
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string) => {
      if (String(url).includes('latest.json')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve(manifest ?? { artifacts: {} }),
        } as unknown as Response)
      }
      if (overview === 'missing') {
        return Promise.resolve({ ok: false, status: 404 } as unknown as Response)
      }
      return Promise.resolve({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/geo+json' }),
        arrayBuffer: () => Promise.resolve(new TextEncoder().encode(SKETCH).buffer),
        ...overview,
      } as unknown as Response)
    }),
  )
}

beforeEach(() => {
  vi.stubGlobal('URL', {
    ...URL,
    createObjectURL: vi.fn(() => 'blob:overview'),
    revokeObjectURL: vi.fn(),
  })
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('the corridor-view centerline', () => {
  it('hands back a URL for bytes that match what was published', async () => {
    serve({
      manifest: { artifacts: { [TRAILS_OVERVIEW_KEY]: { sha256: await sketchHash() } } },
    })

    await expect(fetchTrailOverview()).resolves.toBe('blob:overview')
  })

  it('draws nothing when the bytes are not what was published', async () => {
    // The case that matters. A corrupted sketch is a trail line in the wrong
    // place - briefly, at a zoom where nobody could take a bearing off it, and
    // still not something this map does. Nothing is drawn and the real
    // centerline arrives on its own schedule.
    serve({ manifest: { artifacts: { [TRAILS_OVERVIEW_KEY]: { sha256: 'nope' } } } })

    await expect(fetchTrailOverview()).resolves.toBeNull()
  })

  it('draws it when the manifest names no hash for it', async () => {
    // A bucket published before this artifact existed, or one with no manifest
    // at all - the same downgrade lib/dataManifest.ts describes for every
    // other artifact, and for this one the thing riding on it is a few
    // seconds of sketch.
    serve({ manifest: { artifacts: {} } })

    await expect(fetchTrailOverview()).resolves.toBe('blob:overview')
  })

  it('says nothing when the release does not publish one', async () => {
    // A 404 here is "this release predates the overview", exactly as it is for
    // spurs.json and elevation_profile.json.
    serve({ overview: 'missing' })

    await expect(fetchTrailOverview()).resolves.toBeNull()
  })

  it('says nothing when the fetch fails outright', async () => {
    // No signal, a refused origin, an aborted request when the real line won
    // the race. Nobody asked for this, so none of them is worth a word.
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.reject(new TypeError('Failed to fetch'))),
    )

    await expect(fetchTrailOverview()).resolves.toBeNull()
  })

  it('asks for the key the pipeline publishes', async () => {
    // The other end of the same contract pipeline/tests/
    // test_published_key_contract.py checks: a name that drifts is a 404 on a
    // mountain, and this one is silent by design.
    serve({ manifest: { artifacts: {} } })

    await fetchTrailOverview()

    expect(vi.mocked(fetch).mock.calls.map(([url]) => String(url))).toContain(
      `https://data.example/${TRAILS_OVERVIEW_KEY}`,
    )
  })
})
