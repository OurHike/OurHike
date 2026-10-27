// Invented sites for tests, local development and screenshots: never real ones.
// Every site sits near 0°N 0°E, in the Gulf of Guinea, so no picture taken from these can
// show a real user-created campsite (CLAUDE.md's screenshot rule). Clubs, names and miles
// are made up too. `npm run dev:fixtures` serves the app on these.

import { needUnder, tierFor } from './ranking'
import type { Action, Crew, NeedParts, Site, Summary, Tier, Weights } from './types'

const FEET_PER_DEG = 364_000

interface Seed {
  n: number
  club: string
  north: number
  east: number
  type: 'User Created Campsite' | 'Shelter' | 'A.T. Club or Agency Created Campsite'
  action: Action
  crew: Crew | null
  csi: number
  size: number
  water: number
  complex: number
  withheld?: boolean
}

const SEEDS: Seed[] = [
  {
    n: 1,
    club: 'Example Trail Club',
    north: 0,
    east: 0,
    type: 'User Created Campsite',
    action: 'close_restore',
    crew: 'team',
    csi: 7,
    size: 900,
    water: 60,
    complex: 3,
  },
  {
    n: 2,
    club: 'Example Trail Club',
    north: 150,
    east: 40,
    type: 'User Created Campsite',
    action: 'close_restore',
    crew: 'crew',
    csi: 9,
    size: 1800,
    water: 140,
    complex: 3,
  },
  {
    n: 3,
    club: 'Example Trail Club',
    north: 260,
    east: -30,
    type: 'Shelter',
    action: 'harden',
    crew: 'crew',
    csi: 8,
    size: 2400,
    water: 310,
    complex: 3,
  },
  {
    n: 4,
    club: 'Example Trail Club',
    north: 6000,
    east: 500,
    type: 'User Created Campsite',
    action: 'close_restore',
    crew: 'one_person',
    csi: 8,
    size: 280,
    water: 420,
    complex: 1,
  },
  {
    n: 5,
    club: 'Example Trail Club',
    north: 9000,
    east: -800,
    type: 'User Created Campsite',
    action: 'close_restore',
    crew: 'one_person',
    csi: 11,
    size: 350,
    water: 95,
    complex: 1,
  },
  {
    n: 6,
    club: 'Example Trail Club',
    north: 12000,
    east: 300,
    type: 'A.T. Club or Agency Created Campsite',
    action: 'harden',
    crew: 'crew',
    csi: 12,
    size: 1200,
    water: 600,
    complex: 1,
  },
  {
    n: 7,
    club: 'Example Trail Club',
    north: 15000,
    east: -200,
    type: 'User Created Campsite',
    action: 'close_restore',
    crew: 'team',
    csi: 12,
    size: 700,
    water: 260,
    complex: 1,
  },
  {
    n: 8,
    club: 'Example Trail Club',
    north: 18000,
    east: 900,
    type: 'User Created Campsite',
    action: 'adopt_note',
    crew: null,
    csi: 24,
    size: 220,
    water: 330,
    complex: 1,
  },
  {
    n: 9,
    club: 'Example Trail Club',
    north: 21000,
    east: 100,
    type: 'User Created Campsite',
    action: 'monitor',
    crew: null,
    csi: 16,
    size: 500,
    water: 520,
    complex: 1,
  },
  {
    n: 10,
    club: 'Example Trail Club',
    north: 24000,
    east: -400,
    type: 'Shelter',
    action: 'ok',
    crew: null,
    csi: 23,
    size: 600,
    water: 250,
    complex: 1,
    withheld: true,
  },
  {
    n: 11,
    club: 'Second Example Club',
    north: 40000,
    east: 0,
    type: 'User Created Campsite',
    action: 'close_restore',
    crew: 'team',
    csi: 10,
    size: 650,
    water: 80,
    complex: 2,
  },
  {
    n: 12,
    club: 'Second Example Club',
    north: 40120,
    east: 60,
    type: 'User Created Campsite',
    action: 'close_restore',
    crew: 'team',
    csi: 12,
    size: 480,
    water: 180,
    complex: 2,
  },
  {
    n: 13,
    club: 'Second Example Club',
    north: 45000,
    east: -600,
    type: 'User Created Campsite',
    action: 'monitor_recovery',
    crew: null,
    csi: 14,
    size: 300,
    water: 400,
    complex: 1,
  },
  {
    n: 14,
    club: 'Second Example Club',
    north: 50000,
    east: 250,
    type: 'User Created Campsite',
    action: 'close_restore',
    crew: 'one_person',
    csi: 12,
    size: 260,
    water: 700,
    complex: 1,
  },
]

