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

  it('shows a site someone else claimed as held, without their name until the work is done', async () => {
    const api = fakeApi()
    await api.seedWorkedByOther('example-0004', 'Ridge Runner')
    render(
      withAccount(
        fakeAccount(SIGNED_IN, api),
        <SitePage site={site4} sites={fixtureSites} />,
      ),
    )
    expect(
      await screen.findByText(/by a volunteer, 14 days left on the claim/),
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

  it('is marked done once both points have a before and an after, and is then public', async () => {
    const { api, id } = await openClaim()
    for (const box of screen.getAllByRole('checkbox').slice(0, 6))
      await userEvent.click(box)
    const doneButton = screen.getByRole('button', { name: 'Mark as done' })
    expect(doneButton).toBeDisabled()
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
    expect(screen.getByText(/Done is public at once/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Mark as done' }))
    await waitFor(async () => expect((await api.claim(id)).state).toBe('done'))
    expect((await api.claim(id)).steps_done).toEqual(['Hide the site'])
    // No reviewer: the record and the site's follow-up visits come next.
    expect(
      await screen.findByRole('region', { name: 'Follow-up visits' }),
    ).toBeInTheDocument()
  })

  it('has no crew, no invite and no reminder (decided 2026-10-28)', async () => {
    await openClaim()
    expect(
      screen.queryByRole('button', { name: 'Invite someone' }),
    ).not.toBeInTheDocument()
    expect(screen.queryByText(/Under five days left/)).not.toBeInTheDocument()
    expect(screen.getByText(/volunteer agreement/)).toBeInTheDocument()
  })
})

describe('A claim seen by someone else', () => {
  it('says its photos and report are the claimer’s until done, not that it has none', async () => {
    const api = fakeApi()
    const id = await api.seedWorkedByOther('example-0004')
    render(
      withAccount(
        fakeAccount(SIGNED_IN, api),
        <ClaimScreen id={id} sites={fixtureSites} prepare={prepare} />,
      ),
    )
    expect(
      await screen.findByText(/Its photos and report are theirs until they mark it done/),
    ).toBeInTheDocument()
    expect(screen.queryByText('No photo')).not.toBeInTheDocument()
    expect(screen.queryByText('No steps ticked.')).not.toBeInTheDocument()
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
  })

  it('shows done work to anyone: the before and after, the name, and no review to give', async () => {
    const api = fakeApi()
    const id = await api.seedDoneByOther('example-0004', 'Ridge Runner')
    render(
      withAccount(
        fakeAccount(SIGNED_IN, api),
        <ClaimScreen id={id} sites={fixtureSites} prepare={prepare} />,
      ),
    )
    expect(await screen.findByAltText('After, point 2')).toBeInTheDocument()
    expect(screen.getByText(/by Ridge Runner/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Verify' })).not.toBeInTheDocument()
  })
})

describe('Follow-up visits', () => {
  it('a restored site offers its open visit, and taking it opens a claim of its own', async () => {
    const api = fakeApi()
    await api.seedDoneByOther('example-0004', 'Ridge Runner', true)
    render(
      withAccount(
        fakeAccount(SIGNED_IN, api),
        <SitePage site={site4} sites={fixtureSites} />,
      ),
    )
    const visits = await screen.findByRole('region', { name: 'Follow-up visits' })
    expect(
      screen.getByRole('link', { name: 'See the before and after' }),
    ).toHaveAttribute('href', expect.stringMatching(/^#\/claim\//))
    expect(within(visits).getAllByText(/Not open yet/)).toHaveLength(2)
    await userEvent.click(within(visits).getByRole('button', { name: 'Take visit 1' }))
    await waitFor(() => expect(window.location.hash).toMatch(/^#\/claim\//))
    expect(api.calls).toContain('take follow-up 1')
  })

  it('a visit re-photographs only the after, lined up with the restoration’s', async () => {
    const api = fakeApi()
    await api.seedDoneByOther('example-0004', 'Ridge Runner', true)
    const [first] = await api.followUps('example-0004')
    const visit = await api.takeFollowUp(first.id)
    render(
      withAccount(
        fakeAccount(SIGNED_IN, api),
        <ClaimScreen id={visit.id} sites={fixtureSites} prepare={prepare} />,
      ),
    )
    await screen.findByRole('region', { name: 'Time left' })
    expect(screen.getByText(/Follow-up visit 1 of 3/)).toBeInTheDocument()
    expect(screen.queryByLabelText('Before, point 1')).not.toBeInTheDocument()
    expect(screen.getByLabelText('After, point 1')).toBeInTheDocument()
    expect(
      screen.getAllByRole('img', { name: /At the restoration, point/ }),
    ).toHaveLength(2)
    expect(
      screen.getByRole('checkbox', { name: 'Redo the cover where it has moved' }),
    ).toBeInTheDocument()
  })
})

describe('Your work', () => {
  it('lists your claims with days left and your hours on done work', async () => {
    const api = fakeApi()
    await api.claimSites(['example-0004'])
    render(withAccount(fakeAccount(SIGNED_IN, api), <WorkScreen sites={fixtureSites} />))
    const working = await screen.findByRole('region', { name: 'In progress' })
    expect(within(working).getByText('14 days left')).toBeInTheDocument()
    expect(screen.getByText('hours on done work')).toBeInTheDocument()
    expect(screen.queryByText(/Waiting for a reviewer/)).not.toBeInTheDocument()
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
      await screen.findByAltText('The earlier photo at point 1, to line up with'),
    ).toBeInTheDocument()
    expect(
      screen.queryByAltText('The earlier photo at point 2, to line up with'),
    ).not.toBeInTheDocument()
  })
})
