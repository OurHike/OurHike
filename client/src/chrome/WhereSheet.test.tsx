import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { WhereSheet } from './WhereSheet'
import { ATC_CHALLENGE } from '../lib/challenges.fixtures'
import { whereOptions } from '../lib/wherePlace'

// jsdom has no navigator.geolocation; a stand-in whose every call is
// watched, so "never asks for location" is held by what the sheet calls and
// not only by what it says (review of #2015).
const geolocation = {
  getCurrentPosition: vi.fn(),
  watchPosition: vi.fn(),
  clearWatch: vi.fn(),
}
beforeEach(() => {
  Object.defineProperty(navigator, 'geolocation', {
    value: geolocation,
    configurable: true,
  })
})
afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

function expectNoLocationAsked() {
  expect(geolocation.getCurrentPosition).not.toHaveBeenCalled()
  expect(geolocation.watchPosition).not.toHaveBeenCalled()
}

const TODAY = '2027-07-14'
const sunrise = ATC_CHALLENGE.items.find((entry) => entry.id === 'white-blaze-photo')!
const PLACES = [
  { id: 'atc_shelters:campbell', name: 'Campbell Shelter', type: 'shelter', mile: 713 },
  {
    id: 'atc_viewpoints:knob',
    name: 'McAfee Knob Summit',
    type: 'viewpoint',
    mile: 714.9,
  },
]

function sheet(overrides: Partial<Parameters<typeof WhereSheet>[0]> = {}) {
  const onChoose = vi.fn()
  const onBack = vi.fn()
  render(
    <WhereSheet
      challenge={ATC_CHALLENGE}
      item={sunrise}
      today={TODAY}
      options={whereOptions({ fixMile: null, todayRanges: [] })}
      places={PLACES}
      onChoose={onChoose}
      onBack={onBack}
      {...overrides}
    />,
  )
  return { onChoose, onBack }
}

describe('Where did it happen? (#1963)', () => {
  it('with no fix opens on "On the trail, somewhere", offers no Here, and never mentions or asks for location', () => {
    sheet()
    expectNoLocationAsked()
    expect(screen.queryByRole('button', { name: /^Here/ })).toBeNull()
    expect(
      screen.getByRole('button', { name: /On the trail, somewhere/ }),
    ).toHaveAttribute('aria-pressed', 'true')
    expect(document.body.textContent).not.toMatch(
      /turn on location|location services|GPS/i,
    )
    // Nothing can be earned until a state is chosen.
    expect(screen.getByRole('button', { name: 'Earn it here' })).toBeDisabled()
  })

  it('earns it in a state, and hands back the state as the place', async () => {
    const { onChoose } = sheet()
    await userEvent.selectOptions(
      screen.getByRole('combobox', { name: 'Which state' }),
      'VA',
    )
    await userEvent.click(screen.getByRole('button', { name: 'Earn it here' }))
    expect(onChoose).toHaveBeenCalledWith({ kind: 'state', state: 'VA' })
  })

  it('offers Here only with a fix inside the corridor, chosen already, with its mile', async () => {
    const { onChoose } = sheet({
      options: whereOptions({ fixMile: 714.9, todayRanges: [] }),
    })
    const here = screen.getByRole('button', { name: /^Here/ })
    expect(here).toHaveAttribute('aria-pressed', 'true')
    expect(here).toHaveTextContent('mi 714.9')
    await userEvent.click(screen.getByRole('button', { name: 'Earn it here' }))
    expect(onChoose).toHaveBeenCalledWith({ kind: 'here', mile: 714.9 })
  })

  it('offers today’s walk only on a day something was walked', async () => {
    const { onChoose } = sheet({
      options: whereOptions({
        fixMile: null,
        todayRanges: [{ startMile: 710, endMile: 716 }],
      }),
    })
    await userEvent.click(
      screen.getByRole('button', { name: /Somewhere I walked today/ }),
    )
    await userEvent.click(screen.getByRole('button', { name: 'Earn it here' }))
    expect(onChoose).toHaveBeenCalledWith({ kind: 'walked', fromMile: 710, toMile: 716 })
  })

  it('finds a place by name from the phone’s own waypoints', async () => {
    const { onChoose } = sheet()
    await userEvent.click(screen.getByRole('button', { name: /Pick a place/ }))
    await userEvent.type(screen.getByRole('searchbox', { name: 'Its name' }), 'campbell')
    await userEvent.click(screen.getByRole('button', { name: /Campbell Shelter/ }))
    await userEvent.click(screen.getByRole('button', { name: 'Earn it here' }))
    expect(onChoose).toHaveBeenCalledWith({
      kind: 'poi',
      poi: 'atc_shelters:campbell',
      name: 'Campbell Shelter',
      mile: 713,
    })
  })

  it('earns "Not on the trail" with no place at all, and says what leaves the phone', async () => {
    const { onChoose } = sheet()
    await userEvent.click(screen.getByRole('button', { name: /Not on the trail/ }))
    expect(
      screen.getByText(/gets the item and the day, never the place or a track/),
    ).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Earn it' }))
    expect(onChoose).toHaveBeenCalledWith({ kind: 'off' })
  })

  it('goes back on Escape and never says anything comparative', async () => {
    const { onBack } = sheet()
    await userEvent.keyboard('{Escape}')
    expect(onBack).toHaveBeenCalled()
    expect(document.body.textContent).not.toMatch(
      /other hikers|behind|streak|\brank|leaderboard|you haven[’']t|left to go|remaining/i,
    )
  })

  it('asks for no location through every answer it offers', async () => {
    sheet({
      options: whereOptions({
        fixMile: 714.9,
        todayRanges: [{ startMile: 700, endMile: 715 }],
      }),
    })
    for (const name of [
      /^Here/,
      /Somewhere I walked today/,
      /Pick a place/,
      /On the trail, somewhere/,
      /Not on the trail/,
    ])
      await userEvent.click(screen.getByRole('button', { name }))
    expectNoLocationAsked()
  })

  it('offers only that kind of place for "any shelter", so the answer cannot be a summit', async () => {
    const logbook = ATC_CHALLENGE.items.find((entry) => entry.id === 'shelter-logbook')!
    sheet({ item: logbook })
    await userEvent.click(screen.getByRole('button', { name: /Pick a place/ }))
    expect(screen.getByRole('button', { name: /Pick a place/ })).toHaveTextContent(
      'which one, by its name',
    )
    await userEvent.type(screen.getByRole('searchbox', { name: 'Its name' }), 'm')
    const offered = screen
      .getAllByRole('button', { name: /Shelter|Summit/ })
      .filter((button) => button.classList.contains('where-places__row'))
      .map((button) => button.textContent)
    expect(offered.join()).toContain('Campbell Shelter')
    expect(offered.join()).not.toContain('McAfee Knob Summit')
  })

  it('offers no Pick a place for "any shelter" when the phone holds no shelter', () => {
    const logbook = ATC_CHALLENGE.items.find((entry) => entry.id === 'shelter-logbook')!
    sheet({ item: logbook, places: PLACES.filter((place) => place.type !== 'shelter') })
    expect(screen.queryByRole('button', { name: /Pick a place/ })).toBeNull()
  })
})
