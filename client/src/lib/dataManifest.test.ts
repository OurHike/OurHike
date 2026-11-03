import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { RELEASE_MANIFEST_PATH } from './dataRelease'

// The published-hash lookup (#197). Everything here turns on one distinction:
// null means "no published answer", never "verified" - so the cases that
// matter most are the ones where the manifest is missing, stale or wrong,
// and the answer still has to be an honest null rather than a hash that
// happens to be lying around.
//
// The artifact key is passed in by the caller (lib/packages.ts owns which
// artifact a package is) rather than parsed back out of a URL here - see
// DownloadOptions.artifactKey for why that stopped being this module's job.
//
// config.ts reads VITE_DATA_BASE_URL once at module load and it is unset
// under test, so each case stubs the env and imports the module fresh -
// which is also the only way to cover "no bucket configured at all".

const BASE = 'https://cdn.example.org'

async function loadWithBase(base: string | undefined) {
  vi.resetModules()
  if (base === undefined) vi.stubEnv('VITE_DATA_BASE_URL', '')
  else vi.stubEnv('VITE_DATA_BASE_URL', base)
  return await import('./dataManifest')
}

function mockManifestResponse(body: unknown, { status = 200 } = {}) {
  return vi
    .spyOn(globalThis, 'fetch')
    .mockImplementation(
      async () =>
        new Response(typeof body === 'string' ? body : JSON.stringify(body), { status }),
    )
}

beforeEach(() => {
  vi.clearAllMocks()
})

afterEach(() => {
  vi.unstubAllEnvs()
  vi.restoreAllMocks()
})

