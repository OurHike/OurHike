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
// The component's own half - the three location states, the Change control,
// "Where was this?" and what it sends - is screens/ReportForm.test.tsx.

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from './App'
import { appHarness } from './test/appHarness'

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

    await user.click(screen.getByRole('button', { name: /change/i }))

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
    await user.click(screen.getByRole('button', { name: /change/i }))

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
    await user.click(screen.getByRole('button', { name: /change/i }))
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
    await user.click(screen.getByRole('button', { name: /change/i }))
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
