import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { NoticeList } from './NoticeList'
import type { AtcUpdate } from '../lib/atcUpdates'
import {
  ATC_SOURCE_KEY,
  atcUpdateAsNotice,
  noticeBandId,
  type TrailNotice,
} from '../lib/notices'
import type { Stewards } from '../lib/stewards'

// The list exists because of a gap, and the gap is what this file holds.
//
// Before it, a notice reached a hiker through the banner (at most two, and
// only ahead of them) or through a tap on the map (only if it was drawn). An
// update that obstructs nothing, spans a range rather than a point, and sits
// behind the hiker reached them through neither. Every case below is a way of
// proving that no notice OurHike holds is unreadable.
//
// #1083 added a second failure to guard, and it is the more dangerous of the
// two: the list holding two organizations' notices and rendering both in the
// first organization's voice. features/ORG_NOTICES.md §6 - "a string in a
// component is how the app ends up telling a hiker that NYNJTC's closure is
// ATC's word."

const HELENE: AtcUpdate = {
  atc_id: 'hurricane-helene-storm-damage',
  title: 'Hurricane Helene Storm Damage',
  category: 'Alert',
  states: ['NC', 'TN', 'VA'],
  // 398 miles - over `MAX_BAND_MILES`, so the map draws nothing for it.
  start_mile_marker: 239.4,
  end_mile_marker: 637.8,
  obstructs_trail: false,
  updated_at: '2026-06-02T00:00:00Z',
  source_url: 'https://appalachiantrail.org/trail-updates/helene/',
}

const FOOTBRIDGE: AtcUpdate = {
  atc_id: 'harpers-ferry-footbridge-closure',
  title: 'Harpers Ferry: Footbridge Closure',
  category: 'Detour',
  states: ['MD', 'WV'],
  start_mile_marker: 1026.7,
  end_mile_marker: 1026.7,
  obstructs_trail: true,
  updated_at: '2026-07-31T19:54:12Z',
  source_url:
    'https://appalachiantrail.org/trail-updates/harpers-ferry-footbridge-closure/',
}

const SHELTER: AtcUpdate = {
  atc_id: 'limestone-spring-shelter-closed',
  title: 'Connecticut: Limestone Spring Shelter Closed',
  category: 'Closure',
  states: ['CT'],
  start_mile_marker: 1503.6,
  end_mile_marker: 1503.6,
  obstructs_trail: false,
  updated_at: '2026-05-04T00:00:00Z',
  source_url: 'https://appalachiantrail.org/trail-updates/limestone-spring/',
}

/** Two real rows from `conditions/nynjtc_alerts.json`, read live 2026-08-27.
 *  Both `unplaced`, both `unreviewed`, both with a null category - which is
 *  NYNJTC's true state and not a fixture convenience: they file every alert
 *  under one category and publish no per-alert vocabulary. */
const HARRIMAN: TrailNotice = {
  notice_id: 'nynjtc_trail_alerts:a-t-detour-at-harriman-state-park',
  source_key: 'nynjtc_trail_alerts',
  title: 'A.T. Detour at Harriman State Park',
  category: null,
  locality: 'Harriman-Bear Mountain',
  place: { kind: 'unplaced' },
  obstructs_trail: false,
  updated_at: '2026-06-16T14:37:46Z',
  source_url: 'https://www.nynjtc.org/trail-alerts/a-t-detour-at-harriman-state-park/',
  review_state: 'unreviewed',
}

const BREAKNECK: TrailNotice = {
  notice_id: 'nynjtc_trail_alerts:breakneck-ridge-and-wilkinson-memorial-t',
  source_key: 'nynjtc_trail_alerts',
  title: 'Reminder: Breakneck Ridge and Wilkinson Memorial Trailhead Closure',
  category: null,
  locality: 'Hudson Highlands State Park Preserve',
  place: { kind: 'unplaced' },
  obstructs_trail: false,
  updated_at: '2026-04-02T00:00:00Z',
  source_url: 'https://www.nynjtc.org/trail-alerts/breakneck-ridge/',
  review_state: 'unreviewed',
}

