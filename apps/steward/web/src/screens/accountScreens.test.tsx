import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { fixtureSites, fixtureSummary } from '../fixtures'
import {
  SIGNED_IN,
  SIGNED_OUT,
  fakeAccount,
  fakeApi,
  withAccount,
} from '../test/fakeAccount'
import { AccountScreen } from './AccountScreen'
import { ListsScreen } from './ListsScreen'
import { SharedScreen } from './SharedScreen'
import { SitePage } from './SitePage'
import { SitesScreen } from './SitesScreen'

vi.mock('../components/SiteMap', () => ({ SiteMap: () => <div data-testid="map" /> }))

const site1 = fixtureSites.find((s) => s.rims_id === 'example-0001')!

describe('AccountScreen', () => {
  it('says sign-in is not set up on a build with no accounts', () => {
    render(withAccount(fakeAccount({ state: 'off' }), <AccountScreen />))
    expect(
      screen.getByText('Sign-in is not set up on this site yet.'),
    ).toBeInTheDocument()
  })

  it('signs in with an emailed six-digit code', async () => {
    const account = fakeAccount(SIGNED_OUT)
    render(withAccount(account, <AccountScreen />))
    await userEvent.type(screen.getByLabelText('Email'), 'volunteer@example.com')
    await userEvent.click(screen.getByRole('button', { name: 'Email me a code' }))
    await userEvent.type(
      screen.getByLabelText(/six-digit code sent to volunteer@example.com/),
      '123 456',
    )
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(account.sent).toEqual([
      'code to volunteer@example.com',
      'verify volunteer@example.com 123 456',
    ])
  })

  it('shows a wrong code as a plain sentence', async () => {
    render(withAccount(fakeAccount(SIGNED_OUT), <AccountScreen />))
    await userEvent.type(screen.getByLabelText('Email'), 'v@example.com')
    await userEvent.click(screen.getByRole('button', { name: 'Email me a code' }))
    await userEvent.type(screen.getByLabelText(/six-digit code/), '000000')
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'That code is wrong or has expired.',
    )
  })

  it('saves the name others see', async () => {
    render(withAccount(fakeAccount(SIGNED_IN), <AccountScreen />))
    await userEvent.type(await screen.findByLabelText('Name others see'), 'Ridge Runner')
    await userEvent.click(screen.getByRole('button', { name: 'Save' }))
    expect(
      await screen.findByText('Saved. Others see you as "Ridge Runner".'),
    ).toBeInTheDocument()
  })
})

describe('Saving and sharing lists', () => {
  it('asks a signed-out visitor to sign in rather than offering to save', () => {
    render(
      withAccount(
        fakeAccount(SIGNED_OUT),
        <SitePage site={site1} sites={fixtureSites} />,
      ),
    )
    expect(screen.getByText(/to save this site to a list/)).toBeInTheDocument()
  })

  it('saves a site to a new list from its page', async () => {
    const api = fakeApi()
    render(
      withAccount(
        fakeAccount(SIGNED_IN, api),
        <SitePage site={site1} sites={fixtureSites} />,
      ),
    )
    await userEvent.type(
      await screen.findByLabelText("New list's name"),
      'Spring workday',
    )
    await userEvent.click(screen.getByRole('button', { name: 'Save' }))
    expect(await screen.findByRole('status')).toHaveTextContent(
      'Saved to "Spring workday".',
    )
    const [saved] = await api.lists()
    expect((await api.list(saved.id)).rims_ids).toEqual(['example-0001'])
  })

  it('lists the saved sites by name, and a share link opens the same list for someone else', async () => {
    const api = fakeApi()
    const made = await api.createList('Spring workday', ['example-0001', 'gone-from-atc'])
    render(withAccount(fakeAccount(SIGNED_IN, api), <ListsScreen sites={fixtureSites} />))
    const card = await screen.findByRole('region', { name: 'Spring workday' })
    expect(within(card).getByRole('link', { name: 'Example site 1' })).toHaveAttribute(
      'href',
      '#/site/example-0001',
    )
    expect(within(card).getByText(/no longer in ATC's inventory/)).toBeInTheDocument()

    await userEvent.click(within(card).getByRole('button', { name: 'Share' }))
    const link = await within(card).findByText(/#\/shared\//)
    const token = decodeURIComponent(link.textContent!.split('#/shared/')[1])
    expect((await api.openShared(token)).rims_ids).toEqual(made.rims_ids)
  })

  it('a shared list asks a signed-out visitor to sign in first', () => {
    render(
      withAccount(
        fakeAccount(SIGNED_OUT),
        <SharedScreen token="t" sites={fixtureSites} />,
      ),
    )
    expect(screen.getByText(/Sign in to open it/)).toBeInTheDocument()
  })

  it('a replaced share link says it does not open a list', async () => {
    const api = fakeApi()
    const list = await api.createList('x', [])
    const { token } = await api.share(list.id)
    await api.share(list.id)
    render(
      withAccount(
        fakeAccount(SIGNED_IN, api),
        <SharedScreen token={token} sites={fixtureSites} />,
      ),
    )
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'This link does not open a list',
    )
  })
})

describe("A club's own weights", () => {
  it('re-rank the club on the dashboard once a signed-in person picks it', async () => {
    const api = fakeApi()
    // Only the cluster counts: Example site 1, 2 and Shelter 3 share a cluster and lead.
    await api.changeWeights(
      'Example Trail Club',
      { deficit: 0, water: 0, trail: 0, cluster: 100, restricted: 0 },
      null,
    )
    render(
      withAccount(
        fakeAccount(SIGNED_IN, api),
        <SitesScreen sites={fixtureSites} summary={fixtureSummary} />,
      ),
    )
    await userEvent.selectOptions(screen.getByLabelText('Club'), 'Example Trail Club')
    expect(
      await screen.findByText("Ranked by Example Trail Club's weights"),
    ).toBeInTheDocument()
    const needs = within(screen.getByRole('table'))
      .getAllByRole('row')
      .slice(1, 4)
      .map((row) => row.querySelector('.need')!.textContent)
    expect(needs).toEqual(['50', '50', '50'])
  })

  it('a signed-out visitor sees the default ranking and an offer to sign in', async () => {
    render(
      withAccount(
        fakeAccount(SIGNED_OUT),
        <SitesScreen sites={fixtureSites} summary={fixtureSummary} />,
      ),
    )
    await userEvent.selectOptions(screen.getByLabelText('Club'), 'Example Trail Club')
    expect(screen.getByText('Ranked by the default weights')).toBeInTheDocument()
    expect(
      screen.getByRole('link', {
        name: "Sign in to rank by Example Trail Club's own weights",
      }),
    ).toBeInTheDocument()
  })

  it('a change is saved, shown in the history, and can be restored away', async () => {
    const api = fakeApi()
    render(
      withAccount(
        fakeAccount(SIGNED_IN, api),
        <SitesScreen sites={fixtureSites} summary={fixtureSummary} />,
      ),
    )
    await userEvent.selectOptions(screen.getByLabelText('Club'), 'Second Example Club')
    await userEvent.click(await screen.findByRole('button', { name: 'Edit weights' }))
    const water = screen.getByLabelText('Near water')
    await userEvent.clear(water)
    await userEvent.type(water, '30')
    await userEvent.click(screen.getByRole('button', { name: 'Save weights' }))
    await waitFor(() =>
      expect(screen.getByText(/60 · 30 · 6 · 8 · 10/)).toBeInTheDocument(),
    )
    expect((await api.weights('Second Example Club')).current.water).toBe(30)
  })
})
