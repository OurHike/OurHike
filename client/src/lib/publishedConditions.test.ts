import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

// The published conditions baselines (#435 closures, #436 reports).
// Everything here turns on the same distinction lib/dataManifest.test.ts
// records: `null` means "no usable baseline", never "no conditions" - the two
// are opposite answers and the whole point of this path is that a hiker can
// tell them apart.
//
// config.ts reads VITE_DATA_BASE_URL once at module load and it is unset under
// test, so each case imports the module fresh against a stubbed env - which is
// also the only way to cover "no bucket configured at all".

const BASE = 'https://cdn.example.org'

async function loadWithBase(base: string | undefined) {
  vi.resetModules()
  vi.stubEnv('VITE_DATA_BASE_URL', base ?? '')
  return await import('./publishedConditions')
}

function mockResponse(body: unknown, { status = 200 } = {}) {
  return vi
    .spyOn(globalThis, 'fetch')
    .mockImplementation(
      async () =>
        new Response(typeof body === 'string' ? body : JSON.stringify(body), { status }),
    )
}

const A_CLOSURES_DOCUMENT = {
  generated_at: '2026-08-08T06:00:00Z',
  closures: [{ id: 'c1', start_mile_marker: 10, end_mile_marker: 11 }],
}

const A_REPORTS_DOCUMENT = {
  generated_at: '2026-08-08T06:00:00Z',
  reports: [{ id: 'r1', type: 'blowdown', severity: 'serious', lat: 41.2, lon: -74.1 }],
}

beforeEach(() => {
  vi.clearAllMocks()
})

afterEach(() => {
  vi.unstubAllEnvs()
  vi.restoreAllMocks()
})

// The two baselines share one loader, so the failure handling is proven once,
// against whichever artifact the case reads most naturally with - and each
// artifact still gets its own happy path, because the key and the payload
// field are the two things that genuinely differ.

describe('fetchPublishedClosures', () => {
  it('reads the artifact from the configured bucket', async () => {
    const fetchSpy = mockResponse(A_CLOSURES_DOCUMENT)
    const { fetchPublishedClosures, PUBLISHED_CLOSURES_KEY } = await loadWithBase(BASE)

    const published = await fetchPublishedClosures()

    expect(fetchSpy).toHaveBeenCalledWith(
      `${BASE}/${PUBLISHED_CLOSURES_KEY}`,
      expect.anything(),
    )
    expect(published?.items).toHaveLength(1)
    expect(published?.generatedAt.toISOString()).toBe('2026-08-08T06:00:00.000Z')
  })

  it('asks for nothing when no bucket was configured at build time', async () => {
    const fetchSpy = mockResponse(A_CLOSURES_DOCUMENT)
    const { fetchPublishedClosures } = await loadWithBase(undefined)

    expect(await fetchPublishedClosures()).toBeNull()
    expect(fetchSpy).not.toHaveBeenCalled()
  })

  it('returns null rather than throwing when the bucket is unreachable', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('offline'))
    const { fetchPublishedClosures } = await loadWithBase(BASE)

    await expect(fetchPublishedClosures()).resolves.toBeNull()
  })

  it('returns null on a 404, which is what a release built before this artifact looks like', async () => {
    mockResponse('', { status: 404 })
    const { fetchPublishedClosures } = await loadWithBase(BASE)

    expect(await fetchPublishedClosures()).toBeNull()
  })

  it('returns null on a document that is not JSON', async () => {
    mockResponse('<!doctype html>')
    const { fetchPublishedClosures } = await loadWithBase(BASE)

    expect(await fetchPublishedClosures()).toBeNull()
  })

  it('refuses a document with no generated_at, rather than defaulting one', async () => {
    // The strict case, and the only one. That timestamp is what becomes
    // "as of <date>" - without it the app would show day-old closures with no
    // sign of their age, which is the failure this path exists to remove.
    mockResponse({ closures: [] })
    const { fetchPublishedClosures } = await loadWithBase(BASE)

    expect(await fetchPublishedClosures()).toBeNull()
  })

  it('refuses a document whose generated_at is not a date', async () => {
    mockResponse({ generated_at: 'whenever', closures: [] })
    const { fetchPublishedClosures } = await loadWithBase(BASE)

    expect(await fetchPublishedClosures()).toBeNull()
  })

  it('refuses a document whose closures are not a list', async () => {
    mockResponse({ generated_at: '2026-08-08T06:00:00Z', closures: 'none' })
    const { fetchPublishedClosures } = await loadWithBase(BASE)

    expect(await fetchPublishedClosures()).toBeNull()
  })

  it('accepts an empty list, which is a real answer and not a failure', async () => {
    // The state of the bucket the day this shipped: the bake ran, read zero
    // verified closures, and published exactly that. Treating it as a failure
    // would fall back to "unavailable" and tell a hiker we could not ask,
    // when in fact we asked and the trail is open.
    mockResponse({ generated_at: '2026-08-08T06:00:00Z', closures: [] })
    const { fetchPublishedClosures } = await loadWithBase(BASE)

    const published = await fetchPublishedClosures()

    expect(published).not.toBeNull()
    expect(published?.items).toEqual([])
  })
})