const ATC_NOTICES = [SHELTER, HELENE, FOOTBRIDGE].map(atcUpdateAsNotice)
const ALL = [...ATC_NOTICES, HARRIMAN, BREAKNECK]

const DRAWN = new Set([
  noticeBandId(atcUpdateAsNotice(FOOTBRIDGE)),
  noticeBandId(atcUpdateAsNotice(SHELTER)),
])
const REVIEWED = new Date('2026-08-12T00:00:00Z')
const NOW = new Date('2026-08-27T12:00:00Z')

/** As `pipeline/export_sources.py` writes it, checked against the real
 *  registry 2026-08-27. Both organizations, because the whole point is that
 *  the component looks a name up rather than knowing one. */
const STEWARDS: Stewards = [
  {
    provider: 'ATC',
    name: 'Appalachian Trail Conservancy',
    trust: null,
    licence: '© ATC, used with permission',
    attribution: null,
    layers: ['ATC Trail Updates'],
    keys: [ATC_SOURCE_KEY],
  },
  {
    provider: 'NYNJTC',
    name: 'New York-New Jersey Trail Conference',
    trust: 'authoritative',
    licence: null,
    attribution: 'New York-New Jersey Trail Conference',
    layers: ['NYNJTC Trail Alerts'],
    keys: ['nynjtc_trail_alerts'],
  },
]

/** Only ATC reviews anything. NYNJTC's key is ABSENT rather than null, which
 *  is the third state the component renders differently - nobody has ever
 *  checked their page, and `export_nynjtc_alerts.py` refuses to carry a date
 *  saying otherwise. */
const REVIEWED_BY_SOURCE = new Map<string, Date | null>([[ATC_SOURCE_KEY, REVIEWED]])

function renderList(overrides: Partial<Parameters<typeof NoticeList>[0]> = {}) {
  return render(
    <NoticeList
      notices={ALL}
      drawnIds={DRAWN}
      reviewedAt={REVIEWED_BY_SOURCE}
      stewards={STEWARDS}
      extent={null}
      now={NOW}
      onClose={vi.fn()}
      {...overrides}
    />,
  )
}

function entries(): HTMLElement[] {
  return screen.getAllByRole('listitem')
}

function entryFor(title: string): HTMLElement {
  const found = entries().find((entry) => within(entry).queryByText(title))
  expect(found).toBeDefined()
  return found as HTMLElement
}

afterEach(cleanup)

describe('every notice, including the ones with no other surface', () => {
  it('lists all of them, from every organization, not only the ones the map draws', () => {
    renderList()

    expect(entries()).toHaveLength(5)
  })

  it('shows the region-wide advisory the map refuses to draw', () => {
    // Helene is 398 miles. `MAX_BAND_MILES` keeps it off the canvas for a good
    // reason - a fifth of the trail painted closed buries the nine-mile
    // closure a hiker actually has to walk around - and that reason was never
    // an argument that they should not be able to read it.
    renderList()

    expect(screen.getByText('Hurricane Helene Storm Damage')).toBeInTheDocument()
  })

  it('shows the notices nobody can place at all', () => {
    // The failure #1083 is about. These were published, fetched, parsed and
    // then reached no screen, because every notice surface required a mile.
    renderList()

    expect(screen.getByText('A.T. Detour at Harriman State Park')).toBeInTheDocument()
    expect(
      screen.getByText(
        'Reminder: Breakneck Ridge and Wilkinson Memorial Trailhead Closure',
      ),
    ).toBeInTheDocument()
  })

  it('says which placed notices have no mark on the map to look for', () => {
    // A hiker who read this list, walked the miles and saw nothing red would
    // otherwise be entitled to conclude the notice had been lifted.
    renderList()

    expect(entryFor('Hurricane Helene Storm Damage')).toHaveTextContent(
      /Not drawn on the map/,
    )
  })

  it('says nothing of the kind about the ones it does draw', () => {
    renderList()

    expect(entryFor('Harpers Ferry: Footbridge Closure')).not.toHaveTextContent(
      /Not drawn on the map/,
    )
  })

  it('says so on every unplaced row, because none of them is on the map', () => {
    renderList()

    expect(entryFor('A.T. Detour at Harriman State Park')).toHaveTextContent(
      /Not drawn on the map/,
    )
  })

  it('reads the drawn set it is given rather than working one out', () => {
    // The same notices, same props, minus the map. `trailSlice` can refuse a
    // mile that falls outside this build's centerline, so "would this be
    // drawn?" is not answerable from the row - and a list that guessed would
    // send someone looking for a dot that is not there.
    renderList({ notices: ATC_NOTICES, drawnIds: new Set<string>() })

    for (const entry of entries()) {
      expect(entry).toHaveTextContent(/Not drawn on the map/)
    }
  })
})