describe('publishedHash', () => {
  const HASH = 'A'.repeat(64)

  it('returns the manifest entry for the artifact, lowercased', async () => {
    const { publishedHash } = await loadWithBase(BASE)
    mockManifestResponse({
      version: 'v1',
      artifacts: { 'background.pmtiles': { sha256: HASH } },
    })

    expect(await publishedHash('background.pmtiles')).toBe(HASH.toLowerCase())
    expect(globalThis.fetch).toHaveBeenCalledWith(
      `${BASE}/${RELEASE_MANIFEST_PATH}`,
      // The shared read's own deadline signal, never the caller's - see
      // "four overlapping callers read one manifest" below.
      { signal: expect.any(AbortSignal) },
    )
  })

  it('fetches the manifest again for a call made after the last one settled', async () => {
    // Not cached on purpose: a republished archive must not leave the app
    // verifying against a hash the bucket has stopped serving, which would
    // make every retry discard its own bytes until the app restarted.
    //
    // AWAITED, and that is the whole distinction #1612 turns on: these two
    // calls do not overlap, so the sharing below does not reach them and each
    // reads the bucket. Two calls in the same tick DO share - which is the
    // launch, and the next test.
    const { publishedHash } = await loadWithBase(BASE)
    mockManifestResponse({ artifacts: { 'background.pmtiles': { sha256: HASH } } })

    await publishedHash('background.pmtiles')
    await publishedHash('background.pmtiles')
    expect(globalThis.fetch).toHaveBeenCalledTimes(2)
  })

  it('reads one manifest for four callers that overlap, not four', async () => {
    // THE LAUNCH, spelled as the four calls it actually makes: lib/coverageCells.ts
    // asks publishedHash for a cell index's hash once per family, and there are
    // four families. Before #1612 each ran its own bare fetch, and a launch
    // pulled releases/<id>/manifest.json seven times counting the other
    // callers - 412,128 bytes each on 2026-09-16-4, measured 2026-09-21, all
    // of it in front of the map.
    //
    // Counted rather than timed, for App.loadBudget.test.tsx's reason: what
    // makes this expensive is that the reads happen at all, and a count is the
    // same on any machine.
    const { publishedHash } = await loadWithBase(BASE)
    mockManifestResponse({ artifacts: { 'background.pmtiles': { sha256: HASH } } })

    const hashes = await Promise.all([
      publishedHash('background.pmtiles'),
      publishedHash('background.pmtiles'),
      publishedHash('background.pmtiles'),
      publishedHash('background.pmtiles'),
    ])

    expect(globalThis.fetch).toHaveBeenCalledTimes(1)
    // Every caller still gets the answer, which is the half a de-duplication
    // can silently drop.
    expect(hashes).toEqual(Array(4).fill(HASH.toLowerCase()))
  })

  it('does not cancel the shared read when one of its callers aborts', async () => {
    // #1302's trade, inherited here: one caller's abort must reject that
    // caller without ending the read the other three are waiting on. The
    // alternative - passing the caller's signal to the fetch - is how a
    // cancelled download used to take the whole launch's manifest with it.
    const { publishedHash } = await loadWithBase(BASE)
    mockManifestResponse({ artifacts: { 'background.pmtiles': { sha256: HASH } } })
    const controller = new AbortController()

    const cancelled = publishedHash('background.pmtiles', { signal: controller.signal })
    const other = publishedHash('background.pmtiles')
    controller.abort()

    await expect(cancelled).rejects.toThrow('Aborted')
    expect(await other).toBe(HASH.toLowerCase())
  })

  it('reads a nested key exactly as given', async () => {
    // DATA_RELEASES.md's versioned layout will address
    // releases/<date>/<name>, and the manifest names artifacts the same way.
    // Nothing here splits or normalises the key: the catalog's string is the
    // manifest's string.
    const { publishedHash } = await loadWithBase(BASE)
    mockManifestResponse({
      artifacts: { 'releases/2026-08-07/background.pmtiles': { sha256: HASH } },
    })

    expect(await publishedHash('releases/2026-08-07/background.pmtiles')).toBe(
      HASH.toLowerCase(),
    )
  })

  it('has no answer for an artifact the manifest does not list', async () => {
    // A release published before an artifact existed lists the others and
    // nothing else - which is "unverifiable", not "corrupt".
    const { publishedHash } = await loadWithBase(BASE)
    mockManifestResponse({ artifacts: { 'trails.geojson': { sha256: HASH } } })

    expect(await publishedHash('background.pmtiles')).toBeNull()
  })

  it('has no answer when the manifest is absent, unreachable or malformed', async () => {
    const { publishedHash } = await loadWithBase(BASE)

    mockManifestResponse({}, { status: 404 })
    expect(await publishedHash('background.pmtiles')).toBeNull()

    mockManifestResponse('not json at all')
    expect(await publishedHash('background.pmtiles')).toBeNull()

    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('Failed to fetch'))
    expect(await publishedHash('background.pmtiles')).toBeNull()

    mockManifestResponse({ artifacts: { 'background.pmtiles': { sha256: 42 } } })
    expect(await publishedHash('background.pmtiles')).toBeNull()

    mockManifestResponse({ artifacts: { 'background.pmtiles': { sha256: '' } } })
    expect(await publishedHash('background.pmtiles')).toBeNull()
  })

  it('lets the caller own cancellation through instead of reporting no hash', async () => {
    // The hiker aborting the download has to stop the attempt, not silently
    // downgrade it to an unverified one that keeps running. Driven through the
    // caller's own signal since #1612, because that is now the only abort this
    // function can see - see the next test for the one it deliberately cannot.
    const { publishedHash } = await loadWithBase(BASE)
    mockManifestResponse({ artifacts: { 'background.pmtiles': { sha256: HASH } } })
    const controller = new AbortController()
    controller.abort()

    await expect(
      publishedHash('background.pmtiles', { signal: controller.signal }),
    ).rejects.toThrow('Aborted')
  })

  it('reads a manifest read that gave up on its own deadline as unreadable, not as a cancellation', async () => {
    // The distinction #1612 drew by routing this through publishedSnapshot.
    // MANIFEST_READ_TIMEOUT_MS aborts a read nobody answered - a captive
    // portal at a trailhead, which HANGS rather than failing - and that abort
    // is the app giving up, not the hiker cancelling. Reported as a
    // cancellation it would stop a download the hiker never touched; reported
    // as null it downgrades to unverified, which is what an unreachable
    // manifest has always meant here.
    //
    // A bare fetch rejection is what the deadline looks like from inside, so
    // that is what this drives.
    const { publishedHash } = await loadWithBase(BASE)
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(
      new DOMException('Aborted', 'AbortError'),
    )

    expect(await publishedHash('background.pmtiles')).toBeNull()
  })

  it('does not fetch a manifest when no bucket is configured', async () => {
    const { publishedHash } = await loadWithBase(undefined)
    const fetchSpy = mockManifestResponse({ artifacts: {} })

    expect(await publishedHash('background.pmtiles')).toBeNull()
    expect(fetchSpy).not.toHaveBeenCalled()
  })
})

