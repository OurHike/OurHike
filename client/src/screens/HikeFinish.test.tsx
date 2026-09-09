// The finish (#1317).
//
// THE GUARD IS THE POINT OF THIS FILE. A finish screen is where
// percentages, ranks, streaks and "you beat 80% of hikers" arrive, because
// every other app's has them. The last two tests are the standing Plan-tab
// guard extended to cover this surface, which is what the handoff asks for.

import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { HikeFinish } from './HikeFinish'

const PROPS = {
  hikeName: 'Springer → Katahdin',
  sentence: 'You walked the whole Appalachian Trail, 14 Mar 2024 to 12 Aug 2026.',
  finishedOn: '2026-08-12',
  walkedMi: 2198.4,
  daysWalking: 152,
  climbedFt: 464500,
  sections: 9,
  seasons: 'three seasons',
  photos: [],
  crews: null,
  units: 'imperial' as const,
  onSayThanks: vi.fn(),
  onShare: vi.fn(),
  onKeepTheRecord: vi.fn(),
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('the finish', () => {
  it('names the hike, the date and what was walked', () => {
    render(<HikeFinish {...PROPS} />)

    expect(
      screen.getByRole('heading', { name: 'Springer → Katahdin' }),
    ).toBeInTheDocument()
    expect(screen.getByText(/Finished · 12 Aug/)).toBeInTheDocument()
    expect(screen.getByText(PROPS.sentence)).toBeInTheDocument()
  })

  it('shows four figures, every one a record of what happened', () => {
    // Not one of them is a comparison, a rate or a placing.
    render(<HikeFinish {...PROPS} />)

    expect(screen.getByText('2,198.4 mi')).toBeInTheDocument()
    expect(screen.getByText('152')).toBeInTheDocument()
    expect(screen.getByText('9')).toBeInTheDocument()
    expect(screen.getByText(/days walking, three seasons/)).toBeInTheDocument()
  })

  it('omits the climb rather than reading zero when nothing measured it', () => {
    // Nobody climbed zero feet.
    render(<HikeFinish {...PROPS} climbedFt={null} />)

    expect(screen.queryByText('climbed')).not.toBeInTheDocument()
    expect(screen.queryByText('0 ft')).not.toBeInTheDocument()
  })

  it('says a hiker’s own photos stay on their phone', () => {
    render(
      <HikeFinish
        {...PROPS}
        photos={[{ id: 'p1', src: 'data:,', credit: 'A photographer' }]}
      />,
    )

    expect(screen.getByText(/your photos drop in here/)).toBeInTheDocument()
    expect(
      screen.getByText(/Yours stay on your phone unless you share them/),
    ).toBeInTheDocument()
  })

  it('says nothing about the crews when this phone cannot say', () => {
    render(<HikeFinish {...PROPS} crews={null} />)
    expect(screen.queryByRole('button', { name: /Say thanks/ })).not.toBeInTheDocument()
  })

  it('offers thanks to the crews when it can', async () => {
    const user = userEvent.setup()
    const onSayThanks = vi.fn()
    render(
      <HikeFinish
        {...PROPS}
        crews={{ clubs: 31, fieldNotes: 24, thanks: 6 }}
        onSayThanks={onSayThanks}
      />,
    )

    expect(
      screen.getByText(/31 clubs maintain the trail you just walked/),
    ).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Say thanks to the crews' }))
    expect(onSayThanks).toHaveBeenCalled()
  })

  it('says out loud that there is no badge, no rank and nobody to compare with', () => {
    render(<HikeFinish {...PROPS} />)
    expect(
      screen.getByText(/No badge, no rank, nobody to compare with/),
    ).toBeInTheDocument()
  })

  it('THE GUARD: no percentage, no rank, no streak, no other hiker, no on track', () => {
    // The standing Plan-tab guard, extended to the surface most likely to
    // break it. OurHikeValues.md #1.
    //
    // ONE EXEMPTION, written out rather than the regex loosened: the closing
    // line is "No badge, no rank, nobody to compare with", which is the
    // promise this guard exists to keep. Removing that sentence and then
    // applying the guard in full is the honest version - relaxing the
    // pattern to allow "no rank" would also stop it catching "rank 412".
    const { container } = render(
      <HikeFinish {...PROPS} crews={{ clubs: 31, fieldNotes: 24, thanks: 6 }} />,
    )
    const whole = container.textContent ?? ''
    const text = whole.replace('No badge, no rank, nobody to compare with.', '')

    expect(text).not.toMatch(/%|behind|ahead of|on track|streak|in a row/i)
    expect(text).not.toMatch(/\brank\b|placing|leaderboard|faster than|other hikers/i)
    expect(text).not.toMatch(/congratulations|well done|you beat/i)
    // And the exempted sentence really is the only "rank" on the screen.
    expect(whole.match(/rank/gi)).toHaveLength(1)
  })

  it('THE GUARD: nothing on it counts down', () => {
    const { container } = render(<HikeFinish {...PROPS} />)
    expect(container.querySelector('progress')).toBeNull()
    expect(container.textContent).not.toMatch(/to go/i)
  })
})
