import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Onboarding } from './Onboarding'
import { ONBOARDING_STEPS } from '../lib/onboardingSteps'

// WIREFRAMES.md §5, plus TESTING.md item 11 (first run).
//
// Two things here are not layout preferences but explicit product decisions
// that a later well-meaning change could quietly undo, so they are asserted
// directly:
//
//  - NO notification prompt anywhere in first run. Notifications belong to the
//    wrong-way alert, asked at hike start. OurHike sends exactly one kind of
//    push and asking for it up front would spend that permission before it has
//    been earned.
//  - NO account prompt. Reading the map never needs an account; sign-in is
//    asked at the first contribution instead.
//
// Also asserted: the "map size" step must not mention taking single sections
// later. WIREFRAMES.md Known Deviations #1 retires per-section downloads
// entirely, and the wireframe's own copy still carried the old clause.

const PROPS = { onComplete: vi.fn() }

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

/** Moves forward via "Continue". The location step is answered explicitly with
 *  Allow / Not now, since which one is pressed is the thing under test. */
async function advance(user: ReturnType<typeof userEvent.setup>, times: number) {
  for (let i = 0; i < times; i++) {
    await user.click(screen.getByRole('button', { name: /^continue$/i }))
  }
}

describe('Onboarding', () => {
  it('starts on the value-proposition step', () => {
    render(<Onboarding {...PROPS} />)

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(/what ourhike/i)
  })

  it('counts steps from the live step list, not a hardcoded total', () => {
    render(<Onboarding {...PROPS} />)

    expect(screen.getByText(`1 of ${ONBOARDING_STEPS.length}`)).toBeInTheDocument()
  })

  it('says plainly on the first screen that nothing needs signing up for', () => {
    render(<Onboarding {...PROPS} />)

    expect(screen.getByText(/no account\. nothing to sign up for\./i)).toBeInTheDocument()
  })

  it('says memberships fund the ATC and the volunteer clubs', () => {
    render(<Onboarding {...PROPS} />)

    expect(screen.getByText(/fund/i)).toHaveTextContent(/ATC|club/i)
  })

  it('offers the hiking sheet\u2019s two levels on the map-size step, with the real figures', async () => {
    // The download decision shown is the one a hiker will actually meet in
    // the Downloads window (#277): the hiking sheet's Standard/Fine cuts at
    // their whole-sheet sizes, not the optional USGS raster's tiers.
    const user = userEvent.setup()
    render(<Onboarding {...PROPS} />)
    await advance(user, 1)

    expect(screen.getByRole('radio', { name: /standard/i })).toBeEnabled()
    expect(screen.getByRole('radio', { name: /fine/i })).toBeEnabled()
    expect(screen.getByText('789.6 MB')).toBeInTheDocument()
    expect(screen.getByText('1.14 GB')).toBeInTheDocument()
  })

  it('asks the map-size question in the download window\u2019s shape (#298)', async () => {
    // First run ends by opening that window, so the two are consecutive
    // views of one decision. They looked like two: a flat list here, a sheet
    // per tab there.
    const user = userEvent.setup()
    render(<Onboarding {...PROPS} />)
    await advance(user, 1)

    expect(screen.getByRole('tab', { name: /hiking sheet/i })).toHaveAttribute(
      'aria-selected',
      'true',
    )
    expect(screen.getByRole('tab', { name: /usgs sheet/i })).toBeInTheDocument()
  })

  it('greys the hiking sheet\u2019s missing Light rung rather than dropping it (#298)', async () => {
    // The basemap is cut at z13 and z14 and nothing below. Under a tab
    // beside the raster's three, a two-row picker cannot say whether this
    // map has no Light version or whether the app forgot to ask.
    const user = userEvent.setup()
    render(<Onboarding {...PROPS} />)
    await advance(user, 1)

    expect(screen.getAllByRole('radio')).toHaveLength(3)
    expect(screen.getByRole('radio', { name: /light/i })).toBeDisabled()
  })

  it('names and prices the USGS sheet without configuring it here (#277)', async () => {
    // #277 took the raster's tiers out of first run on purpose. The tab
    // shows what the optional map would cost and points at Downloads; every
    // level under it is greyed, so nothing about it is chosen in this flow.
    const user = userEvent.setup()
    render(<Onboarding {...PROPS} />)
    await advance(user, 1)
    await user.click(screen.getByRole('tab', { name: /usgs sheet/i }))

    for (const level of screen.getAllByRole('radio')) {
      expect(level).toBeDisabled()
      expect(level).not.toBeChecked()
    }
    expect(screen.getByText(/chosen in downloads/i)).toBeInTheDocument()
  })

  it('finishes with the hiking level even after a look at the USGS tab', async () => {
    // Switching tabs is looking, not choosing: the USGS tab writes nothing,
    // so what first run reports is still the hiking sheet's level.
    const user = userEvent.setup()
    render(<Onboarding {...PROPS} />)
    await advance(user, 1)
    await user.click(screen.getByRole('radio', { name: /fine/i }))
    await user.click(screen.getByRole('tab', { name: /usgs sheet/i }))
    await user.click(screen.getByRole('tab', { name: /hiking sheet/i }))
    await advance(user, 1)
    await user.click(screen.getByRole('button', { name: /allow/i }))

    expect(PROPS.onComplete).toHaveBeenCalledWith(
      expect.objectContaining({ hikingDetailLevel: 'fine' }),
    )
  })

  it('marks Standard as the recommended size', async () => {
    const user = userEvent.setup()
    render(<Onboarding {...PROPS} />)
    await advance(user, 1)

    expect(screen.getByRole('radio', { name: /standard/i })).toBeChecked()
  })

  it('never offers to take single sections later - per-section downloads are retired', async () => {
    const user = userEvent.setup()
    render(<Onboarding {...PROPS} />)
    await advance(user, 1)

    expect(screen.queryByText(/section/i)).not.toBeInTheDocument()
  })

  it('asks for location only after the value-prop step, so the reason is visible first', async () => {
    const user = userEvent.setup()
    render(<Onboarding {...PROPS} />)

    expect(screen.queryByText(/location/i)).not.toBeInTheDocument()

    await advance(user, 2)

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(/location/i)
  })

  it('promises on the location step that position never leaves the phone', async () => {
    const user = userEvent.setup()
    render(<Onboarding {...PROPS} />)
    await advance(user, 2)

    expect(screen.getByText(/never leaves (your|the) phone/i)).toBeInTheDocument()
  })

  it('never asks about notifications anywhere in first run', async () => {
    const user = userEvent.setup()
    render(<Onboarding {...PROPS} />)

    for (let step = 0; step < ONBOARDING_STEPS.length; step++) {
      expect(screen.queryByText(/notification/i)).not.toBeInTheDocument()
      if (step < ONBOARDING_STEPS.length - 1) await advance(user, 1)
    }
  })

  it('never asks for an account anywhere in first run', async () => {
    const user = userEvent.setup()
    render(<Onboarding {...PROPS} />)

    for (let step = 0; step < ONBOARDING_STEPS.length; step++) {
      expect(
        screen.queryByRole('button', { name: /sign in|sign up|create account/i }),
      ).toBe(null)
      if (step < ONBOARDING_STEPS.length - 1) await advance(user, 1)
    }
  })

  it('lets every step be skipped', async () => {
    const user = userEvent.setup()
    render(<Onboarding {...PROPS} />)

    for (let step = 0; step < ONBOARDING_STEPS.length; step++) {
      expect(screen.getByRole('button', { name: /skip/i })).toBeInTheDocument()
      if (step < ONBOARDING_STEPS.length - 1) await advance(user, 1)
    }
  })

  it('keeps the total steady when a step is skipped - the counter never grows mid-flow', async () => {
    const user = userEvent.setup()
    render(<Onboarding {...PROPS} />)

    await user.click(screen.getByRole('button', { name: /skip/i }))

    expect(screen.getByText(`2 of ${ONBOARDING_STEPS.length}`)).toBeInTheDocument()
  })

  it('finishes with the chosen level', async () => {
    const user = userEvent.setup()
    render(<Onboarding {...PROPS} />)

    await advance(user, 1)
    await user.click(screen.getByRole('radio', { name: /fine/i }))
    await advance(user, 1)
    await user.click(screen.getByRole('button', { name: /allow/i }))

    expect(PROPS.onComplete).toHaveBeenCalledWith(
      expect.objectContaining({ hikingDetailLevel: 'fine' }),
    )
  })

  it('reports whether location was granted or declined, rather than assuming', async () => {
    const user = userEvent.setup()
    render(<Onboarding {...PROPS} />)

    await advance(user, 2)
    await user.click(screen.getByRole('button', { name: /not now/i }))

    expect(PROPS.onComplete).toHaveBeenCalledWith(
      expect.objectContaining({ locationRequested: false }),
    )
  })

  it('still completes with a usable default when every step is skipped', async () => {
    const user = userEvent.setup()
    render(<Onboarding {...PROPS} />)

    for (let step = 0; step < ONBOARDING_STEPS.length; step++) {
      await user.click(screen.getByRole('button', { name: /skip/i }))
    }

    // Skipping must not leave the app with no map to download.
    expect(PROPS.onComplete).toHaveBeenCalledWith(
      expect.objectContaining({ hikingDetailLevel: 'standard' }),
    )
  })
})
