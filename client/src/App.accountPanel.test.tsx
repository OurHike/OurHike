import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from './App'
import { appHarness, openMapTab } from './test/appHarness'
import { signOut } from './lib/auth'

// WHAT THE ACCOUNT BUTTON OPENS WHEN YOU ARE ALREADY SIGNED IN (#1596).
//
// Its own file because it needs the whole module mocked signed in, which is
// the arrangement App.outboxRetry.test.tsx uses and which a `describe` inside
// App.flows.test.tsx could not have without signing every other test in there
// in too.
//
// THE DEFECT THESE EXIST FOR. #1596 gave the button one glyph in two states
// and App.tsx handed `SignInPrompt` to the window in BOTH: signed in, the
// filled glyph offered "Continue with GitHub" for an account the hiker
// already had, and the one thing they came for - a way out - was not there.
// Sign-out was, and still is, on More -> You. `AccountButton.tsx` asserted
// the opposite in a docstring and `AccountButton.test.tsx` put that sentence
// in a test NAME while checking only that the opener fired, so nothing went
// red. The review of #1596 found it by reading the two together.

vi.mock('maplibre-gl', () => import('./test/mocks/maplibre-gl'))
vi.mock('idb-keyval', () => ({
  get: vi.fn(),
  getMany: vi.fn(),
  set: vi.fn(),
  setMany: vi.fn(),
  del: vi.fn(),
  update: vi.fn(),
}))
vi.mock('./map/archiveZooms', () => ({
  readArchiveZooms: () => Promise.resolve(null),
  readArchiveFootprint: () => Promise.resolve(null),
}))

const SIGNED_IN = { email: 'hiker@example.org' }

vi.mock('./lib/auth', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./lib/auth')>()),
  currentAccount: vi.fn(async () => SIGNED_IN),
  subscribeToAccount: (listener: (a: { email: string } | null) => void) => {
    listener(SIGNED_IN)
    return () => {}
  },
  signOut: vi.fn(async () => {}),
}))

const app = appHarness()

async function openTheAccountWindow(): Promise<void> {
  const user = userEvent.setup()
  app.onboard()
  app.putTrailData()
  render(<App />)
  await openMapTab()
  await screen.findByRole('region', { name: /trail map/i })
  await user.click(screen.getByRole('button', { name: /^Account, signed in as/ }))
}

describe('the account window, signed in', () => {
  it('says which account, and offers the way out rather than the way in', async () => {
    await openTheAccountWindow()

    // The window, named for what it is rather than for what it was.
    const panel = await screen.findByRole('dialog', { name: 'Your account' })
    expect(panel).toBeInTheDocument()
    // The address, because on a borrowed handset "whose account is this" is
    // the question the filled glyph raises and cannot answer.
    expect(screen.getByText(SIGNED_IN.email)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Sign out' })).toBeInTheDocument()

    // AND NOT THE ASK. This is the assertion the defect would fail: before
    // the panel existed, all three of these were on screen instead.
    expect(screen.queryByRole('button', { name: /^Continue with/ })).toBe(null)
  })

  it('signs out and closes, rather than leaving the sign-in ask under the finger', async () => {
    const user = userEvent.setup()
    await openTheAccountWindow()
    await screen.findByRole('dialog', { name: 'Your account' })

    await user.click(screen.getByRole('button', { name: 'Sign out' }))

    expect(vi.mocked(signOut)).toHaveBeenCalledTimes(1)
    // Closed, not re-rendered into the signed-out ask: App.tsx clears the
    // flow before the sign-out runs for exactly this reason, and a window
    // that swapped to "Continue with GitHub" under the tap would read as the
    // sign-out having failed and reopened the sign-in.
    expect(screen.queryByRole('dialog', { name: 'Your account' })).toBe(null)
    expect(screen.queryByRole('dialog', { name: 'Sign in' })).toBe(null)
  })
})
