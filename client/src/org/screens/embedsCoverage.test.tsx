/**
 * The console's coverage-badge preview draws what the badge actually draws.
 *
 * WHY THIS TEST EXISTS. `preview-shots/org-embed-preview.mjs` states the
 * contract this screen is built on: "THE LIVE PREVIEW IS THE EVIDENCE AND THE
 * PASTE IS THE CLAIM." An embed is a line of HTML an organization copies onto
 * a page we will never see, so the panel headed "Live preview · this is what
 * visitors see" is the only thing standing behind the paste above it.
 *
 * It stopped being true when the badge was rebuilt. `ourhike.js`'s
 * `mountCoverage` drew a gap count off `GET /clubs/{slug}/coverage` - a gated
 * endpoint, so on every real site it drew NOTHING - and was replaced with the
 * design's scoreboard off the public `/scoreboard`. The preview here was not,
 * so the console promised an organization a sentence about their gaps and
 * their own homepage would have shown three counts.
 *
 * Both halves of that are worth a test, and the second one is the safety
 * rule rather than a cosmetic mismatch: `features/ORG_ONBOARDING.md` has the
 * argument, which is that a public list of which miles nobody is looking
 * after is a list of miles to avoid. A preview that offers one teaches an
 * organization to expect it.
 */

import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it } from 'vitest'

import { Embeds } from './Embeds'
import { DEMO_SCOREBOARD } from '../demoOrg'

afterEach(cleanup)

function drawEmbeds() {
  return render(
    <Embeds
      orgName="Central Park Throughikers"
      slug="central-park-throughikers"
      scriptOrigin="https://ourhike.org"
      hikes={[]}
      workdays={[]}
      scoreboard={DEMO_SCOREBOARD}
      keys={[]}
      freshSecret={null}
      consoleEnabled={false}
      canEdit={false}
      onCreateKey={() => {}}
      onRevokeKey={() => {}}
      units="imperial"
    />,
  )
}

async function openTheCoverageTab() {
  drawEmbeds()
  await userEvent.click(screen.getByRole('button', { name: 'Coverage badge' }))
}

describe('the coverage badge preview, against what the embed draws', () => {
  it('draws the three figures the embed draws, each with its own label', async () => {
    await openTheCoverageTab()
    for (const label of ['Miles maintained', 'Active volunteers', 'Hours this season']) {
      expect(screen.getByText(label)).toBeInTheDocument()
    }
    expect(screen.getByText(String(DEMO_SCOREBOARD.miles_maintained))).toBeInTheDocument()
    expect(
      screen.getByText(String(DEMO_SCOREBOARD.active_volunteers)),
    ).toBeInTheDocument()
    expect(
      screen.getByText(String(DEMO_SCOREBOARD.hours_this_season)),
    ).toBeInTheDocument()
  })

  it('never offers an organization a gap count to put on their own homepage', async () => {
    // The old preview read "3 of 12 sections looking for somebody". The
    // coverage report is right to be gated and this is the screen that would
    // teach an org to expect it in public.
    await openTheCoverageTab()
    expect(screen.queryByText(/looking for somebody/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/sections/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/\bgap/i)).not.toBeInTheDocument()
  })

  it('does not claim a freshness the badge does not have', async () => {
    // `ourhike.js` computes the figures when the badge loads and says so.
    // "Updated nightly" is the design mock-up's line and nothing delivers it.
    await openTheCoverageTab()
    expect(screen.queryByText(/nightly/i)).not.toBeInTheDocument()
    expect(screen.getByText(/when this page loaded/i)).toBeInTheDocument()
  })
})
