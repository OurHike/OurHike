import { StrictMode, type ReactNode } from 'react'
import { createRoot } from 'react-dom/client'
import { AccountProvider } from './account'
import { App } from './App'
import './styles.css'

const root = createRoot(document.getElementById('root')!)
const render = (children: ReactNode) => root.render(<StrictMode>{children}</StrictMode>)

// `npm run dev:account` serves the invented sites with an invented signed-in
// account held in memory (src/test/fakeAccount.tsx): for screenshots of the
// signed-in screens without anybody's real account (CLAUDE.md's screenshot
// rule). The flag is unset in every real build, which then never loads that file.
if (import.meta.env.VITE_STEWARD_FAKE_ACCOUNT === '1') {
  void import('./test/fakeAccount').then(
    async ({ SIGNED_IN, fakeAccount, fakeApi, withAccount }) => {
      const api = fakeApi()
      await api.setDisplayName('Example volunteer')
      const list = await api.createList('Spring workday', [
        'example-0001',
        'example-0002',
        'example-0004',
      ])
      await api.share(list.id)
      await api.changeWeights(
        'Example Trail Club',
        { deficit: 50, water: 24, trail: 6, cluster: 8, restricted: 10 },
        'Water first this season',
      )
      await api.claimSites(['example-0004'])
      await api.seedSubmittedByOther('example-0005', 'Ridge Runner')
      render(withAccount(fakeAccount(SIGNED_IN, api), <App />))
    },
  )
} else {
  render(
    <AccountProvider>
      <App />
    </AccountProvider>,
  )
}
