// Correcting where a report goes, through the shell (#1439, D16).
//
// WHAT THIS FILE IS FOR, and it is one property: taking the crosshair must
// not cost the hiker what they have already written. `screens/ReportForm.tsx`
// holds the note and the photo tiles in its own state, so the difference
// between "stood aside" and "unmounted" is the difference between coming back
// to a form and coming back to an empty one - and that difference is a
// RENDERING DECISION in App.tsx, invisible to a component test. It is the
// same call #1329 made for the hike set-up window, which is holding a draft
// for the same reason.
//
// The component's own half - the location line, the picker behind Change,
// the words field and what it sends - is screens/ReportForm.test.tsx.
//
// SINCE #1563 "Change" OPENS THE PICKER, not the map: the map is one row in
// it ("Mark it on the map"), beside a named place and where you are. This
// harness has no GPS fix, so every form here opens with the picker already
// expanded - nothing has placed the report - and the drives below tap the
// map row directly. The window takes the crosshair too, and the last block
// here is that.

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from './App'
import { appHarness } from './test/appHarness'
import { MockMap } from './test/mocks/maplibre-gl'

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

const app = appHarness()

beforeEach(() => app.onboard())

/**
 * Open the long form the only way a test can without a map: More's Contribute
 * door to the six-tile window, then the one heavy row that opens a form
 * rather than filing on a tap.
 *
 * "Something unsafe happened" is that row deliberately (categories.ts's
 * `filesOnTap`): somebody in trouble has to be able to read the 911 line
 * before the tap rather than after it.
 */
async function openTheLongForm(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole('tab', { name: 'More' }))
  await user.click(screen.getByRole('button', { name: /^Volunteer & report/ }))
  await user.click(screen.getByRole('button', { name: 'Report a problem' }))
  await user.click(await screen.findByRole('button', { name: /Something unsafe/ }))
  return screen.findByRole('heading', { name: 'Something unsafe happened' })
}

describe('the report form keeps what is in it while the crosshair is out', () => {
  it('still holds the note after standing aside for the map, and after coming back', async () => {
    const user = userEvent.setup()
    render(<App />)

    await openTheLongForm(user)
    const note = screen.getByRole('textbox', { name: /note/i })
    await user.type(note, 'Followed for two miles north of the gap.')

    // No fix in this harness; Change opens the location sheet over the form
    // and the map row is in it.
    await user.click(await screen.findByTestId('report-form-change'))
    await user.click(await screen.findByTestId('location-map'))

    // The form is still mounted - stood aside, not unmounted - so the words
    // are still in it. Hidden by `visibility`, which jsdom reports as
    // not-visible while leaving the node and its value in the tree, so this
    // asserts on the value rather than on visibility.
    expect(note).toHaveValue('Followed for two miles north of the gap.')
    // And the map is what the hiker is now aiming at.
    expect(
      await screen.findByRole('dialog', { name: 'Say where this was' }),
    ).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Cancel' }))

    expect(screen.getByRole('textbox', { name: /note/i })).toHaveValue(
      'Followed for two miles north of the gap.',
    )
  })

  it('offers nothing to keep until something has been tapped', async () => {
    // D10 at the level the whole review keeps insisting on: the way to say
    // "there is nothing to keep yet" is to draw no Keep, not a Keep that
    // does nothing.
    const user = userEvent.setup()
    render(<App />)

    await openTheLongForm(user)
    // No fix in this harness; Change opens the location sheet over the form
    // and the map row is in it.
    await user.click(await screen.findByTestId('report-form-change'))
    await user.click(await screen.findByTestId('location-map'))

    const bar = await screen.findByRole('dialog', { name: 'Say where this was' })
    expect(bar).toHaveTextContent('Tap the map where this was.')
    expect(screen.queryByRole('button', { name: /keep this spot/i })).toBeNull()
  })
})