const DEFAULT_WEIGHTS: Weights = {
  deficit: 60,
  water: 12,
  trail: 6,
  cluster: 8,
  restricted: 10,
}

/** The analysis job's rules.need_parts, for these invented facts, so need and tier
 *  below come out as the job would write them rather than as typed numbers. */
function needParts(seed: Seed, trailFt: number): NeedParts {
  if (seed.action === 'monitor_recovery') {
    return { deficit: 0, water: 0, trail: 0, cluster: 0, restricted: 0 }
  }
  return {
    deficit: (30 - seed.csi) / 27,
    water: seed.water < 100 ? 1 : seed.water < 200 ? 0.5 : 0,
    trail: trailFt < 50 ? 1 : 0,
    cluster: seed.complex >= 4 ? 1 : seed.complex >= 2 ? 0.5 : 0,
    restricted: 0,
  }
}

function site(seed: Seed): Site {
  const lat = seed.north / FEET_PER_DEG
  const lon = seed.east / FEET_PER_DEG
  const trailFt = 40 + (seed.n % 4) * 60
  const parts = needParts(seed, trailFt)
  const scored = { need: 0, need_parts: parts } as Site
  const need = needUnder(scored, DEFAULT_WEIGHTS)
  return {
    rims_id: `example-${String(seed.n).padStart(4, '0')}`,
    global_id: `example-global-${seed.n}`,
    name:
      seed.type === 'Shelter' ? `Example Shelter ${seed.n}` : `Example site ${seed.n}`,
    club: seed.club,
    region: 'EXAMPLE',
    site_type: seed.type,
    inventory_status:
      seed.action === 'monitor_recovery' ? 'Closed/Recovering' : 'Established',
    documented_in: seed.n % 3 === 0 ? ['FarOut'] : [],
    lat,
    lon,
    mile: 100 + seed.north / 5280,
    csi: seed.csi,
    indicators: {
      Expansion_Potential_Indicator: 1,
      Size_Indicator:
        seed.size > 1500 ? 0 : seed.size > 750 ? 1 : seed.size > 300 ? 2 : 3,
      Proximity_Other_Site_Indicator: seed.complex > 1 ? 1 : 3,
      Proximity_Water_Ecological_Indicator:
        seed.water < 50 ? 0 : seed.water < 100 ? 1 : seed.water < 200 ? 2 : 3,
      Proximity_Water_Social_Indicator: 2,
      Proximity_AT_Indicator:
        trailFt < 50 ? 0 : trailFt < 100 ? 1 : trailFt < 200 ? 2 : 3,
      Side_Hill_Footprint_Indicator: 0,
      Side_Hill_Buffer_Indicator: 0,
    },
    size_ft2: seed.size,
    water_ft: seed.water,
    water_ft_source: 'NHDP_HR_Stream',
    trail_ft: trailFt,
    nearest_site_ft: seed.complex > 1 ? 120 : 2400,
    slope_footprint_pct: 6,
    complex_id:
      seed.complex > 1 ? `cx-example-${seed.club.length}` : `cx-example-solo-${seed.n}`,
    complex_size: seed.complex,
    nearest_parking: {
      name: seed.club === 'Example Trail Club' ? 'Example Gap lot' : 'Example Notch lot',
      mi: 0.4 + (seed.n % 5) * 0.3,
    },
    from_trail: seed.withheld
      ? null
      : {
          lat,
          lon: lon - trailFt / FEET_PER_DEG,
          ft: trailFt,
          bearing_deg: 90,
          toward: 'E',
        },
    land_unit: {
      manager: 'USFS',
      designation: 'NF',
      name: 'Example National Forest',
      state: 'XX',
    },
    camping: { source: 'guess', regime: 'dispersed_allowed?' },
    need,
    need_parts: parts,
    tier: tierFor(need, seed.action, { P1_min: 60, P2_min: 50 }),
    action: seed.action,
    crew: seed.crew,
  }
}

