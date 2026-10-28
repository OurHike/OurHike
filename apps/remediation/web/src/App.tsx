import { useEffect, useState } from 'react'
import { useAccount } from './account'
import { useRemediationData, type RemediationData } from './data'
import { useRoute, type Route } from './route'
import { AccountScreen } from './screens/AccountScreen'
import { AnalysisScreen } from './screens/AnalysisScreen'
import { ClaimScreen } from './screens/ClaimScreen'
import { GuideScreen } from './screens/GuideScreen'
import { JoinScreen } from './screens/JoinScreen'
import { ListsScreen } from './screens/ListsScreen'
import { SharedScreen } from './screens/SharedScreen'
import { SitePage } from './screens/SitePage'
import { SitesScreen } from './screens/SitesScreen'
import { WorkScreen } from './screens/WorkScreen'
import { watchForUpdates } from './update'

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

function Screen({ route, data }: { route: Route; data: RemediationData }) {
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
  if (route.screen === 'account') return <AccountScreen />
  if (route.screen === 'lists') return <ListsScreen sites={data.sites} />
  if (route.screen === 'shared')
    return <SharedScreen token={route.token} sites={data.sites} />
  if (route.screen === 'claim') return <ClaimScreen id={route.id} sites={data.sites} />
  if (route.screen === 'join') return <JoinScreen token={route.token} />
  if (route.screen === 'work') return <WorkScreen sites={data.sites} />
  return <SitesScreen sites={data.sites} summary={data.summary} />
}

export function App({ load }: { load?: () => Promise<RemediationData> }) {
  const route = useRoute()
  const loaded = useRemediationData(load)
  const { session } = useAccount()
  const [update, setUpdate] = useState<(() => void) | null>(null)
  useEffect(() => watchForUpdates((apply) => setUpdate(() => apply)), [])
  return (
    <>
      <header className="top">
        <div className="top-inner">
          <a className="brand" href="#/">
            <Logo />
            Site Remediation
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
            {session.state === 'signed_in' && (
              <>
                <a
                  href="#/work"
                  aria-current={
                    route.screen === 'work' || route.screen === 'claim'
                      ? 'page'
                      : undefined
                  }
                >
                  Your work
                </a>
                <a
                  href="#/lists"
                  aria-current={route.screen === 'lists' ? 'page' : undefined}
                >
                  Your lists
                </a>
              </>
            )}
          </nav>
          {session.state !== 'off' && (
            <a
              className="nav-account"
              href="#/account"
              aria-current={route.screen === 'account' ? 'page' : undefined}
            >
              {session.state === 'signed_in' ? 'Account' : 'Sign in'}
            </a>
          )}
        </div>
      </header>
      <main className="page">
        {update && (
          <p
            className="note"
            role="status"
            style={{
              margin: 0,
              display: 'flex',
              gap: 8,
              flexWrap: 'wrap',
              alignItems: 'center',
            }}
          >
            A new version of Site Remediation is ready. Anything you have not saved on
            this screen goes when it reloads.
            <button type="button" className="button primary" onClick={update}>
              Reload now
            </button>
          </p>
        )}
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