// LEAVING THE CROSSHAIR BY A DOOR THAT IS NEITHER KEEP NOR CANCEL.
//
// The two tests above drive the two exits the feature was built around, and
// both were green over a flow that was broken: the tab bar stays reachable
// while the bar is out, and nothing was watching what a tap on it did. What
// it did was strand the hiker - the bar is rendered in the MAP screen's sheet
// slot, so on Today it is in the tree and on nobody's screen, while the form
// standing aside for it is `inert` and `aria-hidden`. No form, no bar, and
// `reportPointOnMap` still true, so every later form in the session opened
// stood aside behind a crosshair that was never on screen.
//
// Found by reading the diff rather than by running it, which is the reason
// these two cases exist: an exit nobody drove is an exit nobody tested.
describe('leaving the crosshair by a tab', () => {
  it('gives the form back rather than stranding it behind a bar on another tab', async () => {
    const user = userEvent.setup()
    render(<App />)

    await openTheLongForm(user)
    await user.type(
      screen.getByRole('textbox', { name: /note/i }),
      'Two trunks across the tread.',
    )
    // No fix in this harness; Change opens the location sheet over the form
    // and the map row is in it.
    await user.click(await screen.findByTestId('report-form-change'))
    await user.click(await screen.findByTestId('location-map'))
    await screen.findByRole('dialog', { name: 'Say where this was' })

    await user.click(screen.getByRole('tab', { name: 'Today' }))

    // The form is back, reachable, and still holding what was typed into it -
    // the hiker went to look at something, not to abandon their report.
    expect(
      await screen.findByRole('heading', { name: 'Something unsafe happened' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: /note/i })).toHaveValue(
      'Two trunks across the tread.',
    )
    // And the bar is not being drawn at somebody who cannot see it.
    expect(screen.queryByRole('dialog', { name: 'Say where this was' })).toBeNull()
  })

  it('does not leave the next report standing aside for a pick nobody made', async () => {
    // The half that outlived the session. Abandon one report mid-pick, file
    // nothing, then open another: it must open like any other form.
    const user = userEvent.setup()
    render(<App />)

    await openTheLongForm(user)
    // No fix in this harness; Change opens the location sheet over the form
    // and the map row is in it.
    await user.click(await screen.findByTestId('report-form-change'))
    await user.click(await screen.findByTestId('location-map'))
    await screen.findByRole('dialog', { name: 'Say where this was' })
    await user.click(screen.getByRole('tab', { name: 'Today' }))
    await user.click(screen.getByRole('button', { name: 'Cancel' }))

    // The second report comes through Today's own door rather than More's,
    // which is both the realistic second try and the one that does not
    // depend on where More was left standing (#1054 keeps its page).
    await user.click(screen.getByRole('button', { name: /^Report a problem/ }))
    await user.click(await screen.findByRole('button', { name: /Something unsafe/ }))

    const form = document.querySelector('.reporting-window')
    expect(form).not.toBeNull()
    expect(form).not.toHaveClass('reporting-window--stood-aside')
    expect(form?.hasAttribute('inert')).toBe(false)
    expect(
      screen.getByRole('heading', { name: 'Something unsafe happened' }),
    ).toBeInTheDocument()
  })
})

// THE WINDOW TAKES THE CROSSHAIR TOO (#1563). The six-tile window used to
// offer only the places walked past today; its picker now has the same map
// row the long form's has, and the same property has to hold: standing aside
// for the map must not cost the hiker the window's state.
describe('the report window stands aside for the map and comes back', () => {
  it('hides the window while the crosshair is out, and brings it back with the same place', async () => {
    const user = userEvent.setup()
    render(<App />)

    // No fix in this harness; Change opens the location sheet over the
    // window, and the map row is the way out of "No location yet".
    await user.click(screen.getByRole('tab', { name: 'More' }))
    await user.click(screen.getByRole('button', { name: /^Volunteer & report/ }))
    await user.click(screen.getByRole('button', { name: 'Report a problem' }))
    await screen.findByRole('dialog', { name: 'What did you find?' })
    expect(screen.getByTestId('report-anchor')).toHaveTextContent('No location yet')

    await user.click(screen.getByTestId('report-change-anchor'))
    await user.click(await screen.findByTestId('location-map'))

    // The bar is up over the map, and the window is stood aside - hidden and
    // inert - rather than unmounted.
    expect(
      await screen.findByRole('dialog', { name: 'Say where this was' }),
    ).toBeInTheDocument()
    const scrim = screen.getByTestId('report-window-scrim')
    expect(scrim).toHaveClass('report-window__scrim--stood-aside')
    expect(scrim.hasAttribute('inert')).toBe(true)

    await user.click(screen.getByRole('button', { name: 'Cancel' }))

    expect(screen.getByTestId('report-window-scrim')).not.toHaveClass(
      'report-window__scrim--stood-aside',
    )
    expect(screen.getByTestId('report-anchor')).toHaveTextContent('No location yet')
    expect(screen.queryByRole('dialog', { name: 'Say where this was' })).toBeNull()
  })
})

