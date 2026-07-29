// The tab set, kept separate from TabBar.tsx so that file exports only a
// component (React Fast Refresh stops working for a module that mixes the two).

export interface Tab {
  id: 'trail' | 'downloads' | 'more'
  label: string
}

// Three tabs and no more: v1's whole surface fits in them, and the bar lives in
// the thumb zone where every extra target costs accuracy for someone walking.
// This is data so a future tab is one entry, not an edit to markup.
export const TABS: Tab[] = [
  { id: 'trail', label: 'Trail' },
  { id: 'downloads', label: 'Downloads' },
  { id: 'more', label: 'More' },
]

export type TabId = Tab['id']