describe('publishedSnapshot (#919)', () => {
  const HASH = 'B'.repeat(64)

  const manifest = {
    version: 'v2',
    previous_version: 'v1',
    artifacts: {
      'poi_water.geojson': {
        sha256: HASH,
        size_bytes: 300_000,
        transfer_bytes: 100_000,
        change: { severity: 'consequential', added: 1, removed: 2, moved: 3, edited: 4 },
      },
    },
  }

  it('reads the version and the hop its descriptions cover', async () => {
    mockManifestResponse(manifest)
    const { publishedSnapshot } = await loadWithBase(BASE)

    const snapshot = await publishedSnapshot()

    expect(snapshot.version).toBe('v2')
    expect(snapshot.previousVersion).toBe('v1')
  })

  it('takes the wire cost and not the decoded size', async () => {
    // publish.py measures both. `size_bytes` is decoded and about 3x larger
    // for the gzipped text artifacts, and this figure is shown to a hiker
    // deciding whether to spend it - so the bigger one is wrong, not cautious.
    mockManifestResponse(manifest)
    const { publishedSnapshot } = await loadWithBase(BASE)

    expect((await publishedSnapshot()).sizes['poi_water.geojson']).toBe(100_000)
  })

  it('has no size for an artifact published before the wire cost was measured', async () => {
    mockManifestResponse({
      version: 'v2',
      artifacts: { 'poi_water.geojson': { sha256: HASH, size_bytes: 300_000 } },
    })
    const { publishedSnapshot } = await loadWithBase(BASE)

    // Absent rather than the decoded fallback: dataRefresh renders an unknown
    // size as "cannot say", which cautions. The fallback would print a number.
    expect((await publishedSnapshot()).sizes).toEqual({})
  })

  it('carries the decoded size beside the wire cost, for the launch budget (#1254)', async () => {
    // The other number, on purpose: `sizes` is what a hiker is shown before
    // spending mobile data; this is what the phone pays in memory once the
    // gzip is off, and lib/artifactBudget.ts weighs an artifact by it.
    mockManifestResponse(manifest)
    const { publishedSnapshot } = await loadWithBase(BASE)

    const snapshot = await publishedSnapshot()

    expect(snapshot.decodedSizes['poi_water.geojson']).toBe(300_000)
    expect(snapshot.sizes['poi_water.geojson']).toBe(100_000)
  })

  it('has no decoded size for an artifact the manifest never measured', async () => {
    mockManifestResponse({
      version: 'v2',
      artifacts: { 'poi_water.geojson': { sha256: HASH } },
    })
    const { publishedSnapshot } = await loadWithBase(BASE)

    // Absent, not zero: a launch reads absent as "unknown is not too large"
    // and weighs the response on arrival instead.
    expect((await publishedSnapshot()).decodedSizes).toEqual({})
  })

  it('carries a well-formed change grade', async () => {
    mockManifestResponse(manifest)
    const { publishedSnapshot } = await loadWithBase(BASE)

    expect((await publishedSnapshot()).changes['poi_water.geojson']).toEqual({
      severity: 'consequential',
      added: 1,
      removed: 2,
      moved: 3,
      edited: 4,
    })
  })

  it('drops a grade that is not the shape the publisher writes', async () => {
    // A published document is no more trustworthy than a fetched one. A
    // malformed grade rendered into a prompt would be this app telling a hiker
    // something nobody computed - and dataRefresh reads a missing grade as
    // "cannot describe", never as routine.
    mockManifestResponse({
      version: 'v2',
      artifacts: {
        a: {
          sha256: HASH,
          change: { severity: 'mild', added: 1, removed: 0, moved: 0, edited: 0 },
        },
        b: { sha256: HASH, change: { severity: 'routine', added: 'lots' } },
      },
    })
    const { publishedSnapshot } = await loadWithBase(BASE)

    expect((await publishedSnapshot()).changes).toEqual({})
  })

  it('knows nothing when the manifest cannot be read', async () => {
    mockManifestResponse('not json at all')
    const { publishedSnapshot } = await loadWithBase(BASE)

    const snapshot = await publishedSnapshot()

    expect(snapshot.version).toBeNull()
    expect(snapshot.hashes).toEqual({})
  })

  it('knows nothing when no bucket is configured', async () => {
    const fetched = mockManifestResponse(manifest)
    const { publishedSnapshot } = await loadWithBase(undefined)

    expect((await publishedSnapshot()).version).toBeNull()
    expect(fetched).not.toHaveBeenCalled()
  })
})

