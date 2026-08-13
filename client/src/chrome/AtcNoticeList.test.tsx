import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AtcNoticeList } from './AtcNoticeList'
import { atcBandId, type AtcUpdate } from '../lib/atcUpdates'

// The list exists because of a gap, and the gap is what this file holds.
//
// Before it, an ATC notice reached a hiker through the banner (at most two,
// and only ahead of them) or through a tap on the map (only if it was drawn).
// An update that obstructs nothing, spans a range rather than a point, and
// sits behind the hiker reached them through neither. Every case below is a
// way of proving that no notice OurHike holds is unreadable.

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

const ALL = [SHELTER, HELENE, FOOTBRIDGE]
const DRAWN = new Set([atcBandId(FOOTBRIDGE), atcBandId(SHELTER)])
const REVIEWED = new Date('2026-08-12T00:00:00Z')

function renderList(overrides: Partial<Parameters<typeof AtcNoticeList>[0]> = {}) {
  return render(
    <AtcNoticeList
      updates={ALL}
      drawnIds={DRAWN}
      reviewedAt={REVIEWED}
      onClose={vi.fn()}
      {...overrides}
    />,
  )
}

function entries(): HTMLElement[] {
  return screen.getAllByRole('listitem')
}

afterEach(cleanup)

describe('every notice, including the ones with no other surface', () => {
  it('lists all of them, not only the ones the map draws', () => {
    renderList()

    expect(entries()).toHaveLength(3)
  })

  it('shows the region-wide advisory the map refuses to draw', () => {
    // Helene is 398 miles. `MAX_BAND_MILES` keeps it off the canvas for a good
    // reason - a fifth of the trail painted closed buries the nine-mile
    // closure a hiker actually has to walk around - and that reason was never
    // an argument that they should not be able to read it.
    renderList()

    expect(screen.getByText('Hurricane Helene Storm Damage')).toBeInTheDocument()
  })

  it('says which notices have no mark on the map to look for', () => {
    // A hiker who read this list, walked the miles and saw nothing red would
    // otherwise be entitled to conclude the notice had been lifted.
    renderList()

    const helene = entries().find((entry) =>
      within(entry).queryByText('Hurricane Helene Storm Damage'),
    )
    expect(helene).toBeDefined()
    expect(helene).toHaveTextContent(/Not drawn on the map/)
  })

  it('says nothing of the kind about the ones it does draw', () => {
    renderList()

    const footbridge = entries().find((entry) =>
      within(entry).queryByText('Harpers Ferry: Footbridge Closure'),
    )
    expect(footbridge).toBeDefined()
    expect(footbridge).not.toHaveTextContent(/Not drawn on the map/)
  })

  it('reads the drawn set it is given rather than working one out', () => {
    // The same notice, same props, minus the map. `trailSlice` can refuse a
    // mile that falls outside this build's centerline, so "would this be
    // drawn?" is not answerable from an AtcUpdate - and a list that guessed
    // would send someone looking for a dot that is not there.
    renderList({ drawnIds: new Set<string>() })

    for (const entry of entries()) {
      expect(entry).toHaveTextContent(/Not drawn on the map/)
    }
  })
})

describe('in an order that is a fact rather than a judgement', () => {
  it('runs NOBO, by mile', () => {
    // Not by date, which would put a notice edited yesterday above one two
    // miles ahead, and not by severity, which this app refuses to rank ATC's
    // categories by (lib/atcUpdateStyle.ts).
    renderList()

    expect(entries().map((entry) => entry.textContent)).toEqual([
      expect.stringContaining('Hurricane Helene Storm Damage'),
      expect.stringContaining('Harpers Ferry: Footbridge Closure'),
      expect.stringContaining('Connecticut: Limestone Spring Shelter Closed'),
    ])
  })
})

describe('each entry carries everything the artifact holds', () => {
  it('shows ATC’s own category, not a closure reason', () => {
    // `ClosureReason` would render a Detour as "Closed", a claim they did not
    // make - and the footbridge is exactly that case.
    renderList()

    expect(screen.getByText('Detour')).toBeInTheDocument()
    expect(screen.getByText('Alert')).toBeInTheDocument()
    expect(screen.getByText('Closure')).toBeInTheDocument()
  })

  it('shows their headline, their states and their miles', () => {
    renderList()

    expect(screen.getByText('Harpers Ferry: Footbridge Closure')).toBeInTheDocument()
    expect(screen.getByText(/MD, WV · mi 1,026\.7/)).toBeInTheDocument()
    expect(screen.getByText(/NC, TN, VA · mi 239\.4 – 637\.8/)).toBeInTheDocument()
  })

  it('shows the date ATC last edited each one', () => {
    renderList()

    expect(screen.getByText(/updated July 31, 2026/)).toBeInTheDocument()
    expect(screen.getByText(/updated May 4, 2026/)).toBeInTheDocument()
  })

  it('answers the passability question in both directions', () => {
    // `obstructs_trail` is the reviewer's judgement and the one field that is
    // not a fact about ATC's page. "The trail is passable" is something a
    // hiker wants to have been told, not the absence of a warning.
    renderList()

    expect(
      screen.getByText(/says this stops a hiker walking through/),
    ).toBeInTheDocument()
    expect(screen.getAllByText(/did not report the trail itself blocked/)).toHaveLength(2)
  })

  it('links every one of them back to ATC’s page', () => {
    // The link is the whole of the detail, because the artifact carries facts
    // and not ATC's prose.
    renderList()

    const links = screen.getAllByRole('link')

    expect(links).toHaveLength(3)
    expect(links.map((link) => link.getAttribute('href'))).toContain(
      FOOTBRIDGE.source_url,
    )
  })

  it('refuses to render a link that is not http(s)', () => {
    // The second line, not the only one - pipeline/lib/atc_updates.py refuses
    // one on the way in as well. A check that only exists at the far end is
    // one a future second producer walks straight past.
    renderList({
      updates: [{ ...FOOTBRIDGE, source_url: 'javascript:alert(1)' }],
    })

    expect(screen.queryByRole('link')).not.toBeInTheDocument()
    // And the notice itself is still shown. Dropping a safety notice because
    // its URL is malformed would be the worse failure by a long way.
    expect(screen.getByText('Harpers Ferry: Footbridge Closure')).toBeInTheDocument()
  })
})

describe('and is honest about what it is not', () => {
  it('says up front that OurHike does not carry ATC’s notice in full', () => {
    // A list this complete-looking reads as the notices themselves unless it
    // says otherwise, and it has to say so before the list rather than under
    // it - a reader who has been misled is not repaired by a footnote.
    renderList()

    expect(screen.getByRole('note')).toHaveTextContent(/never their notice in full/)
  })

  it('names the ATC as the author, in the dialog’s own label', () => {
    renderList()

    expect(
      screen.getByRole('dialog', {
        name: /Appalachian Trail Conservancy/,
      }),
    ).toBeInTheDocument()
  })

  it('says when a person last checked the copy against their page', () => {
    renderList()

    expect(
      screen.getByText(/last checked ATC’s updates on August 12, 2026/),
    ).toBeInTheDocument()
  })

  it('says it cannot tell, rather than inventing a date', () => {
    renderList({ reviewedAt: null })

    expect(screen.getByText(/cannot tell when it last checked/)).toBeInTheDocument()
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
