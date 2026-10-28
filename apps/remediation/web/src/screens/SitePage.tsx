import { useState } from 'react'
import { SiteMap } from '../components/SiteMap'
import {
  ACTION_LABEL,
  CREW_LABEL,
  compassWord,
  feet,
  isOfficial,
  miles,
  regimeWords,
  siteKind,
  siteName,
} from '../format'
import { useAccount } from '../account'
import { ClaimPanel } from '../components/ClaimPanel'
import { SaveToList } from '../components/SaveToList'
import { planFor } from '../guide'
import { siteHref } from '../route'
import type { Site } from '../types'

interface Props {
  site: Site | undefined
  sites: Site[]
}

/** The indicators a volunteer can see on the ground, with the raw figure behind each (PLAN.md §1). */
const INDICATORS: {
  field: string
  label: string
  max: number
  raw: (s: Site) => string
}[] = [
  {
    field: 'Size_Indicator',
    label: 'Size',
    max: 3,
    raw: (s) => (s.size_ft2 === null ? '' : `${feet(s.size_ft2)}²`),
  },
  {
    field: 'Expansion_Potential_Indicator',
    label: 'Room to grow',
    max: 3,
    raw: () => 'judged on site',
  },
  {
    field: 'Proximity_Water_Ecological_Indicator',
    label: 'Water',
    max: 3,
    raw: (s) => feet(s.water_ft),
  },
  {
    field: 'Proximity_AT_Indicator',
    label: 'Trail',
    max: 3,
    raw: (s) => feet(s.trail_ft),
  },
  {
    field: 'Proximity_Other_Site_Indicator',
    label: 'Other sites',
    max: 3,
    raw: (s) => feet(s.nearest_site_ft),
  },
  {
    field: 'Side_Hill_Footprint_Indicator',
    label: 'Side hill',
    max: 1,
    raw: (s) => (s.slope_footprint_pct === null ? '' : `${s.slope_footprint_pct}% slope`),
  },
]

