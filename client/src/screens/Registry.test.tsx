import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, within } from '@testing-library/react'
import { Registry } from './Registry'
import type { SourceRegistry } from '../lib/registry'

// The org console, read-only (#929).
//
// The failures worth guarding are not crashes. Every one of them is the screen
// making a claim the registry does not:
//
// - An empty table where the real answer is "we could not ask", which says
//   nothing is registered on the evidence that the phone is offline.
// - A filled-in `kind` where the registration declares none, which hides
//   exactly the twelve rows a probe could not describe.
// - A licence that reads as the organization's grant when it is the
//   maintainer's own call.

const REGISTRY: SourceRegistry = {
  sources: [
    {
      key: 'nynjtc_trail_alerts',
      title: 'NYNJTC Trail Alerts',
      provider: 'NYNJTC',
      steward_id: 'org:nynjtc',
      steward: 'New York-New Jersey Trail Conference',
      kind: 'published_notices',
      trust: 'authoritative',
      reaches_hikers: true,
      licence_basis: 'maintainer_authorisation',
      freshness_kind: 'http_etag',
      supports_donation: true,
      mark_state: 'not_asked',
    },
    {
      key: 'oprhp_trails',
      title: 'NYS Parks Trails',
      provider: 'NYS OPRHP',
      steward_id: 'org:nysoprhp',
      steward: 'New York State Office of Parks, Recreation and Historic Preservation',
      kind: 'external_arcgis_layer',
      trust: 'authoritative',
      reaches_hikers: true,
      licence_basis: 'stated_by_org',
      freshness_kind: null,
      supports_donation: true,
      mark_state: 'not_asked',
    },
    {
      key: 'oprhp_park_polygons',
      title: 'NYS Park Polygons',
      provider: 'NYS OPRHP',
      steward_id: 'org:nysoprhp',
      steward: 'New York State Office of Parks, Recreation and Historic Preservation',
      kind: 'external_arcgis_layer',
      trust: 'authoritative',
      reaches_hikers: false,
      licence_basis: 'stated_by_org',
      freshness_kind: null,
      supports_donation: true,
      mark_state: 'not_asked',
    },
    {
      // The twelve-of-thirty-three case: an ATC entry declaring no kind.
      key: 'centerline',
      title: 'A.T. Centerline',
      provider: 'ATC',
      steward_id: 'org:atc',
      steward: 'Appalachian Trail Conservancy',
      kind: null,
      trust: null,
      reaches_hikers: true,
      licence_basis: 'maintainer_authorisation',
      freshness_kind: null,
      supports_donation: true,
      mark_state: 'not_asked',
    },
  ],
  organizations: [
    {
      steward_id: 'org:atc',
      provider: 'ATC',
      name: 'Appalachian Trail Conservancy',
      note: 'The A.T.’s route owner.',
    },
    {
      steward_id: 'org:nynjtc',
      provider: 'NYNJTC',
      name: 'New York-New Jersey Trail Conference',
      note: 'Maintains trails across the NY-NJ region.',
    },
    {
      steward_id: 'org:nysoprhp',
      provider: 'NYS OPRHP',
      name: 'New York State Office of Parks, Recreation and Historic Preservation',
      note: 'The landowner inside Harriman and Fahnestock.',
    },
  ],
}

/** The third licence basis, which is neither of the other two: nobody has
 *  answered, and nothing ships. GATC's club PDF is the real one. */
const WITH_UNANSWERED: SourceRegistry = {
  organizations: REGISTRY.organizations,
  sources: [
    REGISTRY.sources[0],
    {
      ...REGISTRY.sources[0],
      key: 'gatc_water_sources',
      title: 'GATC Water Sources',
      licence_basis: 'unresolved',
      reaches_hikers: false,
    },
  ],
}

function renderScreen(load: () => Promise<SourceRegistry | null>) {
  return render(<Registry onClose={vi.fn()} load={load} />)
}

afterEach(cleanup)

