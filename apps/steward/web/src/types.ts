// The shapes of the two files the analysis job writes (apps/steward/pipeline/steward_analysis/build.py).
// The job is the one home for what these mean; this file only names them for the compiler.

export type Tier = 'P1' | 'P2' | 'P3'
export type Action =
  | 'close_restore'
  | 'harden'
  | 'adopt_note'
  | 'monitor'
  | 'monitor_recovery'
  | 'ok'
  | 'unknown'
export type Crew = 'one_person' | 'team' | 'crew'
export type Compass = 'N' | 'NE' | 'E' | 'SE' | 'S' | 'SW' | 'W' | 'NW'

export interface FromTrail {
  lat: number
  lon: number
  ft: number
  bearing_deg: number
  toward: Compass
}

export const WEIGHT_NAMES = [
  'deficit',
  'water',
  'trail',
  'cluster',
  'restricted',
] as const
export type WeightName = (typeof WEIGHT_NAMES)[number]
export type Weights = Record<WeightName, number>
export type NeedParts = Record<WeightName, number>

export type Camping =
  { source: 'guess'; regime: string } | { source: 'reviewed'; restricted: boolean }

export interface Site {
  rims_id: string
  global_id: string
  name: string | null
  club: string | null
  region: string | null
  site_type: string | null
  inventory_status: string | null
  documented_in: string[]
  lat: number
  lon: number
  mile: number | null
  csi: number | null
  indicators: Record<string, number | null>
  size_ft2: number | null
  water_ft: number | null
  water_ft_source: string | null
  trail_ft: number | null
  nearest_site_ft: number | null
  slope_footprint_pct: number | null
  complex_id: string
  complex_size: number
  nearest_parking: { name: string | null; mi: number | null }
  from_trail: FromTrail | null
  land_unit: {
    manager: string | null
    designation: string | null
    name: string | null
    state: string | null
  }
  camping: Camping
  need: number
  /** What each weight multiplies for this site (rules.need_parts); null where the
   *  assessment is incomplete. A club's need is the weighted sum: src/ranking.ts. */
  need_parts: NeedParts | null
  tier: Tier | null
  action: Action
  crew: Crew | null
}

export interface ClubCounts {
  club: string | null
  sites: number
  actionable: number
  p1: number
  p2: number
  p3: number
  one_person: number
  team: number
  crew: number
}

export interface Summary {
  generated_at: string
  source: {
    layer: string
    data_last_edited: string | null
    sites: number
    skipped_no_location: number
  }
  csi_formula: { reproduces: number; of: number; incomplete_rows: number }
  sites_by_type: Record<string, number>
  actions: Record<string, number>
  priority_by_crew: {
    tier: Tier
    one_person: number
    team: number
    crew: number
    total: number
  }[]
  from_trail?: {
    given: number
    withheld_disagreeing_with_atc: number
    agreement_ft: number
  }
  complexes: {
    join_ft: number
    count: number
    with_2_plus: number
    with_4_plus: number
    largest: number
  }
  clubs: ClubCounts[]
  camping_rules: {
    reviewed_units: number
    status: string
    guesses: Record<string, number>
  }
  method: {
    weights: Weights
    tiers: { P1_min: number; P2_min: number }
    work_csi_max: number
    close_water_ft: number
    adopt_csi_min: number
    one_person_max_ft2: number
    crew_min_ft2: number
    csi_weights: Record<string, number>
  }
}
