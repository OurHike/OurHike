// Onboarding step counter. See WIREFRAMES.md's Onboarding — Tier 1 section:
// three skippable screens, counter derived from the live step list so a
// skipped step still counts (the total never shrinks mid-flow) and a future
// step (e.g. trail name, still Post-MVP) can be added without touching call
// sites - they all just read ONBOARDING_STEPS.length indirectly.

export interface OnboardingStep {
  id: 'what-ourhike-is' | 'map-size' | 'location-permission'
  skippable: true
}

export const ONBOARDING_STEPS: OnboardingStep[] = [
  { id: 'what-ourhike-is', skippable: true },
  { id: 'map-size', skippable: true },
  { id: 'location-permission', skippable: true },
]

export interface OnboardingProgressInput {
  currentStepId: OnboardingStep['id']
  skippedStepIds: OnboardingStep['id'][]
}

export interface OnboardingProgress {
  position: number
  total: number
  label: string
}

export function buildOnboardingProgress({
  currentStepId,
}: OnboardingProgressInput): OnboardingProgress {
  const total = ONBOARDING_STEPS.length
  const position = ONBOARDING_STEPS.findIndex((s) => s.id === currentStepId) + 1

  return { position, total, label: `${position} of ${total}` }
}
