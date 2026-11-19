import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { usePreferencesSync, PUSH_SETTLE_MS } from './usePreferencesSync'
import { pushIfChanged, reconcilePreferences, type SyncOutcome } from './preferencesSync'
import { DEFAULT_PREFERENCES, type UserPreferences } from './userPreferences'

// WHEN the reconciliation runs (#891) - "pull on sign-in, push on change".
//
// The rule itself is tested in preferencesSync.test.ts. What is tested here
// is the wiring, and the two ways it can be wrong are both silent:
//
//   - running the pull while signed out, which spends a request that can
//     only ever come back 401; and
//   - pushing on a render rather than on a change, which turns every
//     re-render of the app into a PUT.

vi.mock('./preferencesSync', () => ({
  reconcilePreferences: vi.fn(),
  pushIfChanged: vi.fn(),
}))

const NOOP = () => {}
/** The account answered, and there was nothing to adopt. */
const REACHED: SyncOutcome = { adopted: null, reached: true }
/** No signal: nothing heard from the account. */
const UNREACHED: SyncOutcome = { adopted: null, reached: false }

beforeEach(() => {
  vi.useFakeTimers()
  vi.mocked(reconcilePreferences).mockReset().mockResolvedValue(REACHED)
  vi.mocked(pushIfChanged).mockReset().mockResolvedValue(REACHED)
})

afterEach(() => {
  vi.useRealTimers()
})

/**
 * The reconciliation is loaded behind import() since #1903 (the launch
 * budget), once, and shared - so a call it makes lands a few promise turns
 * after the effect or the timer that asked for it: the import on the first
 * test, the shared promise's turns after that. Waited on, and counted, never
 * timed.
 */
async function arrived(): Promise<void> {
  await act(async () => {
    await vi.dynamicImportSettled()
    for (let turn = 0; turn < 5; turn += 1) await Promise.resolve()
  })
}

function mount(
  preferences: UserPreferences,
  signedIn: boolean,
  onAdopt = NOOP,
  onSettled?: (reached: boolean) => void,
) {
  return renderHook(
    ({
      prefs,
      signed,
      online,
    }: {
      prefs: UserPreferences
      signed: boolean
      online?: boolean
    }) => usePreferencesSync(prefs, signed, onAdopt, onSettled, online),
    {
      initialProps: { prefs: preferences, signed: signedIn } as {
        prefs: UserPreferences
        signed: boolean
        online?: boolean
      },
    },
  )
}

describe('pulling on sign-in', () => {
  it('asks the account for nothing while signed out', () => {
    mount(DEFAULT_PREFERENCES, false)

    expect(reconcilePreferences).not.toHaveBeenCalled()
  })

  it('reconciles once when the app opens already signed in', async () => {
    mount(DEFAULT_PREFERENCES, true)
    await arrived()

    expect(reconcilePreferences).toHaveBeenCalledOnce()
  })

  it('reconciles when a signed-out hiker signs in', async () => {
    const view = mount(DEFAULT_PREFERENCES, false)

    view.rerender({ prefs: DEFAULT_PREFERENCES, signed: true })
    await arrived()

    expect(reconcilePreferences).toHaveBeenCalledOnce()
  })

  it('does not reconcile again because a preference changed', async () => {
    // The pull is a sign-in event. Re-running it per toggle would spend a
    // GET on every tap, and could pull the account's blob back over the
    // change the hiker is in the middle of making.
    const view = mount(DEFAULT_PREFERENCES, true)
    await arrived()

    view.rerender({ prefs: { ...DEFAULT_PREFERENCES, theme: 'dark' }, signed: true })
    await arrived()

    expect(reconcilePreferences).toHaveBeenCalledOnce()
  })

  it('hands the account’s preferences to the caller when they win', async () => {
    const adopted = { ...DEFAULT_PREFERENCES, theme: 'dark' as const }
    vi.mocked(reconcilePreferences).mockResolvedValue({ adopted, reached: true })
    const onAdopt = vi.fn()

    mount(DEFAULT_PREFERENCES, true, onAdopt)
    await arrived()
    // The promise, not the timer: awaiting an observable effect rather than
    // a duration is what stops this passing on an idle machine and failing
    // in CI.
    await act(async () => {
      await vi.mocked(reconcilePreferences).mock.results[0]?.value
    })

    expect(onAdopt).toHaveBeenCalledWith(adopted)
  })

  it('says nothing to the caller when there is nothing to adopt', async () => {
    const onAdopt = vi.fn()

    mount(DEFAULT_PREFERENCES, true, onAdopt)
    await arrived()
    await act(async () => {
      await vi.mocked(reconcilePreferences).mock.results[0]?.value
    })

    expect(onAdopt).not.toHaveBeenCalled()
  })

  it('does not adopt into an unmounted app', async () => {
    let settle: (value: SyncOutcome) => void = NOOP
    vi.mocked(reconcilePreferences).mockReturnValue(
      new Promise((resolve) => {
        settle = resolve
      }),
    )
    const onAdopt = vi.fn()

    const view = mount(DEFAULT_PREFERENCES, true, onAdopt)
    await arrived()
    view.unmount()
    await act(async () => {
      settle({ adopted: { ...DEFAULT_PREFERENCES, theme: 'dark' }, reached: true })
    })

    expect(onAdopt).not.toHaveBeenCalled()
  })
})