describe('fetchPublishedReports', () => {
  it('reads its own artifact, under its own key', async () => {
    const fetchSpy = mockResponse(A_REPORTS_DOCUMENT)
    const { fetchPublishedReports, PUBLISHED_REPORTS_KEY } = await loadWithBase(BASE)

    const published = await fetchPublishedReports()

    expect(fetchSpy).toHaveBeenCalledWith(
      `${BASE}/${PUBLISHED_REPORTS_KEY}`,
      expect.anything(),
    )
    expect(published?.items).toHaveLength(1)
    expect(published?.generatedAt.toISOString()).toBe('2026-08-08T06:00:00.000Z')
  })

  it('refuses a document whose payload is under the wrong name', async () => {
    // A closures document served where reports were expected - a bucket
    // misconfiguration, or a copy-paste in the bake. Validating the field by
    // name turns it into "no usable baseline" rather than an empty trail.
    mockResponse(A_CLOSURES_DOCUMENT)
    const { fetchPublishedReports } = await loadWithBase(BASE)

    expect(await fetchPublishedReports()).toBeNull()
  })

  it('accepts an empty list, which is a real answer and not a failure', async () => {
    mockResponse({ generated_at: '2026-08-08T06:00:00Z', reports: [] })
    const { fetchPublishedReports } = await loadWithBase(BASE)

    const published = await fetchPublishedReports()

    expect(published).not.toBeNull()
    expect(published?.items).toEqual([])
  })
})

// The third artifact (features/ATC_TRAIL_UPDATES.md, #461). Its own key and
// its own payload name like the other two, plus the one field neither of them
// has: `reviewed_at`, which is when a PERSON last checked ATC's page rather
// than when the bake ran. Both are real, they differ, and a daily bake
// stamping a daily `generated_at` on a three-month-old review would claim a
// freshness nobody has.

const AN_ATC_UPDATES_DOCUMENT = {
  generated_at: '2026-08-12T08:40:00Z',
  reviewed_at: '2026-08-12',
  atc_updates: [
    {
      atc_id: 'va-creeper-trail-closure-detour',
      title: 'SW Virginia: VA Creeper Trail Closure/Detour',
      category: 'Closure',
      states: ['VA'],
      start_mile_marker: 476.6,
      end_mile_marker: 485.8,
      obstructs_trail: true,
      updated_at: '2026-07-17T00:00:00Z',
      source_url: 'https://appalachiantrail.org/trail-updates/va-creeper/',
    },
  ],
}

describe('fetchPublishedAtcUpdates', () => {
  it('reads its own artifact, under its own key', async () => {
    const fetchSpy = mockResponse(AN_ATC_UPDATES_DOCUMENT)
    const { fetchPublishedAtcUpdates, PUBLISHED_ATC_UPDATES_KEY } =
      await loadWithBase(BASE)

    const published = await fetchPublishedAtcUpdates()

    expect(fetchSpy).toHaveBeenCalledWith(
      `${BASE}/${PUBLISHED_ATC_UPDATES_KEY}`,
      expect.anything(),
    )
    expect(published?.items).toHaveLength(1)
  })

  it('carries the review date alongside the bake date', async () => {
    mockResponse(AN_ATC_UPDATES_DOCUMENT)
    const { fetchPublishedAtcUpdates } = await loadWithBase(BASE)

    const published = await fetchPublishedAtcUpdates()

    expect(published?.generatedAt.toISOString()).toBe('2026-08-12T08:40:00.000Z')
    expect(published?.reviewedAt?.toISOString()).toBe('2026-08-12T00:00:00.000Z')
  })

  it('still reads a document that has no review date', async () => {
    // Lenient where `generated_at` is strict, because the two carry different
    // weight: a missing review date costs a line of provenance on a sheet,
    // not the age of the data.
    mockResponse({ generated_at: '2026-08-12T08:40:00Z', atc_updates: [] })
    const { fetchPublishedAtcUpdates } = await loadWithBase(BASE)

    const published = await fetchPublishedAtcUpdates()

    expect(published).not.toBeNull()
    expect(published?.reviewedAt).toBeUndefined()
  })

  it('drops an unparseable review date rather than carrying an Invalid Date', async () => {
    mockResponse({ ...AN_ATC_UPDATES_DOCUMENT, reviewed_at: 'sometime in May' })
    const { fetchPublishedAtcUpdates } = await loadWithBase(BASE)

    expect((await fetchPublishedAtcUpdates())?.reviewedAt).toBeUndefined()
  })

  it('answers null for the 404 served while nobody has reviewed the file', async () => {
    // The pipeline publishes nothing at all in that state, deliberately: "we
    // have not looked" and "ATC reports nothing" are different claims, and
    // only one of them is safe to draw as an empty map.
    mockResponse('', { status: 404 })
    const { fetchPublishedAtcUpdates } = await loadWithBase(BASE)

    expect(await fetchPublishedAtcUpdates()).toBeNull()
  })

  it('refuses a document whose payload is under the wrong name', async () => {
    mockResponse(A_CLOSURES_DOCUMENT)
    const { fetchPublishedAtcUpdates } = await loadWithBase(BASE)

    expect(await fetchPublishedAtcUpdates()).toBeNull()
  })

  it('accepts an empty list, which a reviewer can honestly produce', async () => {
    // "We looked, and ATC has nothing placeable" - the reviewed-but-empty
    // case, which is a real answer and distinct from the 404 above.
    mockResponse({
      generated_at: '2026-08-12T08:40:00Z',
      reviewed_at: '2026-08-12',
      atc_updates: [],
    })
    const { fetchPublishedAtcUpdates } = await loadWithBase(BASE)

    const published = await fetchPublishedAtcUpdates()

    expect(published).not.toBeNull()
    expect(published?.items).toEqual([])
  })
})

