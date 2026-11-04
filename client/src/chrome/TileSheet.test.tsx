import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { TileSheet } from './TileSheet'
import { ATC_CHALLENGE } from '../lib/challenges.fixtures'
import { EMPTY_CHALLENGE_STATE, join, tag, tagsFor } from '../lib/challengeProgress'

afterEach(cleanup)

const TODAY = '2027-07-14'
const item = (id: string) => ATC_CHALLENGE.items.find((entry) => entry.id === id)!

function earned(ids: string[], how: 'gps' | 'hand' = 'hand', poi?: string) {
  let state = join(
    EMPTY_CHALLENGE_STATE,
    ATC_CHALLENGE.id,
    new Date('2027-06-01T12:00:00Z'),
  )
  for (const id of ids)
    state = tag(state, ATC_CHALLENGE, item(id), {
      at: new Date('2027-07-02T15:00:00Z'),
      how,
      poi,
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

  it('offers no Earn button on a sealed mystery item, whatever the caller says', () => {
    // ChallengeDetail decides `earnable`; this holds that the tile itself
    // never offers what the page refused (review of #2015).
    sheet({ item: item('mystery-1'), today: '2027-07-19', earnable: false })
    expect(screen.queryByRole('button', { name: /Earn/ })).toBeNull()
  })
})

describe('what the review of #2015 found in the tile sheet', () => {
  it.each(['summit-4000', 'trail-crew'])(
    'offers no Take it back on %s, which earns itself and would only be earned again',
    (id) => {
      sheet({ item: item(id), tags: earned([id], 'gps') })
      expect(screen.getByRole('status')).toHaveTextContent('Earned · Jul 2')
      expect(screen.queryByRole('button', { name: 'Take it back' })).toBeNull()
    },
  )

  it('still offers Take it back on a place a walk earned, which nothing earns again unasked', () => {
    sheet({ tags: earned(['mcafee-knob'], 'gps') })
    expect(screen.getByRole('button', { name: 'Take it back' })).toBeInTheDocument()
  })

  it('says nothing "Near you" about a place off the trail, whose mile is only where the trail passes nearest', () => {
    sheet({
      item: item('monson-visitor-center'),
      todayRanges: [{ startMile: 2070, endMile: 2090 }],
      fixMile: 2080,
    })
    expect(screen.queryByText(/Near you/)).toBeNull()
    expect(screen.queryByText(/passed it today|along the trail from you/)).toBeNull()
  })

  it('shows a Triple Crown’s first peak not yet earned, not always its last', () => {
    sheet({
      item: item('virginia-triple-crown'),
      tags: earned(
        ['virginia-triple-crown'],
        'hand',
        'atc_viewpoints:3cadebda-9d7d-4373-88f6-b240420eb958',
      ),
    })
    expect(screen.getByText(/McAfee Knob Summit · mi 714\.9/)).toBeInTheDocument()
  })

  it('moves focus to Take it back when the item is earned in place, not to the page', async () => {
    const props = {
      challenge: ATC_CHALLENGE,
      item: item('mcafee-knob'),
      number: 7,
      today: TODAY,
      earnable: true,
      onEarn: vi.fn(),
      onTakeBack: vi.fn(),
      onSetNote: vi.fn(),
      onClose: vi.fn(),
    }
    const { rerender } = render(<TileSheet {...props} tags={earned([])} />)
    screen.getByRole('button', { name: 'Earn some karma' }).focus()
    rerender(<TileSheet {...props} tags={earned(['mcafee-knob'])} />)
    expect(screen.getByRole('button', { name: 'Take it back' })).toHaveFocus()
  })

  it('links to workdays under the club’s note on an item with a place', async () => {
    const onOpenWorkdays = vi.fn()
    sheet({
      item: { ...item('mcafee-knob'), note: 'Park at the Route 311 lot.', noteBy: null },
      onOpenWorkdays,
    })
    await userEvent.click(
      screen.getByRole('button', { name: 'Workdays on this section' }),
    )
    expect(onOpenWorkdays).toHaveBeenCalledOnce()
  })

  it('hands the Earn button to the caller, so focus can come back to it from the Where sheet', async () => {
    const props = sheet({ item: item('white-blaze-photo') })
    const earn = screen.getByRole('button', { name: 'Earn some karma' })
    await userEvent.click(earn)
    expect(props.onEarn).toHaveBeenCalledWith(earn)
  })
})
