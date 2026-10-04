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
  it('lists each planned hike with its notices, the route’s first and then the clubs’', () => {
    renderList({
      empty: null,
      undated: 0,
      hikes: [
        {
          stretch: STRETCH,
          onRoute: [notice({ notice_id: 'gmc:closure', obstructs_trail: true })],
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
          fromClubs: [],
        },
      ],
    })
    expect(screen.getByText('Advisory')).toBeTruthy()
    expect(screen.getByText('Hunting allowed')).toBeTruthy()
    expect(screen.queryByText('Closure')).toBeNull()
  })

  it('says when a club’s notices are the last OurHike could read', () => {
    renderList({
      empty: null,
      undated: 0,
      hikes: [
        {
          stretch: STRETCH,
          onRoute: [],
          fromClubs: [
            notice({ notice_id: 'gmc:held', carried_since: '2026-10-03T08:00:00Z' }),
          ],
        },
      ],
    })
    expect(
      screen.getByText(
        /couldn’t re-read Green Mountain Club’s notices since October 3, 2026/,
      ),
    ).toBeTruthy()
  })

  it('says a day hike was matched to its taps when the network is not on the phone', () => {
    renderList({
      empty: null,
      undated: 0,
      hikes: [
        {
          stretch: { ...STRETCH, kind: 'day_hike', routeResolved: false, label: 'Loop' },
          onRoute: [],
          fromClubs: [],
        },
      ],
    })
    expect(screen.getByText(/matched to the points you tapped/)).toBeTruthy()
    expect(screen.getByText('No notices touch this hike.')).toBeTruthy()
  })
})
