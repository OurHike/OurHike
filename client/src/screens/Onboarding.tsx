// First run (WIREFRAMES.md §5). Three steps, each skippable.
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
// THE MAP-SIZE STEP IS THE DOWNLOAD WINDOW'S QUESTION, ASKED IN THE DOWNLOAD
// WINDOW'S SHAPE (#298).
//
// First run ends by opening the download window (App.tsx), so this step and
// that window are two consecutive views of the same decision - and they used
// to disagree about what the decision was. This asked for one detail level,
// full stop; the window offers a sheet per tab, each with its own sizes, and
// the level being chosen here only ever applied to one of them. Someone
// picking "Light 64 MB" on this screen and meeting a 1.14 GB hiking sheet on
// the next has been misled by us, not by the map.
//
// So the same components render both: the same tabs (screens/Tabs.tsx), the
// same levels, the same greyed-out where a sheet has none
// (screens/DetailPicker.tsx), from the same catalog (lib/packages.ts). What
// this step does NOT have is the download itself - no progress, no buttons,
// nothing already on the phone to delete. That is the window's, one screen
// later, and duplicating it here would mean starting a download inside a flow
// whose last step has not been asked yet.

import { useState } from 'react'
import { Logo } from '../design-system/components'
import { ONBOARDING_STEPS, buildOnboardingProgress } from '../lib/onboardingSteps'
import type { DetailLevel } from '../lib/downloadDetail'
import {
  offeredSheets,
  sheetDetailOptions,
  sheetSizeBytes,
  type BackgroundSheet,
} from '../lib/packages'
import { DetailPicker } from './DetailPicker'
import { Tabs } from './Tabs'
import './onboarding.css'

export interface OnboardingResult {
  detailLevel: DetailLevel
  locationRequested: boolean
}

export interface OnboardingProps {
  onComplete: (result: OnboardingResult) => void
}

/** The sheets on offer, read once - the catalog is a constant, not state. */
const SHEETS = offeredSheets()

export function Onboarding({ onComplete }: OnboardingProps) {
  const [stepIndex, setStepIndex] = useState(0)
  // Standard is pre-selected, so skipping every step still leaves a usable
  // map to download rather than no choice at all.
  const [detailLevel, setDetailLevel] = useState<DetailLevel>('standard')
  // The default background's tab first, the same order the download window
  // opens on (lib/packages.ts). Opening on the sheet with the sizes would put
  // the optional gigabyte of government raster in front of the map everyone
  // actually navigates by.
  const [openSheetId, setOpenSheetId] = useState(SHEETS[0]?.id ?? '')
  const openSheet = SHEETS.find((sheet) => sheet.id === openSheetId) ?? SHEETS[0]

  const step = ONBOARDING_STEPS[stepIndex]
  const progress = buildOnboardingProgress({
    currentStepId: step.id,
    skippedStepIds: [],
  })

  const finish = (locationRequested: boolean) =>
    onComplete({ detailLevel, locationRequested })

  /** One sheet's levels: its own sizes, or all three greyed with its one size
   *  stated. The same picker the download window renders. */
  const sheetPicker = (sheet: BackgroundSheet) => (
    <DetailPicker
      value={detailLevel}
      onChange={setDetailLevel}
      options={sheetDetailOptions(sheet)}
      singleSizeBytes={sheetSizeBytes(sheet, detailLevel)}
      name="onboarding-map-detail"
    />
  )

  const next = () => {
    if (stepIndex < ONBOARDING_STEPS.length - 1) setStepIndex(stepIndex + 1)
    else finish(false)
  }

  return (
    <main className="onboarding">
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
            Paid memberships fund the ATC and the volunteer clubs who keep the trail open.
          </p>
          <p className="onboarding__reassurance">No account. Nothing to sign up for.</p>
        </section>
      )}

      {step.id === 'map-size' && openSheet !== undefined && (
        <section className="onboarding__step">
          <h1 className="onboarding__title">Map size</h1>
          <p>
            The whole trail, in one download. Each background map has its own size &mdash;
            pick the detail you want, and you can change this later.
          </p>

          {SHEETS.length > 1 ? (
            <Tabs
              label="Background maps"
              tabs={SHEETS.map((sheet) => ({ id: sheet.id, label: sheet.title }))}
              activeId={openSheet.id}
              onSelect={setOpenSheetId}
              idPrefix="onboarding-sheet"
            >
              <p className="onboarding__sheet-summary">{openSheet.summary}</p>
              {sheetPicker(openSheet)}
            </Tabs>
          ) : (
            sheetPicker(openSheet)
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
    </main>
  )
}
