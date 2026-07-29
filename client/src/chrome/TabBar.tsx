// Trail / Downloads / More (WIREFRAMES.md §6). The tab set itself lives in
// tabs.ts - see the note there.

import { TABS, type TabId } from './tabs'

export interface TabBarProps {
  active: TabId
  onSelect: (id: TabId) => void
}

export function TabBar({ active, onSelect }: TabBarProps) {
  return (
    <nav className="tab-bar" role="tablist" aria-label="Main">
      {TABS.map((tab) => (
        <button
          key={tab.id}
          type="button"
          role="tab"
          className="tab-bar__tab"
          aria-selected={tab.id === active}
          // Fires even when already active, so the screen can scroll to top -
          // the standard tab-bar affordance people already expect.
          onClick={() => onSelect(tab.id)}
        >
          {tab.label}
        </button>
      ))}
    </nav>
  )
}
