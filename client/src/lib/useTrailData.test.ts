// What a cold launch is allowed to put on the wire, and in what order (#1117).
//
// WHY THIS IS A HOOK TEST AND NOT A TIMING ONE
//
// The defect was measured with a real throttled Chromium against the real
// published artifacts - `trail_graph.json` opening at 1,524 ms and
// `nearby_trails.geojson` at 2,612 ms, alongside a `trails.geojson` that did
// not land until 20,267 ms of a 32,325 ms launch. None of that is assertable
// here: jsdom has no network stack worth the name, and a millisecond budget
// tuned on one machine is the flaky test CLAUDE.md warns about.
//
// What IS assertable, exactly, is the RULE those milliseconds came from:
// neither background artifact may be asked for while the trail line is still
// coming. So this counts calls and the order they happen in, which is
// deterministic on a machine of any speed.
//
// Every wait below is on something observable - a mock having been called, a
// deferred promise having been resolved by the test itself - rather than on a
// timer, because the whole subject is a sequence and a test that guesses at
// one cannot tell "not yet" from "never".

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'

vi.mock('./config', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./config')>()),
  DATA_BASE_URL: 'https://data.example',
  DATA_CONFIGURED: true,
  dataUrl: (key: string) => `https://data.example/${key}`,
}))

vi.mock('./trailData', () => ({
  downloadTrailData: vi.fn(),
  haveTrailData: vi.fn(),
  loadTrailData: vi.fn(),
  loadTrailLines: vi.fn(),
  TrailDataHashMismatchError: class extends Error {},
}))
vi.mock('./nearbyTrailData', () => ({ loadNearbyTrails: vi.fn() }))
vi.mock('./trailGraphData', () => ({
  loadTrailGraph: vi.fn(),
  isSettledAbsence: () => false,
}))
vi.mock('./trailOverview', () => ({ fetchTrailOverview: vi.fn() }))
vi.mock('./dataManifest', () => ({ publishedSnapshot: vi.fn() }))
vi.mock('./dataRefresh', () => ({
  availableRefresh: () => null,
  dismissRelease: vi.fn(),
  dismissedRelease: vi.fn(),
  recallRelease: vi.fn(),
  warnsAboutData: () => false,
}))

const { downloadTrailData, haveTrailData, loadTrailData, loadTrailLines } =
  await import('./trailData')
const { loadNearbyTrails } = await import('./nearbyTrailData')
const { loadTrailGraph } = await import('./trailGraphData')
const { fetchTrailOverview } = await import('./trailOverview')
const { publishedSnapshot } = await import('./dataManifest')
const { recallRelease } = await import('./dataRefresh')
const { useTrailData } = await import('./useTrailData')

/** A promise this test resolves by hand, so "the trail fetch is still in
 *  flight" is a state the assertions can stand in rather than race. */
function deferred<T>() {
  let settle!: (value: T) => void
  let fail!: (reason: unknown) => void
  const promise = new Promise<T>((resolve, reject) => {
    settle = resolve
    fail = reject
  })
  return { promise, settle, fail }
}

beforeEach(() => {
  vi.stubGlobal('URL', {
    ...URL,
    createObjectURL: vi.fn(() => 'blob:trails'),
    revokeObjectURL: vi.fn(),
  })
  vi.mocked(loadTrailLines).mockResolvedValue(null)
  vi.mocked(loadTrailData).mockResolvedValue({
    pois: [],
    spurs: {},
    elevation: null,
    clubSections: { sections: [] },
    stewards: { stewards: [] },
    highlights: [],
    retiredPois: { ids: [] },
  } as never)
  vi.mocked(fetchTrailOverview).mockResolvedValue(null)
  vi.mocked(publishedSnapshot).mockResolvedValue({} as never)
  vi.mocked(recallRelease).mockResolvedValue(null)
  vi.mocked(loadNearbyTrails).mockResolvedValue(null)
  vi.mocked(loadTrailGraph).mockResolvedValue({
    kind: 'absent',
    because: 'missing',
  } as never)
})

afterEach(() => {
  vi.clearAllMocks()
  vi.unstubAllGlobals()
})

describe('a cold launch, with signal', () => {
  it('asks for neither background artifact while the trail line is still coming', async () => {
    const trailFetch = deferred<void>()
    vi.mocked(haveTrailData).mockResolvedValue(false)
    vi.mocked(downloadTrailData).mockReturnValue(trailFetch.promise)

    renderHook(() => useTrailData(true))

    // The observable that proves the sequence reached the point being
    // asserted: the launch fetch is genuinely in flight, not merely not
    // started yet. Without this the two expectations below would pass on a
    // render that had not run any effect at all.
    await waitFor(() => expect(downloadTrailData).toHaveBeenCalled())
    expect(loadNearbyTrails).not.toHaveBeenCalled()
    expect(loadTrailGraph).not.toHaveBeenCalled()

    trailFetch.settle()

    await waitFor(() => expect(loadNearbyTrails).toHaveBeenCalled())
    await waitFor(() => expect(loadTrailGraph).toHaveBeenCalled())
  })

  it('releases them when the trail line fails, rather than holding them forever', async () => {
    // The half that keeps the gate from being a trap. A phone whose trail
    // fetch died must behave exactly as it did before this rule existed -
    // otherwise one failed request costs the map its other organizations'
    // lines and the day-hike builder, permanently, with nothing on screen
    // explaining why.
    const trailFetch = deferred<void>()
    vi.mocked(haveTrailData).mockResolvedValue(false)
    vi.mocked(downloadTrailData).mockReturnValue(trailFetch.promise)

    renderHook(() => useTrailData(true))
    await waitFor(() => expect(downloadTrailData).toHaveBeenCalled())
    expect(loadNearbyTrails).not.toHaveBeenCalled()

    trailFetch.fail(new Error('the bucket refused this origin'))

    await waitFor(() => expect(loadNearbyTrails).toHaveBeenCalled())
    await waitFor(() => expect(loadTrailGraph).toHaveBeenCalled())
  })
})

describe('the launches that must not pay for the rule', () => {
  it('lets a warm phone through without waiting on any fetch', async () => {
    // `fetchOnce` returns after two small IndexedDB reads once a release is
    // on the phone, so the gate opens in milliseconds and a returning hiker
    // is charged nothing for it. Asserted as "downloadTrailData was never
    // called AND both ran", which is the warm launch exactly.
    vi.mocked(haveTrailData).mockResolvedValue(true)

    renderHook(() => useTrailData(true))

    await waitFor(() => expect(loadNearbyTrails).toHaveBeenCalled())
    await waitFor(() => expect(loadTrailGraph).toHaveBeenCalled())
    expect(downloadTrailData).not.toHaveBeenCalled()
  })

  it('reads the stored nearby lines with no signal, without waiting for anything', async () => {
    // Offline the gate is not applied at all, and that asymmetry is the
    // design: what waits is the 7.5 MB refetch, never the store read. A phone
    // on a ridge draws its last verified nearby lines on the first tick.
    vi.mocked(haveTrailData).mockResolvedValue(true)

    renderHook(() => useTrailData(false))

    await waitFor(() =>
      expect(loadNearbyTrails).toHaveBeenCalledWith(false, expect.anything()),
    )
    // The graph is a different case and stays one: offline it records
    // 'unreachable' rather than fetching, which is an answer the network
    // strip renders and not a request.
    expect(loadTrailGraph).not.toHaveBeenCalled()
  })
})
