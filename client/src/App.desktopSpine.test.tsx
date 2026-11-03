import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from './App'
import { appHarness, stubDesktop } from './test/appHarness'

// The planning spine on a laptop (the maintainer's review of #1374: "That 3
// step process should be a sidebar on the map. Match the original design";
// the design's R2, "the map never leaves"). Step 1 is the column beside the
// map - the same slot steps 2 and 3 take (App.dayHike.test.tsx holds those,
// with the graph) - rather than the Plan tab's page, which is what a phone
// still gets (App.pathway.test.tsx).

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

describe('step 1 on a laptop', () => {
  it('stands beside the map, in the column the builder will take, with the map still drawn', async () => {
    stubDesktop()
    const user = userEvent.setup()
    app.onboard()
    app.putTrailData()
    render(<App />)

    // A desktop builds its map from launch (App.dayHike.test.tsx's reason).
    await screen.findByRole('region', { name: /trail map/i })
    await user.click(screen.getByRole('tab', { name: 'Plan' }))
    await user.click(await screen.findByRole('button', { name: 'Start on the map' }))

    const heading = await screen.findByRole('heading', {
      name: 'Where do you want to go?',
    })
    // Beside the map, not instead of it.
    expect(screen.getByRole('region', { name: /trail map/i })).toBeInTheDocument()
    const column = heading.closest('.plan-start')
    expect(column).not.toBeNull()
    expect(column?.parentElement?.className).toBe('map-screen__body')
    expect(column?.closest('.map-screen__canvas')).toBeNull()
    // The legend rail stands down for the column, as it does for the builder.
    expect(screen.queryByRole('region', { name: /legend/i })).toBeNull()

    // Cancel is the way back to Plan's page, and the map goes with it.
    await user.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(screen.queryByRole('heading', { name: 'Where do you want to go?' })).toBeNull()
    expect(screen.queryByRole('region', { name: /trail map/i })).toBeNull()
  })
})

describe('the account button on a laptop', () => {
  // #1596 put one on the map header's cluster and one on Today's own chrome,
  // which is one button on a phone because one screen is drawn at a time.
  // Above the breakpoint Today and the map are side by side and both were on
  // the page - the maintainer's report, 2026-09-20. The three places now read
  // `useDesktop()` and decide, which is the arrangement these two pin.

  it('is in the sidebar and nowhere else, so one screen offers one way in', async () => {
    stubDesktop()
    const user = userEvent.setup()
    app.onboard()
    app.putTrailData()
    render(<App />)

    await screen.findByRole('region', { name: /trail map/i })

    // ONE, not "at least one": `getAllByRole` and a length assertion rather
    // than `getByRole`, because `getByRole` throwing on two would report a
    // strict-mode violation and not the thing that is actually wrong.
    const doors = screen.getAllByRole('button', { name: 'Sign in' })
    expect(doors).toHaveLength(1)
    expect(doors[0].className).toBe('tab-bar__account-button')
    expect(doors[0].closest('.tab-bar')).not.toBeNull()

    // And it opens the window, which is the point of it being there at all.
    await user.click(doors[0])
    expect(await screen.findByRole('dialog', { name: 'Sign in' })).toBeInTheDocument()
  })

  it('leaves the map header and Today their own, below the breakpoint', async () => {
    // No `stubDesktop()`: appHarness's default matchMedia answers no, which
    // is the phone. The assertion is the mirror of the one above - the
    // sidebar's button is absent, and the header still has its.
    const user = userEvent.setup()
    app.onboard()
    app.putTrailData()
    render(<App />)

    await user.click(await screen.findByRole('tab', { name: 'Map' }))
    await screen.findByRole('region', { name: /trail map/i })

    const doors = screen.getAllByRole('button', { name: 'Sign in' })
    expect(doors).toHaveLength(1)
    expect(doors[0].className).toContain('map-header__account')
  })
})
