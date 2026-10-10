import { describe, expect, it, afterEach } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { HazardAreaSheet } from './HazardAreaSheet'
import type { TrailNotice } from '../lib/notices'
import type { Stewards } from '../lib/stewards'

// Decision 67's card (#1805): the kind of area, an Advisory, what to do, and
// that the trail stays open - the mock's option A - then who published it.

const STEWARDS: Stewards = [
  {
    provider: 'IATA',
    name: 'Ice Age Trail Alliance',
    trust: null,
    licence: null,
    attribution: null,
    terms: null,
    termsSource: null,
    layers: [],
    keys: ['iata_lands_hunting_regs'],
    support: null,
    store: null,
  },
]

const HUNTING: TrailNotice = {
  notice_id: 'iata_lands_hunting_regs:1',
  source_key: 'iata_lands_hunting_regs',
  title: 'Fixture Preserve',
  category: 'Open for public hunting',
  locality: 'Fixture County',
  place: { kind: 'geometry', geometry: { type: 'Point', coordinates: [-89.5, 44.5] } },
  obstructs_trail: false,
  updated_at: null,
  source_url: null,
  review_state: 'unreviewed',
  hazard: 'hunting',
}

afterEach(cleanup)

describe('HazardAreaSheet', () => {
  it('is an advisory that says the trails through it stay open, in OurHike’s words', () => {
    render(
      <HazardAreaSheet notice={HUNTING} stewards={STEWARDS} onClose={() => undefined} />,
    )
    const sheet = screen.getByRole('dialog', { name: 'Hunting allowed' })
    expect(sheet.textContent).toContain('Advisory')
    expect(sheet.textContent).toContain('Trails through it stay open.')
    expect(sheet.textContent).not.toMatch(/\bclosed\b/i)
  })

  // Decision 99 (poll, 2026-10-07): the hiker tapped the area, not a stretch,
  // so its card talks about the area; "This stretch…" is the tapped line's.
  it('talks about the area the hiker tapped, never a stretch of trail', () => {
    render(
      <HazardAreaSheet notice={HUNTING} stewards={STEWARDS} onClose={() => undefined} />,
    )
    const sheet = screen.getByRole('dialog', { name: 'Hunting allowed' })
    expect(sheet.textContent).toContain('Hunting is allowed in this area.')
    expect(sheet.textContent).not.toMatch(/this stretch/i)
  })

  it('says "From Ice Age Trail Alliance", the registry’s name, and the area’s facts', () => {
    render(
      <HazardAreaSheet notice={HUNTING} stewards={STEWARDS} onClose={() => undefined} />,
    )
    expect(screen.getByText('From Ice Age Trail Alliance')).toBeTruthy()
    expect(
      screen.getByText('Fixture Preserve · Open for public hunting · Fixture County'),
    ).toBeTruthy()
  })

  it('says the publisher gives no season dates rather than inventing one', () => {
    render(
      <HazardAreaSheet notice={HUNTING} stewards={STEWARDS} onClose={() => undefined} />,
    )
    expect(
      screen.getByText(
        'Ice Age Trail Alliance gives no season dates. Check hunting seasons before you go.',
      ),
    ).toBeTruthy()
  })

  // The note under the card keeps both of its caveats: the advice is
  // OurHike's, and nobody from OurHike has been to the area.
  it('says who drew the area, that the advice is OurHike’s and that nobody checked the ground', () => {
    render(
      <HazardAreaSheet notice={HUNTING} stewards={STEWARDS} onClose={() => undefined} />,
    )
    expect(screen.getByRole('note').textContent).toBe(
      'Ice Age Trail Alliance drew this area; the advice is OurHike’s. OurHike hasn’t checked it on the ground.',
    )
  })

  it('never calls the publisher’s data a "layer", the GIS word a hiker does not use', () => {
    render(
      <HazardAreaSheet
        notice={{ ...HUNTING, starts_on: '2026-11-15', ends_on: '2026-12-13' }}
        stewards={STEWARDS}
        onClose={() => undefined}
      />,
    )
    const sheet = screen.getByRole('dialog', { name: 'Hunting allowed' })
    expect(sheet.textContent).toContain(
      'From November 15, 2026 to December 13, 2026, according to Ice Age Trail Alliance.',
    )
    expect(sheet.textContent).not.toMatch(/\blayer\b/i)
  })

  it('draws nothing for a notice that is not a hazard area', () => {
    const { container } = render(
      <HazardAreaSheet
        notice={{ ...HUNTING, hazard: null }}
        stewards={STEWARDS}
        onClose={() => undefined}
      />,
    )
    expect(container.textContent).toBe('')
  })
})
