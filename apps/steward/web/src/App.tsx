import { useStewardData, type StewardData } from './data'
import { useRoute, type Route } from './route'
import { AnalysisScreen } from './screens/AnalysisScreen'
import { GuideScreen } from './screens/GuideScreen'
import { SitePage } from './screens/SitePage'
import { SitesScreen } from './screens/SitesScreen'

const NAV: { href: string; label: string; screens: Route['screen'][] }[] = [
  { href: '#/', label: 'Sites', screens: ['sites', 'site'] },
  { href: '#/analysis', label: 'Analysis', screens: ['analysis'] },
  { href: '#/guide', label: 'Guide', screens: ['guide'] },
]

/** A strip of flagging tape on a stake: what a trail crew ties to mark a site for work. */
function Logo() {
  return (
    <svg width="26" height="26" viewBox="0 0 26 26" aria-hidden="true">
      <rect x="5" y="3" width="2.5" height="21" rx="1" fill="#c9d4d2" />
      <path d="M7.5 4 H21 L17.5 8.5 L21 13 H7.5 Z" fill="var(--flag)" />
    </svg>
  )
}

function Screen({ route, data }: { route: Route; data: StewardData }) {
  if (route.screen === 'site') {
    return (
      <SitePage
        site={data.sites.find((s) => s.rims_id === route.id)}
        sites={data.sites}
      />
    )
  }
  if (route.screen === 'analysis') return <AnalysisScreen summary={data.summary} />
  if (route.screen === 'guide') return <GuideScreen />
  return <SitesScreen sites={data.sites} summary={data.summary} />
}

export function App({ load }: { load?: () => Promise<StewardData> }) {
  const route = useRoute()
  const loaded = useStewardData(load)
  return (
    <>
      <header className="top">
        <div className="top-inner">
          <a className="brand" href="#/">
            <Logo />
            Campsite Steward
          </a>
          <nav className="nav" aria-label="Main">
            {NAV.map((item) => (
              <a
                key={item.href}
                href={item.href}
                aria-current={item.screens.includes(route.screen) ? 'page' : undefined}
              >
                {item.label}
              </a>
            ))}
          </nav>
        </div>
      </header>
      <main className="page">
        {route.screen === 'guide' ? (
          <GuideScreen />
        ) : loaded.state === 'loading' ? (
          <p className="muted">Loading the latest analysis…</p>
        ) : loaded.state === 'failed' ? (
          <section className="card" role="alert">
            <h1 style={{ fontSize: 24 }}>The analysis did not load</h1>
            <p>{loaded.message}</p>
            <p className="muted">The guide does not need it.</p>
            <a className="button" href="#/guide">
              Open the guide
            </a>
          </section>
        ) : (
          <Screen route={route} data={loaded.data} />
        )}
        <footer className="foot">
          <span>
            Site data: ATC's Campsite Sustainability Index. Land managers: USGS PAD-US.
            Map: OpenFreeMap, © OpenStreetMap contributors.
          </span>
          <span>Not an ATC or OurHike product.</span>
        </footer>
      </main>
    </>
  )
}
