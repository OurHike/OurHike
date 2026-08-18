// The identity step, which existed on paper and nowhere on screen (#233).
//
// `lib/contributionFlow.ts`'s `stepAfterSaving()` has returned 'identity'
// since the flow was designed, `screens/IdentitySetup.tsx` was built and fully
// tested for it, and App.tsx imported neither - so the branch ended the flow
// the way it already ended and every report went out signed `thru`.
//
// Its own file because these need an ACCOUNT: the step sits after sign-in
// (a trail name belongs to a profile), so a shell with no session never
// reaches it. Mocking `lib/useAuth` here rather than in App.flows.test.tsx
// keeps every other flow test running as the signed-out hiker it was written
// for.

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from './App'
import { appHarness } from './test/appHarness'
import { PREFERENCES_KEY } from './lib/preferences'

vi.mock('maplibre-gl', () => import('./test/mocks/maplibre-gl'))
vi.mock('idb-keyval', () => ({
  get: vi.fn(),
  set: vi.fn(),
  del: vi.fn(),
  update: vi.fn(),
}))
vi.mock('./lib/useAuth', () => ({
  useAccount: () => ({ email: 'hiker@example.com' }),
}))

const app = appHarness({ navigator: { onLine: true }, objectUrls: true })
const store = app.store

beforeEach(() => {
  app.onboard()
  app.putTrailData({ miles: 20 })
})

async function fileAReport(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole('tab', { name: 'Settings' }))
  await user.click(await screen.findByRole('button', { name: /report a problem/i }))
  await user.click(await screen.findByRole('button', { name: /blow down/i }))
  await user.click(await screen.findByRole('button', { name: /send|save to outbox/i }))
}

function queued() {
  return (store.get('ourhike:outbox') ?? []) as Array<{
    payload: { reporter_type?: string }
  }>
}

describe('asking who is reporting', () => {
  it('mounts the screen the flow has always routed to', async () => {
    const user = userEvent.setup()
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await fileAReport(user)

    expect(
      await screen.findByRole('heading', { name: /how should reports be signed/i }),
    ).toBeInTheDocument()
  })

  it('signs the next report with the answer, and remembers it', async () => {
    const user = userEvent.setup()
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await fileAReport(user)
    await screen.findByRole('heading', { name: /how should reports be signed/i })
    await user.click(screen.getByRole('radio', { name: /section hiker/i }))
    await user.click(screen.getByRole('button', { name: /save|done|continue/i }))

    await waitFor(() => {
      const saved = store.get(PREFERENCES_KEY) as { reporter_type?: string }
      expect(saved.reporter_type).toBe('section')
    })

    await fileAReport(user)

    await waitFor(() => expect(queued()).toHaveLength(2))
    expect(queued()[1].payload.reporter_type).toBe('section')
  })

  it('asks once a session, so a skip is not a question asked again', async () => {
    // Skipping writes nothing - inventing a type is the bug this closes - so
    // without the guard the screen returns on the very next report.
    const user = userEvent.setup()
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await fileAReport(user)
    await screen.findByRole('heading', { name: /how should reports be signed/i })
    await user.click(screen.getByRole('button', { name: /skip|not now/i }))

    await fileAReport(user)

    await waitFor(() => expect(queued()).toHaveLength(2))
    expect(
      screen.queryByRole('heading', { name: /how should reports be signed/i }),
    ).not.toBeInTheDocument()
  })

  it('does not ask a hiker who has already said', async () => {
    app.onboard({ reporter_type: 'maintainer' })
    const user = userEvent.setup()
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await fileAReport(user)

    await waitFor(() => expect(queued()).toHaveLength(1))
    expect(queued()[0].payload.reporter_type).toBe('maintainer')
    expect(
      screen.queryByRole('heading', { name: /how should reports be signed/i }),
    ).not.toBeInTheDocument()
  })
})
