import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { DaySummary } from './DaySummary'
import { ownPhotosOn } from '../lib/poiPhotos'
import { buildPlan, planDayViews, type PlanDayView } from '../lib/plan'
import { priceLeg, type PricedLeg } from '../lib/route'
import { paceMinutes, STANDARD_PACE } from '../lib/pace'
import type { StoredPoi } from '../lib/trailData'

// The day summary (#966, wireframe 2c frame 1).
//
// What this file exists to prove is the CARD'S HONESTY, not its layout.
// Three of the four tiles the wireframe drew either changed their wording
// or are absent, each because of what the phone can actually stand behind,
// and every one of those is a claim a future change could quietly undo:
//
//   - nothing here says "field notes filed" or "water you drank at" (#967);
//   - the water figure says "on the map", because water coverage is
//     incomplete and the honest sentence is about waypoints, not water;
//   - the time is Naismith and wears its ≈ and its "walking", because
//     lib/walkedMiles.ts stores no timestamps and the app therefore cannot
//     know how long anybody's day took.
//
// And the guardrail the whole Plan tab is built around: this card is where
// "you're a day behind" would arrive if it ever arrived, so nothing here
// may compare the day against anything.

vi.mock('../lib/poiPhotos', () => ({ ownPhotosOn: vi.fn() }))

const mockedPhotos = vi.mocked(ownPhotosOn)

const poi = (id: string, type: string, mile: number): StoredPoi => ({
  id,
  type,
  name: id,
  lat: 0,
  lon: 0,
  confidence: 'high',
  mile,
})

const POIS = [poi('w1', 'water', 496.0), poi('w2', 'water', 501.0)]

/** Damascus → Wise, walked, crossing mile 500 - the wireframe's own day. */
function walkedDay(overrides: Partial<PlanDayView> = {}): PlanDayView {
  const plan = buildPlan(
    [
      { mile: 494.2, name: 'Lost Mountain', resupply: false },
      { mile: 503.4, name: 'Wise Shelter', resupply: false },
    ],
    { miles: 15 },
    '2026-05-12',
  )
  return { ...planDayViews(plan)[0], walked: true, ...overrides }
}

// Priced through priceLeg rather than written out, so the estimate the card
// prints is derived from these figures by the same function the screens use -
// a fixture that stated its own `estimate.text` could agree with nothing.
//
// `minutes` comes from paceMinutes for the same reason, and it is a
// correction: this fixture used to state 520 against a 9.2 mi / 3,400 ft day
// that Naismith prices at 281, and the card's assertion pinned the 520. The
// number was nobody's - the card now derives its time from the three terms,
// so an inconsistent fixture would have asserted an impossible screen.
const WALKED = { distanceMi: 9.2, ascentFt: 3400, descentFt: 1200, unmeasuredMi: 0 }
const FIGURES: PricedLeg = priceLeg(
  { ...WALKED, minutes: paceMinutes(WALKED, STANDARD_PACE) },
  STANDARD_PACE,
)

