// The sheet over a club closure tapped on the map (the maintainer's S6, poll
// of 2026-10-11: "same sheet as its list row"): the planned-hike list's own
// row for the notice, in the closing organization's voice.

import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, within } from '@testing-library/react'
import { ClubClosureSheet } from './ClubClosureSheet'
import { DATA_BUILT_URL } from '../lib/dataPages'
import { NoticeRow } from './PlannedNoticeList'
import type { TrailClosure } from '../lib/publishedConditions'
import { validTrailClosure } from '../lib/publishedNotices'
import type { Stewards } from '../lib/stewards'

/** One invented closure, as conditions/trail_closures.json carries it. */
function closure(fields: Record<string, unknown> = {}): TrailClosure {
  const read = validTrailClosure({
    notice_id: 'example_trail_club_alerts:creek-bridge',
    source_key: 'example_trail_club_alerts',
    club: 'example',
    provider: 'ETC',
    steward_kind: 'club',
    title: 'Bridge out at Example Creek (example)',
    category: 'Bridge out',
    starts_on: '2026-10-01',
    ends_on: null,
    current_until: '2026-12-30',
    updated_at: '2026-10-01T12:00:00Z',
    checked_at: '2026-10-11T09:00:00Z',
    first_seen_at: null,
    changed_at: null,
    carried_since: null,
    source_url: 'https://example.org/alerts/creek-bridge',
    review_state: 'unreviewed',
    obstructs_trail: true,
    hazard: null,
    locality: 'Example Creek',
    place: { kind: 'geometry', geometry: { type: 'Point', coordinates: [-100.2, 38.7] } },
    shape: 'point',
    ...fields,
  })
  if (read === null) throw new Error('the fixture row did not read')
  return read
}

const STEWARDS: Stewards = [
  {
    provider: 'ETC',
    name: 'Example Trail Club',
    trust: null,
    licence: null,
    attribution: null,
    terms: null,
    termsSource: null,
    layers: [],
    keys: ['example_trail_club_alerts'],
    support: null,
    store: null,
  },
]

const TODAY = '2026-10-11'

function sheet(notice: TrailClosure, generatedAt: Date | null = null) {
  render(
    <ClubClosureSheet
      notice={notice}
      stewards={STEWARDS}
      today={TODAY}
      generatedAt={generatedAt}
      onClose={vi.fn()}
    />,
  )
  return screen.getByRole('dialog', { name: 'Closure notice' })
}

afterEach(() => {
  cleanup()
})

describe('ClubClosureSheet', () => {
  it('shows exactly the row the planned-hike list shows for the same notice', () => {
    const notice = closure()
    const shown = within(sheet(notice)).getByRole('listitem')
    const { container } = render(
      <ul>
        <NoticeRow notice={notice} org="Example Trail Club" today={TODAY} />
      </ul>,
    )
    expect(shown.outerHTML).toBe(container.querySelector('li')?.outerHTML)
    expect(shown).toHaveTextContent('Bridge out at Example Creek (example)')
    expect(shown).toHaveTextContent('Example Trail Club — updated')
  })

  it('says the closure is the organization’s and not OurHike’s, and that OurHike works out no detour', () => {
    // A route the hiker builds still goes through a drawn club closure (the
    // maintainer's Q2, 2026-10-11), so the detour sentence is load-bearing.
    const note = within(sheet(closure())).getByRole('note')
    expect(note).toHaveTextContent(
      'This is Example Trail Club’s notice, not OurHike’s. OurHike has not checked the trail itself, and does not work out detours — follow their notice, or the signage on the ground.',
    )
  })

  it('greys a closure that may no longer apply and says so, where the map draws it at full strength', () => {
    const shown = within(sheet(closure({ current_until: '2026-10-01' }))).getByRole(
      'listitem',
    )
    expect(shown).toHaveClass('notice--not-current')
    expect(shown).toHaveTextContent(
      'Last reported October 1, 2026. It may no longer apply.',
    )
  })

  it('leads a closure that has not started with its start day', () => {
    const shown = within(
      sheet(closure({ starts_on: '2026-10-12', current_until: null })),
    ).getByRole('listitem')
    expect(within(shown).getByText('Starts Oct 12')).toBeInTheDocument()
    expect(shown).not.toHaveClass('notice--not-current')
  })

  it('says when OurHike gathered the file, and nothing about it when the date is unknown', () => {
    expect(
      within(sheet(closure(), new Date('2026-10-11T09:00:00Z'))).getByText(
        /^Gathered by OurHike on /,
      ),
    ).toBeInTheDocument()
    cleanup()
    expect(within(sheet(closure())).queryByText(/Gathered by OurHike/)).toBeNull()
  })

  it('says the closure came from the organization’s own published notices, and links how OurHike gathers and checks it (Q24 of #1805)', () => {
    const shown = sheet(closure(), new Date('2026-10-11T09:00:00Z'))
    const age = within(shown).getByText(/^Gathered by OurHike on /)
    expect(age).toHaveTextContent(
      /^Gathered by OurHike on October 11, 2026 from .+’s own published notices\. How OurHike gathers and checks this ›$/,
    )
    const link = within(age).getByRole('link', {
      name: 'How OurHike gathers and checks this ›',
    })
    expect(link).toHaveAttribute('href', DATA_BUILT_URL)
    expect(link).toHaveAttribute('target', '_blank')
  })
})
