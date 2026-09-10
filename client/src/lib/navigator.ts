// One navigation model for the shell (#1373, phase 0 of the pathway).
//
// WHAT IT REPLACES. App.tsx held where the hiker is as a set of booleans and
// small enums that grew one at a time: `activeTab`, then Today's `todayPage`
// with `openHikeId` and `cameFromFinder` beside it ("a boolean rather than a
// stack: there are two doors and no third is coming"), then More's `morePage`
// with its own rule about surviving a tab change. Each was right on its own.
// Together they had no single place a move goes through - which is what the
// design's decision D8 needs: "every exit from a half-built route shows the
// bail sheet", and an exit can be a tab tap, a Back, a card opening over the
// route, or a door on another screen. Only one `navigate()` can see all of
// them.
//
// THE MODEL. Four tabs, each with a stack of screens pushed over its home,
// innermost last; an empty stack is the home itself. A `Screen` names which
// tab it lives under (`screenTab`), so pushing More's Volunteer page from the
// Today column is one move that selects More AND pushes the page, the way
// two setState calls used to.
//
// Two courtesies the booleans kept are kept here, as one rule rather than
// two special cases. #1284: "any tab selection returns [Today] to the
// journal, so a hiker who leaves mid-search comes back to the room the tab
// is named for". #1054: More's page is "deliberately NOT reset when the tab
// changes: a hiker who steps out to the map mid-form comes back to the page
// they left". So a screen either survives a tab selection or it does not
// (`keptAcrossTabs`), and a tab selection drops every screen that does not,
// on every tab. The pathway's steps (F3-F5) will not survive one - leaving
// the builder by the tab bar IS the exit D8 guards.
//
// THE GUARD. Every move is applied to a copy first; the screens present
// before and absent after are what the move LEAVES. When something is left
// the guard is asked, and a guard that answers with a bail parks the move
// as `pending` instead of applying it. The shell renders the bail sheet from
// `pending.bail`, and the sheet's buttons end in `proceed()` (the parked
// move applies, unguarded) or `stay()`. What the bail carries - what the
// route costs, in words - is the shell's type, not this module's: the
// navigator knows that a move was stopped, never why.
//
// A push is not an exit. A card or a sheet opened OVER step 2 leaves the
// step on the stack and is not asked about; Back from that card returns to
// the step. And a push of a More page that crossed tabs remembers where it
// came from (`from`), so Back from Volunteer opened off Today's column
// lands on Today, not on More's home - the tab was selected by the push,
// and the pop that undoes the push undoes the selection with it. The
// spine's steps do not: a step belongs to Plan, and leaving one by Cancel
// lands in Plan's room whatever door opened it (features/PATHWAY.md), which
// is `returnsToOrigin`'s one distinction.
//
// Tapping the tab you are already on is a tab selection like any other: it
// returns the tab to its home, which is #1284's courtesy and also means a
// re-tap on Plan from step 1 goes through the guard, so a route half-built
// is asked about rather than silently dropped - the defect D8 names.
//
// NOT A ROUTER. Nothing here touches the URL or the history API - #970 (the
// website links at /app/ and the app has no router) is a follow-up this
// module makes small, and adding a dependency to the hottest file in the
// repository is its own decision. What this does give a future back button
// is one `back()` to call.

import { useCallback, useMemo, useReducer, useRef } from 'react'
import type { TabId } from '../chrome/tabs'
import type { HikeFacets } from './suggestedHikes'
import type { PlanStep } from '../chrome/StepRail'

/** More's pages other than its home, which is the tab itself. */
export type MorePageAway =
  | 'you'
  | 'map'
  | 'safety'
  | 'volunteer'
  | 'sources'
  /** Under Volunteer & report and under You (#1373, F9 and D5): what this
   *  phone has reported, and its own photos and notes. */
  | 'reports'
  | 'work'

/**
 * Every screen a stack can hold. Grows with the phases that add one (the
 * pathway's steps land with F3); a kind listed here is a kind the shell
 * renders.
 */
export type Screen =
  /** Today's finder room (#1284), pushed from its shelf - with facets
   *  already applied when a chip on Today asked for them (#1373, F2). */
  (
    | { readonly kind: 'find'; readonly facets?: Partial<HikeFacets> }
    /** One published route's detail (#1290), from a card on Today or the finder. */
    | { readonly kind: 'hike'; readonly id: string }
    /** One of More's pages (features/MORE_TAB.md). */
    | { readonly kind: 'more'; readonly page: MorePageAway }
    /** A step of the planning spine (#1373, F3-F5), under Plan. Not kept
     *  across a tab selection: leaving the spine by the tab bar IS the exit
     *  the guard asks about. */
    | { readonly kind: 'step'; readonly step: PlanStep }
  ) & {
    /**
     * The tab the push left, when it was not the one the screen lives under -
     * what Back returns to. Set by `applyMove`, never by a caller: a screen
     * pushed from its own tab has no `from`, and Back stays there.
     */
    readonly from?: TabId
  }

