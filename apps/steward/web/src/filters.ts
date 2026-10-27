import type { Action, Crew, Site, Tier } from './types'

export interface Filters {
  club: string | null
  mileFrom: number | null
  mileTo: number | null
  tiers: Tier[]
  actions: Action[]
  crews: Crew[]
  search: string
}

export const NO_FILTERS: Filters = {
  club: null,
  mileFrom: null,
  mileTo: null,
  tiers: [],
  actions: [],
  crews: [],
  search: '',
}

export function isFiltered(f: Filters): boolean {
  return (
    f.club !== null ||
    f.mileFrom !== null ||
    f.mileTo !== null ||
    f.tiers.length > 0 ||
    f.actions.length > 0 ||
    f.crews.length > 0 ||
    f.search.trim() !== ''
  )
}

/** Every club with at least one site, alphabetically. */
export function clubs(sites: Site[]): string[] {
  return [...new Set(sites.map((s) => s.club).filter((c): c is string => !!c))].sort()
}

/** The lowest and highest A.T. mile among a club's sites: the default "section". */
export function mileRange(sites: Site[], club: string | null): [number, number] | null {
  const miles = sites
    .filter((s) => club === null || s.club === club)
    .map((s) => s.mile)
    .filter((m): m is number => m !== null)
  if (miles.length === 0) return null
  return [Math.min(...miles), Math.max(...miles)]
}

function matchesSearch(site: Site, search: string): boolean {
  const q = search.trim().toLowerCase()
  if (!q) return true
  return [site.name, site.rims_id, site.land_unit.name, site.mile?.toFixed(1)]
    .filter(Boolean)
    .some((field) => String(field).toLowerCase().includes(q))
}

/** The sites that pass every filter, highest need first. An empty list in a filter means "any". */
export function filterSites(sites: Site[], filters: Filters): Site[] {
  return sites
    .filter((s) => filters.club === null || s.club === filters.club)
    .filter(
      (s) => filters.mileFrom === null || (s.mile !== null && s.mile >= filters.mileFrom),
    )
    .filter(
      (s) => filters.mileTo === null || (s.mile !== null && s.mile <= filters.mileTo),
    )
    .filter(
      (s) =>
        filters.tiers.length === 0 || (s.tier !== null && filters.tiers.includes(s.tier)),
    )
    .filter((s) => filters.actions.length === 0 || filters.actions.includes(s.action))
    .filter(
      (s) =>
        filters.crews.length === 0 || (s.crew !== null && filters.crews.includes(s.crew)),
    )
    .filter((s) => matchesSearch(s, filters.search))
    .sort((a, b) => b.need - a.need || (a.mile ?? 0) - (b.mile ?? 0))
}

/** Adds the value to the list if absent and removes it if present. */
export function toggle<T>(list: T[], value: T): T[] {
  return list.includes(value) ? list.filter((v) => v !== value) : [...list, value]
}

const CSV_COLUMNS: [string, (s: Site) => string | number | null][] = [
  ['rims_id', (s) => s.rims_id],
  ['name', (s) => s.name],
  ['club', (s) => s.club],
  ['mile', (s) => s.mile],
  ['lat', (s) => s.lat],
  ['lon', (s) => s.lon],
  ['site_type', (s) => s.site_type],
  ['need', (s) => s.need],
  ['tier', (s) => s.tier],
  ['action', (s) => s.action],
  ['crew', (s) => s.crew],
  ['csi', (s) => s.csi],
  ['size_ft2', (s) => s.size_ft2],
  ['water_ft', (s) => s.water_ft],
  ['trail_ft', (s) => s.trail_ft],
  ['complex_id', (s) => s.complex_id],
  ['complex_size', (s) => s.complex_size],
  ['nearest_parking', (s) => s.nearest_parking.name],
  ['nearest_parking_mi', (s) => s.nearest_parking.mi],
  ['land_unit', (s) => s.land_unit.name],
]

function csvCell(value: string | number | null): string {
  if (value === null) return ''
  const text = String(value)
  return /[",\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text
}

export function toCsv(sites: Site[]): string {
  const header = CSV_COLUMNS.map(([name]) => name).join(',')
  const rows = sites.map((s) => CSV_COLUMNS.map(([, get]) => csvCell(get(s))).join(','))
  return [header, ...rows].join('\n') + '\n'
}
