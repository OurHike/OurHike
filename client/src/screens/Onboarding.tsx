// First run (WIREFRAMES.md §5). Three steps, each skippable.
//
// A card over the live map, not a page instead of it. The shell puts the map
// behind these steps (App.tsx's onboarding branch) and this file is the half
// of that which leaves room to see it: the card is anchored to the bottom of
// the screen, capped well short of filling it, and scrolls its own contents if
// they outgrow that - so the map is visible above the steps on every screen
// size rather than only on tall ones.
//
// Every step says something about a thing that is now on screen. "The whole
// trail's topo map lives on your phone" is drawn behind that sentence; "pick
// how much detail" is a choice about the map being looked at; and the location
// step was always specified as an overlay over the map (§5), so the reason for
// asking is visible. Showing the claim is the argument here - a screenshot of
// a map, or a page of prose about one, is the thing this replaces.
//
// What is NOT here matters as much as what is:
//
//  - No notification prompt. OurHike sends exactly one kind of push - the
//    wrong-way alert - and it is asked for at hike start, when the reason is
//    concrete. Spending that permission during onboarding, before anyone has
//    seen the app work, is how an app gets denied notifications forever.
//  - No account prompt. Reading the map never needs an account; sign-in is
//    asked at the first contribution instead.
//
// The step counter comes from lib/onboardingSteps.ts, so a skipped step still
// counts and the total cannot grow mid-flow.
//
// THE MAP-SIZE STEP IS THE DOWNLOAD WINDOW'S QUESTION, IN THE DOWNLOAD
// WINDOW'S SHAPE (#298).
//
// First run ends by opening the download window (App.tsx), so this step and
// that window are two consecutive views of one decision - and they looked
// like two different decisions. Here, one flat list of levels; there, a
// sheet per tab, each with its own sizes. Same tabs now, same level ladder,
// same greying, from the same builders (screens/DetailPicker.tsx).
//
// WHAT THE USGS TAB DOES NOT DO IS CONFIGURE ANYTHING.
//
// #277 took the raster's tiers out of first run deliberately: offering the
// levels of a map the newcomer is not downloading, in place of the one they
// are, sized the wrong decision. That still holds, and the tab does not undo
// it - the USGS sheet is named and priced here, and its levels render
// greyed, pointing at Downloads. Showing what the optional map costs is not
// the same as asking a newcomer to configure it.
//
// That tab is ABSENT for v2, and the paragraph above is kept whole for when
// it returns. The USGS sheet is withdrawn (lib/packages.ts, #855), and a
// first-run step that prices a map the Downloads window will not sell would
// be worse than one that never mentions it. SHEET_TABS reads the catalog
// rather than listing the sheets, so nothing here had to learn about the
// withdrawal to stop showing it.
//
// What this step does NOT have at all is the download itself - no progress,
// no buttons, nothing on the phone to delete. That is the window's, one
// screen later; duplicating it would mean starting a download inside a flow
// whose last step has not been asked yet.

import { useState } from 'react'
import { Logo } from '../design-system/components'
import { ONBOARDING_STEPS, buildOnboardingProgress } from '../lib/onboardingSteps'
import type { HikingDetailLevel } from '../lib/userPreferences'
import { HIKING_SHEET, offeredSheets, USGS_SHEET } from '../lib/packages'
import { DetailPicker, hikingDetailOptions, rasterDetailOptions } from './DetailPicker'
import { useAvailableBytes } from '../lib/useAvailableBytes'
import { Tabs } from './Tabs'
import './onboarding.css'

/**
 * How much of the viewport the entry card is allowed to cover.
 *
 * The twin of `max-height` in onboarding.css, and the reason it is a number
 * here rather than only a CSS declaration: the map behind these steps has to be
 * framed against the part of the screen the card does NOT cover, which is
 * something only the map can do and only if it knows this figure
 * (App.tsx's `entryFitPadding`). test/entryLayout.test.ts asserts the two agree,
 * because a stylesheet and a constant drifting apart would leave the trail
 * fitted to a screen nobody can see.
 */
export const ENTRY_CARD_MAX_VIEWPORT_FRACTION = 0.78

export interface OnboardingResult {
  /** The hiking sheet's level (#276/#277) - the download decision this flow
   *  actually shows, so the preference written matches the choice made. */
  hikingDetailLevel: HikingDetailLevel
  locationRequested: boolean
}

export interface OnboardingProps {
  onComplete: (result: OnboardingResult) => void
}

/**
 * The sheets on offer, in the download window's own order - the background
 * everyone gets first, any optional second map after it. Named from the
 * catalog so first run and the window cannot come to call them different
 * things, and FILTERED by it too: a withdrawn sheet is not something to put
 * in front of a newcomer, and since #855 that is the USGS raster.
 *
 * So this is usually one tab today, and the strip disappears when it is -
 * the download window's own rule, for its own reason (Downloads.tsx): "a
 * single tab is a heading pretending to be a control". The two screens are
 * two consecutive views of one decision and they have to keep looking like
 * it.
 */
