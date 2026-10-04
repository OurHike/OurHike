import { describe, expect, it, afterEach } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { HazardAreaSheet } from './HazardAreaSheet'
import type { TrailNotice } from '../lib/notices'
import type { Stewards } from '../lib/stewards'

// Decision 67's card (#1805): the kind of area, an Advisory, what to do, and
// that the trail stays open - the mock's option A - then whose layer it is.

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
  it('is an advisory that says the trail stays open, in OurHike’s words', () => {
    render(
      <HazardAreaSheet notice={HUNTING} stewards={STEWARDS} onClose={() => undefined} />,
    )
    const sheet = screen.getByRole('dialog', { name: 'Hunting allowed' })
    expect(sheet.textContent).toContain('Advisory')
    expect(sheet.textContent).toContain('The trail stays open.')
    expect(sheet.textContent).not.toMatch(/\bclosed\b/i)
  })

  it('names whose layer it is from the registry, and its facts', () => {
    render(
      <HazardAreaSheet notice={HUNTING} stewards={STEWARDS} onClose={() => undefined} />,
    )
    expect(screen.getByText('Ice Age Trail Alliance’s layer')).toBeTruthy()
    expect(
      screen.getByText('Fixture Preserve · Open for public hunting · Fixture County'),
    ).toBeTruthy()
  })

  it('says the layer gives no season rather than inventing one', () => {
    render(
      <HazardAreaSheet notice={HUNTING} stewards={STEWARDS} onClose={() => undefined} />,
    )
    expect(screen.getByText(/gives no season dates/)).toBeTruthy()
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