// KEEPING A SPOT IS A WINDOW (#1563, the maintainer's steer of 2026-09-17).
// The crosshair's bar carried the Keep button beside its answer; the tap
// opens a window now, with the answer said large and Keep under it, and the
// tile that was refused for want of a place files the moment the spot is
// kept - the category is asked once.
describe('keeping a spot marked on the map', () => {
  /** The live map with its tap listener attached - a wait on something
   *  observable that proves the wiring, never on a tick. */
  async function liveMap() {
    await waitFor(() => {
      expect(MockMap.live.length).toBeGreaterThan(0)
      expect(MockMap.live[0].listenerCount('click')).toBeGreaterThan(0)
    })
    return MockMap.live[0]
  }

  /** Report a problem, tap Blow down with no fix (refused), and take the
   *  sheet's map row: the window stands aside and the crosshair is out. */
  async function aimFromTheWindow(user: ReturnType<typeof userEvent.setup>) {
    await user.click(screen.getByRole('tab', { name: 'More' }))
    await user.click(screen.getByRole('button', { name: /^Volunteer & report/ }))
    await user.click(screen.getByRole('button', { name: 'Report a problem' }))
    await screen.findByRole('dialog', { name: 'What did you find?' })
    await user.click(await screen.findByRole('button', { name: /blow down/i }))
    await user.click(await screen.findByTestId('location-map'))
    await screen.findByRole('dialog', { name: 'Say where this was' })
    expect(screen.queryByRole('dialog', { name: 'Keep this spot?' })).toBeNull()
    return liveMap()
  }

  it('opens the keep window on a tap, naming what the tap got, and Keep files the tile that was refused', async () => {
    const user = userEvent.setup()
    render(<App />)
    const map = await aimFromTheWindow(user)

    await act(async () => {
      map.emit('click', { lngLat: { lng: -80.35, lat: 37.35 } })
    })
    const keep = await screen.findByRole('dialog', { name: 'Keep this spot?' })
    // No trail index in this harness, so the honest answer is the second of
    // lib/placement.ts's three - not a mile, and not "off the trail".
    expect(screen.getByTestId('keep-spot-words')).toHaveTextContent('This spot')
    expect(keep).toHaveFocus()

    await user.click(screen.getByTestId('keep-spot-keep'))

    // Back to the window, which files the Blow down that was waiting - no
    // second tap on the tile - and the receipt names the kept spot.
    expect(screen.queryByRole('dialog', { name: 'Keep this spot?' })).toBeNull()
    expect(await screen.findByText(/Filed — blow down/)).toBeInTheDocument()
    expect(screen.getByTestId('report-window-scrim')).not.toHaveClass(
      'report-window__scrim--stood-aside',
    )
    expect(screen.queryByTestId('report-tile-blowdown')).toBeNull()
  })

  it('"Tap again" clears the aim and leaves the map up, and the header Cancel goes back with nothing kept', async () => {
    const user = userEvent.setup()
    render(<App />)
    const map = await aimFromTheWindow(user)

    await act(async () => {
      map.emit('click', { lngLat: { lng: -80.35, lat: 37.35 } })
    })
    await screen.findByRole('dialog', { name: 'Keep this spot?' })
    await user.click(screen.getByTestId('keep-spot-again'))
    expect(screen.queryByRole('dialog', { name: 'Keep this spot?' })).toBeNull()
    expect(screen.getByRole('dialog', { name: 'Say where this was' })).toHaveTextContent(
      'Tap the map where this was.',
    )

    await act(async () => {
      map.emit('click', { lngLat: { lng: -80.36, lat: 37.36 } })
    })
    await screen.findByRole('dialog', { name: 'Keep this spot?' })
    await user.click(screen.getByTestId('keep-spot-cancel'))

    // The window is back with the sheet it left open, and nothing filed.
    expect(screen.queryByRole('dialog', { name: 'Say where this was' })).toBeNull()
    expect(screen.getByTestId('report-window-scrim')).not.toHaveClass(
      'report-window__scrim--stood-aside',
    )
    expect(screen.getByTestId('report-anchor')).toHaveTextContent('No location yet')
    expect(screen.queryByText(/Filed —/)).toBeNull()
  })
})
