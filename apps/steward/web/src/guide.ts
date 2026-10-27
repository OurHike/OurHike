// The remediation guide: apps/steward/PLAN.md §7, read from ATC's documents on 2026-10-24.
// ATC's terms allow quoting but no other reproduction "without our prior written
// permission" (decided 2026-10-24: summarize, quote briefly, link). So every step here is
// our own words, carries at most a short quote, and names the document it comes from.
// A site page's plan is the step list for its action, from this file, so the two cannot drift.

import type { Action } from './types'

export interface Source {
  title: string
  url: string
}

export const SOURCES = {
  planning2023: {
    title: 'ATC Overnight Site Planning Guidance (2023)',
    url: 'https://appalachiantrail.org/wp-content/uploads/2023/09/202309-ATC-Overnight-Site-Planning-Guidance.pdf',
  },
  marion2003: {
    title: 'Marion, Camping Impact Management on the A.T. (2003, published by ATC)',
    url: 'https://appalachiantrail.org/wp-content/uploads/2020/05/camping-impact-mgmt-on-the-a-t-.pdf',
  },
  bmp2019: {
    title: 'Sustainable Camping BMPs review draft (USGS, 2019, hosted by ATC)',
    url: 'https://appalachiantrail.org/wp-content/uploads/2020/04/at-final-rpt-bmp-review-draft.pdf',
  },
  facilities: {
    title: 'ATC: Trail facility management',
    url: 'https://appalachiantrail.org/protect/trail-management/at-partner-resources/trail-facility-management/',
  },
  protections: {
    title: 'ATC: Volunteer protections',
    url: 'https://appalachiantrail.org/get-involved/volunteer/safety-training/volunteer-protections/',
  },
  agreements: {
    title: 'ATC: Volunteer services agreements',
    url: 'https://appalachiantrail.org/wp-content/uploads/2020/04/volunteer-services-agreements.pdf',
  },
  hazards: {
    title: 'ATC: Job hazard analyses library',
    url: 'https://appalachiantrail.org/get-involved/volunteer/safety-training/job-hazard-analyses-library/',
  },
  handTools: {
    title: 'ATC: Hand tools hazard analysis',
    url: 'https://appalachiantrail.org/wp-content/uploads/2020/04/hand-tools-1.pdf',
  },
  checkIn: {
    title: 'ATC: Check-in and check-out policy',
    url: 'https://appalachiantrail.org/wp-content/uploads/2022/07/Check-in-Checkout-Policy.pdf',
  },
  updates: {
    title: 'ATC: Trail updates',
    url: 'https://appalachiantrail.org/trail-updates/',
  },
  regulations: {
    title: 'ATC: Camping regulations',
    url: 'https://appalachiantrail.org/explore/hike-the-a-t/thru-hiking/camping-regulations/',
  },
} satisfies Record<string, Source>

export type SourceKey = keyof typeof SOURCES

export interface Step {
  title: string
  detail: string
  quote?: string
  source: SourceKey
  /** Work ATC's documents put behind land-manager approval. */
  needsApproval?: boolean
}

export const CLOSE_AND_RESTORE: Step[] = [
  {
    title: 'Photograph first',
    detail:
      'Take the before photos from fixed points, so the next visit can line up on them and compare.',
    quote:
      'a photographic record of existing site sizes and conditions provide a baseline… prior to implementing corrective actions',
    source: 'bmp2019',
  },
  {
    title: 'Hide the site',
    detail:
      'Drag woody debris over the bare ground and spread leaf litter. Use big pieces: small brush is soon cleared away.',
    quote: 'The objective is to hide the site.',
    source: 'marion2003',
  },
  {
    title: 'Take down the new fire ring',
    detail:
      'Scatter the rocks and the ash. Leave an established fire ring at an official site alone.',
    quote: 'only dismantle new fire sites',
    source: 'marion2003',
  },
  {
    title: 'Block the way in',
    detail:
      'Close the side path where it leaves the A.T., with rocks and woody debris, so the site stops being found.',
    quote:
      'where they first leave the A.T. with rocks, woody debris and possibly transplanted shrubs',
    source: 'marion2003',
  },
  {
    title: 'Sign it, if your club agrees',
    detail:
      'A small post asking campers to let the site recover. Ask your club before putting one up.',
    quote: 'Campsite Closed - Please allow this site to recover',
    source: 'marion2003',
  },
  {
    title: 'Restore the ground, only with approval',
    detail:
      'Half-buried rocks, transplants and watering are land-manager work. Ask your club; do not start it on your own.',
    quote: 'These generally require land management agency actions and approval.',
    source: 'marion2003',
    needsApproval: true,
  },
  {
    title: 'Come back after busy weekends',
    detail:
      'Spread the debris again where campers have moved it. Most of the work happens in the first three years.',
    quote: 'The bulk of this work will occur during the first three years.',
    source: 'marion2003',
  },
]

export const HARDEN: Step[] = [
  {
    title: 'Consult before any work',
    detail:
      'Renovating an official site is a club decision made with ATC and the land manager.',
    quote: 'Trail Clubs must consult with ATC and their land management partners',
    source: 'planning2023',
    needsApproval: true,
  },
  {
    title: 'Define the footprint',
    detail:
      'Prefer side-hill benches, which the slope stops from growing; keep tent platforms few and one central fire ring.',
    quote: 'where the slope is >15%',
    source: 'planning2023',
    needsApproval: true,
  },
  {
    title: 'Build tent pads',
    detail:
      'Cut-and-fill pads with stone cribbing and a crowned surface, one to three a site (up to five for groups).',
    source: 'marion2003',
    needsApproval: true,
  },
  {
    title: 'Keep the distances',
    detail:
      'Sites at least 200 ft from water and out of sight of the footpath; a privy at least 200 ft from water and from the campsites.',
    quote: 'at least 200 feet from water sources',
    source: 'planning2023',
  },
]

/** A site page's plan: the guide's steps for its action, or nothing for an action that is not work. */
export function planFor(action: Action): Step[] {
  if (action === 'close_restore') return CLOSE_AND_RESTORE
  if (action === 'harden') return HARDEN
  return []
}

export interface CoverNote {
  text: string
  quote: string
  source: SourceKey
}

export const WHO_IS_COVERED: CoverNote[] = [
  {
    text: "ATC's volunteer protections cover people working through a maintaining club or ATC.",
    quote: 'under the auspices of one of the designated Trail maintaining clubs or ATC',
    source: 'protections',
  },
  {
    text: 'Everyone going signs the club’s volunteer agreement, even for a short visit.',
    quote:
      'must be completed and signed by any and all participants… even for projects lasting only a few hours',
    source: 'agreements',
  },
  {
    text: 'Every group has someone named as its supervisor.',
    quote: 'each individual or group must have a stated supervisor',
    source: 'agreements',
  },
]

export interface Check {
  text: string
  source: SourceKey
}

export const BEFORE_YOU_GO: Check[] = [
  {
    text: "You're on your club's volunteer roster and have signed its agreement",
    source: 'protections',
  },
  { text: 'Your club knows who is going, when, and to which site', source: 'agreements' },
  {
    text: 'Everyone going has read the hazard analysis for hand tools',
    source: 'hazards',
  },
  {
    text: 'Gloves, boots, long pants and eye protection; a hard hat if anyone works below someone else',
    source: 'handTools',
  },
  {
    text: 'Your check-in contact has your vehicle, parking spot, route and return time',
    source: 'checkIn',
  },
  { text: 'Weather and ATC trail updates checked for the section', source: 'updates' },
]
