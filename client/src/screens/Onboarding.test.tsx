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

    expect(screen.getAllByRole('radio')).toHaveLength(2)
    expect(screen.getByText('789.6 MB')).toBeInTheDocument()
    expect(screen.getByText('1.14 GB')).toBeInTheDocument()
  })

  it('names the USGS sheet as optional rather than configuring it here', async () => {
    const user = userEvent.setup()
    render(<Onboarding {...PROPS} />)
    await advance(user, 1)

    expect(screen.getByText(/optional second map/i)).toBeInTheDocument()
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
