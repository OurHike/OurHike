import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useTripsSync, TRIP_SETTLE_MS } from './useTripsSync'
import { syncTripsWithAccount } from './tripsSync'
import { EMPTY_STORE, type TripStore } from './trips'

// WHEN the trip reconciliation runs (#892). The rule is the server's and the
// merge is tested in tripsSync.test.ts; what is tested here is the wiring,
// and the two ways it can be wrong are both silent: syncing while signed out
// spends requests that can only come back 401, and syncing per render turns
// every re-render of the app into a round trip carrying a hiker's plans.

vi.mock('./tripsSync', () => ({ syncTripsWithAccount: vi.fn() }))

const NOOP = () => {}

beforeEach(() => {
  vi.useFakeTimers()
  vi.mocked(syncTripsWithAccount).mockReset().mockResolvedValue(null)
})

afterEach(() => {
  vi.useRealTimers()
})

function mount(trips: TripStore, signedIn: boolean, onAdopt = NOOP) {
  return renderHook(
    ({ store, signed }: { store: TripStore; signed: boolean }) =>
      useTripsSync(store, signed, onAdopt),
    { initialProps: { store: trips, signed: signedIn } },
  )
}

describe('when it runs', () => {
  it('never talks to the account while signed out', () => {
    const view = mount(EMPTY_STORE, false)
    view.rerender({ store: { ...EMPTY_STORE }, signed: false })
    act(() => vi.advanceTimersByTime(TRIP_SETTLE_MS * 4))

    expect(syncTripsWithAccount).not.toHaveBeenCalled()
  })

  it('reconciles once when the app opens already signed in', () => {
    mount(EMPTY_STORE, true)

    expect(syncTripsWithAccount).toHaveBeenCalledOnce()
  })

  it('reconciles when a signed-out hiker signs in', () => {
    const view = mount(EMPTY_STORE, false)

    view.rerender({ store: EMPTY_STORE, signed: true })

    expect(syncTripsWithAccount).toHaveBeenCalledOnce()
  })

  it('lets a burst of plan edits settle into one exchange', () => {
    // Editing a plan is sustained - dragging a day boundary, renaming a
    // stop - and each of those is a `saveTrips`. One round trip per drag
    // would carry a hiker's whole planning over a bad connection, repeatedly.
    const view = mount(EMPTY_STORE, true)
    vi.mocked(syncTripsWithAccount).mockClear()

    for (let edit = 0; edit < 3; edit += 1) {
      view.rerender({ store: { ...EMPTY_STORE }, signed: true })
      act(() => vi.advanceTimersByTime(TRIP_SETTLE_MS / 3))
    }
    expect(syncTripsWithAccount).not.toHaveBeenCalled()

    act(() => vi.advanceTimersByTime(TRIP_SETTLE_MS))
    expect(syncTripsWithAccount).toHaveBeenCalledOnce()
  })

  it('sends nothing after the app closes mid-burst', () => {
    const view = mount(EMPTY_STORE, true)
    vi.mocked(syncTripsWithAccount).mockClear()
    view.rerender({ store: { ...EMPTY_STORE }, signed: true })

    view.unmount()
    act(() => vi.advanceTimersByTime(TRIP_SETTLE_MS * 4))

    expect(syncTripsWithAccount).not.toHaveBeenCalled()
  })
})

describe('what it hands back', () => {
  it('gives the caller the merged store when the exchange changed something', async () => {
    const merged = { ...EMPTY_STORE, openId: 'trip-1' }
    vi.mocked(syncTripsWithAccount).mockResolvedValue(merged)
    const onAdopt = vi.fn()

    mount(EMPTY_STORE, true, onAdopt)
    await act(async () => {
      await vi.mocked(syncTripsWithAccount).mock.results[0]?.value
    })

    expect(onAdopt).toHaveBeenCalledWith(merged)
  })

  it('says nothing when the exchange changed nothing', async () => {
    const onAdopt = vi.fn()

    mount(EMPTY_STORE, true, onAdopt)
    await act(async () => {
      await vi.mocked(syncTripsWithAccount).mock.results[0]?.value
    })

    expect(onAdopt).not.toHaveBeenCalled()
  })

  it('does not adopt into an app that has closed', async () => {
    let settle: (value: TripStore | null) => void = NOOP
    vi.mocked(syncTripsWithAccount).mockReturnValue(
      new Promise((resolve) => {
        settle = resolve
      }),
    )
    const onAdopt = vi.fn()

    const view = mount(EMPTY_STORE, true, onAdopt)
    view.unmount()
    await act(async () => {
      settle({ ...EMPTY_STORE, openId: 'trip-1' })
    })

    expect(onAdopt).not.toHaveBeenCalled()
  })
})