describe('in one flat list, newest first', () => {
  it('orders every organization-s notices together by how recently they changed', () => {
    // A maintainer's call (2026-08-27). lib/notices.ts carries the argument it
    // overrules - this file's own `byMile` comment.
    renderList()

    expect(entries().map((entry) => entry.textContent)).toEqual([
      expect.stringContaining('Harpers Ferry: Footbridge Closure'),
      expect.stringContaining('A.T. Detour at Harriman State Park'),
      expect.stringContaining('Hurricane Helene Storm Damage'),
      expect.stringContaining('Connecticut: Limestone Spring Shelter Closed'),
      expect.stringContaining('Breakneck Ridge'),
    ])
  })

  it('draws no section headings, because there are no sections', () => {
    renderList()

    expect(screen.queryByText(/On the A\.T\./)).not.toBeInTheDocument()
  })
})

describe('scoped to the stretch on screen', () => {
  // Connecticut. `SHELTER` is at mile 1,503.6 and inside it; `HELENE`
  // (239.4-637.8) and `FOOTBRIDGE` (1,026.7) are not.
  const CONNECTICUT = { startMile: 1450, endMile: 1550 }

  it('shows the notices on the stretch the hiker is looking at', () => {
    renderList({ extent: CONNECTICUT, drawnIds: new Set<string>() })

    expect(
      screen.getByText('Connecticut: Limestone Spring Shelter Closed'),
    ).toBeInTheDocument()
    expect(screen.queryByText('Hurricane Helene Storm Damage')).not.toBeInTheDocument()
  })

  it('keeps every unplaceable notice however the map is pointed', () => {
    // Filtering something on a criterion it cannot answer excludes it always.
    renderList({ extent: CONNECTICUT, drawnIds: new Set<string>() })

    expect(screen.getByText('A.T. Detour at Harriman State Park')).toBeInTheDocument()
  })

  it('never drops one silently - it says how many and offers them', () => {
    renderList({ extent: CONNECTICUT, drawnIds: new Set<string>() })

    expect(
      screen.getByRole('button', { name: /Show 2 more, elsewhere on the trail/ }),
    ).toBeInTheDocument()
  })

  it('shows them all when a hiker asks', () => {
    renderList({ extent: CONNECTICUT, drawnIds: new Set<string>() })

    return userEvent
      .click(screen.getByRole('button', { name: /Show 2 more/ }))
      .then(() => {
        expect(entries()).toHaveLength(5)
        expect(screen.getByText('Hurricane Helene Storm Damage')).toBeInTheDocument()
      })
  })

  it('keeps a notice the map is drawing even when it is off the stretch', () => {
    // If a hiker can see the mark, the list has to be able to explain it.
    renderList({ extent: CONNECTICUT })

    expect(screen.getByText('Harpers Ferry: Footbridge Closure')).toBeInTheDocument()
  })

  it('says the stretch is clear rather than that OurHike holds nothing', () => {
    // Two different claims, and only one of them is true here.
    renderList({
      notices: [atcUpdateAsNotice(HELENE)],
      extent: CONNECTICUT,
      drawnIds: new Set<string>(),
    })

    expect(screen.getByText(/No trail notices on the stretch/)).toBeInTheDocument()
  })
})

