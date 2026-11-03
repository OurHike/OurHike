// A club's own ranking (#1906): the same need score under that club's weights.
//
// The analysis job writes each site's need_parts, the multipliers of the five
// weights, so the need under any weights is their weighted sum. This file is
// that sum and nothing else: the rules that produce the parts live only in
// apps/remediation/pipeline/remediation_analysis/rules.py, and need_from_parts there is
// this function's twin, down to adding in WEIGHT_NAMES order and rounding a half
// up, so the two give the same integer for the same weights.

import { WEIGHT_NAMES, type Action, type Site, type Tier, type Weights } from './types'

const ACTIONABLE: Action[] = ['close_restore', 'harden']

export function needUnder(site: Site, weights: Weights): number {
  if (site.need_parts === null) return site.need
  let score = 0
  for (const name of WEIGHT_NAMES) score += weights[name] * site.need_parts[name]
  return Math.floor(Math.min(Math.max(score, 0), 100) + 0.5)
}

export function tierFor(
  need: number,
  action: Action,
  tiers: { P1_min: number; P2_min: number },
): Tier | null {
  if (!ACTIONABLE.includes(action)) return null
  if (need >= tiers.P1_min) return 'P1'
  return need >= tiers.P2_min ? 'P2' : 'P3'
}

export function sameWeights(a: Weights, b: Weights): boolean {
  return WEIGHT_NAMES.every((name) => a[name] === b[name])
}

/** The sites with need and tier recomputed under `weights`; the input is untouched. */
export function rerank(
  sites: Site[],
  weights: Weights,
  tiers: { P1_min: number; P2_min: number },
): Site[] {
  return sites.map((site) => {
    const need = needUnder(site, weights)
    return { ...site, need, tier: tierFor(need, site.action, tiers) }
  })
}
