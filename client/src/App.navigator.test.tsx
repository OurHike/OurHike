import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from './App'
import { appHarness } from './test/appHarness'
import type { SuggestedHike } from './lib/suggestedHikes'

// Where the hiker is, since #1373, is one navigator (lib/navigator.ts) rather
// than a tab and three booleans, and these are the promises the shell makes
// with it. The courtesies the booleans kept still hold - a tab tap returns
// Today to its journal (#1284) and leaves More on its page (#1054). Back on
// a route's detail returns to the screen it was opened from, which used to be
// a boolean beside the page and is now what a stack remembers for free. And
// the phone's bar reads the mode and opens the one switch (the review's
// rule R11) without carrying a second - App.test.tsx pins that no radiogroup
// lives in that bar, and this file pins what lives there instead.

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

// Two published routes on the shelf, so the finder has a door and a card has
// somewhere to go. Mocked at the hook rather than seeded through the cache,
// because which routes exist is not the subject.
const { SUGGESTED } = vi.hoisted(() => {
  const NJ = { lon: -74.6, lat: 41.2 }
  const suggestion = (name: string): SuggestedHike => ({
    id: name,
    name,
    miles: 6.2,
    climb: { gainFt: 980, lossFt: 980 },
    difficulty: 'moderate',
    author: { kind: 'club', name: 'NY-NJ Trail Conference' },
    segments: [
      [
        { coord: [NJ.lon, NJ.lat], poiId: null },
        { coord: [NJ.lon + 0.01, NJ.lat], poiId: null },
      ],
    ],
  })
  return { SUGGESTED: [suggestion('Sunrise Mtn loop'), suggestion('Angels Rest')] }
})
vi.mock('./lib/useSuggestedHikes', () => ({ useSuggestedHikes: () => SUGGESTED }))

const app = appHarness()

beforeEach(() => app.onboard())

async function openFinder(user: ReturnType<typeof userEvent.setup>) {
  await user.click(
    within(await screen.findByRole('group', { name: 'Find or plan a hike' })).getByRole(
      'button',
      { name: 'Find a hike' },
    ),
  )
  await screen.findByRole('heading', { name: 'Find a hike' })
}

describe('Today’s rooms are a stack', () => {
  it('Back from a route opened in the finder returns to the finder; from the shelf, to the journal', async () => {
    const user = userEvent.setup()
    render(<App />)

    await openFinder(user)
    await user.click(screen.getByRole('button', { name: /Sunrise Mtn loop/ }))
    expect(
      await screen.findByRole('heading', { name: 'Sunrise Mtn loop' }),
    ).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: '‹ Back' }))
    expect(
      await screen.findByRole('heading', { name: 'Find a hike' }),
    ).toBeInTheDocument()

    // Out of the finder, then the same route straight off the shelf.
    await user.click(screen.getByRole('button', { name: '‹ Today' }))
    await user.click(await screen.findByRole('button', { name: /Angels Rest/ }))
    expect(
      await screen.findByRole('heading', { name: 'Angels Rest' }),
    ).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: '‹ Back' }))
    expect(
      await screen.findByRole('group', { name: 'Find or plan a hike' }),
    ).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Find a hike' })).toBeNull()
  })

  it('a tab tap returns Today to its journal (#1284) and leaves More on its page (#1054)', async () => {
    const user = userEvent.setup()
    render(<App />)

    await openFinder(user)
    await user.click(screen.getByRole('tab', { name: 'Map' }))
    await user.click(screen.getByRole('tab', { name: 'Today' }))
    expect(
      await screen.findByRole('group', { name: 'Find or plan a hike' }),
    ).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Find a hike' })).toBeNull()

    await user.click(screen.getByRole('tab', { name: 'More' }))
    await user.click(await screen.findByRole('button', { name: /Volunteer & report/ }))
    expect(await screen.findByRole('heading', { name: 'Volunteer' })).toBeInTheDocument()

    await user.click(screen.getByRole('tab', { name: 'Map' }))
    await user.click(screen.getByRole('tab', { name: 'More' }))
    expect(await screen.findByRole('heading', { name: 'Volunteer' })).toBeInTheDocument()

    // And More's own way home, which is the same navigator's `home`.
    await user.click(screen.getByRole('button', { name: /^‹?\s*More$/ }))
    expect(await screen.findByRole('heading', { name: 'More' })).toBeInTheDocument()
  })
})

describe('the phone’s mode read-out', () => {
  it('names the mode in the bar and opens Today’s switch, from any tab', async () => {
    const user = userEvent.setup()
    render(<App />)
    await screen.findByRole('group', { name: 'Find or plan a hike' })

    // The bar still carries no switch of its own (App.test.tsx's rule) -
    // what it carries is one button that opens the one switch.
    expect(
      within(screen.getByRole('navigation', { name: 'Main' })).queryByRole('radiogroup'),
    ).toBeNull()

    // The Map tab's bar too - it is the one screen with its own bar mount
    // (MapScreen), and the first version left the read-out off it.
    await user.click(screen.getByRole('tab', { name: 'Map' }))
    await screen.findByRole('region', { name: /trail map/i })
    expect(
      within(screen.getByRole('navigation', { name: 'Main' })).getByRole('button', {
        name: /Today I.m day hike\. Switch mode/i,
      }),
    ).toBeInTheDocument()

    await user.click(screen.getByRole('tab', { name: 'More' }))
    await screen.findByRole('heading', { name: 'More' })
    // Queried again: each tab's screen mounts its own bar, and a button held
    // from Today's is a detached node once More is up.
    const nav = screen.getByRole('navigation', { name: 'Main' })
    await user.click(
      within(nav).getByRole('button', { name: /Today I.m day hike\. Switch mode/i }),
    )

    expect(screen.getByRole('tab', { name: 'Today', selected: true })).toBeInTheDocument()
    await waitFor(() => expect(document.activeElement).toHaveAccessibleName('Day hike'))
    expect(document.activeElement).toHaveAttribute('role', 'radio')
  })

  it('reads whatever the switch says', async () => {
    const user = userEvent.setup()
    render(<App />)
    await screen.findByRole('group', { name: 'Find or plan a hike' })

    const group = screen.getByRole('radiogroup', { name: /today i/i })
    await user.click(within(group).getByRole('radio', { name: 'Volunteer' }))

    const nav = screen.getByRole('navigation', { name: 'Main' })
    expect(
      await within(nav).findByRole('button', {
        name: /Today I.m volunteer\. Switch mode/i,
      }),
    ).toBeInTheDocument()
  })
})
