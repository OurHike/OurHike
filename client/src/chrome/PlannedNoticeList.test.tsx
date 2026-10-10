import { describe, expect, it, afterEach } from 'vitest'
import { cleanup, render, screen, within } from '@testing-library/react'
import { PlannedNoticeList } from './PlannedNoticeList'
import type { PlannedNotices, PlannedStretch } from '../lib/plannedNotices'
import type { TrailNotice } from '../lib/notices'
import type { Stewards } from '../lib/stewards'

// The panel decision 66 chose (#1805): each hike planned in the next 7 days
// and the notices that touch it, and with none an honest sentence - never a
// feed of every club.

const STEWARDS: Stewards = [
  {
    provider: 'GMC',
    name: 'Green Mountain Club',
    trust: null,
    licence: null,
    attribution: null,
    terms: null,
    termsSource: null,
    layers: [],
    keys: ['gmc_trail_conditions'],
    support: null,
    store: null,
  },
]

function notice(
  overrides: Partial<TrailNotice> & Pick<TrailNotice, 'notice_id'>,
): TrailNotice {
  return {
    source_key: 'gmc_trail_conditions',
    title: 'Fixture bridge out at mile 12',
    category: null,
    locality: '',
    place: { kind: 'unplaced' },
    obstructs_trail: false,
    updated_at: '2026-10-02T12:00:00Z',
    source_url: 'https://www.greenmountainclub.org/fixture',
    review_state: 'unreviewed',
    ...overrides,
  }
}

const STRETCH: PlannedStretch = {
  id: 'trip:t1',
  kind: 'long_hike',
  label: 'Vermont section',
  from: '2026-10-04',
  to: '2026-10-10',
  atSpans: [[1600, 1700]],
  lines: [],
  routeResolved: true,
  providers: new Set(['GMC']),
}

function renderList(planned: PlannedNotices) {
  return render(
    <PlannedNoticeList
      planned={planned}
      stewards={STEWARDS}
      generatedAt={new Date('2026-10-04T12:00:00Z')}
      onClose={() => undefined}
    />,
  )
}

afterEach(cleanup)