export type Move = (
  | { readonly to: 'tab'; readonly tab: TabId }
  | { readonly to: 'push'; readonly screen: Screen }
  | { readonly to: 'replace'; readonly screen: Screen }
  | { readonly to: 'back' }
  | { readonly to: 'home' }
) & {
  /**
   * The app's own move rather than the hiker's - landing on Plan after a
   * save, opening the map for a builder - which the guard never sees. An
   * exit the guard asks about is a tap the hiker took: a tab, a Back, a
   * door. A move the app makes for them has already decided.
   */
  readonly unguarded?: boolean
}

export interface Pending<B> {
  readonly move: Move
  readonly bail: B
}

export interface NavState<B = never> {
  readonly tab: TabId
  readonly stacks: Readonly<Record<TabId, readonly Screen[]>>
  readonly pending: Pending<B> | null
}

/**
 * Asked on every guarded move. `leaving` is every screen the move removes,
 * outermost first - possibly none, since what a guard protects need not be
 * a screen on the stack (the builders live on the map); a non-null answer
 * parks the move.
 */
export type Guard<B> = (
  leaving: readonly Screen[],
  move: Move,
  state: NavState<B>,
) => B | null

export const NAV_HOME: NavState<never> = {
  tab: 'today',
  stacks: { today: [], map: [], plan: [], more: [] },
  pending: null,
}

/** Which tab a screen lives under - selected by pushing it. */
export function screenTab(screen: Screen): TabId {
  switch (screen.kind) {
    case 'find':
    case 'hike':
      return 'today'
    case 'more':
      return 'more'
    case 'step':
      return 'plan'
  }
}

/** Whether a tab selection leaves the screen where it is (#1054's rule for
 *  More) or drops it (#1284's for Today). */
export function keptAcrossTabs(screen: Screen): boolean {
  return screen.kind === 'more'
}

/** Whether Back from the screen, pushed from another tab, returns to that
 *  tab: More's pages are a detour from wherever they were opened; the
 *  spine's steps belong to Plan, and Back from one lands there. */
export function returnsToOrigin(screen: Screen): boolean {
  return screen.kind === 'more'
}

export function sameScreen(a: Screen, b: Screen): boolean {
  if (a.kind !== b.kind) return false
  switch (a.kind) {
    case 'find':
      return true
    case 'hike':
      return a.id === (b as typeof a).id
    case 'more':
      return a.page === (b as typeof a).page
    case 'step':
      return a.step === (b as typeof a).step
  }
}

/** The screen showing on `tab`, or null at its home. */
export function topOf<B>(state: NavState<B>, tab: TabId): Screen | null {
  const stack = state.stacks[tab]
  return stack.length === 0 ? null : stack[stack.length - 1]
}

/** The screen showing on the active tab, or null at the tab's home. */
export function topScreen<B>(state: NavState<B>): Screen | null {
  return topOf(state, state.tab)
}

/** The move applied, with no guard consulted. Pure. */
export function applyMove<B>(state: NavState<B>, move: Move): NavState<B> {
  switch (move.to) {
    case 'tab': {
      const stacks = { ...state.stacks }
      for (const tab of Object.keys(stacks) as TabId[]) {
        stacks[tab] = stacks[tab].filter(keptAcrossTabs)
      }
      return { ...state, tab: move.tab, stacks }
    }
    case 'push': {
      const tab = screenTab(move.screen)
      const screen =
        tab === state.tab || !returnsToOrigin(move.screen)
          ? move.screen
          : { ...move.screen, from: state.tab }
      return {
        ...state,
        tab,
        stacks: { ...state.stacks, [tab]: [...state.stacks[tab], screen] },
      }
    }
    case 'replace': {
      const tab = screenTab(move.screen)
      const stack = state.stacks[tab]
      // The replaced screen's origin carries over: step 2 replacing step 1
      // is still the spine that was entered from wherever step 1 was.
      const replaced = stack.length === 0 ? undefined : stack[stack.length - 1]
      const screen =
        replaced?.from === undefined
          ? move.screen
          : { ...move.screen, from: replaced.from }
      return {
        ...state,
        tab,
        stacks: {
          ...state.stacks,
          [tab]: [...stack.slice(0, Math.max(0, stack.length - 1)), screen],
        },
      }
    }
    case 'back': {
      const stack = state.stacks[state.tab]
      if (stack.length === 0) return state
      const leaving = stack[stack.length - 1]
      return {
        ...state,
        tab: leaving.from ?? state.tab,
        stacks: { ...state.stacks, [state.tab]: stack.slice(0, -1) },
      }
    }
    case 'home':
      return { ...state, stacks: { ...state.stacks, [state.tab]: [] } }
  }
}

