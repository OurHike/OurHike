import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { fixtureSites } from '../fixtures'
import { SitePage } from './SitePage'

vi.mock('../components/SiteMap', () => ({ SiteMap: () => <div data-testid="map" /> }))

const byId = (n: number) =>
  fixtureSites.find((s) => s.rims_id === `example-${String(n).padStart(4, '0')}`)!

describe('SitePage', () => {
  it('says where to leave the trail, how far to walk and which way', () => {
    render(<SitePage site={byId(1)} sites={fixtureSites} />)
    expect(
      screen.getByText(/Leave the A\.T\. at mile 100\.0 and walk/),
    ).toHaveTextContent(
      'Leave the A.T. at mile 100.0 and walk 100 ft east (bearing 90°).',
    )
    expect(screen.getByText('0.00000, 0.00000')).toBeInTheDocument()
  })

  it('gives no walking directions where ATC withheld them, and says to use the coordinates', () => {
    render(<SitePage site={byId(10)} sites={fixtureSites} />)
    expect(screen.queryByText(/Leave the A\.T\./)).not.toBeInTheDocument()
    expect(screen.getByText(/No walking directions for this site/)).toHaveTextContent(
      'Use the coordinates.',
    )
  })

  it("lists the guide's close-and-restore steps as the plan, with the approval mark on restoring the ground", () => {
    render(<SitePage site={byId(1)} sites={fixtureSites} />)
    const plan = screen.getByRole('heading', { name: 'The plan' }).closest('section')!
    expect(plan.querySelectorAll('li')).toHaveLength(7)
    expect(plan).toHaveTextContent(
      'Restore the ground, only with approval · needs land-manager approval',
    )
  })

  it('names the other sites in its cluster, so closing one does not just move campers next door', () => {
    render(<SitePage site={byId(1)} sites={fixtureSites} />)
    expect(screen.getByText(/1 of 3 sites less than 200 ft apart/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Example site 2' })).toHaveAttribute(
      'href',
      '#/site/example-0002',
    )
    expect(screen.getByRole('link', { name: 'Example Shelter 3' })).toBeInTheDocument()
  })

  it('suggests adoption for a site that scores well, and has no plan to give it', () => {
    render(<SitePage site={byId(8)} sites={fixtureSites} />)
    expect(screen.getByText(/your club may want to adopt it/)).toBeInTheDocument()
    expect(screen.getByText(/Nothing to do here now/)).toBeInTheDocument()
  })

  it('calls the camping rule a guess until a reviewed rule exists', () => {
    render(<SitePage site={byId(1)} sites={fixtureSites} />)
    expect(
      screen.getByText(/Dispersed camping allowed\? This is a guess/),
    ).toBeInTheDocument()
  })

  it('warns that a user-created site listed in FarOut keeps drawing hikers after it is closed', () => {
    render(<SitePage site={byId(9)} sites={fixtureSites} />)
    expect(
      screen.getByText(/keeps drawing hikers until FarOut changes too/),
    ).toBeInTheDocument()
  })

  it('says so when the link names a site the analysis does not have', () => {
    render(<SitePage site={undefined} sites={fixtureSites} />)
    expect(screen.getByRole('heading', { name: 'No such site' })).toBeInTheDocument()
  })
})
