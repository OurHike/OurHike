import { describe, it, expect, vi, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useAlertLayerPanel } from './alertLayerPanel'

// #1047's constraint, which is the whole feature: "we shouldnt let the
// throughhikers just turn that off for many days. The map should always open
// to the alerts being shown."
//
// Everything below is one of the two halves of that sentence. The first half
// is what is NOT here - no storage, no preference, no writer - and is asserted
// by watching the two APIs that could carry it and finding them untouched. The
// second half is "open", which on a phone whose process survives the night
// means a RESUME rather than a launch, so the visibility event is the one that
// has to do the work.

afterEach(() => {
  vi.restoreAllMocks()
})

function becomeVisible(): void {
  act(() => {
    vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('visible')
    document.dispatchEvent(new Event('visibilitychange'))
  })
}

function becomeHidden(): void {
  act(() => {
    vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('hidden')
    document.dispatchEvent(new Event('visibilitychange'))
  })
}

describe('useAlertLayerPanel', () => {
  it('opens with the alerts on the map', () => {
    const { result } = renderHook(() => useAlertLayerPanel())

    expect(result.current.mapScreen.alertsShown).toBe(true)
  })

  it('takes them off when the hiker asks', () => {
    const { result } = renderHook(() => useAlertLayerPanel())

    act(() => result.current.mapScreen.onToggleAlerts?.())

    expect(result.current.mapScreen.alertsShown).toBe(false)
  })

  it('puts them back when the hiker asks again', () => {
    const { result } = renderHook(() => useAlertLayerPanel())

    act(() => result.current.mapScreen.onToggleAlerts?.())
    act(() => result.current.mapScreen.onToggleAlerts?.())

    expect(result.current.mapScreen.alertsShown).toBe(true)
  })

  it('puts them back when the app comes back, without being asked', () => {
    // THE TEST THIS FILE EXISTS FOR. A thru-hiker's phone keeps this app alive
    // for days, so the initial state above never runs again - and a hide that
    // survives every night in a pocket is exactly the "many days" #1047 rules
    // out. `visibilitychange` is the only moment the platform gives for it.
    const { result } = renderHook(() => useAlertLayerPanel())
    act(() => result.current.mapScreen.onToggleAlerts?.())
    expect(result.current.mapScreen.alertsShown).toBe(false)

    becomeHidden()
    becomeVisible()

    expect(result.current.mapScreen.alertsShown).toBe(true)
  })

  it('does not put them back merely because the app went away', () => {
    // Backgrounding is not a return. Acting on it would flip the flag while
    // nobody is looking and cost the sequence above its meaning - the hiker
    // would come back to a change they never saw happen.
    const { result } = renderHook(() => useAlertLayerPanel())
    act(() => result.current.mapScreen.onToggleAlerts?.())

    becomeHidden()

    expect(result.current.mapScreen.alertsShown).toBe(false)
  })

  it('leaves a hider alone for as long as they are looking at the map', () => {
    // The other side of the rule. Coming back is what restores them; a render
    // in between must not, or the switch would appear not to work at all.
    const { result, rerender } = renderHook(() => useAlertLayerPanel())
    act(() => result.current.mapScreen.onToggleAlerts?.())

    rerender()

    expect(result.current.mapScreen.alertsShown).toBe(false)
  })

  it('writes nothing down', () => {
    // The half of #1047 that a stored flag would have broken silently: a
    // preference reaches an account and arrives on the next phone already off.
    // Watched at the API rather than by reading the source, so an
    // `updatePreferences` import added later fails here rather than in the
    // field.
    const setItem = vi.spyOn(Storage.prototype, 'setItem')
    const { result } = renderHook(() => useAlertLayerPanel())

    act(() => result.current.mapScreen.onToggleAlerts?.())
    becomeHidden()
    becomeVisible()

    expect(setItem).not.toHaveBeenCalled()
  })

  it('starts a second mount shown, whatever the first one did', () => {
    // A reload, a cold start, or this app rebuilt around a new trail: none of
    // them may inherit a hide. Nothing is stored, so nothing can - and this is
    // what would catch a later "helpful" module-level cache of the flag.
    const first = renderHook(() => useAlertLayerPanel())
    act(() => first.result.current.mapScreen.onToggleAlerts?.())
    first.unmount()

    const { result } = renderHook(() => useAlertLayerPanel())

    expect(result.current.mapScreen.alertsShown).toBe(true)
  })

  it('stops listening when it goes away', () => {
    const remove = vi.spyOn(document, 'removeEventListener')
    const { unmount } = renderHook(() => useAlertLayerPanel())

    unmount()

    expect(remove).toHaveBeenCalledWith('visibilitychange', expect.any(Function))
  })
})
