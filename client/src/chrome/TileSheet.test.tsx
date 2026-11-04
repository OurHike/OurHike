import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { TileSheet } from './TileSheet'
import { ATC_CHALLENGE } from '../lib/challenges.fixtures'
import { EMPTY_CHALLENGE_STATE, join, tag, tagsFor } from '../lib/challengeProgress'

afterEach(cleanup)

const TODAY = '2027-07-14'
const item = (id: string) => ATC_CHALLENGE.items.find((entry) => entry.id === id)!

function earned(ids: string[], how: 'gps' | 'hand' = 'hand') {
  let state = join(
    EMPTY_CHALLENGE_STATE,
    ATC_CHALLENGE.id,
    new Date('2027-06-01T12:00:00Z'),
  )
  for (const id of ids)
    state = tag(state, ATC_CHALLENGE, item(id), {
      at: new Date('2027-07-02T15:00:00Z'),
      how,
      place: how === 'hand' ? { kind: 'state', state: 'VA' } : undefined,
    }).state
  return tagsFor(state, ATC_CHALLENGE.id)
}

function sheet(overrides: Partial<Parameters<typeof TileSheet>[0]> = {}) {
  const props = {
    challenge: ATC_CHALLENGE,
    item: item('mcafee-knob'),
    number: 7,
    today: TODAY,
    tags: earned([]),
    earnable: true,
    onEarn: vi.fn(),
    onTakeBack: vi.fn(),
    onSetNote: vi.fn(),
    onClose: vi.fn(),
    ...overrides,
  }
  render(<TileSheet {...props} />)
  return props
}

describe('a tile, opened (#1963)', () => {
  it('leads with the glyph when there is no photo, names the item, its number and its place', () => {
    const { container } = { container: document.body }
    sheet()
    expect(container.querySelector('.blaze-tile')).not.toBeNull()
    expect(
      screen.getByRole('heading', { name: /Take the McAfee Knob shuttle/ }),
    ).toBeInTheDocument()
    expect(screen.getByText(/Experience · 7 of/)).toBeInTheDocument()
    expect(screen.getByText(/McAfee Knob Summit · mi 714\.9/)).toBeInTheDocument()
  })

  it('earns with one tap and never toggles: an earned tile offers Take it back instead', async () => {
    const props = sheet()
    await userEvent.click(screen.getByRole('button', { name: 'Earn some karma' }))
    expect(props.onEarn).toHaveBeenCalledOnce()
    cleanup()
    const done = sheet({ tags: earned(['mcafee-knob']) })
    expect(screen.queryByRole('button', { name: 'Earn some karma' })).toBeNull()
    expect(screen.getByRole('status')).toHaveTextContent('Earned · Jul 2')
    await userEvent.click(screen.getByRole('button', { name: 'Take it back' }))
    expect(done.onTakeBack).toHaveBeenCalledWith(undefined)
  })

  it('says where it happened, from the phone’s own record', () => {
    sheet({ item: item('white-blaze-photo'), tags: earned(['white-blaze-photo']) })
    expect(screen.getByText(/On the trail in Virginia/)).toBeInTheDocument()
  })

  it('says "Near you" only from what the phone knows: today’s walk, or the fix, never a guess', () => {
    sheet({ todayRanges: [{ startMile: 710, endMile: 716 }] })
    expect(screen.getByText('You passed it today.')).toBeInTheDocument()
    cleanup()
    sheet({ fixMile: 711.7 })
    expect(screen.getByText('3.2 mi along the trail from you.')).toBeInTheDocument()
    cleanup()
    sheet()
    expect(screen.queryByText(/Near you/)).toBeNull()
  })

  it('says how far "Near you" is in the hiker’s own units, not always in miles', () => {
    // McAfee Knob Summit is mile 714.92 in the fixture; a fix at 711.7 is
    // 3.22 miles back, 5.18 km. unitDisplay.test.ts caught this line spelling
    // "mi" itself, which a hiker on kilometres would have read as miles.
    sheet({ fixMile: 711.7, units: 'metric' })
    expect(screen.getByText('5.2 km along the trail from you.')).toBeInTheDocument()
  })

  it('tells an on-trail at-home item that earning it asks where, and a couch item nothing', () => {
    sheet({ item: item('white-blaze-photo') })
    expect(screen.getByText(/asks where it happened/)).toBeInTheDocument()
    cleanup()
    sheet({ item: item('trivia-quiz') })
    expect(screen.queryByText(/asks where it happened/)).toBeNull()
  })

  it('keeps the register line on the phone and gives it back on close', async () => {
    const props = sheet({ tags: earned(['mcafee-knob']) })
    await userEvent.type(
      screen.getByRole('textbox', { name: /register/ }),
      'cold morning',
    )
    await userEvent.click(screen.getByRole('button', { name: 'Close' }))
    expect(props.onSetNote).toHaveBeenLastCalledWith('cold morning')
    expect(props.onClose).toHaveBeenCalled()
  })

  it('never renders a sealed mystery title', () => {
    sheet({ item: item('mystery-1'), today: '2027-07-19', earnable: false })
    expect(document.body.textContent).not.toMatch(/Jefferson Rock/)
    expect(
      screen.getByRole('heading', { name: 'Sealed until Jul 20' }),
    ).toBeInTheDocument()
  })
})
