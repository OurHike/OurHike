// The tab set, kept separate from TabBar.tsx so that file exports only a
// component (React Fast Refresh stops working for a module that mixes the two).

export interface Tab {
  id: 'trail' | 'more'
  label: string
}

// Two tabs. There were three, with Downloads between these, and it went
// because of what is actually behind it: ONE whole-corridor package
// (WIREFRAMES.md Known Deviations #1), started once and deleted maybe never.
// A permanent target in the thumb zone - the most expensive space on the
// screen - bought a screen almost nobody opens twice, while the moment someone
// genuinely wants it, "why is there no map", was reached by leaving the map.
// It is now a window opened from the background picker, which is where that
// moment happens (chrome/BackgroundPicker.tsx).
//
// The tab comes back in v2, when there is more than one package to manage
// (#192) and a list is somewhere worth standing. This is data so that is one
// entry, not an edit to markup.
export const TABS: Tab[] = [
  { id: 'trail', label: 'Trail' },
  { id: 'more', label: 'More' },
]

export type TabId = Tab['id']
