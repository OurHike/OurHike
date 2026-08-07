import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from './App'
import { resetMapLibreMock } from './test/mocks/maplibre-gl'
import { PREFERENCES_KEY } from './lib/preferences'
import { DEFAULT_PREFERENCES } from './lib/userPreferences'
import { get, set } from 'idb-keyval'

// A throw anywhere in the More screen used to escape to the ROOT boundary -
// the one with no tab bar and no reset - so one bad render of Settings was a
// permanently dead app, offline, with the map a tap away the whole time. The
// More branch has its own boundary now, and these tests are that boundary's
// teeth: the tab bar survives, and the trail tab still leads to the map.
//
// Its own file rather than a describe in App.test.tsx because the way to make
// More throw deterministically is to mock the module, and a module mock is
// file-wide - App.test.tsx needs the real one.

vi.mock('maplibre-gl', () => import('./test/mocks/maplibre-gl'))
vi.mock('idb-keyval', () => ({ get: vi.fn(), set: vi.fn(), del: vi.fn() }))
vi.mock('./map/archiveZooms', () => ({
  readArchiveZooms: () => Promise.resolve(null),
}))
vi.mock('./screens/More', () => ({
  More: () => {
    throw new Error('a stored value this screen cannot render')
  },
}))

const store = new Map<string, unknown>()

beforeEach(() => {
  store.clear()
  resetMapLibreMock()
  vi.mocked(get).mockImplementation((key) => Promise.resolve(store.get(key as string)))
  vi.mocked(set).mockImplementation((key, value) => {
    store.set(key as string, value)
    return Promise.resolve()
  })
  vi.stubGlobal('fetch', vi.fn())
  store.set(PREFERENCES_KEY, {
    ...DEFAULT_PREFERENCES,
    onboarding_completed: true,
    download_choice_made: true,
  })
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  vi.unstubAllGlobals()
})

describe('a More screen that throws', () => {
  it('keeps the tab bar, so the map stays one tap away', async () => {
    const user = userEvent.setup()
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await user.click(screen.getByRole('tab', { name: 'More' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/stopped working/i)
    expect(screen.getByRole('tab', { name: 'Trail' })).toBeInTheDocument()
  })

  it('still reaches the map from the fallback', async () => {
    const user = userEvent.setup()
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await user.click(screen.getByRole('tab', { name: 'More' }))
    await screen.findByRole('alert')
    await user.click(screen.getByRole('tab', { name: 'Trail' }))

    expect(await screen.findByRole('region', { name: /trail map/i })).toBeInTheDocument()
  })
})
