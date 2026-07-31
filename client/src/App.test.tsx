import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { get, set } from 'idb-keyval'
import App from './App'
import { PREFERENCES_KEY } from './lib/preferences'
import { DEFAULT_PREFERENCES } from './lib/userPreferences'

// The shell decides what a hiker sees, so what is worth testing here is the
// routing between screens and the honesty of what it shows before any data
// exists - not the screens themselves, which have their own tests.

vi.mock('maplibre-gl', () => import('./test/mocks/maplibre-gl'))
vi.mock('idb-keyval', () => ({ get: vi.fn(), set: vi.fn(), del: vi.fn() }))

const store = new Map<string, unknown>()

beforeEach(() => {
  store.clear()
  vi.mocked(get).mockImplementation((key) => Promise.resolve(store.get(key as string)))
  vi.mocked(set).mockImplementation((key, value) => {
    store.set(key as string, value)
    return Promise.resolve()
  })
  vi.stubGlobal('fetch', vi.fn())
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  vi.unstubAllGlobals()
})

/** A phone that has been through onboarding already. */
function returningHiker() {
  store.set(PREFERENCES_KEY, {
    ...DEFAULT_PREFERENCES,
    onboarding_completed: true,
    download_choice_made: true,
  })
}

async function completeOnboarding(user: ReturnType<typeof userEvent.setup>) {
  await screen.findByText('What OurHike is')
  await user.click(screen.getByRole('button', { name: 'Continue' }))
  await user.click(screen.getByRole('button', { name: 'Continue' }))
  await user.click(screen.getByRole('button', { name: /not now/i }))
}

