import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { act } from '@testing-library/react'
import { ApiError } from '../api'
import { clearOffline, queuedPhotos, refusedPhotos, saveClaim } from '../offline'
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

afterEach(async () => {
  window.location.hash = ''
  window.localStorage.clear()
  await clearOffline(ME)
})

const ME = SIGNED_IN.state === 'signed_in' ? SIGNED_IN.userId : ''

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

  it('shows a site someone else claimed as held, without their name until the work is verified', async () => {
    const api = fakeApi()
    await api.seedSubmittedByOther('example-0004', 'Ridge Runner')
    render(
      withAccount(
        fakeAccount(SIGNED_IN, api),
        <SitePage site={site4} sites={fixtureSites} />,
      ),
    )
    expect(
      await screen.findByText(/by a volunteer, and waiting for someone off the crew/),
    ).toBeInTheDocument()
    expect(screen.queryByText(/Ridge Runner/)).not.toBeInTheDocument()
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

describe('A claim seen from outside its crew', () => {
  it('says its photos and report are the crew’s until submitted, not that it has none', async () => {
    const api = fakeApi()
    const id = await api.seedWorkedByOther('example-0004')
    render(
      withAccount(
        fakeAccount(SIGNED_IN, api),
        <ClaimScreen id={id} sites={fixtureSites} prepare={prepare} />,
      ),
    )
    expect(
      await screen.findByText(
        /Its photos and report are the crew’s until they submit it/,
      ),
    ).toBeInTheDocument()
    expect(screen.queryByText('No photo')).not.toBeInTheDocument()
    expect(screen.queryByText('No steps ticked.')).not.toBeInTheDocument()
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
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

describe('With no signal', () => {
  it('opens a claim this phone saved, and says it is the saved copy', async () => {
    const api = fakeApi()
    const [made] = await api.claimSites(['example-0004'])
    await saveClaim(ME, await api.claim(made.id))
    const offline = {
      ...api,
      claim: vi.fn(async () => Promise.reject(new TypeError('Failed to fetch'))),
    }
    render(
      withAccount(
        fakeAccount(SIGNED_IN, offline),
        <ClaimScreen id={made.id} sites={fixtureSites} prepare={prepare} />,
      ),
    )
    expect(
      await screen.findByText(/This is the claim as this phone saved it/),
    ).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Time left' })).toBeInTheDocument()
  })

  it('says so when a claim was never opened on this phone', async () => {
    const api = {
      ...fakeApi(),
      claim: vi.fn(async () => Promise.reject(new TypeError('Failed to fetch'))),
    }
    render(
      withAccount(
        fakeAccount(SIGNED_IN, api),
        <ClaimScreen id="claim-x" sites={fixtureSites} prepare={prepare} />,
      ),
    )
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'has not been opened on this phone before',
    )
  })

  it('keeps a photo on the phone, shows it waiting, and sends it when the signal comes back', async () => {
    const api = fakeApi()
    const [made] = await api.claimSites(['example-0004'])
    let signal = false
    const flaky = {
      ...api,
      uploadPhoto: vi.fn(async (...args: Parameters<typeof api.uploadPhoto>) =>
        signal
          ? api.uploadPhoto(...args)
          : Promise.reject(new TypeError('Failed to fetch')),
      ),
    }
    render(
      withAccount(
        fakeAccount(SIGNED_IN, flaky),
        <ClaimScreen id={made.id} sites={fixtureSites} prepare={prepare} />,
      ),
    )
    await screen.findByRole('region', { name: 'Time left' })
    for (const box of screen.getAllByRole('checkbox').slice(0, 6))
      await userEvent.click(box)
    await userEvent.upload(screen.getByLabelText('Before, point 1'), picture())
    expect(
      await screen.findByText(/1 photo waiting on this phone for signal/),
    ).toBeInTheDocument()
    expect(screen.getByText('Waiting for signal')).toBeInTheDocument()
    expect(await queuedPhotos(ME, made.id)).toHaveLength(1)

    signal = true
    await act(async () => {
      window.dispatchEvent(new Event('online'))
    })
    await waitFor(async () => expect(await queuedPhotos(ME, made.id)).toHaveLength(0))
    await waitFor(() =>
      expect(screen.queryByText(/waiting on this phone/)).not.toBeInTheDocument(),
    )
    expect(api.calls).toContain('photo before 1 image/jpeg')
  })

  it('keeps photos the claim no longer takes, and lets their owner save, retry or discard each', async () => {
    // The third pass's P1: the claim ran out while the phone had no signal,
    // and the photos waiting for it were deleted when the signal came back.
    const api = fakeApi()
    const [made] = await api.claimSites(['example-0004'])
    let answer: 'none' | 'released' = 'none'
    const closing = {
      ...api,
      uploadPhoto: vi.fn(async () =>
        Promise.reject(
          answer === 'none'
            ? new TypeError('Failed to fetch')
            : new ApiError(409, 'This claim is released, so that cannot be done now'),
        ),
      ),
    }
    render(
      withAccount(
        fakeAccount(SIGNED_IN, closing),
        <ClaimScreen id={made.id} sites={fixtureSites} prepare={prepare} />,
      ),
    )
    await screen.findByRole('region', { name: 'Time left' })
    for (const box of screen.getAllByRole('checkbox').slice(0, 6))
      await userEvent.click(box)
    await userEvent.upload(screen.getByLabelText('After, point 1'), picture())
    await screen.findByText(/1 photo waiting on this phone for signal/)

    answer = 'released'
    await act(async () => {
      window.dispatchEvent(new Event('online'))
    })
    const kept = await screen.findByRole('region', { name: /Not sent/ })
    expect(within(kept).getByText('After, point 1')).toBeInTheDocument()
    expect(within(kept).getByText(/This claim is released/)).toBeInTheDocument()
    expect(refusedPhotos(await queuedPhotos(ME, made.id))).toHaveLength(1)

    await userEvent.click(within(kept).getByRole('button', { name: 'Try again' }))
    await waitFor(() => expect(closing.uploadPhoto).toHaveBeenCalledTimes(3))
    expect(await queuedPhotos(ME, made.id)).toHaveLength(1)

    await userEvent.click(
      within(await screen.findByRole('region', { name: /Not sent/ })).getByRole(
        'button',
        {
          name: 'Discard',
        },
      ),
    )
    await waitFor(() =>
      expect(screen.queryByRole('region', { name: /Not sent/ })).not.toBeInTheDocument(),
    )
    expect(await queuedPhotos(ME, made.id)).toEqual([])
  })

  it('shows the before photo under an empty after slot, to line up with', async () => {
    const api = fakeApi()
    const [made] = await api.claimSites(['example-0004'])
    await api.uploadPhoto(made.id, 'before', 1, new Blob(['x'], { type: 'image/jpeg' }))
    render(
      withAccount(
        fakeAccount(SIGNED_IN, api),
        <ClaimScreen id={made.id} sites={fixtureSites} prepare={prepare} />,
      ),
    )
    expect(
      await screen.findByAltText('The before photo at point 1, to line up with'),
    ).toBeInTheDocument()
    expect(
      screen.queryByAltText('The before photo at point 2, to line up with'),
    ).not.toBeInTheDocument()
  })
})
