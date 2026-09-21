import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from './App'
import { appHarness } from './test/appHarness'

// WHAT THE SHELL DOES WITH A SIGN-IN REFUSED AT GOOGLE OR GITHUB (#1573).
//
// THE DEFECT THESE EXIST FOR, and it is a silence rather than a wrong
// answer, which is why nothing went red for it. `signInWithProvider` is a
// full off-origin navigation: the tab leaves, and when the round trip fails
// Supabase redirects back to `/app/` with `#error=access_denied&…` on the
// URL. supabase-js reads that inside `GoTrueClient._initialize()`, which
// nothing in this app awaits and which fires no `onAuthStateChange` - so the
// hiker landed on the map, signed out, with the window shut and no sentence
// anywhere. Every other sign-in failure has said something out loud since
// #279 (#397's acceptance is that none of them stays quiet).
//
// Its own file, not a `describe` in App.flows.test.tsx, because the subject
// is what the shell does with the URL IT LOADED WITH - so the fragment has
// to be on `window.location` before `render(<App />)`, which is a per-test
// arrangement rather than a per-suite one.

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

const app = appHarness()

/** Put a returned-to URL in the address bar the way a redirect would, and
 *  take it off again afterwards - jsdom's `location` is shared by every test
 *  in the file, so a fragment left behind would open this window in the
 *  next one. `replaceState` rather than assigning `location.hash`, so the
 *  test's own arrangement does not add the history entry the code under test
 *  is careful not to add. */
function returnedOn(fragment: string): void {
  window.history.replaceState(null, '', `/${fragment}`)
}

beforeEach(() => {
  returnedOn('')
})

afterEach(() => {
  returnedOn('')
})

describe('landing back from a refused sign-in', () => {
  it('re-opens the ask with the reason above the doors', async () => {
    returnedOn(
      '#error=access_denied&error_code=403&error_description=The+user+denied+the+request',
    )
    app.onboard()
    app.putTrailData()

    render(<App />)

    // Named "Sign in" rather than "One thing first": the round trip reloaded
    // the page, so nothing survives that could say this hiker was part-way
    // through filing a report, and promising that one is saved would be a
    // claim about something this shell cannot see.
    const window_ = await screen.findByRole('dialog', { name: 'Sign in' })
    expect(window_).toBeInTheDocument()
    expect(await screen.findByRole('alert')).toHaveTextContent(/was not finished/i)
    expect(screen.queryByText(/already saved on your phone/i)).toBe(null)
  })

  it('takes the refusal off the address bar, so a reload does not repeat it', async () => {
    returnedOn('#error=access_denied&error_code=403')
    app.onboard()
    app.putTrailData()

    render(<App />)
    await screen.findByRole('dialog', { name: 'Sign in' })

    expect(window.location.hash).toBe('')
  })

  it('forgets the reason once the window is dismissed', async () => {
    // The sentence lives on the flow state and dies with it, which is what
    // stops a refusal from an hour ago greeting somebody who opens the ask
    // from the account button. A `useState` of its own would need this
    // written out at three call sites and would be one missed call away from
    // a stale sentence.
    const user = userEvent.setup()
    returnedOn('#error=access_denied')
    app.onboard()
    app.putTrailData()

    render(<App />)
    await screen.findByRole('dialog', { name: 'Sign in' })
    await user.click(screen.getByRole('button', { name: /not now/i }))

    expect(screen.queryByRole('dialog', { name: 'Sign in' })).toBe(null)

    await user.click(screen.getByRole('button', { name: /^Sign in$/ }))

    await screen.findByRole('dialog', { name: 'Sign in' })
    expect(screen.queryByRole('alert')).toBe(null)
  })
})

describe('landing on an ordinary URL', () => {
  it('opens no sign-in window, which is nearly every launch', async () => {
    app.onboard()
    app.putTrailData()

    render(<App />)
    await screen.findByRole('button', { name: /^Sign in$/ })

    expect(screen.queryByRole('dialog', { name: 'Sign in' })).toBe(null)
  })

  it('opens none for the fragment a SUCCESSFUL sign-in comes back on either', async () => {
    // The mirror-image defect, and the cheaper one to ship: an alert in
    // front of somebody who just signed in fine. supabase-js reads and
    // clears this fragment itself.
    returnedOn('#access_token=fake.jwt.value&expires_in=3600&token_type=bearer')
    app.onboard()
    app.putTrailData()

    render(<App />)
    await screen.findByRole('button', { name: /^Sign in$/ })

    expect(screen.queryByRole('dialog', { name: 'Sign in' })).toBe(null)
  })
})