describe('PlannedNoticeList', () => {
  // H12 of the word-choice review (2026-10-09): one name for the panel, the
  // one the legend's row and the dialog already carry.
  it('heads the panel "Notices for your planned hikes", the name its dialog and the legend row use', () => {
    renderList({ empty: 'nothing_planned', undated: 0, hikes: [] })
    const panel = screen.getByRole('dialog', { name: 'Notices for your planned hikes' })
    expect(within(panel).getByRole('heading', { level: 2 }).textContent).toBe(
      'Notices for your planned hikes',
    )
  })

  // "Planned for the next 7 days", never "plan to start": lib/plannedNotices.ts
  // takes every unwalked day in the window, so a long hike already under way
  // is in the panel too.
  it('says the panel covers hikes planned for the next 7 days, not only ones that start in them', () => {
    renderList({ empty: 'nothing_planned', undated: 0, hikes: [] })
    const note = screen.getByRole('note')
    expect(note.textContent).toContain(
      'Notices for hikes you’ve planned for the next 7 days',
    )
    expect(note.textContent).not.toMatch(/start/)
    expect(note.textContent).toContain('where there is one, a link to the full notice')
  })

  it('lists each planned hike with its notices, the route’s first and then the clubs’', () => {
    renderList({
      empty: null,
      undated: 0,
      hikes: [
        {
          stretch: STRETCH,
          onRoute: [notice({ notice_id: 'gmc:closure', obstructs_trail: true })],
          stateWide: [],
          fromClubs: [
            notice({
              notice_id: 'gmc:spring',
              title: 'Fixture spring dry near Stratton',
            }),
          ],
        },
      ],
    })

    const hike = screen.getByRole('region', { name: 'Vermont section' })
    expect(within(hike).getByText(/Sat, Oct 10/)).toBeTruthy()
    expect(
      within(hike).getByText('The stretch you plan to walk in the next 7 days.'),
    ).toBeTruthy()
    const onRoute = within(hike).getByRole('list', { name: 'On your route' })
    expect(within(onRoute).getByText('Closure')).toBeTruthy()
    const fromClubs = within(hike).getByRole('list', {
      name: 'From the clubs on your route',
    })
    expect(
      within(hike).getByText(
        'From the clubs that look after these trails. These aren’t on the map, so check each one for where it applies.',
      ),
    ).toBeTruthy()
    expect(within(fromClubs).getByText('Fixture spring dry near Stratton')).toBeTruthy()
    // The organization's name comes from the registry, never the component.
    expect(within(fromClubs).getByText(/Green Mountain Club — updated/)).toBeTruthy()
    expect(
      within(fromClubs).getByRole('link', { name: 'Read Green Mountain Club’s notice' }),
    ).toBeTruthy()
  })

  it('says why there is nothing with no hike planned, and lists no club’s notices', () => {
    renderList({ empty: 'nothing_planned', undated: 0, hikes: [] })
    expect(
      screen.getByText(
        'You have no hike planned, so there are no notices to pick for one.',
      ),
    ).toBeTruthy()
    expect(screen.queryByRole('list')).toBeNull()
  })

  it('says a planned hike has no day in the window, and counts the undated plans', () => {
    renderList({ empty: 'nothing_in_the_window', undated: 2, hikes: [] })
    expect(
      screen.getByText('None of your planned hikes has a day in the next 7 days.'),
    ).toBeTruthy()
    expect(screen.getByText(/2 of your plans have no dates yet\./)).toBeTruthy()
  })

  it('marks a hazard area as an advisory, never a closure', () => {
    renderList({
      empty: null,
      undated: 0,
      hikes: [
        {
          stretch: STRETCH,
          onRoute: [
            notice({ notice_id: 'iata:1', hazard: 'hunting', title: 'Fixture parcel' }),
          ],
          stateWide: [],
          fromClubs: [],
        },
      ],
    })
    expect(screen.getByText('Advisory')).toBeTruthy()
    expect(screen.getByText('Hunting allowed')).toBeTruthy()
    expect(screen.queryByText('Closure')).toBeNull()
  })

  it('says OurHike has not been able to read a held club’s notices since carried_since', () => {
    renderList({
      empty: null,
      undated: 0,
      hikes: [
        {
          stretch: STRETCH,
          onRoute: [],
          stateWide: [],
          fromClubs: [
            notice({ notice_id: 'gmc:held', carried_since: '2026-10-03T08:00:00Z' }),
          ],
        },
      ],
    })
    expect(
      screen.getByText(
        'OurHike hasn’t been able to read Green Mountain Club’s notices since October 3, 2026. This is the last version it saw.',
      ),
    ).toBeTruthy()
  })

  it('names a state-wide notice’s states as “All of”, tagged Notice and never Advisory (decision 76)', () => {
    const area = (state: string, name: string) => ({
      state,
      name,
      edge_margin_m: 500,
      geometry: { type: 'Polygon', coordinates: [] },
    })
    renderList({
      empty: null,
      undated: 0,
      hikes: [
        {
          stretch: { ...STRETCH, kind: 'day_hike', label: 'Fixture canyon loop' },
          onRoute: [],
          stateWide: [
            notice({
              notice_id: 'agency:fire',
              title: 'Fixture fire restrictions',
              steward_kind: 'agency',
              states: ['OR', 'WA'],
              state_areas: [area('OR', 'Oregon'), area('WA', 'Washington')],
            }),
          ],
          fromClubs: [],
        },
      ],
    })
    const list = screen.getByRole('list', { name: 'For the whole state' })
    expect(within(list).getByText('Fixture fire restrictions')).toBeTruthy()
    expect(within(list).getByText('All of Oregon and Washington')).toBeTruthy()
    expect(within(list).getByText('Notice')).toBeTruthy()
    expect(within(list).queryByText('Advisory')).toBeNull()
  })

  // Decision 78 (card N2, frame A): the source's own category, on its own line
  // under the title. Every row here is invented.
  function renderRows(...rows: TrailNotice[]) {
    renderList({
      empty: null,
      undated: 0,
      hikes: [{ stretch: STRETCH, onRoute: rows, stateWide: [], fromClubs: [] }],
    })
  }

  function row(title: string): HTMLElement {
    const item = screen.getByText(title).closest('li')
    if (item === null) throw new Error(`no row holds ${title}`)
    return item
  }

  it('shows a category "closed" as Listed as “Closed” under the title and before the locality (decision 78)', () => {
    renderRows(
      notice({
        notice_id: 'usfs:1',
        title: 'Fixture Creek Campground',
        category: 'closed',
        locality: 'Fixture National Forest',
      }),
    )
    const lines = Array.from(row('Fixture Creek Campground').children).map(
      (line) => line.textContent,
    )
    expect(lines.slice(0, 3)).toEqual([
      'Notice Fixture Creek Campground',
      'Listed as “Closed”',
      'Fixture National Forest',
    ])
    expect(screen.getByText('Listed as “Closed”').className).toBe(
      'planned-notices__category',
    )
  })

  it('keeps a category as its source wrote it past the first letter (decision 78)', () => {
    renderRows(
      notice({
        notice_id: 'usfs:2',
        title: 'Fixture Lake Site',
        category: 'temporarily closed',
      }),
      notice({ notice_id: 'usfs:3', title: 'Fixture Order', category: 'Closure Order' }),
    )
    expect(
      within(row('Fixture Lake Site')).getByText('Listed as “Temporarily closed”'),
    ).toBeTruthy()
    expect(
      within(row('Fixture Order')).getByText('Listed as “Closure Order”'),
    ).toBeTruthy()
  })

  // A row beside the ones under test whose category does show, so neither test
  // below can pass on a list that never shows a category at all.
  const SHOWN = notice({
    notice_id: 'gmc:shown',
    title: 'Fixture shown',
    category: 'Detour',
  })

  it('adds no category line to a row whose category is null or blank (decision 78)', () => {
    renderRows(
      SHOWN,
      notice({ notice_id: 'gmc:null', title: 'Fixture null category', category: null }),
      notice({ notice_id: 'gmc:blank', title: 'Fixture blank category', category: '  ' }),
    )
    expect(within(row('Fixture shown')).getByText('Listed as “Detour”')).toBeTruthy()
    for (const title of ['Fixture null category', 'Fixture blank category']) {
      expect(row(title).querySelector('.planned-notices__category')).toBeNull()
    }
  })

  it('does not repeat a category equal to the title or to the tag, ignoring case and spacing (decision 78)', () => {
    renderRows(
      SHOWN,
      notice({
        notice_id: 'usfs:fire',
        title: 'Fixture Creek Fire',
        category: 'fixture creek  FIRE',
      }),
      notice({
        notice_id: 'gmc:closed',
        title: 'Fixture footbridge out',
        category: 'closure',
        obstructs_trail: true,
      }),
    )
    expect(within(row('Fixture shown')).getByText('Listed as “Detour”')).toBeTruthy()
    for (const title of ['Fixture Creek Fire', 'Fixture footbridge out']) {
      expect(row(title).querySelector('.planned-notices__category')).toBeNull()
    }
  })

  it('still shows a category that only appears inside the title, or names another tag (decision 78)', () => {
    renderRows(
      notice({
        notice_id: 'usfs:order',
        title: 'Fixture Fire Closure Superseding',
        category: 'Fixture Fire',
      }),
      // The source says Closure where OurHike's tag says Notice.
      notice({ notice_id: 'cdtc:1', title: 'Fixture washout', category: 'Closure' }),
    )
    expect(
      within(row('Fixture Fire Closure Superseding')).getByText(
        'Listed as “Fixture Fire”',
      ),
    ).toBeTruthy()
    const washout = row('Fixture washout')
    expect(within(washout).getByText('Notice')).toBeTruthy()
    expect(washout.querySelector('.planned-notices__category')?.textContent).toBe(
      'Listed as “Closure”',
    )
  })

  it('says a day hike’s notices were matched to straight lines between its taps when its trails are not on the phone', () => {
    renderList({
      empty: null,
      undated: 0,
      hikes: [
        {
          stretch: { ...STRETCH, kind: 'day_hike', routeResolved: false, label: 'Loop' },
          onRoute: [],
          stateWide: [],
          fromClubs: [],
        },
      ],
    })
    expect(
      screen.getByText(
        'This hike’s trails aren’t on this phone yet, so notices were matched to straight lines between your tapped points, not to the trails.',
      ),
    ).toBeTruthy()
    // What OurHike found, never "the trail is clear".
    expect(screen.getByText('OurHike found no notices for this hike.')).toBeTruthy()
  })

  // H3 of the word-choice review: with no trail line, lib/plannedNotices.ts's
  // noticeTouches skips every notice placed by a shape, so the line warns of
  // what may be missing before it says what is still matched.
  it('warns that notices placed on the map may be missing while a long hike’s trail line has not loaded', () => {
    renderList({
      empty: null,
      undated: 0,
      hikes: [
        {
          stretch: { ...STRETCH, routeResolved: false },
          onRoute: [],
          stateWide: [],
          fromClubs: [],
        },
      ],
    })
    expect(
      screen.getByText(
        'The trail line hasn’t loaded yet, so notices tied to a place on the map may be missing. Notices given by A.T. mile are included.',
      ),
    ).toBeTruthy()
  })

  // H7: the row's own dates in the long style the rest of the panel prints.
  it('prints a notice’s own dates as "from October 1, 2026 until October 31, 2026", never ISO days', () => {
    renderRows(
      notice({
        notice_id: 'gmc:dated',
        title: 'Fixture reroute',
        locality: 'Fixture Notch',
        starts_on: '2026-10-01',
        ends_on: '2026-10-31',
      }),
    )
    expect(
      within(row('Fixture reroute')).getByText(
        'Fixture Notch · from October 1, 2026 until October 31, 2026',
      ),
    ).toBeTruthy()
    expect(row('Fixture reroute').textContent).not.toMatch(/2026-10-/)
  })
})