describe('whose claim each row is', () => {
  it('names each organization on its own rows, from the registry', () => {
    renderList()

    expect(entryFor('Harpers Ferry: Footbridge Closure')).toHaveTextContent(
      /Appalachian Trail Conservancy/,
    )
    expect(entryFor('A.T. Detour at Harriman State Park')).toHaveTextContent(
      /New York-New Jersey Trail Conference/,
    )
  })

  it('never puts one organization-s name on another-s notice', () => {
    // The failure this whole change exists to prevent, asserted directly.
    renderList()

    expect(entryFor('A.T. Detour at Harriman State Park')).not.toHaveTextContent(
      /Appalachian Trail/,
    )
  })

  it('links each row back to its own organization-s page', () => {
    renderList()

    expect(
      within(entryFor('A.T. Detour at Harriman State Park')).getByRole('link'),
    ).toHaveTextContent(/New York-New Jersey Trail Conference’s notice/)
  })

  it('prints the raw registry key when no steward claims it, rather than guessing', () => {
    // Real when a phone holds a notice artifact and a stewards artifact from
    // different releases. Ugly and true beats a prettified guess.
    renderList({ stewards: [] })

    expect(entryFor('A.T. Detour at Harriman State Park')).toHaveTextContent(
      /nynjtc_trail_alerts/,
    )
  })

  it('still shows every notice when the registry is empty', () => {
    // Dropping a safety notice because this build cannot name its publisher
    // would be the worse failure by a long way.
    renderList({ stewards: [] })

    expect(entries()).toHaveLength(5)
  })
})

describe('each entry carries everything the artifact holds', () => {
  it('shows the organization-s own category, not a closure reason', () => {
    // `ClosureReason` would render a Detour as "Closed", a claim they did not
    // make - and the footbridge is exactly that case.
    renderList()

    expect(screen.getByText('Detour')).toBeInTheDocument()
    expect(screen.getByText('Alert')).toBeInTheDocument()
    expect(screen.getByText('Closure')).toBeInTheDocument()
  })

  it('prints no category at all where the organization publishes none', () => {
    // NYNJTC's is null on every row. Borrowing a word from ATC's list would be
    // this app inventing a classification NYNJTC did not make.
    renderList()

    const harriman = entryFor('A.T. Detour at Harriman State Park')
    expect(harriman.querySelector('.atc-notices__category')).toBeNull()
  })

  it('shows their headline, their locality and their miles', () => {
    renderList()

    expect(screen.getByText('Harpers Ferry: Footbridge Closure')).toBeInTheDocument()
    expect(screen.getByText(/MD, WV · mi 1,026\.7/)).toBeInTheDocument()
    expect(screen.getByText(/NC, TN, VA · mi 239\.4 – 637\.8/)).toBeInTheDocument()
  })

  it('shows a locality with no mile where that is all the organization gave', () => {
    renderList()

    expect(screen.getByText('Harriman-Bear Mountain')).toBeInTheDocument()
  })

  it('shows the date each organization last edited each one', () => {
    renderList()

    expect(screen.getByText(/updated July 31, 2026/)).toBeInTheDocument()
    expect(screen.getByText(/updated June 16, 2026/)).toBeInTheDocument()
  })

  it('answers the passability question in both directions', () => {
    // `obstructs_trail` is the reviewer's judgement and the one field that is
    // not a fact about the organization's page. "The trail is passable" is
    // something a hiker wants to have been told, not the absence of a warning.
    renderList({ notices: ATC_NOTICES })

    expect(
      screen.getByText(/says this stops a hiker walking through/),
    ).toBeInTheDocument()
    expect(screen.getAllByText(/didn’t report the trail itself blocked/)).toHaveLength(2)
  })

  it('says nobody has checked an unreviewed row, rather than reading its false boolean', () => {
    // Every NYNJTC row ships `obstructs_trail: false` because the pipeline
    // forces it - an unread notice may never draw a barrier. A UI reading that
    // naively would tell a hiker "NYNJTC didn't report the trail blocked
    // here", which is a claim nobody checked.
    renderList()

    expect(entryFor('A.T. Detour at Harriman State Park')).toHaveTextContent(
      /hasn’t checked this one yet/,
    )
  })

  it('links every one of them back to its publisher-s page', () => {
    // The link is the whole of the detail, because the artifacts carry facts
    // and not anybody's prose.
    renderList()

    const links = screen.getAllByRole('link')

    expect(links).toHaveLength(5)
    expect(links.map((link) => link.getAttribute('href'))).toContain(
      FOOTBRIDGE.source_url,
    )
    expect(links.map((link) => link.getAttribute('href'))).toContain(HARRIMAN.source_url)
  })

  it('refuses to render a link that is not http(s)', () => {
    // The second line, not the only one - pipeline/lib/atc_updates.py refuses
    // one on the way in as well. A check that only exists at the far end is
    // one a future second producer walks straight past.
    renderList({
      notices: [{ ...HARRIMAN, source_url: 'javascript:alert(1)' }],
    })

    expect(screen.queryByRole('link')).not.toBeInTheDocument()
    // And the notice itself is still shown. Dropping a safety notice because
    // its URL is malformed would be the worse failure by a long way.
    expect(screen.getByText('A.T. Detour at Harriman State Park')).toBeInTheDocument()
  })
})

