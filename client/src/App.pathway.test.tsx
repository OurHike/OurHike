import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from './App'
import { appHarness } from './test/appHarness'
import { HIKER_MODE_KEY } from './lib/hikerMode'

// The planning spine's front door and its exit (#1373, F3): step 1 is where
// the Plan tab's primary and Today's pinned Plan both land, the kind read off
// the mode and never asked (D2, D6); and once a builder is live, leaving the
// map by the bar is asked about, never assumed either way (D8).

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

beforeEach(() => {
  app.onboard()
  app.putTrailData()
})

async function openStepOne(user: ReturnType<typeof userEvent.setup>) {
  await user.click(
    within(await screen.findByRole('group', { name: 'Find or plan a hike' })).getByRole(
      'button',
      { name: 'Plan a hike' },
    ),
  )
  await screen.findByRole('heading', { name: 'Where do you want to go?' })
}

describe('step 1 of the spine', () => {
  it('is where Today’s pinned Plan lands, under the Plan tab, and Cancel is the way back', async () => {
    const user = userEvent.setup()
    render(<App />)

    await openStepOne(user)
    expect(screen.getByRole('tab', { name: 'Plan', selected: true })).toBeInTheDocument()
    expect(screen.getByRole('navigation', { name: 'Planning steps' })).toHaveTextContent(
      'Day hike',
    )
    // The retired kind sheet's question is not asked anywhere on the way.
    expect(screen.queryByText(/what are you planning/i)).toBeNull()

    await user.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(screen.queryByRole('heading', { name: 'Where do you want to go?' })).toBeNull()
    expect(screen.getByRole('tab', { name: 'Plan', selected: true })).toBeInTheDocument()
  })

  it('reads the mode: a long hiker’s step 1 opens the A.T. builder’s own door on the map', async () => {
    app.store.set(HIKER_MODE_KEY, 'long')
    const user = userEvent.setup()
    render(<App />)

    await openStepOne(user)
    expect(screen.getByRole('navigation', { name: 'Planning steps' })).toHaveTextContent(
      'Long hike',
    )
    await user.click(screen.getByRole('button', { name: 'Pick on the map' }))

    expect(await screen.findByText('Where from?')).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Map', selected: true })).toBeInTheDocument()
  })
})

describe('the bail sheet (D8)', () => {
  it('asks before a tab tap leaves a live builder; Stay stays, Discard drops the draft and goes', async () => {
    app.store.set(HIKER_MODE_KEY, 'long')
    const user = userEvent.setup()
    render(<App />)

    await openStepOne(user)
    await user.click(screen.getByRole('button', { name: 'Pick on the map' }))
    await screen.findByText('Where from?')

    await user.click(screen.getByRole('tab', { name: 'Today' }))
    const sheet = await screen.findByRole('dialog', {
      name: 'Keep this half-built route?',
    })
    expect(sheet).toBeInTheDocument()
    // Still on the map, the builder still up.
    expect(screen.getByRole('tab', { name: 'Map', selected: true })).toBeInTheDocument()

    await user.click(within(sheet).getByRole('button', { name: 'Stay here' }))
    expect(
      screen.queryByRole('dialog', { name: 'Keep this half-built route?' }),
    ).toBeNull()
    expect(screen.getByRole('tab', { name: 'Map', selected: true })).toBeInTheDocument()
    expect(screen.getByText('Where from?')).toBeInTheDocument()

    await user.click(screen.getByRole('tab', { name: 'Today' }))
    await user.click(
      within(
        await screen.findByRole('dialog', { name: 'Keep this half-built route?' }),
      ).getByRole('button', { name: 'Discard it' }),
    )
    expect(
      await screen.findByRole('tab', { name: 'Today', selected: true }),
    ).toBeInTheDocument()
    // Nothing waits on Plan: its primary offers a new plan, not a way back
    // to a route that is gone.
    await user.click(screen.getByRole('tab', { name: 'Plan' }))
    expect(screen.queryByRole('button', { name: 'Back to your route' })).toBeNull()
  })

  it('"Keep it for later" leaves the draft where it is, and Plan offers the way back', async () => {
    app.store.set(HIKER_MODE_KEY, 'long')
    const user = userEvent.setup()
    render(<App />)

    await openStepOne(user)
    await user.click(screen.getByRole('button', { name: 'Pick on the map' }))
    await screen.findByText('Where from?')

    await user.click(screen.getByRole('tab', { name: 'Plan' }))
    await user.click(
      within(
        await screen.findByRole('dialog', { name: 'Keep this half-built route?' }),
      ).getByRole('button', { name: 'Keep it for later' }),
    )

    expect(
      await screen.findByRole('tab', { name: 'Plan', selected: true }),
    ).toBeInTheDocument()
    expect(
      await screen.findByRole('button', { name: 'Back to your route' }),
    ).toBeInTheDocument()
  })

  it('never asks about the app’s own moves: landing on the map for a builder is not an exit', async () => {
    app.store.set(HIKER_MODE_KEY, 'long')
    const user = userEvent.setup()
    render(<App />)

    await openStepOne(user)
    await user.click(screen.getByRole('button', { name: 'Pick on the map' }))
    await screen.findByText('Where from?')

    expect(
      screen.queryByRole('dialog', { name: 'Keep this half-built route?' }),
    ).toBeNull()
  })
})
