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

import { useState } from 'react'
import { Logo } from '../design-system/components'
import { ONBOARDING_STEPS, buildOnboardingProgress } from '../lib/onboardingSteps'
import type { DetailLevel } from '../lib/downloadDetail'
import { DetailPicker } from './DetailPicker'
import './onboarding.css'

export interface OnboardingResult {
  detailLevel: DetailLevel
  locationRequested: boolean
}

export interface OnboardingProps {
  onComplete: (result: OnboardingResult) => void
}

export function Onboarding({ onComplete }: OnboardingProps) {
  const [stepIndex, setStepIndex] = useState(0)
  // Standard is pre-selected, so skipping every step still leaves a usable
  // map to download rather than no choice at all.
  const [detailLevel, setDetailLevel] = useState<DetailLevel>('standard')

  const step = ONBOARDING_STEPS[stepIndex]
  const progress = buildOnboardingProgress({
    currentStepId: step.id,
    skippedStepIds: [],
  })

  const finish = (locationRequested: boolean) =>
    onComplete({ detailLevel, locationRequested })

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

      {step.id === 'map-size' && (
        <section className="onboarding__step">
          <h1 className="onboarding__title">Map size</h1>
          <p>
            The whole trail, in one download. Pick how much detail you want &mdash; you
            can change this later.
          </p>
          <DetailPicker value={detailLevel} onChange={setDetailLevel} />
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
