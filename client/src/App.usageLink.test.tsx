import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import App from './App'
import { appHarness } from './test/appHarness'
import { noteSignInStarted } from './lib/signInMarker'
import { USAGE_KEY, type UsageStore } from './lib/usageQueue'

// "Link your usage to your account?" is asked after a sign-in this app
// started (#1902) - and only in a build that has somewhere to send the rows.
// With no API_BASE_URL (unset is what every build currently produces,
// .github/expected-settings.yml) lib/usageQueue.ts answers 'later' for every
// batch, so the question used to ask a hiker to link rows that never leave
// the phone. Counting is unchanged either way: the login row is recorded,
// and the question waits for a backend.

const config = vi.hoisted(() => ({ apiConfigured: true }))

vi.mock('maplibre-gl', () => import('./test/mocks/maplibre-gl'))
vi.mock('idb-keyval', () => ({
  get: vi.fn(),
  getMany: vi.fn(),
  set: vi.fn(),
  del: vi.fn(),
  update: vi.fn(),
}))
vi.mock('./map/archiveZooms', () => ({
  readArchiveZooms: () => Promise.resolve(null),
  readArchiveFootprint: () => Promise.resolve(null),
}))
vi.mock('./lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./lib/api')>()),
  // Read at render, so one file can hold both builds.
  get API_CONFIGURED() {
    return config.apiConfigured
  },
  accessToken: vi.fn(async () => null),
  fetchReports: vi.fn(async () => []),
  fetchClosures: vi.fn(async () => []),
  fetchFieldNotes: vi.fn(async () => []),
  fetchDisputes: vi.fn(async () => []),
  fetchMyProfile: vi.fn(async () => ({ id: 'p-1', role: 'hiker', display_name: null })),
  fetchMyVolunteerHours: vi.fn(async () => []),
}))
vi.mock('./lib/supportApi', () => ({
  fetchSupport: vi.fn(async () => null),
  chooseSupport: vi.fn(),
  stopSupport: vi.fn(),
  setSupportMail: vi.fn(),
  supportAccepting: vi.fn(async () => false),
}))
// The account is in from the first render, as it is on the page a provider's
// redirect lands on; the marker below is what makes it a finished sign-in
// rather than a restored session.
vi.mock('./lib/useAuth', () => ({
  useAccount: () => ({ email: 'hiker@example.org' }),
}))

const app = appHarness({ navigator: { onLine: true } })

const QUESTION = 'Link your usage to your account?'

beforeEach(() => {
  app.onboard()
  noteSignInStarted()
})

/** The usage rows on the phone, by event. */
function recorded(): string[] {
  const usage = app.store.get(USAGE_KEY) as UsageStore | undefined
  return (usage?.rows ?? []).map((queued) => queued.row.event)
}

describe('the usage-link question after a sign-in', () => {
  it('is asked in a build with a backend', async () => {
    config.apiConfigured = true
    render(<App />)

    expect(await screen.findByRole('heading', { name: QUESTION })).toBeInTheDocument()
  })

  it('is not asked in a build with no backend, though the sign-in is still counted', async () => {
    config.apiConfigured = false
    render(<App />)
    // The login row is written before the hook offers the question, in the
    // same run of the same effect (lib/useUsageMeasurement.ts, "sign-in"):
    // once it is in the store, whether the question was offered is decided.
    await waitFor(() => expect(recorded()).toContain('user_login'))

    expect(screen.queryByRole('heading', { name: QUESTION })).not.toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'More' })).toBeInTheDocument()
  })
})
