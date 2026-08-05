// Trail / Downloads / More (WIREFRAMES.md §6). The tab set itself lives in
// tabs.ts - see the note there.
//
// This bar is also where the OurHike mark lives. On a desktop the whole bar
// becomes the left sidebar (desktop.css), and the mark sits at the foot of it -
// the bottom-left corner of the page. On a phone the bar is a horizontal strip
// of three thumb-sized targets with no corner to spare, so the mark is not
// drawn at all rather than squeezed in beside them; maximising the phone's map
// area without losing the brand is its own design question, tracked separately.
//
// The mark rides here rather than on the map itself because the map is the
// product, and a watermark over it costs terrain a hiker may be reading. In the
// sidebar it costs nothing that was showing anything.
//
// The tabs sit in their own element rather than directly under the <nav>. A
// `role="tablist"` is required to own tabs and nothing else, so hanging the
// mark off it would make the brand a fourth member of a set of three - which is
// exactly what a screen reader would then announce.

import { TABS, type TabId } from './tabs'
import { Logo } from '../design-system/components'

export interface TabBarProps {
  active: TabId
  onSelect: (id: TabId) => void
}

// Full lockup, not the bare icon: the sidebar is 13rem wide on a light surface,
// which is the one place in the app chrome where the wordmark is both legible
// and affordable. 32px keeps it plainly subordinate to the 14px tab labels
// above it - branding sits below wayfinding on this screen.
const BRAND_MARK_SIZE = 32

export function TabBar({ active, onSelect }: TabBarProps) {
  return (
    <nav className="tab-bar" aria-label="Main">
      <div className="tab-bar__tabs" role="tablist">
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
      </div>

      {/* Rendered on every screen, not only the map: the sidebar is one shared
          piece of chrome, and a mark that appeared under Trail and vanished
          under Downloads would read as a bug rather than as branding. */}
      <div className="tab-bar__brand">
        <Logo size={BRAND_MARK_SIZE} />
      </div>
    </nav>
  )
}
