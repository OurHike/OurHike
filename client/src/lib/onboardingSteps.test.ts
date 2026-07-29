import { describe, it, expect } from 'vitest'
import { buildOnboardingProgress, ONBOARDING_STEPS } from './onboardingSteps'

// WIREFRAMES.md's Onboarding section: three skippable screens (What OurHike
// is / Map size / Location permission), step counter derived from the live
// step list, a skipped step still counts so the total never grows mid-flow.
// Accounts and notifications are never asked here - covered by the "never
// asked here" list, not this counter's concern.

describe('onboardingSteps', () => {
  it('has exactly the three MVP steps, in order', () => {
    expect(ONBOARDING_STEPS.map((s) => s.id)).toEqual([
      'what-ourhike-is',
      'map-size',
      'location-permission',
    ])
  })

  it('the total is derived from the live step list length, not a hardcoded number', () => {
    const progress = buildOnboardingProgress({
      currentStepId: 'what-ourhike-is',
      skippedStepIds: [],
    })
    expect(progress.total).toBe(ONBOARDING_STEPS.length)
  })

  it('a skipped step still counts toward the total - skipping does not shrink it', () => {
    const noSkips = buildOnboardingProgress({
      currentStepId: 'location-permission',
      skippedStepIds: [],
    })
    const oneSkipped = buildOnboardingProgress({
      currentStepId: 'location-permission',
      skippedStepIds: ['map-size'],
    })
    expect(oneSkipped.total).toBe(noSkips.total)
  })

  it('reports the correct 1-indexed position for the current step', () => {
    expect(
      buildOnboardingProgress({ currentStepId: 'what-ourhike-is', skippedStepIds: [] })
        .position,
    ).toBe(1)
    expect(
      buildOnboardingProgress({ currentStepId: 'map-size', skippedStepIds: [] }).position,
    ).toBe(2)
    expect(
      buildOnboardingProgress({
        currentStepId: 'location-permission',
        skippedStepIds: [],
      }).position,
    ).toBe(3)
  })

  it('formats as "of N" text using the live total, so adding a future step needs no call-site changes', () => {
    const progress = buildOnboardingProgress({
      currentStepId: 'map-size',
      skippedStepIds: [],
    })
    expect(progress.label).toBe(`2 of ${ONBOARDING_STEPS.length}`)
  })
})
