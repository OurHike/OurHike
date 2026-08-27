import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Onboarding } from './Onboarding'
import { ONBOARDING_STEPS } from '../lib/onboardingSteps'
import { HIKING_SHEET, USGS_SHEET } from '../lib/packages'
import { HERO_PHOTOS } from '../lib/heroPhotos'

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

/** Light's whole-sheet size as first run renders it: the z12 basemap cut plus
 *  the harder-tapered DEM, both measured in UA's bucket (#1107). Written out
 *  rather than computed from hikingDetail.ts, for the same reason the other two
 *  rungs' figures are - a test that derives the expected string from the same
 *  table the screen reads cannot notice the two disagreeing. */
const LIGHT_MB = '257.7 MB'

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

/** Moves forward via each step's own primary - "Continue", or the size
 *  step's "Keep going" (#1054). The location step is answered explicitly with
 *  Allow / Not now, since which one is pressed is the thing under test. */
async function advance(user: ReturnType<typeof userEvent.setup>, times: number) {
  for (let i = 0; i < times; i++) {
    await user.click(screen.getByRole('button', { name: /^continue$|^keep going$/i }))
  }
}

/** The step's decline control - "Skip", or the size step's "Decide this
 *  later", which is the same promise in the words of what it declines. */
const SKIP = /^skip$|^decide this later$/i

