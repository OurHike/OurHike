import { useMemo, useState } from 'react'
import { SiteMap } from '../components/SiteMap'
import {
  NO_FILTERS,
  clubs,
  filterSites,
  isFiltered,
  mileRange,
  toCsv,
  toggle,
  type Filters,
} from '../filters'
import { ACTION_LABEL, CREW_LABEL, TIERS, count, siteKind, siteName } from '../format'
import { siteHref } from '../route'
import type { Action, Crew, Site, Summary } from '../types'

const ACTION_CHIPS: Action[] = ['close_restore', 'harden', 'adopt_note', 'monitor']
const CREW_CHIPS: Crew[] = ['one_person', 'team', 'crew']
/** Rows drawn before "Show all": enough for any one club's work list, light enough for a phone. */
const FIRST_ROWS = 100

interface Props {
  sites: Site[]
  summary: Summary
}

export function SitesScreen({ sites, summary }: Props) {
  const [filters, setFilters] = useState<Filters>(NO_FILTERS)
  const [showAll, setShowAll] = useState(false)
  const allClubs = useMemo(() => clubs(sites), [sites])
  const shown = useMemo(() => filterSites(sites, filters), [sites, filters])
  const range = mileRange(sites, filters.club)
  const rows = showAll ? shown : shown.slice(0, FIRST_ROWS)
  const p1 = shown.filter((s) => s.tier === 'P1').length
  const work = shown.filter((s) => s.tier !== null).length

  const set = (patch: Partial<Filters>) => {
    setFilters((f) => ({ ...f, ...patch }))
    setShowAll(false)
  }
  const downloadCsv = () => {
    const url = URL.createObjectURL(new Blob([toCsv(shown)], { type: 'text/csv' }))
    const link = document.createElement('a')
    link.href = url
    link.download = 'campsite-steward-sites.csv'
    link.click()
    URL.revokeObjectURL(url)
  }

  return (
    <>
      <div className="filters" role="group" aria-label="Filters">
        <div className="field">
          <label htmlFor="club">Club</label>
          <select
            id="club"
            value={filters.club ?? ''}
            onChange={(e) =>
              set({ club: e.target.value || null, mileFrom: null, mileTo: null })
            }
          >
            <option value="">All clubs</option>
            {allClubs.map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="mile-from">Section, A.T. miles</label>
          <div className="miles">
            <input
              id="mile-from"
              type="number"
              inputMode="decimal"
              aria-label="From mile"
              placeholder={range ? range[0].toFixed(1) : 'from'}
              value={filters.mileFrom ?? ''}
              onChange={(e) =>
                set({ mileFrom: e.target.value === '' ? null : Number(e.target.value) })
              }
            />
            <span aria-hidden="true">to</span>
            <input
              type="number"
              inputMode="decimal"
              aria-label="To mile"
              placeholder={range ? range[1].toFixed(1) : 'to'}
              value={filters.mileTo ?? ''}
              onChange={(e) =>
                set({ mileTo: e.target.value === '' ? null : Number(e.target.value) })
              }
            />
          </div>
        </div>
        <div className="field" style={{ flex: '1 1 220px' }}>
          <label htmlFor="search">Find a site</label>
          <input
            id="search"
            type="search"
            placeholder="Name, id, land unit or mile"
            value={filters.search}
            onChange={(e) => set({ search: e.target.value })}
          />
        </div>
      </div>

      <div className="chips" role="group" aria-label="Priority, action and crew">
        {TIERS.map((tier) => (
          <button
            key={tier}
            type="button"
            className="chip"
            aria-pressed={filters.tiers.includes(tier)}
            onClick={() => set({ tiers: toggle(filters.tiers, tier) })}
          >
            <span className={`dot ${tier}`} aria-hidden="true" />
            {tier}
          </button>
        ))}
        {ACTION_CHIPS.map((action) => (
          <button
            key={action}
            type="button"
            className="chip"
            aria-pressed={filters.actions.includes(action)}
            onClick={() => set({ actions: toggle(filters.actions, action) })}
          >
            {ACTION_LABEL[action]}
          </button>
        ))}
        {CREW_CHIPS.map((crew) => (
          <button
            key={crew}
            type="button"
            className="chip"
            aria-pressed={filters.crews.includes(crew)}
            onClick={() => set({ crews: toggle(filters.crews, crew) })}
          >
            {CREW_LABEL[crew]}
          </button>
        ))}
        {isFiltered(filters) && (
          <button type="button" className="chip" onClick={() => set(NO_FILTERS)}>
            Clear filters
          </button>
        )}
      </div>

      <p className="card" style={{ margin: 0, padding: '10px 16px' }} aria-live="polite">
        <b className="mono">{count(shown.length)}</b> sites shown ·{' '}
        <b className="mono">{count(work)}</b> need work ·{' '}
        <b className="mono" style={{ color: '#c23d17' }}>
          {count(p1)}
        </b>{' '}
        top priority (P1)
      </p>

      <div className="split">
        <section className="map-wrap" aria-label="Map">
          <SiteMap
            sites={shown}
            onSelect={(s) => (window.location.hash = siteHref(s.rims_id))}
          />
        </section>
        <section className="card list" aria-label="Sites" style={{ padding: 0 }}>
          <div
            style={{
              display: 'flex',
              flexWrap: 'wrap',
              gap: 10,
              alignItems: 'center',
              padding: '14px 16px',
            }}
          >
            <h1 style={{ fontSize: 22 }}>Sites, by need</h1>
            <button
              type="button"
              className="button"
              style={{ marginLeft: 'auto' }}
              onClick={downloadCsv}
            >
              Export CSV
            </button>
          </div>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th scope="col">Site</th>
                  <th scope="col" className="num">
                    Mile
                  </th>
                  <th scope="col" className="num">
                    Need
                  </th>
                  <th scope="col">Action</th>
                  <th scope="col">Crew</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((s) => (
                  <tr key={s.rims_id}>
                    <td>
                      <a
                        href={siteHref(s.rims_id)}
                        style={{ fontWeight: 600, textDecoration: 'none' }}
                      >
                        {siteName(s)}
                      </a>
                      <div className="muted" style={{ fontSize: 12 }}>
                        {siteKind(s)} · {s.club ?? 'Club not recorded'}
                      </div>
                    </td>
                    <td className="num mono">{s.mile?.toFixed(1) ?? ''}</td>
                    <td className="num">
                      <span className={`need ${s.tier ?? ''}`}>{s.need}</span>
                    </td>
                    <td>{ACTION_LABEL[s.action]}</td>
                    <td>{s.crew ? CREW_LABEL[s.crew] : ''}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {shown.length > rows.length && (
            <div style={{ padding: 16 }}>
              <button type="button" className="button" onClick={() => setShowAll(true)}>
                Show all {count(shown.length)}
              </button>
            </div>
          )}
        </section>
      </div>

      <section
        className="card"
        aria-label="How this list is ranked"
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: '8px 20px',
          alignItems: 'center',
        }}
      >
        <b style={{ fontFamily: 'var(--display)', fontSize: 16 }}>
          How this list is ranked
        </b>
        <span>Need = CSI shortfall ({summary.method.weights.deficit})</span>
        <span>+ water {summary.method.weights.water}</span>
        <span>+ trail {summary.method.weights.trail}</span>
        <span>+ cluster {summary.method.weights.cluster}</span>
        <span>+ camping rules {summary.method.weights.restricted}</span>
        {summary.camping_rules.reviewed_units === 0 && (
          <span
            className="pill"
            style={{ background: 'var(--p2-tint)', color: 'var(--p2-text)' }}
          >
            Camping rules: pending review
          </span>
        )}
        <a href="#/analysis" style={{ marginLeft: 'auto', fontWeight: 600 }}>
          Method and numbers
        </a>
      </section>
    </>
  )
}