export const fixtureSites: Site[] = SEEDS.map(site)

function tally<T extends string>(values: (T | null)[]): Record<string, number> {
  const out: Record<string, number> = {}
  for (const v of values) out[v ?? '(none)'] = (out[v ?? '(none)'] ?? 0) + 1
  return out
}

export const fixtureSummary: Summary = {
  generated_at: '2026-10-27T00:00:00+00:00',
  source: {
    layer: 'example',
    data_last_edited: '2026-08-20',
    sites: fixtureSites.length,
    skipped_no_location: 0,
  },
  csi_formula: {
    reproduces: fixtureSites.length,
    of: fixtureSites.length,
    incomplete_rows: 0,
  },
  sites_by_type: tally(fixtureSites.map((s) => s.site_type)),
  actions: tally(fixtureSites.map((s) => s.action)),
  priority_by_crew: (['P1', 'P2', 'P3'] as Tier[]).map((tier) => {
    const inTier = fixtureSites.filter((s) => s.tier === tier)
    return {
      tier,
      one_person: inTier.filter((s) => s.crew === 'one_person').length,
      team: inTier.filter((s) => s.crew === 'team').length,
      crew: inTier.filter((s) => s.crew === 'crew').length,
      total: inTier.length,
    }
  }),
  from_trail: {
    given: fixtureSites.filter((s) => s.from_trail).length,
    withheld_disagreeing_with_atc: 1,
    agreement_ft: 100,
  },
  complexes: { join_ft: 200, count: 11, with_2_plus: 2, with_4_plus: 0, largest: 3 },
  clubs: ['Example Trail Club', 'Second Example Club'].map((club) => {
    const own = fixtureSites.filter((s) => s.club === club)
    return {
      club,
      sites: own.length,
      actionable: own.filter((s) => s.tier).length,
      p1: own.filter((s) => s.tier === 'P1').length,
      p2: own.filter((s) => s.tier === 'P2').length,
      p3: own.filter((s) => s.tier === 'P3').length,
      one_person: own.filter((s) => s.crew === 'one_person').length,
      team: own.filter((s) => s.crew === 'team').length,
      crew: own.filter((s) => s.crew === 'crew').length,
    }
  }),
  camping_rules: {
    reviewed_units: 0,
    status:
      'pending review: the restricted-camping weight adds nothing until a reviewed rule exists',
    guesses: { 'dispersed_allowed?': fixtureSites.length },
  },
  method: {
    weights: DEFAULT_WEIGHTS,
    tiers: { P1_min: 60, P2_min: 50 },
    work_csi_max: 12,
    close_water_ft: 100,
    adopt_csi_min: 22,
    one_person_max_ft2: 500,
    crew_min_ft2: 1500,
    csi_weights: {
      Expansion_Potential_Indicator: 2,
      Size_Indicator: 2,
      Proximity_Other_Site_Indicator: 1,
      Proximity_Water_Ecological_Indicator: 1,
      Proximity_Water_Social_Indicator: 1,
      Proximity_AT_Indicator: 1,
      Side_Hill_Footprint_Indicator: 3,
      Side_Hill_Buffer_Indicator: 3,
    },
  },
}
