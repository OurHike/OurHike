// The tab set, kept separate from TabBar.tsx so that file exports only a
// component (React Fast Refresh stops working for a module that mixes the two).

export interface Tab {
  id: 'trail' | 'plan' | 'more'
  label: string
}

// Three tabs. The bar is the most expensive space on the screen, and the
// standard a third entry has to meet was set when Downloads lost its place
// here: a screen someone STANDS in, not an errand. Downloads was an errand -
// one whole-corridor package, started once (WIREFRAMES.md Known Deviations
// #1) - and it went to a window opened from the background picker, where the
// "why is there no map" moment actually happens. It returns as a tab only
// when there is more than one package to manage (#192).
//
// Plan meets the standard Downloads did not: it is v2's first feature
// (features/HIKE_PLANNING.md, #756), a surface a hiker returns to every
// evening of a five-month walk, and the v2 wireframes draw it as the second
// tab on every screen that has a bar. This is data so adding one is one
// entry, not an edit to markup.
export const TABS: Tab[] = [
  { id: 'trail', label: 'Trail' },
  { id: 'plan', label: 'Plan' },
  { id: 'more', label: 'Settings' },
]

export type TabId = Tab['id']