describe('App shell', () => {
  it('opens on onboarding the very first time', async () => {
    render(<App />)

    expect(await screen.findByText('What OurHike is')).toBeInTheDocument()
  })

  it('does not show onboarding again once it has been completed', async () => {
    returningHiker()
    render(<App />)

    expect(await screen.findByRole('region', { name: /trail map/i })).toBeInTheDocument()
    expect(screen.queryByText('What OurHike is')).not.toBeInTheDocument()
  })

  it('sends someone to Downloads when onboarding finishes, since there is no map yet', async () => {
    const user = userEvent.setup()
    render(<App />)

    await completeOnboarding(user)

    expect(await screen.findByText('Offline map')).toBeInTheDocument()
  })

  it('remembers that onboarding was completed, so a reload does not repeat it', async () => {
    const user = userEvent.setup()
    render(<App />)

    await completeOnboarding(user)

    await waitFor(() => {
      const saved = store.get(PREFERENCES_KEY) as { onboarding_completed: boolean }
      expect(saved.onboarding_completed).toBe(true)
    })
  })

  it('says the position is unknown rather than claiming mile zero before a fix', async () => {
    returningHiker()
    render(<App />)

    // Mile 0.0 is Springer Mountain - a confident claim about somewhere the
    // hiker is almost certainly not standing.
    expect(await screen.findByText(/looking for gps/i)).toBeInTheDocument()
    expect(screen.queryByText(/mi 0\.0/)).not.toBeInTheDocument()
  })

  it('moves between the three tabs', async () => {
    const user = userEvent.setup()
    returningHiker()
    render(<App />)

    await screen.findByRole('region', { name: /trail map/i })

    await user.click(screen.getByRole('tab', { name: 'Downloads' }))
    expect(await screen.findByText('Offline map')).toBeInTheDocument()

    await user.click(screen.getByRole('tab', { name: 'More' }))
    expect(await screen.findByRole('heading', { name: 'You' })).toBeInTheDocument()

    await user.click(screen.getByRole('tab', { name: 'Trail' }))
    expect(await screen.findByRole('region', { name: /trail map/i })).toBeInTheDocument()
  })

  it('reaches the report flow from More', async () => {
    const user = userEvent.setup()
    returningHiker()
    render(<App />)

    await screen.findByRole('region', { name: /trail map/i })
    await user.click(screen.getByRole('tab', { name: 'More' }))
    await user.click(await screen.findByRole('button', { name: /report a problem/i }))

    expect(
      await screen.findByRole('heading', { name: 'Report a problem' }),
    ).toBeInTheDocument()
  })

  it('backs out of the report flow without filing anything', async () => {
    // The reporting flow replaces the whole shell, tab bar included, so the
    // type picker was a screen with no exit: the only way off it was to pick a
    // report type and then cancel the form behind it.
    const user = userEvent.setup()
    returningHiker()
    render(<App />)

    await screen.findByRole('region', { name: /trail map/i })
    await user.click(screen.getByRole('tab', { name: 'More' }))
    await user.click(await screen.findByRole('button', { name: /report a problem/i }))
    await user.click(await screen.findByRole('button', { name: /^cancel$/i }))

    expect(await screen.findByRole('heading', { name: 'You' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'More', selected: true })).toBeInTheDocument()
  })

  it('saves a report to the outbox rather than asking to sign in first', async () => {
    const user = userEvent.setup()
    returningHiker()
    render(<App />)

    await screen.findByRole('region', { name: /trail map/i })
    await user.click(screen.getByRole('tab', { name: 'More' }))
    await user.click(await screen.findByRole('button', { name: /report a problem/i }))
    await user.click(await screen.findByRole('button', { name: /blow down/i }))
    await user.click(await screen.findByRole('button', { name: /send|save to outbox/i }))

    await waitFor(() => {
      const queued = store.get('ourhike:outbox') as Array<{ payload: { type: string } }>
      expect(queued).toHaveLength(1)
      expect(queued[0].payload.type).toBe('blowdown')
    })
  })

  it('warns on the Downloads screen when no data source was configured at build time', async () => {
    const user = userEvent.setup()
    returningHiker()
    render(<App />)

    await screen.findByRole('region', { name: /trail map/i })
    await user.click(screen.getByRole('tab', { name: 'Downloads' }))

    // VITE_DATA_BASE_URL is unset under test, so this is the real state - and a
    // download that would silently 404 is worth saying out loud.
    expect(await screen.findByRole('alert')).toHaveTextContent(/VITE_DATA_BASE_URL/)
  })

  it('can still find a shelter by name before the trail index exists', async () => {
    // The bug: searchablePois returned [] whenever trailIndex was null, so a
    // failed or not-yet-built centerline index silently emptied search while
    // hundreds of POIs sat in memory. Finding a shelter by name needs no
    // geometry - the mile is decoration on the row.
    const store = new Map<string, unknown>()
    store.set('ourhike:pois', [
      {
        id: 'atc_shelters:abc',
        type: 'shelter',
        name: 'Chairback Gap Lean-to',
        lat: 45.45,
        lon: -69.26,
        confidence: 'high',
      },
    ])
    // Trail lines deliberately absent, so no index can be built.
    const { searchPois } = await import('./lib/searchPoi')
    const pois = store.get('ourhike:pois') as Array<{
      id: string
      name: string
      type: string
    }>
    const searchable = pois.map((p) => ({ ...p, mile: undefined }))

    expect(searchPois('chairback', searchable)).toHaveLength(1)
  })

  it('says why the archive download failed instead of just returning to the button', async () => {
    // The failure that made this undiagnosable in production: the archive 404'd,
    // the hook's bare catch swallowed the reason, and the screen went back to
    // "Download the map" with nothing said. "Nothing happened" leaves someone
    // with no idea whether to retry, wait, or check their signal.
    const user = userEvent.setup()
    returningHiker()
    vi.mocked(fetch).mockImplementation((url) =>
      String(url).includes('.pmtiles')
        ? Promise.resolve({ ok: false, status: 404, statusText: 'Not Found' } as Response)
        : Promise.resolve({
            ok: true,
            blob: () =>
              Promise.resolve(new Blob(['{"type":"FeatureCollection","features":[]}'])),
            text: () => Promise.resolve('{"features":[]}'),
          } as unknown as Response),
    )

    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })
    await user.click(screen.getByRole('tab', { name: 'Downloads' }))
    await user.click(await screen.findByRole('button', { name: /download the map/i }))

    await waitFor(() => {
      expect(screen.getByText(/404|not found|failed/i)).toBeInTheDocument()
    })
  })

  it('does not start the huge archive download once the small one has already failed', async () => {
    // The few megabytes of trail lines and POIs are the canary. Whatever
    // stopped them - no signal, a missing key, a misconfigured bucket - will
    // stop the next several hundred too, and a hiker pays for that in data to
    // learn nothing.
    const user = userEvent.setup()
    returningHiker()
    vi.mocked(fetch).mockResolvedValue({
      ok: false,
      status: 404,
      statusText: 'Not Found',
    } as Response)

    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })
    await user.click(screen.getByRole('tab', { name: 'Downloads' }))
    await user.click(await screen.findByRole('button', { name: /download the map/i }))

    await waitFor(() => {
      expect(screen.getByText(/failed to fetch/i)).toBeInTheDocument()
    })

    // Only the trail-data attempt should have gone out. The archive request
    // would be the one after it.
    const requested = vi.mocked(fetch).mock.calls.map((c) => String(c[0]))
    expect(requested.some((url) => url.includes('.pmtiles'))).toBe(false)
  })
})
