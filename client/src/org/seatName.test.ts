import { describe, expect, it } from 'vitest'

import { seatName, type OrgAdmin } from './orgApi'

const seat = (overrides: Partial<OrgAdmin>): OrgAdmin => ({
  id: 'seat-1',
  person_id: 'person-1',
  title: 'Secretary',
  is_codeowner: false,
  invited_at: '2026-10-01T00:00:00Z',
  approved_at: null,
  declined_at: null,
  decline_reason: null,
  ...overrides,
})

describe('seatName', () => {
  it('names the holder from the roster when this viewer is told whose seat it is', () => {
    expect(seatName(seat({}), { 'person-1': 'Maria Lopez' })).toBe('Maria Lopez')
  })

  it('falls back to the account id when the roster has no name for it', () => {
    expect(seatName(seat({}), {})).toBe('person-1')
  })

  it("says the seat's title when the server withheld whose seat it is (#1914)", () => {
    expect(seatName(seat({ person_id: null }), { 'person-1': 'Maria Lopez' })).toBe(
      'Secretary',
    )
  })

  it('says "An admin" when a withheld seat has no title either', () => {
    expect(seatName(seat({ person_id: null, title: null }), {})).toBe('An admin')
  })
})