describe('what the console shows', () => {
  it('names every registered source, including the ones no hiker sees', async () => {
    // The whole reason this reads its own artifact rather than stewards.json.
    renderScreen(() => Promise.resolve(REGISTRY))

    expect(await screen.findByText('oprhp_park_polygons')).toBeInTheDocument()
    expect(screen.getByText('Held back')).toBeInTheDocument()
  })

  it('groups by organization, largest registration first', async () => {
    renderScreen(() => Promise.resolve(REGISTRY))
    await screen.findByText('nynjtc_trail_alerts')

    const names = screen.getAllByRole('heading', { level: 3 }).map((h) => h.textContent)

    expect(names[0]).toContain('New York State Office of Parks')
  })

  it('shows each organization-s stable id rather than only its display name', async () => {
    // The id is the thing that cannot be reworded, which is why it exists -
    // see pipeline/tests/test_organizations.py.
    renderScreen(() => Promise.resolve(REGISTRY))

    expect(await screen.findByText('org:nynjtc')).toBeInTheDocument()
  })

  it('leaves an undeclared kind visibly empty rather than filling it in', async () => {
    // `lib/source_registry.py` reads an absent kind as an ArcGIS feature
    // layer. That default is a fact about the FETCHER, and printing it here
    // would hide the registrations a probe cannot describe.
    renderScreen(() => Promise.resolve(REGISTRY))
    await screen.findByText('centerline')

    const row = screen.getByText('centerline').closest('tr') as HTMLElement
    expect(within(row).getByText('not declared')).toBeInTheDocument()
  })

  it('says whose word each licence is, in two different words', async () => {
    // The one column where the difference between two values is a difference
    // in who is exposed. "Your call" must never read as the organization's
    // grant, because it is the opposite of one.
    renderScreen(() => Promise.resolve(REGISTRY))
    await screen.findByText('oprhp_trails')

    const stated = screen.getByText('oprhp_trails').closest('tr') as HTMLElement
    const ours = screen.getByText('nynjtc_trail_alerts').closest('tr') as HTMLElement

    expect(within(stated).getByText('Their terms')).toBeInTheDocument()
    expect(within(ours).getByText('Your call')).toBeInTheDocument()
  })

  it('counts how much of the registry ships on the maintainer-s own word', async () => {
    renderScreen(() => Promise.resolve(REGISTRY))

    const counts = await screen.findByText(/ship on your own authorisation/)
    expect(counts).toHaveTextContent('4 registered sources across 3 organizations')
    expect(counts).toHaveTextContent('3 reach a hiker')
    expect(counts).toHaveTextContent('2 ship on your own authorisation')
  })

  it('does not fold an unanswered registration in with the maintainer-s call', async () => {
    // Three bases, not two. Counting `!stated_by_org` printed one number over
    // both, which claims a decision nobody made for the rows where nobody has
    // answered - and this is the one screen whose whole job is saying what
    // rests on what. Real: GATC's club PDF, unanswered and shipping nowhere.
    renderScreen(() => Promise.resolve(WITH_UNANSWERED))

    const counts = await screen.findByText(/ship on your own authorisation/)
    expect(counts).toHaveTextContent('1 ship on your own authorisation')
    expect(counts).toHaveTextContent('1 waiting on an answer')
  })

  it('says nothing about answers when every registration has one', async () => {
    renderScreen(() => Promise.resolve(REGISTRY))

    expect(
      await screen.findByText(/ship on your own authorisation/),
    ).not.toHaveTextContent(/waiting on an answer/)
  })

  it('shows an empty mark slot on every organization, because none is licensed', async () => {
    // #933. An organization's identity is the one thing in this app that must
    // not be approximated, and a visibly empty slot is the thing most likely
    // to prompt somebody to go and ask.
    renderScreen(() => Promise.resolve(REGISTRY))

    expect(await screen.findAllByLabelText('No licensed mark')).toHaveLength(3)
  })
})

describe('what it refuses to claim', () => {
  it('says it could not read the registry, rather than showing none', async () => {
    // "We could not ask" and "nothing is registered" are different claims.
    renderScreen(() => Promise.resolve(null))

    expect(await screen.findByText(/couldn’t read the registry/)).toBeInTheDocument()
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })

  it('says a release genuinely carrying none carries none', async () => {
    renderScreen(() => Promise.resolve({ sources: [], organizations: [] }))

    expect(
      await screen.findByText('This release carries no registry.'),
    ).toBeInTheDocument()
  })

  it('says plainly that nothing here changes a hiker-s map', async () => {
    // The property the whole screen is built around, and the one a reader has
    // to be told rather than infer from the absence of buttons.
    renderScreen(() => Promise.resolve(REGISTRY))

    expect(screen.getByRole('note')).toHaveTextContent(
      /Nothing on this screen changes what is on a hiker’s phone/,
    )
  })

  it('offers no control that could change anything', async () => {
    renderScreen(() => Promise.resolve(REGISTRY))
    await screen.findByText('nynjtc_trail_alerts')

    // Close, and nothing else. A console that grew an Approve button without
    // the pull-request bridge behind it would break the one property that
    // makes this safe to build now.
    expect(screen.getAllByRole('button').map((b) => b.textContent)).toEqual(['Close×'])
  })
})
