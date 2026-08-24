// The other organizations' trail lines, and the one place this module is
// deliberately STRICTER than the sketch it is modelled on (#950).
//
// lib/trailOverview.ts draws unverifiable bytes: a bucket whose manifest
// names no hash for the corridor-view sketch still gets the sketch, because
// what rides on it is three seconds of a line drawn only below the pin seam
// and replaced the moment the real centerline lands.
//
// Nothing about that argument survives the move to these lines. They are
// drawn at every zoom, they sit under the hiker's dot, and at a junction they
// are the map. So the unverifiable case flips: no published hash means
// nothing drawn. The test that pins that flip is the reason this file exists
// rather than a second copy of trailOverview.test.ts.

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

vi.mock('./config', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./config')>()),
  DATA_BASE_URL: 'https://data.example',
  DATA_CONFIGURED: true,
  dataUrl: (key: string) => `https://data.example/${key}`,
}))

const { fetchNearbyTrails } = await import('./nearbyTrailData')
const { NEARBY_TRAILS_KEY } = await import('./config')

// One OPRHP line, carrying exactly the properties
// pipeline/export_nearby_trails.py publishes.
const NETWORK = JSON.stringify({
  type: 'FeatureCollection',
  features: [
    {
      type: 'Feature',
      properties: {
        id: 'oprhp_trails:1',
        source: 'oprhp_trails',
        name: 'Ramapo-Dunderberg',
        blaze_color: 'Red',
        trail_status: 'open',
      },
      geometry: { type: 'LineString', coordinates: [[-74.1, 41.25]] },
    },
  ],
})

/** The sha256 of NETWORK as the manifest would publish it - computed rather
 *  than pasted, so this file cannot drift from the bytes it serves. */
async function networkHash(): Promise<string> {
  const digest = await crypto.subtle.digest(
    'SHA-256',
    new TextEncoder().encode(NETWORK) as unknown as BufferSource,
  )
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, '0')).join('')
}

function serve({
  network,
  manifest,
}: {
  network?: Partial<Response> | 'missing'
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
      if (network === 'missing') {
        return Promise.resolve({ ok: false, status: 404 } as unknown as Response)
      }
      return Promise.resolve({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/geo+json' }),
        arrayBuffer: () => Promise.resolve(new TextEncoder().encode(NETWORK).buffer),
        ...network,
      } as unknown as Response)
    }),
  )
}

beforeEach(() => {
  vi.stubGlobal('URL', {
    ...URL,
    createObjectURL: vi.fn(() => 'blob:nearby'),
    revokeObjectURL: vi.fn(),
  })
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('the nearby-trail network', () => {
  it('hands back a URL for bytes that match what was published', async () => {
    serve({
      manifest: { artifacts: { [NEARBY_TRAILS_KEY]: { sha256: await networkHash() } } },
    })

    await expect(fetchNearbyTrails()).resolves.toBe('blob:nearby')
  })

  it('draws nothing when the bytes are not what was published', async () => {
    // A corrupted trail line is a trail drawn where the trail is not, and a
    // hiker at a junction cannot tell which organization drew the line they
    // are looking at. Somebody else's trail gets the same check ours does.
    serve({ manifest: { artifacts: { [NEARBY_TRAILS_KEY]: { sha256: 'nope' } } } })

    await expect(fetchNearbyTrails()).resolves.toBeNull()
  })

  it('draws nothing when the manifest names no hash for it', async () => {
    // THE DEPARTURE FROM lib/trailOverview.ts, and the reason this file is
    // not a copy of its tests. There, unverifiable bytes are drawn, because
    // the sketch is worth three seconds and is never read for a position.
    // These lines are read for a position, so unverifiable means undrawn.
    serve({ manifest: { artifacts: {} } })

    await expect(fetchNearbyTrails()).resolves.toBeNull()
  })

  it('says nothing when the bucket holds no network - the ordinary case today', async () => {
    // A 404 is what publish.py PRODUCES right now: it holds this artifact
    // back entirely while NYS OPRHP's or NYNJTC's reuse terms are unstated.
    // So this path is the licence gate working, not a release predating the
    // artifact, and it must be as quiet as the day it stops being the answer.
    serve({ network: 'missing' })

    await expect(fetchNearbyTrails()).resolves.toBeNull()
  })

  it('says nothing when the fetch fails outright', async () => {
    // No signal, a refused origin, an aborted request. Nobody asked for these
    // lines - the chosen trail is drawn either way.
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.reject(new TypeError('Failed to fetch'))),
    )

    await expect(fetchNearbyTrails()).resolves.toBeNull()
  })

  it('asks for the key the pipeline publishes', async () => {
    // The client end of the contract pipeline/publish.py's NEARBY_TRAILS_KEY
    // holds up. A name that drifts is a silent 404, and silent is exactly
    // what this path already is.
    serve({ manifest: { artifacts: {} } })

    await fetchNearbyTrails()

    expect(vi.mocked(fetch).mock.calls.map(([url]) => String(url))).toContain(
      `https://data.example/${NEARBY_TRAILS_KEY}`,
    )
  })
})