describe('and is honest about what it is not', () => {
  it('says up front that OurHike does not carry any of them in full', () => {
    // A list this complete-looking reads as the notices themselves unless it
    // says otherwise, and it has to say so before the list rather than under
    // it - a reader who has been misled is not repaired by a footnote.
    renderList()

    expect(screen.getByRole('note')).toHaveTextContent(/never their notice in full/)
  })

  it('names the one publisher in the heading when there is only one', () => {
    // features/ATC_TRAIL_UPDATES.md's "an ATC update must be visibly ATC's",
    // still holding in the case where it can rather than generalized away.
    renderList({ notices: ATC_NOTICES })

    expect(
      screen.getByRole('heading', { name: /3 Appalachian Trail Conservancy notices/ }),
    ).toBeInTheDocument()
  })

  it('refuses to name one publisher in the heading when it holds two', () => {
    renderList()

    expect(screen.getByRole('heading', { name: '5 trail notices' })).toBeInTheDocument()
  })

  it('says when a person last checked each copy against its own page', () => {
    renderList()

    expect(
      screen.getByText(
        /last checked Appalachian Trail Conservancy’s notices on August 12, 2026/,
      ),
    ).toBeInTheDocument()
  })

  it('says nobody has checked an organization nobody reviews', () => {
    // The distinction an absent key carries. NYNJTC's artifact has no
    // `reviewed_at` at all - "we cannot tell when" would be a softer lie than
    // the truth, which is that nobody has ever looked.
    renderList()

    expect(
      screen.getByText(
        /Nobody at OurHike has checked New York-New Jersey Trail Conference’s notices/,
      ),
    ).toBeInTheDocument()
  })

  it('says it cannot tell, rather than inventing a date', () => {
    renderList({
      notices: ATC_NOTICES,
      reviewedAt: new Map<string, Date | null>([[ATC_SOURCE_KEY, null]]),
    })

    expect(screen.getByText(/can’t tell when it last checked/)).toBeInTheDocument()
  })
})

describe('closing it', () => {
  it('reports the close, and does not close itself', () => {
    // The shell owns whether this is open, like every other sheet on the map
    // screen. A component that hid itself would leave the button that opened
    // it lying about what is on screen.
    const onClose = vi.fn()
    renderList({ onClose })

    return userEvent.click(screen.getByRole('button', { name: 'Close' })).then(() => {
      expect(onClose).toHaveBeenCalledTimes(1)
      expect(screen.getByRole('dialog')).toBeInTheDocument()
    })
  })
})
