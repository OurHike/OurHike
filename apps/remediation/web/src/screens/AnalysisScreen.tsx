import { count } from '../format'
import type { Summary } from '../types'

/** The public summary: counts only (PLAN.md §2g), so this screen never needs the sites file. */
export function AnalysisScreen({ summary }: { summary: Summary }) {
  const actionable = summary.priority_by_crew.reduce((n, row) => n + row.total, 0)
  const byTier = Object.fromEntries(
    summary.priority_by_crew.map((row) => [row.tier, row]),
  )
  const totals = summary.priority_by_crew.reduce(
    (t, row) => ({
      one: t.one + row.one_person,
      team: t.team + row.team,
      crew: t.crew + row.crew,
    }),
    { one: 0, team: 0, crew: 0 },
  )
  const topClubs = [...summary.clubs]
    .sort((a, b) => b.p1 - a.p1 || b.p2 - a.p2)
    .filter((c) => c.p1 > 0)
    .slice(0, 12)
  const mostP1 = Math.max(1, ...topClubs.map((c) => c.p1))
  const userCreated = summary.sites_by_type['User Created Campsite'] ?? 0
  const w = summary.method.weights
  const formula = summary.csi_formula

  return (
    <>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <span className="eyebrow" style={{ color: 'var(--teal)' }}>
          Analysis
        </span>
        <h1 style={{ fontSize: 36 }}>Which overnight sites need work first, and why</h1>
        <p className="muted" style={{ margin: 0, maxWidth: '72ch' }}>
          Scored from ATC's Campsite Sustainability Index
          {summary.source.data_last_edited && (
            <> (data edited {summary.source.data_last_edited})</>
          )}
          , joined to USGS land managers and ATC parking. Scored{' '}
          {summary.generated_at.slice(0, 10)} under first-pass rules that nobody has
          validated yet.
        </p>
      </div>

      <div className="kpis">
        <div className="card kpi">
          <div className="big">{count(summary.source.sites)}</div>
          <div className="muted">
            overnight sites, {count(userCreated)} of them user-created
          </div>
        </div>
        <div className="card kpi">
          <div className="big">{count(actionable)}</div>
          <div className="muted">
            need work: {count(summary.actions.close_restore ?? 0)} to close and restore,{' '}
            {count(summary.actions.harden ?? 0)} official sites to harden
          </div>
        </div>
        <div className="card kpi">
          <div className="big p1">{count(byTier.P1?.total ?? 0)}</div>
          <div className="muted">top priority (P1)</div>
        </div>
        <div className="card kpi">
          <div className="big">{count(totals.one)}</div>
          <div className="muted">one-person jobs; the rest need a team or a crew</div>
        </div>
      </div>

      <div className="grid2">
        <section className="card" aria-labelledby="who">
          <h2 id="who" style={{ fontSize: 22 }}>
            Who it takes
          </h2>
          <p className="muted" style={{ marginTop: 4 }}>
            Sites needing work, by priority and crew size.
          </p>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th scope="col">Priority</th>
                  <th scope="col" className="num">
                    One person
                  </th>
                  <th scope="col" className="num">
                    Team 2–3
                  </th>
                  <th scope="col" className="num">
                    Crew 4+
                  </th>
                  <th scope="col" className="num">
                    Total
                  </th>
                </tr>
              </thead>
              <tbody className="mono">
                {summary.priority_by_crew.map((row) => (
                  <tr key={row.tier}>
                    <th
                      scope="row"
                      style={{
                        fontFamily: 'var(--body)',
                        textTransform: 'none',
                        fontSize: 14,
                        color: 'var(--ink)',
                      }}
                    >
                      <span className={`dot ${row.tier}`} aria-hidden="true" /> {row.tier}
                    </th>
                    <td className="num">{count(row.one_person)}</td>
                    <td className="num">{count(row.team)}</td>
                    <td className="num">{count(row.crew)}</td>
                    <td className="num">
                      <b>{count(row.total)}</b>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="muted" style={{ fontSize: 13, marginBottom: 0 }}>
            One person: up to {count(summary.method.one_person_max_ft2)} ft², not in a
            cluster, gentle ground; a buddy is still recommended. Crew: an official site,
            over {count(summary.method.crew_min_ft2)} ft², or a cluster of 4 or more.
          </p>
        </section>

        <section className="card" aria-labelledby="clubs">
          <h2 id="clubs" style={{ fontSize: 22 }}>
            Top-priority sites by club
          </h2>
          <p className="muted" style={{ marginTop: 4 }}>
            P1 sites in each club's sections.
          </p>
          <div className="bars">
            {topClubs.map((c) => (
              <div className="bar-row" key={c.club ?? 'none'}>
                <span>{c.club ?? 'Club not recorded'}</span>
                <span className="bar" style={{ width: `${(c.p1 / mostP1) * 100}%` }} />
                <span className="mono" style={{ textAlign: 'right' }}>
                  {c.p1}
                </span>
              </div>
            ))}
          </div>
        </section>
      </div>

      <div className="grid2">
        <section
          className="card"
          aria-labelledby="method"
          style={{ display: 'flex', flexDirection: 'column', gap: 10 }}
        >
          <h2 id="method" style={{ fontSize: 22 }}>
            How a site is scored
          </h2>
          <p style={{ margin: 0 }}>
            <b>ATC's sustainability score (CSI, 3–30, higher is better)</b> is a weighted
            sum of eight field indicators. This formula reproduces{' '}
            {count(formula.reproduces)} of {count(formula.of)} published scores:
          </p>
          <pre className="formula">
            CSI = 2·Expansion + 2·Size + OtherSites + WaterEcological + WaterSocial +
            TrailProximity + 3·SideHillFootprint + 3·SideHillBuffer
          </pre>
          <p style={{ margin: 0 }}>
            <b>Need (0–100)</b> starts from how far a site falls short of 30, then adds
            weight for the impacts land managers set distances for:
          </p>
          <pre className="formula">{`need = ${w.deficit} × (30 − CSI) / 27
     + ${w.water} within 100 ft of water (+${w.water / 2} within 200 ft)
     + ${w.trail} within 50 ft of the A.T.
     + ${w.cluster} in a cluster of 4+ (+${w.cluster / 2} for 2–3)
     + ${w.restricted} user-created where a reviewed rule restricts camping
P1 ≥ ${summary.method.tiers.P1_min} · P2 ${summary.method.tiers.P2_min}–${summary.method.tiers.P1_min - 1} · P3 below ${summary.method.tiers.P2_min}`}</pre>
          <p style={{ margin: 0 }}>
            <b>Clusters:</b> sites less than {summary.complexes.join_ft} ft apart form one
            cluster ({count(summary.complexes.count)} clusters;{' '}
            {count(summary.complexes.with_4_plus)} hold 4 or more sites).
          </p>
        </section>

        <section
          className="note"
          aria-labelledby="unknowns"
          style={{ display: 'flex', flexDirection: 'column', gap: 8, padding: 16 }}
        >
          <h2 id="unknowns" style={{ fontSize: 22 }}>
            What this doesn't know yet
          </h2>
          <ul
            style={{
              margin: 0,
              paddingLeft: 20,
              display: 'flex',
              flexDirection: 'column',
              gap: 6,
            }}
          >
            <li>
              <b>Camping rules.</b> Where dispersed camping is allowed is a guess from the
              land manager's type until the hand-typed rules table is reviewed (
              {summary.camping_rules.reviewed_units} land units reviewed so far), so the
              camping weight adds nothing yet.
            </li>
            <li>
              <b>Every threshold is a first pass:</b> {summary.method.one_person_max_ft2}{' '}
              ft² for one person, {summary.complexes.join_ft} ft for a cluster, the need
              weights. Nobody has checked them against real workdays.
            </li>
            {summary.from_trail &&
              summary.from_trail.withheld_disagreeing_with_atc > 0 && (
                <li>
                  <b>
                    {count(summary.from_trail.withheld_disagreeing_with_atc)}{' '}
                    {summary.from_trail.withheld_disagreeing_with_atc === 1
                      ? 'site has'
                      : 'sites have'}{' '}
                    no walking directions.
                  </b>{' '}
                  ATC's trail line and ATC's own distance to the trail disagree for them,
                  and a route that could send someone the wrong way is worse than none.
                </li>
              )}
          </ul>
        </section>
      </div>
    </>
  )
}
