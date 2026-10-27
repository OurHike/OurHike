import { act, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { App } from './App'
import { fixtureSites, fixtureSummary } from './fixtures'

vi.mock('./components/SiteMap', () => ({ SiteMap: () => <div data-testid="map" /> }))

const load = () => Promise.resolve({ sites: fixtureSites, summary: fixtureSummary })

afterEach(() => {
  window.location.hash = ''
})

it('App opens on the site list and marks Sites as the current page', async () => {
  render(<App load={load} />)
  expect(await screen.findByRole('table')).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Sites' })).toHaveAttribute(
    'aria-current',
    'page',
  )
})

it('App follows the hash to a site page and to the analysis', async () => {
  render(<App load={load} />)
  await screen.findByRole('table')
  await act(async () => {
    window.location.hash = '#/site/example-0004'
    window.dispatchEvent(new HashChangeEvent('hashchange'))
  })
  expect(
    screen.getByRole('heading', { level: 1, name: 'Example site 4' }),
  ).toBeInTheDocument()
  await act(async () => {
    window.location.hash = '#/analysis'
    window.dispatchEvent(new HashChangeEvent('hashchange'))
  })
  expect(screen.getByRole('link', { name: 'Analysis' })).toHaveAttribute(
    'aria-current',
    'page',
  )
})

it('App says the analysis did not load, and still offers the guide, when the data files fail', async () => {
  render(<App load={() => Promise.reject(new Error('data/sites.json answered 404'))} />)
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'data/sites.json answered 404',
  )
  expect(screen.getByRole('link', { name: 'Open the guide' })).toHaveAttribute(
    'href',
    '#/guide',
  )
})
