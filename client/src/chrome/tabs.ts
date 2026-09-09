// The tab set, kept separate from TabBar.tsx so that file exports only a
// component (React Fast Refresh stops working for a module that mixes the two).

export interface Tab {
  id: 'today' | 'map' | 'plan' | 'more'
  label: string
}

// Four tabs. The bar is the most expensive space on the screen, and the
// standard an entry has to meet was set when Downloads lost its place
// here: a screen someone STANDS in, not an errand. Downloads was an errand -
// one whole-corridor package, started once (WIREFRAMES.md Known Deviations
// #1) - and it went to a window opened from the background picker, where the
// "why is there no map" moment actually happens. It returns as a tab only
// when there is more than one package to manage (#192).
//
// Today is the redesign's home (#1054): the one answer a hiker mostly wants -
// what happens next today - on one screen, ordered by distance. It meets the
// standard more squarely than any other entry, and making it the home is what
// lets the map stop being both the front door and a working surface.
//
// Plan meets the standard Downloads did not: it is v2's first feature
// (features/HIKE_PLANNING.md, #756), a surface a hiker returns to every
// evening of a five-month walk.
//
// VOLUNTEER LEFT THE BAR, and not because it stopped meeting the standard.
// VOLUNTEERING.md argued the word itself against four alternatives precisely
// so a hiker would read "Volunteer" every day, and that outcome is what the
// redesign keeps while the tab goes: the always-visible "today I'm…" switch
// (lib/hikerMode.ts) renders the word on the Today screen every single day,
// the Today column carries the hiker's own section card in every mode, and
// More holds the destination. A tab said the word once per glance at the
// bar; the mode switch says it somewhere a hiker actually reads. Approved by
// the maintainer 2026-08-26, in session, against the argument this comment
// used to carry (#1054).
//
// The fourth tab reads "More" again. MORE_TAB.md (#795) argued "Settings"
// while the screen was four settings panels; the redesign makes it five
// destinations - the download meter, volunteering, the map's provenance -
// and "Settings" would be the narrowest true name for that set rather than
// the honest one. The reversal is recorded on #1054; the doc's reasoning
// ("say what the screen is") is the reasoning here too - what the screen is
// changed.
export const TABS: Tab[] = [
  { id: 'today', label: 'Today' },
  { id: 'map', label: 'Map' },
  { id: 'plan', label: 'Plan' },
  { id: 'more', label: 'More' },
]

export type TabId = Tab['id']
