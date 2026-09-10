import { describe, it, expect, vi } from 'vitest'
import { act, renderHook } from '@testing-library/react'
import {
  NAV_HOME,
  applyMove,
  reduceNav,
  screensLeft,
  topScreen,
  useNavigator,
  type Guard,
  type NavState,
  type Screen,
} from './navigator'

const FIND: Screen = { kind: 'find' }
const HIKE: Screen = { kind: 'hike', id: 'h1' }
const VOLUNTEER: Screen = { kind: 'more', page: 'volunteer' }

function at(state: NavState<string>, ...moves: Parameters<typeof applyMove>[1][]) {
  return moves.reduce((s, move) => applyMove(s, move), state)
}

const HOME = NAV_HOME as NavState<string>

describe('applyMove', () => {
  it('starts on Today at its home', () => {
    expect(HOME.tab).toBe('today')
    expect(topScreen(HOME)).toBeNull()
  })

  it('pushing a screen selects the tab it lives under', () => {
    const state = at(HOME, { to: 'push', screen: VOLUNTEER })

    expect(state.tab).toBe('more')
    expect(topScreen(state)).toEqual(VOLUNTEER)
    expect(state.stacks.today).toEqual([])
  })

  it('a tab selection returns Today to the journal (#1284) and keeps More’s page (#1054)', () => {
    const state = at(
      HOME,
      { to: 'push', screen: FIND },
      { to: 'push', screen: HIKE },
      { to: 'push', screen: VOLUNTEER },
      { to: 'tab', tab: 'map' },
    )

    expect(state.tab).toBe('map')
    expect(state.stacks.today).toEqual([])
    expect(state.stacks.more).toEqual([VOLUNTEER])
  })

  it('re-selecting Today from its finder is the same courtesy', () => {
    const state = at(HOME, { to: 'push', screen: FIND }, { to: 'tab', tab: 'today' })

    expect(topScreen(state)).toBeNull()
  })

  it('back pops one screen and does nothing at a home', () => {
    const two = at(HOME, { to: 'push', screen: FIND }, { to: 'push', screen: HIKE })

    const one = applyMove(two, { to: 'back' })
    expect(topScreen(one)).toEqual(FIND)

    const home = applyMove(one, { to: 'back' })
    expect(topScreen(home)).toBeNull()
    expect(applyMove(home, { to: 'back' })).toBe(home)
  })

  it('home clears the active tab’s stack and no other', () => {
    const state = at(
      HOME,
      { to: 'push', screen: VOLUNTEER },
      { to: 'push', screen: FIND },
      { to: 'home' },
    )

    expect(state.stacks.today).toEqual([])
    expect(state.stacks.more).toEqual([VOLUNTEER])
  })

  it('replace swaps the top screen, or pushes when there is none', () => {
    const you: Screen = { kind: 'more', page: 'you' }
    const swapped = at(
      HOME,
      { to: 'push', screen: VOLUNTEER },
      { to: 'replace', screen: you },
    )
    expect(swapped.stacks.more).toEqual([you])

    const pushed = at(HOME, { to: 'replace', screen: you })
    expect(pushed.stacks.more).toEqual([you])
    expect(pushed.tab).toBe('more')
  })
})

describe('screensLeft', () => {
  it('names what a move removes, and a push removes nothing', () => {
    const on = at(HOME, { to: 'push', screen: FIND })

    expect(screensLeft(on, applyMove(on, { to: 'push', screen: HIKE }))).toEqual([])
    expect(screensLeft(on, applyMove(on, { to: 'tab', tab: 'plan' }))).toEqual([FIND])
    expect(screensLeft(on, applyMove(on, { to: 'back' }))).toEqual([FIND])
  })
})

describe('reduceNav with a guard', () => {
  const guard: Guard<string> = (leaving) =>
    leaving.some((screen) => screen.kind === 'find') ? 'the search you typed' : null
  const onFinder = at(HOME, { to: 'push', screen: FIND })

  it('parks a move the guard answers, rather than applying it', () => {
    const state = reduceNav(onFinder, {
      type: 'move',
      move: { to: 'tab', tab: 'map' },
      guard,
    })

    expect(state.tab).toBe('today')
    expect(topScreen(state)).toEqual(FIND)
    expect(state.pending).toEqual({
      move: { to: 'tab', tab: 'map' },
      bail: 'the search you typed',
    })
  })

  it('proceed applies the parked move unguarded; stay drops it', () => {
    const parked = reduceNav(onFinder, {
      type: 'move',
      move: { to: 'tab', tab: 'map' },
      guard,
    })

    const went = reduceNav(parked, { type: 'proceed' })
    expect(went.tab).toBe('map')
    expect(went.pending).toBeNull()

    const stayed = reduceNav(parked, { type: 'stay' })
    expect(stayed.tab).toBe('today')
    expect(topScreen(stayed)).toEqual(FIND)
    expect(stayed.pending).toBeNull()
  })

  it('does not ask about a push over the guarded screen', () => {
    const state = reduceNav(onFinder, {
      type: 'move',
      move: { to: 'push', screen: HIKE },
      guard,
    })

    expect(state.pending).toBeNull()
    expect(topScreen(state)).toEqual(HIKE)
  })

  it('does not ask when nothing is left, and a guard that declines lets the move through', () => {
    const asked = vi.fn<Guard<string>>(() => null)
    const state = reduceNav(HOME, {
      type: 'move',
      move: { to: 'tab', tab: 'plan' },
      guard: asked,
    })
    expect(state.tab).toBe('plan')
    expect(asked).not.toHaveBeenCalled()

    const through = reduceNav(onFinder, {
      type: 'move',
      move: { to: 'back' },
      guard: asked,
    })
    expect(asked).toHaveBeenCalledWith([FIND], { to: 'back' }, onFinder)
    expect(topScreen(through)).toBeNull()
  })

  it('proceed and stay are no-ops with nothing parked', () => {
    expect(reduceNav(HOME, { type: 'proceed' })).toBe(HOME)
    expect(reduceNav(HOME, { type: 'stay' })).toBe(HOME)
  })
})

describe('useNavigator', () => {
  it('keeps every callback stable across moves, and reads the guard fresh', () => {
    let cost: string | null = null
    const { result, rerender } = renderHook(() =>
      useNavigator<string>((leaving) => (leaving.length > 0 ? cost : null)),
    )
    const first = result.current

    act(() => result.current.push(FIND))
    expect(result.current.top).toEqual(FIND)
    expect(result.current.selectTab).toBe(first.selectTab)
    expect(result.current.navigate).toBe(first.navigate)
    expect(result.current.back).toBe(first.back)

    cost = 'two stops'
    rerender()
    act(() => result.current.selectTab('map'))
    expect(result.current.tab).toBe('today')
    expect(result.current.pending?.bail).toBe('two stops')

    act(() => result.current.proceed())
    expect(result.current.tab).toBe('map')
    expect(result.current.pending).toBeNull()
  })
})