export function SitePage({ site, sites }: Props) {
  const { session } = useAccount()
  if (!site) {
    return (
      <section className="card">
        <h1 style={{ fontSize: 24 }}>No such site</h1>
        <p>
          This link names a site the latest analysis does not have.{' '}
          <a href="#/">See all sites</a>
        </p>
      </section>
    )
  }
  const neighbours = sites.filter(
    (s) => s.complex_id === site.complex_id && s.rims_id !== site.rims_id,
  )
  const plan = planFor(site.action)

  return (
    <>
      <a href="#/" style={{ fontWeight: 600 }}>
        ← All sites
      </a>
      <header style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <h1 style={{ fontSize: 30 }}>{siteName(site)}</h1>
        <span className="muted">
          {siteKind(site)} · {site.club ?? 'Club not recorded'}
          {site.mile !== null && <> · A.T. mile {site.mile.toFixed(1)}</>}
        </span>
        <div className="chips">
          {site.tier ? (
            <span className={`pill ${site.tier}`}>
              {site.tier} · need {site.need}
            </span>
          ) : (
            <span className="pill plain">need {site.need}</span>
          )}
          <span className="pill">{ACTION_LABEL[site.action]}</span>
          {session.state === 'signed_in' && site.club && (
            <span className="muted" style={{ fontSize: 13 }}>
              Need under the default weights; {site.club}'s own weights can rank it
              differently on the dashboard.
            </span>
          )}
          {site.crew && <span className="pill plain">{CREW_LABEL[site.crew]}</span>}
        </div>
      </header>

      <ClaimPanel site={site} neighbours={neighbours} />
      <SaveToList rimsId={site.rims_id} />

      {site.action === 'adopt_note' && (
        <p className="note" style={{ margin: 0 }}>
          This site scores well; your club may want to adopt it.
        </p>
      )}
      {neighbours.length > 0 && (
        <div className="note">
          <b>1 of {site.complex_size} sites less than 200 ft apart.</b> Closing one alone
          can move campers next door. The others:{' '}
          {neighbours.map((n, i) => (
            <span key={n.rims_id}>
              {i > 0 && ', '}
              <a href={siteHref(n.rims_id)}>{siteName(n)}</a>
            </span>
          ))}
        </div>
      )}

      <div className="grid2">
        <WhereItIs site={site} />
        <section className="map-wrap" aria-label="Map" style={{ minHeight: 320 }}>
          <span className="map-label">This site and its neighbours</span>
          <SiteMap sites={[site, ...neighbours]} />
        </section>
      </div>

      <div className="grid2">
        <section className="card" aria-labelledby="why">
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'baseline',
              marginBottom: 8,
            }}
          >
            <h2 id="why" className="eyebrow">
              Why it ranks
            </h2>
            <span className="muted" style={{ fontSize: 13 }}>
              CSI <b className="mono">{site.csi ?? '?'}</b> of 30, higher is better
            </span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {INDICATORS.map((ind) => {
              const value = site.indicators[ind.field]
              const share = value === null || value === undefined ? 0 : value / ind.max
              return (
                <div className="indicator" key={ind.field}>
                  <span>{ind.label}</span>
                  <span
                    className="track"
                    aria-label={`${ind.label}: ${value ?? '?'} of ${ind.max}`}
                  >
                    <span
                      className={`fill ${share < 0.5 ? 'low' : ''}`}
                      style={{ display: 'block', width: `${Math.max(share * 100, 4)}%` }}
                    />
                  </span>
                  <span className="mono" style={{ fontSize: 12, textAlign: 'right' }}>
                    {ind.raw(site)}
                  </span>
                </div>
              )
            })}
          </div>
          {site.water_ft_source === 'OSA_Field_Estimate' && (
            <p className="muted" style={{ fontSize: 13, marginBottom: 0 }}>
              The water distance is a steward's estimate, not a measurement.
            </p>
          )}
        </section>

        <section className="card" aria-labelledby="plan">
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'baseline',
              marginBottom: 8,
            }}
          >
            <h2 id="plan" className="eyebrow">
              The plan
            </h2>
            <a href="#/guide" style={{ fontSize: 13 }}>
              The full guide
            </a>
          </div>
          {plan.length === 0 ? (
            <p style={{ margin: 0 }}>
              Nothing to do here now: this site is{' '}
              {ACTION_LABEL[site.action].toLowerCase()}.
            </p>
          ) : (
            <ol className="steps">
              {plan.map((step) => (
                <li key={step.title}>
                  {step.title}
                  {step.needsApproval && (
                    <span className="approval"> · needs land-manager approval</span>
                  )}
                </li>
              ))}
            </ol>
          )}
        </section>
      </div>

      <section className="card" aria-labelledby="facts">
        <h2 id="facts" className="eyebrow" style={{ marginBottom: 8 }}>
          About this site
        </h2>
        <dl
          style={{
            display: 'grid',
            gridTemplateColumns: 'max-content minmax(0, 1fr)',
            gap: '6px 16px',
            margin: 0,
          }}
        >
          <dt className="muted">Land</dt>
          <dd style={{ margin: 0 }}>
            {[site.land_unit.name, site.land_unit.manager].filter(Boolean).join(' · ') ||
              'No protected-area record'}
          </dd>
          <dt className="muted">Camping rules</dt>
          <dd style={{ margin: 0 }}>
            {site.camping.source === 'reviewed'
              ? site.camping.restricted
                ? 'Dispersed camping restricted (reviewed rule)'
                : 'Dispersed camping allowed (reviewed rule)'
              : `${capitalize(regimeWords(site.camping.regime))} This is a guess from the land manager's type, not a cited rule.`}
          </dd>
          <dt className="muted">Inventory status</dt>
          <dd style={{ margin: 0 }}>{site.inventory_status ?? 'Not recorded'}</dd>
          <dt className="muted">Listed in</dt>
          <dd style={{ margin: 0 }}>
            {site.documented_in.length === 0 ? 'No guide' : site.documented_in.join(', ')}
            {site.documented_in.includes('FarOut') && !isOfficial(site) && (
              <span className="muted">
                {' '}
                · a closed site keeps drawing hikers until FarOut changes too
              </span>
            )}
          </dd>
          <dt className="muted">ATC ids</dt>
          <dd style={{ margin: 0 }} className="mono">
            {site.rims_id}
          </dd>
        </dl>
      </section>
    </>
  )
}

function capitalize(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1)
}

function WhereItIs({ site }: { site: Site }) {
  const [copied, setCopied] = useState(false)
  const coordinates = `${site.lat.toFixed(5)}, ${site.lon.toFixed(5)}`
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(coordinates)
      setCopied(true)
    } catch {
      setCopied(false)
    }
  }
  const t = site.from_trail
  return (
    <section className="card" aria-labelledby="where">
      <h2 id="where" className="eyebrow" style={{ marginBottom: 8 }}>
        Where it is
      </h2>
      {t ? (
        <p style={{ marginTop: 0 }}>
          Leave the A.T.{site.mile !== null && <> at mile {site.mile.toFixed(1)}</>} and
          walk{' '}
          <b>
            {feet(t.ft)} {compassWord(t.toward)}
          </b>{' '}
          (bearing {t.bearing_deg}°).
        </p>
      ) : (
        <p style={{ marginTop: 0 }}>
          No walking directions for this site. ATC's trail line does not come near it,
          though ATC measures it {feet(site.trail_ft)} from the trail. Use the
          coordinates.
        </p>
      )}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
        <span
          className="mono"
          style={{ background: 'var(--ground)', borderRadius: 4, padding: '4px 8px' }}
        >
          {coordinates}
        </span>
        <button type="button" className="button" onClick={copy}>
          {copied ? 'Copied' : 'Copy'}
        </button>
        <a
          className="button"
          href={`https://www.openstreetmap.org/?mlat=${site.lat}&mlon=${site.lon}#map=17/${site.lat}/${site.lon}`}
          target="_blank"
          rel="noreferrer"
        >
          Open in OpenStreetMap
        </a>
      </div>
      <p style={{ marginBottom: 0 }}>
        Nearest parking: {site.nearest_parking.name ?? 'not named'},{' '}
        {miles(site.nearest_parking.mi)} in a straight line.
      </p>
    </section>
  )
}
