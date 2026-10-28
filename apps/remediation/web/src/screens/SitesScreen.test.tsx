import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { fixtureSites, fixtureSummary } from '../fixtures'
import { SitesScreen } from './SitesScreen'

vi.mock('../components/SiteMap', () => ({ SiteMap: () => <div data-testid="map" /> }))

const rows = () => within(screen.getByRole('table')).getAllByRole('row').slice(1)

describe('SitesScreen', () => {
  it('lists every site, highest need first, each row linking to its site page', () => {
    render(<SitesScreen sites={fixtureSites} summary={fixtureSummary} />)
    expect(rows()).toHaveLength(fixtureSites.length)
    expect(
      within(rows()[0]).getByRole('link', { name: 'Example site 1' }),
    ).toHaveAttribute('href', '#/site/example-0001')
  })

  it("narrows the list to one club's sites when that club is picked", async () => {
    render(<SitesScreen sites={fixtureSites} summary={fixtureSummary} />)
    await userEvent.selectOptions(screen.getByLabelText('Club'), 'Second Example Club')
    expect(rows()).toHaveLength(
      fixtureSites.filter((s) => s.club === 'Second Example Club').length,
    )
  })

  it('narrows to P1 sites from the P1 chip, and Clear filters brings every site back', async () => {
    render(<SitesScreen sites={fixtureSites} summary={fixtureSummary} />)
    await userEvent.click(screen.getByRole('button', { name: /^P1/ }))
    expect(rows()).toHaveLength(fixtureSites.filter((s) => s.tier === 'P1').length)
    await userEvent.click(screen.getByRole('button', { name: 'Clear filters' }))
    expect(rows()).toHaveLength(fixtureSites.length)
  })
})