/** The screens in `before` that `after` no longer holds, outermost first. */
export function screensLeft<B>(before: NavState<B>, after: NavState<B>): Screen[] {
  const left: Screen[] = []
  for (const tab of Object.keys(before.stacks) as TabId[]) {
    const remaining = after.stacks[tab]
    for (const screen of before.stacks[tab]) {
      if (!remaining.some((kept) => sameScreen(kept, screen))) left.push(screen)
    }
  }
  return left
}

export type NavAction<B> =
  | { readonly type: 'move'; readonly move: Move; readonly guard: Guard<B> | undefined }
  | { readonly type: 'proceed' }
  | { readonly type: 'stay' }

export function reduceNav<B>(state: NavState<B>, action: NavAction<B>): NavState<B> {
  switch (action.type) {
    case 'move': {
      const next = applyMove(state, action.move)
      const leaving = screensLeft(state, next)
      const bail =
        action.move.unguarded !== true && action.guard !== undefined
          ? action.guard(leaving, action.move, state)
          : null
      if (bail !== null) return { ...state, pending: { move: action.move, bail } }
      return { ...next, pending: null }
    }
    case 'proceed':
      return state.pending === null
        ? state
        : { ...applyMove(state, state.pending.move), pending: null }
    case 'stay':
      return state.pending === null ? state : { ...state, pending: null }
  }
}

export interface Navigator<B> {
  readonly state: NavState<B>
  readonly tab: TabId
  /** The active tab's stack, innermost last; empty at the home. */
  readonly stack: readonly Screen[]
  readonly top: Screen | null
  readonly pending: Pending<B> | null
  readonly navigate: (move: Move) => void
  readonly selectTab: (tab: TabId) => void
  readonly push: (screen: Screen) => void
  readonly replace: (screen: Screen) => void
  readonly back: () => void
  readonly home: () => void
  /** Apply the move the guard parked. */
  readonly proceed: () => void
  /** Drop the parked move and stay. */
  readonly stay: () => void
  /** Replace the guard. The shell's guard closes over state declared long
   *  after the navigator is, so it is handed in each render rather than at
   *  construction; a move reads whatever was set last. */
  readonly setGuard: (guard: Guard<B> | undefined) => void
}

/**
 * The shell's one navigator. Every callback is referentially stable across
 * renders - the shell memoises on `selectTab` and hands `navigate` to
 * screens - and the guard is read fresh on each move through a ref, so a
 * guard closing over the current draft never goes stale.
 */
export function useNavigator<B = never>(
  guard?: Guard<B>,
  initial: NavState<B> = NAV_HOME as NavState<B>,
): Navigator<B> {
  const [state, dispatch] = useReducer(reduceNav<B>, initial)
  const guardRef = useRef(guard)
  guardRef.current = guard
  const setGuard = useCallback((next: Guard<B> | undefined) => {
    guardRef.current = next
  }, [])

  const navigate = useCallback(
    (move: Move) => dispatch({ type: 'move', move, guard: guardRef.current }),
    [],
  )
  const selectTab = useCallback((tab: TabId) => navigate({ to: 'tab', tab }), [navigate])
  const push = useCallback(
    (screen: Screen) => navigate({ to: 'push', screen }),
    [navigate],
  )
  const replace = useCallback(
    (screen: Screen) => navigate({ to: 'replace', screen }),
    [navigate],
  )
  const back = useCallback(() => navigate({ to: 'back' }), [navigate])
  const home = useCallback(() => navigate({ to: 'home' }), [navigate])
  const proceed = useCallback(() => dispatch({ type: 'proceed' }), [])
  const stay = useCallback(() => dispatch({ type: 'stay' }), [])

  return useMemo(
    () => ({
      state,
      tab: state.tab,
      stack: state.stacks[state.tab],
      top: topScreen(state),
      pending: state.pending,
      navigate,
      selectTab,
      push,
      replace,
      back,
      home,
      proceed,
      stay,
      setGuard,
    }),
    [state, navigate, selectTab, push, replace, back, home, proceed, stay, setGuard],
  )
}