describe('a launch with no signal', () => {
  it('spends no request while the phone says it has no signal', async () => {
    renderHook(() =>
      usePreferencesSync(DEFAULT_PREFERENCES, true, NOOP, undefined, false),
    )
    await arrived()

    expect(reconcilePreferences).not.toHaveBeenCalled()
  })

  it('pulls when signal returns, and tells the caller the account answered', async () => {
    const onSettled = vi.fn()
    const view = mount(DEFAULT_PREFERENCES, false, NOOP, onSettled)
    view.rerender({ prefs: DEFAULT_PREFERENCES, signed: true, online: false })
    await arrived()
    expect(reconcilePreferences).not.toHaveBeenCalled()

    view.rerender({ prefs: DEFAULT_PREFERENCES, signed: true, online: true })
    await arrived()

    expect(reconcilePreferences).toHaveBeenCalledOnce()
    expect(onSettled).toHaveBeenLastCalledWith(true)
  })

  it('tries again when signal returns after an attempt that did not reach the account', async () => {
    // navigator.onLine says true on a captive portal or one bar that drops
    // the request: the attempt fails, and the next return of signal is the
    // next chance - not the next launch (#1903's second review).
    vi.mocked(reconcilePreferences).mockResolvedValueOnce(UNREACHED)
    const onSettled = vi.fn()
    const view = mount(DEFAULT_PREFERENCES, true, NOOP, onSettled)
    await arrived()
    expect(onSettled).toHaveBeenLastCalledWith(false)

    view.rerender({ prefs: DEFAULT_PREFERENCES, signed: true, online: false })
    view.rerender({ prefs: DEFAULT_PREFERENCES, signed: true, online: true })
    await arrived()

    expect(reconcilePreferences).toHaveBeenCalledTimes(2)
    expect(onSettled).toHaveBeenLastCalledWith(true)
  })

  it('pulls once a sign-in, however often signal comes and goes after it reached the account', async () => {
    const view = mount(DEFAULT_PREFERENCES, true)
    await arrived()

    for (const online of [false, true, false, true]) {
      view.rerender({ prefs: DEFAULT_PREFERENCES, signed: true, online })
      await arrived()
    }

    expect(reconcilePreferences).toHaveBeenCalledOnce()
  })
})

describe('pushing on change', () => {
  it('sends nothing while signed out, however much changes', () => {
    const view = mount(DEFAULT_PREFERENCES, false)

    view.rerender({ prefs: { ...DEFAULT_PREFERENCES, theme: 'dark' }, signed: false })
    act(() => vi.advanceTimersByTime(PUSH_SETTLE_MS * 4))

    expect(pushIfChanged).not.toHaveBeenCalled()
  })

  it('lets a burst of toggles settle into one push', async () => {
    // The legend's category switches are tapped in runs. Four taps must not
    // be four round trips on a connection this app assumes is bad.
    const view = mount(DEFAULT_PREFERENCES, true)

    for (const theme of ['dark', 'light', 'auto'] as const) {
      view.rerender({ prefs: { ...DEFAULT_PREFERENCES, theme }, signed: true })
      act(() => vi.advanceTimersByTime(PUSH_SETTLE_MS / 3))
    }
    expect(pushIfChanged).not.toHaveBeenCalled()

    // Advancing the timer runs the callback synchronously; the call itself
    // lands once the reconciliation's module has, which `arrived` waits on.
    act(() => vi.advanceTimersByTime(PUSH_SETTLE_MS))
    await arrived()
    expect(pushIfChanged).toHaveBeenCalledOnce()
  })

  it('sends the values as they stand when the burst settles, not as they were', async () => {
    const view = mount(DEFAULT_PREFERENCES, true)

    view.rerender({ prefs: { ...DEFAULT_PREFERENCES, theme: 'dark' }, signed: true })
    act(() => vi.advanceTimersByTime(PUSH_SETTLE_MS + 1))
    await arrived()

    expect(pushIfChanged).toHaveBeenCalledWith(expect.objectContaining({ theme: 'dark' }))
  })

  it('sends nothing after the app closes mid-burst', () => {
    const view = mount(DEFAULT_PREFERENCES, true)
    view.rerender({ prefs: { ...DEFAULT_PREFERENCES, theme: 'dark' }, signed: true })

    view.unmount()
    act(() => vi.advanceTimersByTime(PUSH_SETTLE_MS * 4))

    expect(pushIfChanged).not.toHaveBeenCalled()
  })
})