describe('Onboarding', () => {
  it('starts on the value-proposition step', () => {
    render(<Onboarding {...PROPS} />)

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(/what ourhike/i)
  })

  it('counts steps from the live step list, not a hardcoded total', () => {
    render(<Onboarding {...PROPS} />)

    expect(screen.getByText(`Step 1 of ${ONBOARDING_STEPS.length}`)).toBeInTheDocument()
  })

  it('says plainly on the first screen that nothing needs signing up for', () => {
    render(<Onboarding {...PROPS} />)

    expect(screen.getByText(/no account\. nothing to sign up for\./i)).toBeInTheDocument()
  })

  // This test used to be titled "says memberships fund the ATC and the other
  // organizations, not the ATC alone", and it demanded the claim rather than
  // guarding against it: a /fund/i node containing both /ATC/i and /other
  // organizations/i. A test that pins a false sentence is worse than no test,
  // because it makes the sentence expensive to fix and looks like diligence
  // while doing it. Both halves are replaced - the title as much as the
  // matchers, since the title is what the next reader takes as the contract.
  it('sends a hiker to the organizations instead of claiming OurHike funds them', () => {
    render(<Onboarding {...PROPS} />)

    const money = screen.getByText(/takes no cut and holds no money/i)
    expect(money).toHaveTextContent(/ATC/i)
    expect(money).toHaveTextContent(/other organizations/i)
    expect(money).toHaveTextContent(/directly/i)
  })

  // The guard, and the reason this file is in the diff rather than only the
  // component. OurHike sends no money to any organization (maintainer,
  // 2026-08-27), so no sentence on this step may put OurHike, or anything a
  // hiker would buy from OurHike, in front of the verb "fund". Asserted against
  // the value-prop step's whole rendered text rather than one node, because the
  // defect this replaces spanned two lines and any node-scoped matcher can be
  // walked around by reflowing the JSX. Scope is that step alone: Onboarding
  // renders one step at a time and this test never advances past the first.
  // It is a guard against the sentence coming back, not a proof that no other
  // screen can say it.
  it('never puts OurHike or a purchase in front of "fund"', () => {
    const { container } = render(<Onboarding {...PROPS} />)

    expect(container.textContent).not.toMatch(
      /\b(OurHike|membership|memberships|donation|donations|revenue|purchase|purchases|subscription|subscriptions|pass|passes)\b[^.]{0,80}\bfund(s|ed|ing)?\b/i,
    )
  })

  it('offers the hiking sheet\u2019s three levels on the map-size step, with the real figures', async () => {
    // The download decision shown is the one a hiker will actually meet in
    // the Downloads window (#277): the hiking sheet's own cuts at their
    // whole-sheet sizes, not the optional USGS raster's tiers.
    //
    // The figures are the published artifacts' bytes summed per level, and
    // they moved twice: the tapered DEM took Standard from 789.6 MB to
    // 458.4 MB and Fine from 1.14 GB to 809.5 MB (#1088), and Light arrived
    // at 257.7 MB with a DEM and a basemap cut of its own (#1107). Asserted as rendered
    // strings on purpose - this is the number a hiker weighs against their
    // remaining storage, so a formatter change is a change to that.
    const user = userEvent.setup()
    render(<Onboarding {...PROPS} />)
    await advance(user, 1)

    for (const level of [/light/i, /standard/i, /fine/i]) {
      expect(screen.getByRole('radio', { name: level })).toBeEnabled()
    }
    expect(screen.getByText(LIGHT_MB)).toBeInTheDocument()
    expect(screen.getByText('458.4 MB')).toBeInTheDocument()
    expect(screen.getByText('809.5 MB')).toBeInTheDocument()
  })

  it('asks the map-size question in the download window\u2019s shape (#298, #855)', async () => {
    // First run ends by opening that window, so the two are consecutive
    // views of one decision. They looked like two: a flat list here, a sheet
    // per tab there.
    //
    // With the USGS sheet withdrawn there is one sheet on offer, and the
    // shape they have to share is now the window's OTHER shape: no strip at
    // all, because "a single tab is a heading pretending to be a control"
    // (screens/Downloads.tsx). Asserting the absence of the strip is
    // asserting the same rule the tabs were asserting before it.
    const user = userEvent.setup()
    render(<Onboarding {...PROPS} />)
    await advance(user, 1)

    expect(screen.queryByRole('tablist')).toBeNull()
    expect(screen.getByText(HIKING_SHEET.summary)).toBeInTheDocument()
  })

  it('draws all three of the hiking sheet\u2019s rungs, and every one is takeable (#298)', async () => {
    // This test used to assert the Light rung was GREYED, and the rule it was
    // written for is unchanged: a two-row picker cannot say whether this map
    // has no Light version or whether the app forgot to ask, so an unbuilt
    // level is drawn and disabled rather than left out. Light was the live
    // example of that from #1088, which named its artifacts, until #1107 built
    // them - so what is asserted here now is that first run offers the whole
    // ladder, and DownloadCard.test.tsx carries the greying with a sheet that
    // still has no dial at all.
    const user = userEvent.setup()
    render(<Onboarding {...PROPS} />)
    await advance(user, 1)

    const levels = screen.getAllByRole('radio')
    expect(levels).toHaveLength(3)
    for (const level of levels) expect(level).toBeEnabled()
  })

  it('never mentions the withdrawn USGS sheet at all (#855)', async () => {
    // #277 had first run NAME and PRICE the optional map without configuring
    // it - a greyed ladder under its own tab, pointing at Downloads. That was
    // right while Downloads sold it. It is withdrawn now, so pricing it here
    // would send a newcomer to a window that does not carry it, and the tab
    // reads the catalog rather than listing the sheets - so it simply is not
    // built.
    //
    // Two assertions, because the tab going while the copy stayed would be
    // the failure worth catching: the sheet is not named anywhere on this
    // step, and every level shown is the hiking sheet's own, operable one.
    const user = userEvent.setup()
    render(<Onboarding {...PROPS} />)
    await advance(user, 1)

    expect(screen.queryByText(/usgs/i)).toBeNull()
    expect(screen.queryByText(USGS_SHEET.summary)).toBeNull()
    expect(screen.queryByText(/chosen in downloads/i)).toBeNull()
    expect(screen.getByRole('radio', { name: /standard/i })).toBeEnabled()
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
      expect(screen.getByRole('button', { name: SKIP })).toBeInTheDocument()
      if (step < ONBOARDING_STEPS.length - 1) await advance(user, 1)
    }
  })

  it('keeps the total steady when a step is skipped - the counter never grows mid-flow', async () => {
    const user = userEvent.setup()
    render(<Onboarding {...PROPS} />)

    await user.click(screen.getByRole('button', { name: SKIP }))

    expect(screen.getByText(`Step 2 of ${ONBOARDING_STEPS.length}`)).toBeInTheDocument()
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

  it('starts the download from the size step, exactly once', async () => {
    // #1054: the download happens on the step that asks for it. Once, however
    // the flow is walked - a second transfer for one choice would spend
    // trailhead signal twice.
    const onStartDownload = vi.fn()
    const user = userEvent.setup()
    render(<Onboarding {...PROPS} onStartDownload={onStartDownload} />)

    await advance(user, 2)

    expect(onStartDownload).toHaveBeenCalledTimes(1)
  })

  it('starts nothing when the size step is declined', async () => {
    // "Decide this later" means later: the Today screen holds the door open,
    // and nothing here spends a byte someone declined to spend.
    const onStartDownload = vi.fn()
    const user = userEvent.setup()
    render(<Onboarding {...PROPS} onStartDownload={onStartDownload} />)

    await advance(user, 1)
    await user.click(screen.getByRole('button', { name: /decide this later/i }))

    expect(onStartDownload).not.toHaveBeenCalled()
  })

  it('writes the level through as it changes, before any download starts', async () => {
    // The shell's download requests derive their URL from the stored
    // preference, so the write must land ahead of "Keep going" - a level
    // written at completion would download the wrong artifact.
    const onChangeLevel = vi.fn()
    const user = userEvent.setup()
    render(<Onboarding {...PROPS} onChangeLevel={onChangeLevel} />)

    await advance(user, 1)
    await user.click(screen.getByRole('radio', { name: /fine/i }))

    expect(onChangeLevel).toHaveBeenCalledWith('fine')
  })

  it('shows the transfer honestly while the last step is asked', async () => {
    const user = userEvent.setup()
    render(
      <Onboarding
        {...PROPS}
        downloadActivity={{
          kind: 'downloading',
          doneBytes: 480_000_000,
          totalBytes: 1_400_000_000,
        }}
      />,
    )
    await advance(user, 2)

    expect(screen.getByText(/downloading while you finish up/i)).toBeInTheDocument()
    expect(screen.getByText('34%')).toBeInTheDocument()
    expect(
      screen.getByText(/picks up where it left off if you lose signal/i),
    ).toBeInTheDocument()
  })

  it('tells a stalled phone from a stalled connection, in the panel too', async () => {
    // The checking state exists so someone in a dead spot knows whether to
    // wait or walk (#197) - the panel keeps that distinction.
    render(
      <Onboarding
        {...PROPS}
        downloadActivity={{
          kind: 'checking',
          doneBytes: 200_000_000,
          totalBytes: 1_400_000_000,
        }}
      />,
    )

    expect(
      screen.getByText(/checking what is already on this phone/i),
    ).toBeInTheDocument()
  })

  it('still completes with a usable default when every step is skipped', async () => {
    const user = userEvent.setup()
    render(<Onboarding {...PROPS} />)

    for (let step = 0; step < ONBOARDING_STEPS.length; step++) {
      await user.click(screen.getByRole('button', { name: SKIP }))
    }

    // Skipping must not leave the app with no map to download.
    expect(PROPS.onComplete).toHaveBeenCalledWith(
      expect.objectContaining({ hikingDetailLevel: 'standard' }),
    )
  })
})

// --- The backdrop draw (#1054, lib/heroPhotos.ts) ---------------------------

describe('the photo behind the steps', () => {
  it('credits the photographer of whichever backdrop this run drew', () => {
    // The pool is random per mount, so what is pinned is the contract, not
    // the draw: some pool member's credit is on the plate, prefixed so the
    // photographer's name cannot read as the app's.
    render(<Onboarding {...PROPS} />)

    const credit = screen.getByText(/^Photo: /)
    expect(
      HERO_PHOTOS.some((photo) => credit.textContent === `Photo: ${photo.credit}`),
    ).toBe(true)
  })

  it('keeps the backdrop decorative to a screen reader', () => {
    // The steps are the content; the photo is the room they are read in.
    const { container } = render(<Onboarding {...PROPS} />)

    const hero = container.querySelector('.onboarding__hero')
    expect(hero).not.toBeNull()
    expect(hero).toHaveAttribute('aria-hidden', 'true')
    expect(hero?.querySelector('img')).toHaveAttribute('alt', '')
  })
})
