import { describe, expect, it, afterEach } from 'vitest'
import { DATA_BUILT_URL } from '../lib/dataPages'
import { cleanup, render, screen, within } from '@testing-library/react'
import { PlannedNoticeList } from './PlannedNoticeList'
import type { PlannedNotices, PlannedStretch } from '../lib/plannedNotices'
import type { TrailNotice } from '../lib/notices'
import type { Stewards } from '../lib/stewards'

// The planned-hike panel (#1805): each hike planned in the next 7 days
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

/** The phone's own calendar day each row's `current_until` is read against
 *  (lib/noticeCurrency.ts). */
const TODAY = '2026-10-10'

function renderList(planned: PlannedNotices, today: string = TODAY) {
  return render(
    <PlannedNoticeList
      planned={planned}
      stewards={STEWARDS}
      generatedAt={new Date('2026-10-04T12:00:00Z')}
      today={today}
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

  it('says the notices came from each organization’s own published notices, and links how OurHike gathers and checks them', () => {
    renderList({ empty: 'nothing_planned', undated: 0, hikes: [] })

    const age = screen.getByText(/^Gathered by OurHike on /)
    expect(age).toHaveTextContent(
      'Gathered by OurHike on October 4, 2026 from each organization’s own published notices. How OurHike gathers and checks these ›',
    )
    expect(
      within(age).getByRole('link', { name: 'How OurHike gathers and checks these ›' }),
    ).toHaveAttribute('href', DATA_BUILT_URL)
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

  it('names a state-wide notice’s states as “All of”, tagged Notice and never Advisory', () => {
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

  // The source's own category, on its own line
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

  it('shows a category "closed" as Listed as “Closed” under the title and before the locality', () => {
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

  it('keeps a category as its source wrote it past the first letter', () => {
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

  it('adds no category line to a row whose category is null or blank', () => {
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

  it('does not repeat a category equal to the title or to the tag, ignoring case and spacing', () => {
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

  it('still shows a category that only appears inside the title, or names another tag', () => {
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
  // The maintainer's frame A (poll of 2026-10-10): a notice that may no longer
  // apply stays in the list, greyed, with one line under it. The rows mirror
  // the frame's three, plus the two cases it did not draw. Every one is
  // invented.
  describe('a notice that may no longer apply (frame A)', () => {
    const CURRENT = notice({
      notice_id: 'gmc:a-current',
      title: 'Bridge out at Mill Creek (fixture)',
      obstructs_trail: true,
      updated_at: '2026-10-08T12:00:00Z',
      current_until: '2027-01-06',
    })
    const RAN_PAST_ITS_LIMIT = notice({
      notice_id: 'gmc:b-lower-loop',
      title: 'Lower loop closed for 3 to 6 months (fixture)',
      obstructs_trail: true,
      starts_on: '2025-01-06',
      updated_at: '2026-03-05T12:00:00Z',
      current_until: '2025-07-06',
    })
    const NO_DATE = notice({
      notice_id: 'gmc:c-section-12',
      title: 'Section 12 closed (fixture)',
      obstructs_trail: true,
      updated_at: null,
      current_until: null,
    })

    it('greys a row past its current_until and says "Last reported March 5, 2026. It may no longer apply."', () => {
      renderRows(CURRENT, RAN_PAST_ITS_LIMIT, NO_DATE)
      const greyed = row('Lower loop closed for 3 to 6 months (fixture)')
      expect(greyed.className).toContain('notice--not-current')
      expect(
        within(greyed).getByText('Last reported March 5, 2026. It may no longer apply.')
          .className,
      ).toBe('notice__not-current')
      // The edit date once, in the line, as the frame prints it.
      expect(within(greyed).getByText('Green Mountain Club').className).toBe(
        'closure-sheet__meta',
      )
      expect(within(greyed).queryByText(/— updated/)).toBeNull()
      // Still the closure it was, its link still there to check it.
      expect(within(greyed).getByText('Closure')).toBeTruthy()
      expect(
        within(greyed).getByRole('link', { name: 'Read Green Mountain Club’s notice' }),
      ).toBeTruthy()
    })

    it('greys a row that gives no date with "Its source gives no date. It may no longer apply."', () => {
      renderRows(CURRENT, RAN_PAST_ITS_LIMIT, NO_DATE)
      const greyed = row('Section 12 closed (fixture)')
      expect(greyed.className).toContain('notice--not-current')
      expect(
        within(greyed).getByText('Its source gives no date. It may no longer apply.'),
      ).toBeTruthy()
    })

    it('leaves a row inside its current_until as it was, with its "— updated" date', () => {
      renderRows(CURRENT, RAN_PAST_ITS_LIMIT, NO_DATE)
      const current = row('Bridge out at Mill Creek (fixture)')
      expect(current.className).not.toContain('notice--not-current')
      expect(within(current).queryByText(/may no longer apply/)).toBeNull()
      expect(
        within(current).getByText('Green Mountain Club — updated October 8, 2026'),
      ).toBeTruthy()
    })

    it('reads current_until as the last current day: current on it, greyed the day after', () => {
      const lastDay = notice({
        notice_id: 'gmc:last-day',
        title: 'Fixture order',
        updated_at: '2026-07-12T23:59:59Z',
        current_until: '2026-10-10',
      })
      renderRows(lastDay)
      expect(row('Fixture order').className).not.toContain('notice--not-current')
      cleanup()
      renderList(
        {
          empty: null,
          undated: 0,
          hikes: [{ stretch: STRETCH, onRoute: [lastDay], stateWide: [], fromClubs: [] }],
        },
        '2026-10-11',
      )
      expect(
        within(row('Fixture order')).getByText(
          'Last reported July 12, 2026. It may no longer apply.',
        ),
      ).toBeTruthy()
    })

    it('says "Its source said it would end October 3, 2026." for a notice past its own end date', () => {
      renderRows(
        notice({
          notice_id: 'gmc:ended',
          title: 'Fixture campground closed',
          starts_on: '2026-09-01',
          ends_on: '2026-10-03',
          current_until: '2026-10-03',
        }),
      )
      const greyed = row('Fixture campground closed')
      expect(
        within(greyed).getByText(
          'Its source said it would end October 3, 2026. It may no longer apply.',
        ),
      ).toBeTruthy()
      // Its own dates still print, as they did.
      expect(
        within(greyed).getByText('from September 1, 2026 until October 3, 2026'),
      ).toBeTruthy()
    })

    it('says "The time its source gave ran out" for a duration that ran out with no edit date', () => {
      renderRows(
        notice({
          notice_id: 'gmc:ran-out',
          title: 'Fixture bridge closure for two weeks',
          starts_on: '2026-09-01',
          updated_at: null,
          current_until: '2026-09-15',
        }),
      )
      expect(
        within(row('Fixture bridge closure for two weeks')).getByText(
          'The time its source gave ran out on September 15, 2026. It may no longer apply.',
        ),
      ).toBeTruthy()
    })

    it('says "Closed until Green Mountain Club says otherwise." under standing closed land, never greyed', () => {
      // The pipeline writes such a row no current_until and `standing` true.
      renderRows(
        notice({
          notice_id: 'gmc:standing',
          title: 'Fixture Preserve (standing)',
          obstructs_trail: true,
          updated_at: '2026-07-21T14:39:07Z',
          standing: true,
        }),
      )
      const standing = row('Fixture Preserve (standing)')
      expect(standing.className).not.toContain('notice--not-current')
      expect(
        within(standing).getByText('Closed until Green Mountain Club says otherwise.'),
      ).toBeTruthy()
      expect(screen.queryByText(/may no longer apply/)).toBeNull()
    })

    it('names a compiled order "Bureau of Land Management order, via Green Mountain Club"', () => {
      renderRows(
        notice({
          notice_id: 'gmc:compiled',
          title: 'Fixture compiled order',
          obstructs_trail: false,
          updated_at: null,
          current_until: '2027-01-06',
          issuer: 'Bureau of Land Management',
        }),
      )
      expect(
        within(row('Fixture compiled order')).getByText(
          'Bureau of Land Management order, via Green Mountain Club',
        ).className,
      ).toBe('closure-sheet__meta')
    })

    it('greys nothing in a file that carries no current_until at all', () => {
      // A copy of notices.json kept from before the field: no verdict.
      renderRows(notice({ notice_id: 'gmc:old-file', title: 'Fixture old file row' }))
      expect(row('Fixture old file row').className).not.toContain('notice--not-current')
      expect(screen.queryByText(/may no longer apply/)).toBeNull()
    })
  })

  // The maintainer's frame B (poll of 2026-10-11): "Shown now, marked with
  // its start. It closes the trail only from its start day." The frame's row:
  // the "Starts" tag, the title, the row's own "from" date, then the club.
  describe('a closure whose own start is still ahead (frame B)', () => {
    // Nine days after TODAY. Only a start, so notice_current_until.sql gives
    // it no day at all, which would grey it once it has begun.
    const UPCOMING = notice({
      notice_id: 'gmc:upcoming',
      title: 'Emergency closure, Fixture Creek Trail',
      obstructs_trail: true,
      starts_on: '2026-10-19',
      updated_at: null,
      current_until: null,
    })

    function renderOn(today: string, ...rows: TrailNotice[]) {
      renderList(
        {
          empty: null,
          undated: 0,
          hikes: [{ stretch: STRETCH, onRoute: rows, stateWide: [], fromClubs: [] }],
        },
        today,
      )
    }

    it('nine days out leads with "Starts Oct 19" in place of Closure, then its "from" date and its club, never greyed', () => {
      renderOn(TODAY, UPCOMING)
      const upcoming = row('Emergency closure, Fixture Creek Trail')
      expect(Array.from(upcoming.children).map((line) => line.textContent)).toEqual([
        'Starts Oct 19 Emergency closure, Fixture Creek Trail',
        'from October 19, 2026',
        'Green Mountain Club',
        'Read Green Mountain Club’s notice',
      ])
      expect(within(upcoming).getByText('Starts Oct 19').className).toBe(
        'planned-notices__tag planned-notices__tag--warn',
      )
      expect(within(upcoming).queryByText('Closure')).toBeNull()
      expect(upcoming.className).not.toContain('notice--not-current')
      expect(within(upcoming).queryByText(/may no longer apply/)).toBeNull()
    })

    it('still says "Starts Oct 19" on the day before its start, when it already closes the trail', () => {
      renderOn('2026-10-18', UPCOMING)
      const upcoming = row('Emergency closure, Fixture Creek Trail')
      expect(within(upcoming).getByText('Starts Oct 19')).toBeTruthy()
      expect(within(upcoming).queryByText('Closure')).toBeNull()
    })

    it('is tagged Closure with no "Starts" tag on its start day', () => {
      renderOn('2026-10-19', UPCOMING)
      const started = row('Emergency closure, Fixture Creek Trail')
      expect(within(started).getByText('Closure').className).toBe(
        'planned-notices__tag planned-notices__tag--warn',
      )
      expect(within(started).queryByText(/^Starts /)).toBeNull()
    })

    it('tags a notice that will not close the trail "Starts Oct 19" in the plain tint', () => {
      renderOn(
        TODAY,
        notice({
          notice_id: 'gmc:work',
          title: 'Fixture trail work',
          starts_on: '2026-10-19',
        }),
      )
      expect(within(row('Fixture trail work')).getByText('Starts Oct 19').className).toBe(
        'planned-notices__tag',
      )
    })

    it('shows the source’s own "Closure" category under an upcoming closure, whose tag no longer says it', () => {
      renderOn(TODAY, { ...UPCOMING, category: 'Closure' })
      expect(
        within(row('Emergency closure, Fixture Creek Trail')).getByText(
          'Listed as “Closure”',
        ),
      ).toBeTruthy()
    })

    it('leaves a closure with no start tagged Closure, as before', () => {
      renderOn(
        TODAY,
        notice({
          notice_id: 'gmc:no-start',
          title: 'Fixture bridge',
          obstructs_trail: true,
        }),
      )
      expect(within(row('Fixture bridge')).getByText('Closure')).toBeTruthy()
      expect(screen.queryByText(/^Starts /)).toBeNull()
    })
  })
})
