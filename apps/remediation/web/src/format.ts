import type { Action, Compass, Crew, Site, Tier } from './types'

export const ACTION_LABEL: Record<Action, string> = {
  close_restore: 'Close and restore',
  harden: 'Harden',
  adopt_note: 'Scores well',
  monitor: 'Monitor',
  monitor_recovery: 'Recovering',
  ok: 'OK',
  unknown: 'Unknown type',
}

export const CREW_LABEL: Record<Crew, string> = {
  one_person: 'One person',
  team: 'Team 2–3',
  crew: 'Crew 4+',
}

export const TIERS: Tier[] = ['P1', 'P2', 'P3']

const COMPASS_WORD: Record<Compass, string> = {
  N: 'north',
  NE: 'north-east',
  E: 'east',
  SE: 'south-east',
  S: 'south',
  SW: 'south-west',
  W: 'west',
  NW: 'north-west',
}

export function compassWord(toward: Compass): string {
  return COMPASS_WORD[toward]
}

const number = new Intl.NumberFormat('en-US')

export function feet(value: number | null): string {
  return value === null ? 'unknown' : `${number.format(Math.round(value))} ft`
}

export function miles(value: number | null): string {
  return value === null ? 'unknown' : `${value.toFixed(1)} mi`
}

export function count(value: number): string {
  return number.format(value)
}

/** A site's name as ATC writes it, or its id when ATC gives none. */
export function siteName(site: Site): string {
  return site.name?.trim() || `Site ${site.rims_id.slice(0, 8)}`
}

/** "User-created campsite", "Shelter", ... in sentence case. */
export function siteKind(site: Site): string {
  switch (site.site_type) {
    case 'User Created Campsite':
      return 'User-created campsite'
    case 'A.T. Club or Agency Created Campsite':
      return 'Club or agency campsite'
    case 'Shelter':
      return 'Shelter'
    default:
      return 'Type not recorded'
  }
}

export function isOfficial(site: Site): boolean {
  return (
    site.site_type === 'Shelter' ||
    site.site_type === 'A.T. Club or Agency Created Campsite'
  )
}

/** The placeholder regime's machine name, in words, with the question mark kept (PLAN.md §2e). */
export function regimeWords(regime: string): string {
  const words: Record<string, string> = {
    'dispersed_allowed?': 'dispersed camping allowed?',
    'designated_only?': 'designated sites only?',
    'permit_or_designated?': 'permit or designated sites?',
    'restricted?': 'camping restricted?',
    unknown: 'not known',
  }
  return words[regime] ?? regime
}
