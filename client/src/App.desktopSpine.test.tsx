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