const SHEET_TABS = offeredSheets().map((sheet) => ({ id: sheet.id, label: sheet.title }))

export function Onboarding({ onComplete }: OnboardingProps) {
  const [stepIndex, setStepIndex] = useState(0)
  // Standard is pre-selected, so skipping every step still leaves a usable
  // map to download rather than no choice at all.
  const [hikingLevel, setHikingLevel] = useState<HikingDetailLevel>('standard')
  // Opens on the sheet this step is actually sizing (#277).
  const [openSheetId, setOpenSheetId] = useState(HIKING_SHEET.id)
  // So a level this phone cannot hold is greyed before it is chosen, rather
  // than refused after the newcomer has committed to it (#555).
  const { bytes: availableBytes } = useAvailableBytes()

  const step = ONBOARDING_STEPS[stepIndex]
  const progress = buildOnboardingProgress({
    currentStepId: step.id,
    skippedStepIds: [],
  })

  /** The open sheet's body - its summary and its levels. Lifted out of the
   *  tab strip because it is now rendered with or without one, and a panel
   *  that only exists inside `<Tabs>` cannot be shown when there is nothing
   *  to switch between. */
  const sheetPanel =
    openSheetId === HIKING_SHEET.id ? (
      <>
        <p className="onboarding__sheet-summary">{HIKING_SHEET.summary}</p>
        <DetailPicker
          options={hikingDetailOptions()}
          value={hikingLevel}
          onChange={(level) => setHikingLevel(level as HikingDetailLevel)}
          name="onboarding-detail"
          availableBytes={availableBytes}
        />
      </>
    ) : (
      <>
        <p className="onboarding__sheet-summary">{USGS_SHEET.summary}</p>
        {/* Named and priced, not configured (#277). Locked rather
            than absent so the newcomer can see what the optional map
            would cost before deciding they want it at all. */}
        <DetailPicker
          options={rasterDetailOptions()}
          value=""
          onChange={() => undefined}
          name="onboarding-usgs-detail"
          locked
          lockedNote="Chosen in Downloads, any time. This step is sizing the map you navigate by."
          availableBytes={availableBytes}
        />
      </>
    )

  const finish = (locationRequested: boolean) =>
    onComplete({ hikingDetailLevel: hikingLevel, locationRequested })

  const next = () => {
    if (stepIndex < ONBOARDING_STEPS.length - 1) setStepIndex(stepIndex + 1)
    else finish(false)
  }

  return (
    <main className="onboarding">
      {/* Keyed by step, so React rebuilds this subtree when the step changes
          and the card's entry animation runs again for each one (onboarding.css
          reduces it to nothing under prefers-reduced-motion). The steps rise
          over the map one at a time rather than the copy inside a static panel
          being swapped out underneath the reader. */}
      <div key={step.id} className="onboarding__card">
        <p className="onboarding__progress">{progress.label}</p>

        {step.id === 'what-ourhike-is' && (
          <section className="onboarding__step">
            <Logo />
            <h1 className="onboarding__title">What OurHike is</h1>
            <p>
              The whole trail&rsquo;s topo map lives on your phone. It works with no bars
              and no data plan &mdash; the way the trail actually is.
            </p>
            <p>
              Paid memberships and public support fund the ATC and the other organizations
              who keep these trails open.
            </p>
            <p className="onboarding__reassurance">No account. Nothing to sign up for.</p>
          </section>
        )}

        {step.id === 'map-size' && (
          <section className="onboarding__step">
            <h1 className="onboarding__title">Map size</h1>
            <p>
              The map you&rsquo;ll navigate by &mdash; the whole trail, in one download.
              Pick how much detail you want; you can change this later.
            </p>

            {SHEET_TABS.length > 1 ? (
              <Tabs
                label="Background maps"
                tabs={SHEET_TABS}
                activeId={openSheetId}
                onSelect={setOpenSheetId}
                idPrefix="onboarding-sheet"
              >
                {sheetPanel}
              </Tabs>
            ) : (
              sheetPanel
            )}
          </section>
        )}

        {step.id === 'location-permission' && (
          <section className="onboarding__step">
            <h1 className="onboarding__title">Your location</h1>
            <p>
              OurHike works with no signal at all. Your position never leaves your phone
              &mdash; nothing about where you are is sent anywhere.
            </p>
            <div className="onboarding__actions">
              <button
                type="button"
                className="onboarding__primary"
                onClick={() => finish(true)}
              >
                Allow location
              </button>
              <button
                type="button"
                className="onboarding__secondary"
                onClick={() => finish(false)}
              >
                Not now
              </button>
            </div>
          </section>
        )}

        <div className="onboarding__nav">
          {step.id !== 'location-permission' && (
            <button type="button" className="onboarding__primary" onClick={next}>
              Continue
            </button>
          )}
          <button type="button" className="onboarding__skip" onClick={next}>
            Skip
          </button>
        </div>
      </div>
    </main>
  )
}