function renderCard(props: Partial<Parameters<typeof DaySummary>[0]> = {}) {
  const onKeepNote = vi.fn()
  const onClose = vi.fn()
  const onNextDay = vi.fn()
  render(
    <DaySummary
      day={walkedDay()}
      figures={FIGURES}
      pois={POIS}
      units="imperial"
      nextDayWalked={false}
      onNextDay={onNextDay}
      onKeepNote={onKeepNote}
      onClose={onClose}
      {...props}
    />,
  )
  return { onKeepNote, onClose, onNextDay }
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('DaySummary', () => {
  it('names the day, where it ran, and what it cost', async () => {
    mockedPhotos.mockResolvedValue(11)
    renderCard()

    expect(screen.getByText(/tue 12 may · day 1/i)).toBeTruthy()
    expect(screen.getByText('Lost Mountain → Wise Shelter')).toBeTruthy()
    const figures = screen.getByText(/9\.2 mi/)
    expect(figures.textContent).toContain('3,400 ft')
    // Naismith's own marks: the ≈ and the word "walking". Not "moving",
    // which would read as a stopwatch on the hiker's actual day.
    expect(figures.textContent).toContain('≈4h 40m walking')
    expect(figures.textContent).not.toContain('moving')
  })

  it('withholds the climb and the time where the DEM has a hole (#1039)', () => {
    // Read after the walk, where a wrong climb becomes what the hiker
    // remembers doing. A hole prices as flat, so both figures are short.
    renderCard({ figures: { ...FIGURES, unmeasuredMi: 2.4 } })

    const figures = screen.getByText(/9\.2 mi/)
    expect(figures.textContent).toContain('no climb measured for')
    expect(figures.textContent).not.toContain('3,400 ft')
    expect(figures.textContent).not.toContain('walking')
    // The distance is the one figure a hole cannot corrupt, and it stays.
    expect(figures.textContent).toContain('9.2 mi')
  })

  it('quotes the hiker their own milestone, and nothing about how they walked', async () => {
    mockedPhotos.mockResolvedValue(0)
    renderCard()

    expect(screen.getByText(/somewhere in there you passed mile 500/i)).toBeTruthy()
  })

  it('says nothing at all on a day that crossed no milestone', async () => {
    mockedPhotos.mockResolvedValue(0)
    renderCard({
      day: walkedDay({
        start: { mile: 470.8, name: 'Damascus', resupply: false },
        end: { mile: 486.2, name: 'Lost Mountain', resupply: false },
      }),
    })

    expect(screen.queryByText(/somewhere in there/i)).toBeNull()
  })

  it('counts photos KEPT, once the store answers', async () => {
    mockedPhotos.mockResolvedValue(11)
    renderCard()

    // Waiting on the number itself rather than on a tick: the effect's
    // promise is what has to have settled, and the count is the observable
    // proof that it did.
    await screen.findByText('11')
    expect(screen.getByText(/photos you kept/i)).toBeTruthy()
    expect(screen.queryByText(/photos taken/i)).toBeNull()
    expect(mockedPhotos).toHaveBeenCalledWith('2026-05-12')
  })

  it('shows no photo tile at all while the store has not answered', () => {
    // "0" flashing before the real number tells a hiker they photographed
    // nothing today, which is the one thing this card must not get wrong.
    mockedPhotos.mockReturnValue(new Promise(() => {}))
    renderCard()

    expect(screen.queryByText(/photos you kept/i)).toBeNull()
  })

  it('renders without the photo tile when the store throws', async () => {
    mockedPhotos.mockRejectedValue(new Error('no indexeddb'))
    renderCard()

    // The rest of the card is the observable proof the failure was absorbed.
    await screen.findByText('Lost Mountain → Wise Shelter')
    await waitFor(() => expect(mockedPhotos).toHaveBeenCalled())
    expect(screen.queryByText(/photos you kept/i)).toBeNull()
  })

  it('measures water as WAYPOINTS on the map, and says so', async () => {
    mockedPhotos.mockResolvedValue(0)
    renderCard()

    // 494.2 → 496.0 → 501.0 → 503.4: the long run is the middle 5.0.
    expect(screen.getByText(/longest stretch with no water on the map/i)).toBeTruthy()
    expect(screen.getByText('5.0 mi')).toBeTruthy()
    expect(screen.getByText(/coverage is incomplete/i)).toBeTruthy()
  })

  it('does not claim a dry stretch on a download with no miles', async () => {
    mockedPhotos.mockResolvedValue(0)
    renderCard({ pois: [{ ...poi('w1', 'water', 0), mile: undefined }] })

    expect(screen.queryByText(/longest stretch/i)).toBeNull()
  })

  it('never prints the two tiles that have no source (#967)', async () => {
    mockedPhotos.mockResolvedValue(3)
    renderCard()

    await screen.findByText('3')
    expect(screen.queryByText(/field notes filed/i)).toBeNull()
    expect(screen.queryByText(/water you drank/i)).toBeNull()
  })

  it('compares the day against nothing - no target, no verdict, no score', async () => {
    mockedPhotos.mockResolvedValue(1)
    const { container } = render(
      <DaySummary
        day={walkedDay()}
        figures={FIGURES}
        pois={POIS}
        units="imperial"
        nextDayWalked={false}
        onNextDay={vi.fn()}
        onKeepNote={vi.fn()}
        onClose={vi.fn()}
      />,
    )
    await screen.findByText('1')

    const text = container.textContent ?? ''
    for (const forbidden of [
      'behind',
      'ahead',
      'target',
      'was ',
      'streak',
      'goal',
      'short of',
    ]) {
      expect(text.toLowerCase()).not.toContain(forbidden)
    }
  })

  it("keeps the hiker's line, and starts from what they already wrote", async () => {
    mockedPhotos.mockResolvedValue(0)
    const { onKeepNote } = renderCard({
      day: walkedDay({ note: 'the ponies were unbothered' }),
    })

    const box = screen.getByRole('textbox')
    expect((box as HTMLTextAreaElement).value).toBe('the ponies were unbothered')

    fireEvent.change(box, { target: { value: 'mile 500, and a vending machine' } })
    fireEvent.click(screen.getByRole('button', { name: 'Keep' }))
    expect(onKeepNote).toHaveBeenCalledWith('mile 500, and a vending machine')
  })

  it('offers the next day only when there is a record behind it', async () => {
    mockedPhotos.mockResolvedValue(0)
    const { onNextDay } = renderCard({ nextDayWalked: true })

    fireEvent.click(screen.getByRole('button', { name: /the next day/i }))
    expect(onNextDay).toHaveBeenCalled()

    cleanup()
    renderCard({ nextDayWalked: false })
    expect(screen.queryByRole('button', { name: /the next day/i })).toBeNull()
  })
})
