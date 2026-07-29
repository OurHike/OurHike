// How staleness and confidence are shown (WIREFRAMES.md §11).
//
// They are two separate channels and are kept as two separate functions on
// purpose:
//   - staleness  = when a human last said this was fine   -> ring + fade
//   - confidence = was it ever verified to exist          -> dashed outline
//
// A dashed pin that is Fresh means "we're not certain this spring exists, but
// someone checked recently." A solid pin that is Stale means "it definitely
// exists, but nobody has looked in months." Those are different things to
// tell a hiker who is deciding whether to carry two more litres, and merging
// the channels would collapse them into one vague signal.
//
// Deliberately NO prominence or boost output. Raising stale POIs' visibility
// to solicit confirmations is DATA_NUDGES.md's territory and Post-MVP; today
// staleness is described, never amplified.

import type { StalenessTier } from './staleness'

export interface StalenessTreatment {
  ring: 'green' | 'none' | 'grey-dotted'
  opacity: number
  borderStyle: 'solid' | 'dotted'
}

export interface ConfidenceTreatment {
  outline: 'solid' | 'dashed'
}

const TREATMENTS: Record<StalenessTier, StalenessTreatment> = {
  fresh: { ring: 'green', opacity: 1, borderStyle: 'solid' },
  // No ring at all - the absence is the middle state, so the map doesn't
  // acquire a third ring colour that has to be learned.
  ageing: { ring: 'none', opacity: 1, borderStyle: 'solid' },
  stale: { ring: 'grey-dotted', opacity: 0.5, borderStyle: 'dotted' },
}

export function stalenessTreatment(tier: StalenessTier): StalenessTreatment {
  return TREATMENTS[tier]
}

export function confidenceTreatment(confidence: 'high' | 'low'): ConfidenceTreatment {
  return { outline: confidence === 'low' ? 'dashed' : 'solid' }
}

const DAY_MS = 24 * 60 * 60 * 1000

/**
 * The words that accompany the visual channel - WIREFRAMES.md insists the
 * state is always stated in text too, since a ring alone is not readable in
 * glare or by someone who has never been told what it means.
 */
export function lastConfirmedText(lastConfirmed: Date | null, now: Date): string {
  if (lastConfirmed === null) return 'Never confirmed'

  const month = lastConfirmed.toLocaleDateString('en-US', {
    month: 'long',
    timeZone: 'UTC',
  })
  const days = Math.floor((now.getTime() - lastConfirmed.getTime()) / DAY_MS)

  if (days === 0) return `Last confirmed in ${month} · today`
  if (days === 1) return `Last confirmed in ${month} · yesterday`
  return `Last confirmed in ${month} · ${days} days ago`
}