describe('one manifest read for everyone asking at once (#1302)', () => {
  const shared = {
    version: 'shared-v1',
    artifacts: { 'background.pmtiles': { sha256: 'B'.repeat(64) } },
  }

  // A launch with signal asked for the manifest from six places in the same
  // commit, and the bucket serves the manifest with `cache-control: no-cache`
  // (measured 2026-09-09 off production's own headers), so nothing deduped
  // them: six round trips on the connection the first frame was sharing.

  it('fetches once for callers that arrive together, and hands them all the same answer', async () => {
    const fetched = mockManifestResponse(shared)
    const { publishedSnapshot } = await loadWithBase(BASE)

    const [a, b, c] = await Promise.all([
      publishedSnapshot(),
      publishedSnapshot(),
      publishedSnapshot(),
    ])

    expect(fetched).toHaveBeenCalledTimes(1)
    expect(a.version).toBe(b.version)
    expect(b).toBe(c)
  })

  it('fetches again for a caller that arrives after the first read settled', async () => {
    // Sharing an IN-FLIGHT read is not caching. A hiker who comes back to the
    // app an hour later must be told about a release published in between,
    // which is the whole job of lib/dataRefresh.ts.
    const fetched = mockManifestResponse(shared)
    const { publishedSnapshot } = await loadWithBase(BASE)

    await publishedSnapshot()
    await publishedSnapshot()

    expect(fetched).toHaveBeenCalledTimes(2)
  })

  it('refuses a caller whose signal is already aborted, without fetching anything', async () => {
    const fetched = mockManifestResponse(shared)
    const { publishedSnapshot } = await loadWithBase(BASE)
    const controller = new AbortController()
    controller.abort()

    await expect(publishedSnapshot({ signal: controller.signal })).rejects.toThrow(
      'Aborted',
    )
    expect(fetched).not.toHaveBeenCalled()
  })

  it('rejects rather than hanging when the abort fires before its own listener is attached', async () => {
    // The shape lib/nearbyTrailData.ts drives, and the one that hung: the
    // fetch itself aborts the caller's controller, synchronously, in the same
    // turn the shared read is started - so the abort event has already been
    // dispatched by the time this caller has a listener for it. Settling
    // neither way is worse than the round trip the sharing saves.
    const { publishedSnapshot } = await loadWithBase(BASE)
    const controller = new AbortController()
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => {
      controller.abort()
      const error = new Error('aborted')
      error.name = 'AbortError'
      return Promise.reject(error)
    })

    await expect(publishedSnapshot({ signal: controller.signal })).rejects.toThrow(
      'Aborted',
    )
  })

  it('lets one caller abort without ending the read the others are waiting on', async () => {
    let answer: ((response: Response) => void) | undefined
    vi.spyOn(globalThis, 'fetch').mockImplementation(
      () =>
        new Promise<Response>((resolve) => {
          answer = resolve
        }),
    )
    const { publishedSnapshot } = await loadWithBase(BASE)
    const controller = new AbortController()

    const aborted = publishedSnapshot({ signal: controller.signal })
    const patient = publishedSnapshot()
    // Swallowed here so the rejection below is not unhandled while the other
    // caller is still waiting.
    const abortedSettled = expect(aborted).rejects.toThrow('Aborted')
    controller.abort()
    await abortedSettled

    answer?.(new Response(JSON.stringify(shared)))

    expect((await patient).version).toBe(shared.version)
  })
})
