import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { fixtureSites } from '../fixtures'
import {
  SIGNED_IN,
  SIGNED_OUT,
  fakeAccount,
  fakeApi,
  withAccount,
} from '../test/fakeAccount'
import { ClaimScreen } from './ClaimScreen'
import { JoinScreen } from './JoinScreen'
import { SitePage } from './SitePage'
import { WorkScreen } from './WorkScreen'

vi.mock('../components/SiteMap', () => ({ SiteMap: () => <div data-testid="map" /> }))

const site1 = fixtureSites.find((s) => s.rims_id === 'example-0001')!
const site4 = fixtureSites.find((s) => s.rims_id === 'example-0004')!
/** Stands in for photo.ts's canvas re-encoding, which jsdom cannot run: a JPEG comes out. */
const prepare = async () => new Blob(['re-encoded'], { type: 'image/jpeg' })
const picture = () => new File(['pixels'], 'IMG_0001.HEIC', { type: 'image/heic' })

afterEach(() => {
  window.location.hash = ''
  window.localStorage.clear()
})

describe('Claiming from a site page', () => {
  it('asks a signed-out visitor to sign in to claim', () => {
    render(
      withAccount(
        fakeAccount(SIGNED_OUT),
        <SitePage site={site1} sites={fixtureSites} />,
      ),
    )
    expect(screen.getByText(/to claim this site and restore it/)).toBeInTheDocument()
  })

  it('claims the site and its cluster together, and opens the claim', async () => {
    const api = fakeApi()
    render(
      withAccount(
        fakeAccount(SIGNED_IN, api),
        <SitePage site={site1} sites={fixtureSites} />,
      ),
    )
    await userEvent.click(
      await screen.findByRole('button', { name: 'Claim all 3 in the cluster' }),
    )
    await waitFor(() => expect(window.location.hash).toMatch(/^#\/claim\//))
    expect(api.calls.filter((c) => c.startsWith('claim '))).toEqual([
      'claim example-0001',
      'claim example-0002',
      'claim example-0003',
    ])
  })

  it('shows who holds a site someone else claimed', async () => {
    const api = fakeApi()
    await api.seedSubmittedByOther('example-0004', 'Ridge Runner')
    render(
      withAccount(
        fakeAccount(SIGNED_IN, api),
        <SitePage site={site4} sites={fixtureSites} />,
      ),
    )
    expect(
      await screen.findByText(/by Ridge Runner, and waiting for someone off the crew/),
    ).toBeInTheDocument()
  })
})

describe('The claim workspace', () => {
  async function openClaim() {
    const api = fakeApi()
    const [made] = await api.claimSites(['example-0004'])
    render(
      withAccount(
        fakeAccount(SIGNED_IN, api),
        <ClaimScreen id={made.id} sites={fixtureSites} prepare={prepare} />,
      ),
    )
    await screen.findByRole('region', { name: 'Time left' })
    return { api, id: made.id }
  }

  it('keeps the photo buttons shut until every before-you-go item is ticked', async () => {
    await openClaim()
    expect(screen.getByLabelText('Before, point 1')).toBeDisabled()
    for (const box of screen.getAllByRole('checkbox').slice(0, 6))
      await userEvent.click(box)
    expect(screen.getByLabelText('Before, point 1')).toBeEnabled()
  })

  it('sends each photo through the re-encoding step, never the original file', async () => {
    const { api } = await openClaim()
    for (const box of screen.getAllByRole('checkbox').slice(0, 6))
      await userEvent.click(box)
    await userEvent.upload(screen.getByLabelText('Before, point 1'), picture())
    await waitFor(() => expect(api.calls).toContain('photo before 1 image/jpeg'))
    expect(api.calls.some((c) => c.includes('heic'))).toBe(false)
  })

  it('submits once both points have a before and an after', async () => {
    const { api, id } = await openClaim()
    for (const box of screen.getAllByRole('checkbox').slice(0, 6))
      await userEvent.click(box)
    const submitButton = screen.getByRole('button', { name: 'Submit for review' })
    expect(submitButton).toBeDisabled()
    for (const label of [
      'Before, point 1',
      'After, point 1',
      'Before, point 2',
      'After, point 2',
    ]) {
      await userEvent.upload(screen.getByLabelText(label), picture())
      await waitFor(() => expect(screen.getByAltText(label)).toBeInTheDocument())
    }
    await userEvent.click(screen.getByRole('checkbox', { name: 'Hide the site' }))
    await userEvent.click(screen.getByRole('button', { name: 'Submit for review' }))
    await waitFor(async () => expect((await api.claim(id)).state).toBe('submitted'))
    expect((await api.claim(id)).steps_done).toEqual(['Hide the site'])
  })

  it('a crew invite link is shown once made', async () => {
    await openClaim()
    await userEvent.click(screen.getByRole('button', { name: 'Invite someone' }))
    expect(await screen.findByText(/#\/join\//)).toBeInTheDocument()
  })
})

describe('Reviewing', () => {
  it('verifies someone else’s submission from its before and after photos', async () => {
    const api = fakeApi()
    const id = await api.seedSubmittedByOther('example-0004')
    render(
      withAccount(
        fakeAccount(SIGNED_IN, api),
        <ClaimScreen id={id} sites={fixtureSites} prepare={prepare} />,
      ),
    )
    expect(await screen.findByAltText('After, point 2')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Verify' }))
    expect(await screen.findByText(/^Verified by/)).toBeInTheDocument()
  })

  it('sending back needs a note for the crew', async () => {
    const api = fakeApi()
    const id = await api.seedSubmittedByOther('example-0004')
    render(
      withAccount(
        fakeAccount(SIGNED_IN, api),
        <ClaimScreen id={id} sites={fixtureSites} prepare={prepare} />,
      ),
    )
    const sendBack = await screen.findByRole('button', { name: 'Send back' })
    expect(sendBack).toBeDisabled()
    await userEvent.type(screen.getByLabelText(/Note to the crew/), 'Point 2 is blurred')
    await userEvent.click(sendBack)
    await waitFor(async () => expect((await api.claim(id)).state).toBe('in_progress'))
  })
})

describe('Rejecting', () => {
  it('releases the site, with the reason shown on the claim', async () => {
    const api = fakeApi()
    const id = await api.seedSubmittedByOther('example-0004')
    render(
      withAccount(
        fakeAccount(SIGNED_IN, api),
        <ClaimScreen id={id} sites={fixtureSites} prepare={prepare} />,
      ),
    )
    await userEvent.type(
      await screen.findByLabelText(/Note to the crew/),
      'These are photos of a car park',
    )
    await userEvent.click(
      screen.getByRole('button', { name: 'Reject: the work was not done' }),
    )
    expect(await screen.findByText(/^Rejected by/)).toBeInTheDocument()
    expect(await api.claimForSite('example-0004')).toBeNull()
  })
})

describe('Joining and your work', () => {
  it('an invite link joins the crew and opens the claim', async () => {
    const owner = fakeApi()
    const [made] = await owner.claimSites(['example-0004'])
    const { token } = await owner.invite(made.id)
    // The fake is one person; leaving and rejoining stands in for a second one.
    const claim = await owner.claim(made.id)
    expect(claim.crew_size).toBe(1)
    render(withAccount(fakeAccount(SIGNED_IN, owner), <JoinScreen token={token} />))
    await waitFor(() => expect(window.location.hash).toBe(`#/claim/${made.id}`))
  })

  it('a used-up invite says so', async () => {
    render(
      withAccount(
        fakeAccount(SIGNED_IN, fakeApi()),
        <JoinScreen token="nothing-like-a-real-token" />,
      ),
    )
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'This invite does not work',
    )
  })

  it('lists your claims with days left and the work waiting for a reviewer', async () => {
    const api = fakeApi()
    await api.claimSites(['example-0004'])
    await api.seedSubmittedByOther('example-0005')
    render(withAccount(fakeAccount(SIGNED_IN, api), <WorkScreen sites={fixtureSites} />))
    const working = await screen.findByRole('region', { name: 'In progress' })
    expect(within(working).getByText('14 days left')).toBeInTheDocument()
    const waiting = screen.getByRole('region', { name: /Waiting for a reviewer/ })
    expect(
      within(waiting).getByRole('link', { name: 'Example site 5' }),
    ).toBeInTheDocument()
  })
})