// NYNJTC's alerts are the first notices from an organization that is not the
// ATC, and the document shape differs in the two ways features/ORG_NOTICES.md
// argues for: there is no `reviewed_at` (nobody has reviewed their page, and
// stamping the bake's clock as a review date would claim a review that never
// happened), and location is a tagged `place` rather than two mile columns.

const A_NYNJTC_ALERTS_DOCUMENT = {
  generated_at: '2026-08-27T02:20:00Z',
  nynjtc_alerts: [
    {
      notice_id: 'nynjtc_trail_alerts:a-t-detour-at-harriman-state-park',
      source_key: 'nynjtc_trail_alerts',
      title: 'A.T. Detour at Harriman State Park',
      category: null,
      locality: 'Harriman-Bear Mountain',
      place: { kind: 'unplaced' },
      obstructs_trail: false,
      updated_at: '2026-06-16T14:37:46Z',
      source_url:
        'https://www.nynjtc.org/trail-alerts/a-t-detour-at-harriman-state-park/',
      review_state: 'unreviewed',
    },
  ],
}

describe('fetchPublishedNynjtcAlerts', () => {
  it('reads its own artifact, under its own key', async () => {
    const fetchSpy = mockResponse(A_NYNJTC_ALERTS_DOCUMENT)
    const { fetchPublishedNynjtcAlerts, PUBLISHED_NYNJTC_ALERTS_KEY } =
      await loadWithBase(BASE)

    const published = await fetchPublishedNynjtcAlerts()

    expect(fetchSpy).toHaveBeenCalledWith(
      `${BASE}/${PUBLISHED_NYNJTC_ALERTS_KEY}`,
      expect.anything(),
    )
    expect(published?.items).toHaveLength(1)
  })

  it('carries the bake date and no review date, because nobody has reviewed', async () => {
    mockResponse(A_NYNJTC_ALERTS_DOCUMENT)
    const { fetchPublishedNynjtcAlerts } = await loadWithBase(BASE)

    const published = await fetchPublishedNynjtcAlerts()

    expect(published?.generatedAt.toISOString()).toBe('2026-08-27T02:20:00.000Z')
    expect(published?.reviewedAt).toBeUndefined()
  })

  it('keeps the notice unplaced and unreviewed rather than defaulting either', async () => {
    // The two rails features/ORG_NOTICES.md bolts on until the thing that
    // would remove them exists. A reader that quietly defaulted `place` to a
    // mile range, or `review_state` to reviewed, would draw a notice nobody
    // has checked onto ground nobody has joined it to.
    mockResponse(A_NYNJTC_ALERTS_DOCUMENT)
    const { fetchPublishedNynjtcAlerts } = await loadWithBase(BASE)

    const notice = (await fetchPublishedNynjtcAlerts())?.items[0]

    expect(notice?.place).toEqual({ kind: 'unplaced' })
    expect(notice?.review_state).toBe('unreviewed')
    expect(notice?.obstructs_trail).toBe(false)
  })

  it('reads a null category as absent rather than as a word', async () => {
    // NYNJTC publishes no per-alert vocabulary, so there is nothing true to
    // put there. A renderer shows the title alone; it must not borrow ATC's.
    mockResponse(A_NYNJTC_ALERTS_DOCUMENT)
    const { fetchPublishedNynjtcAlerts } = await loadWithBase(BASE)

    expect((await fetchPublishedNynjtcAlerts())?.items[0].category).toBeNull()
  })

  it('is null when the bucket has no artifact, which is what an unrun fetch looks like', async () => {
    mockResponse('', { status: 404 })
    const { fetchPublishedNynjtcAlerts } = await loadWithBase(BASE)

    expect(await fetchPublishedNynjtcAlerts()).toBeNull()
  })
})
